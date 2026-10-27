"""Evaluation repository — core CRUD and status mutations for evaluations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from asyncpg import UniqueViolationError
from sqlalchemy import ColumnElement, String, and_, cast, func, literal, or_, select, tuple_, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, raiseload, selectinload

from tropek.cache.redis_cache import RedisCache
from tropek.db.models import Asset, EvaluationAnnotation, EvaluationRun, IndicatorResultRow, SLOEvaluation
from tropek.modules.common.exceptions import ConflictError
from tropek.modules.quality_gate.evaluation_engine.constants import EvaluationStatus
from tropek.modules.quality_gate.repositories.indicator import IndicatorRepository
from tropek.modules.quality_gate.repositories.sli_value import SLIValueRepository
from tropek.modules.quality_gate.shared.params import EvalCreateParams, RefetchScope
from tropek.modules.quality_gate.workflows.presentation.heatmap_cache import HeatmapColumnCache

# Statuses a refetch may reset; ``pending`` / ``running`` rows belong to a live job.
REFETCHABLE_STATUSES = (EvaluationStatus.COMPLETED, EvaluationStatus.PARTIAL, EvaluationStatus.FAILED)
IN_PROGRESS_STATUSES = (EvaluationStatus.PENDING, EvaluationStatus.RUNNING)


def _merged_job_stats(new_stats: dict[str, Any], *, drop_error: bool = False) -> ColumnElement[Any]:
    """Build ``job_stats || new_stats``, optionally removing a stale ``error`` key first.

    A terminal write merges rather than replaces so the ``refetch`` audit block, ``fetch_attempts``,
    ``stuck_job_retries`` and ``worker_id`` written earlier in the row's life survive.

    Args:
        new_stats: Keys to write; they win over stored keys of the same name.
        drop_error: Remove ``error`` (JSONB ``-``) before merging, for a successful outcome.

    Returns:
        The SQL expression for the new ``job_stats`` value.
    """
    if drop_error:
        return SLOEvaluation.job_stats.op('-')(cast('error', String)).op('||')(cast(new_stats, JSONB))
    return SLOEvaluation.job_stats.op('||')(cast(new_stats, JSONB))


class EvaluationRepository:
    """Data access layer for evaluation CRUD and status mutations."""

    def __init__(
        self,
        session: AsyncSession,
        cache: RedisCache | None = None,
        heatmap_cache: HeatmapColumnCache | None = None,
    ) -> None:
        self._session = session
        self._cache = cache
        self._heatmap_cache = heatmap_cache

    async def _invalidate_baseline_cache(
        self,
        asset_id: uuid.UUID | None,
        slo_name: str | None,
    ) -> None:
        if self._cache and asset_id and slo_name:
            await self._cache.invalidate(f'baseline:{asset_id}:{slo_name}')

    async def _invalidate_heatmap_column(self, run_id: uuid.UUID | None) -> None:
        """Delete the cached heatmap column fragment for a run.

        Called from every mutation that changes a run's presented state
        (mark_completed, invalidate, restore, override_status, restore_override,
        pin_baseline, unpin_baseline). The cache is opportunistic — Redis
        failures are logged and dropped by ``HeatmapColumnCache.delete``, so
        this method never raises. Short-circuits when the cache is not wired
        or the caller has no run id in scope.
        """
        if run_id is None or self._heatmap_cache is None:
            return
        await self._heatmap_cache.delete(run_id)

    async def invalidate_caches_for(self, rows: list[SLOEvaluation]) -> None:
        """Invalidate baseline + heatmap caches once for a batch of affected rows.

        Collects the distinct ``(asset_id, slo_name)`` pairs and parent
        ``evaluation_id`` run ids from the affected rows and invalidates each
        cache once — one delete per key, not one per row. Reads only those
        scalar columns, so it is safe to call after the transaction commits.

        The bulk mutation methods of this repository call it inside the request
        handler, so the delete happens *before* ``SessionMiddleware`` commits
        the transaction: a concurrent reader in that narrow window could
        repopulate a key with pre-commit data. The cache is opportunistic
        (Redis failures are dropped; entries carry a TTL), so a transient stale
        key self-heals on the next read or write — the same pre-existing
        behaviour as the singular mutation methods. Callers that commit
        themselves (refetch) call it after the commit instead.
        """
        baseline_keys = {(row.asset_id, row.slo_name) for row in rows}
        for asset_id, slo_name in baseline_keys:
            await self._invalidate_baseline_cache(asset_id, slo_name)
        run_ids = {row.evaluation_id for row in rows if row.evaluation_id is not None}
        if run_ids and self._heatmap_cache is not None:
            await self._heatmap_cache.delete_many(run_ids)

    async def _fetch_by_ids(self, eval_ids: list[uuid.UUID]) -> list[SLOEvaluation]:
        """Return the SLO evaluations for the given ids (no eager loads)."""
        if not eval_ids:
            return []
        result = await self._session.execute(select(SLOEvaluation).where(SLOEvaluation.id.in_(eval_ids)))
        return list(result.scalars().all())

    async def create_pending(self, params: EvalCreateParams) -> SLOEvaluation:
        """Create a new evaluation record in pending status.

        Ensures the parent EvaluationRun row exists, creating it if absent.
        This supports both the full trigger flow (parent created first) and
        direct repository usage in tests (parent auto-created on demand).

        Args:
            params: Validated parameters for the new evaluation record.

        Returns:
            Newly created Evaluation in pending status.
        """
        # Ensure parent EvaluationRun exists (auto-create for direct callers / tests)
        run = await self._session.get(EvaluationRun, params.evaluation_id)
        if run is None:
            run = EvaluationRun(
                id=params.evaluation_id,
                asset_id=params.asset_id,
                eval_name=params.evaluation_name,
                period_start=params.period_start,
                period_end=params.period_end,
                status='pending',
            )
            self._session.add(run)
            await self._session.flush()

        # Merge asset tags as defaults into variables (caller values take precedence)
        merged_variables = dict(params.variables)
        asset_row = await self._session.get(Asset, params.asset_id)
        if asset_row is not None and asset_row.tags:
            for key, value in asset_row.tags.items():
                merged_variables.setdefault(str(key), str(value))

        ev = SLOEvaluation(
            id=uuid.uuid4(),
            evaluation_id=params.evaluation_id,
            evaluation_name=params.evaluation_name,
            period_start=params.period_start,
            period_end=params.period_end,
            ingestion_mode=params.ingestion_mode,
            asset_snapshot=params.asset_snapshot,
            variables=merged_variables,
            asset_id=params.asset_id,
            slo_name=params.slo_name,
            slo_version=params.slo_version,
            adapter_used=params.adapter_used,
            sli_name=params.sli_name,
            sli_version=params.sli_version,
            data_source_name=params.data_source_name,
            slo_definition_id=params.slo_definition_id,
            sli_definition_id=params.sli_definition_id,
            status=EvaluationStatus.PENDING,
        )
        self._session.add(ev)
        try:
            await self._session.flush()
        except Exception as exc:
            # asyncpg wraps the PG error; walk the cause chain to find UniqueViolationError
            cause: BaseException | None = exc
            while cause is not None:
                if isinstance(cause, UniqueViolationError):
                    raise ConflictError('evaluation', str(params.evaluation_name), 'duplicate') from exc
                cause = cause.__cause__
            raise
        return ev

    async def find_duplicate(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        evaluation_name: str,
        period_start: datetime,
        period_end: datetime,
    ) -> SLOEvaluation | None:
        """Find an existing non-failed evaluation matching the identity tuple.

        Returns the existing evaluation if found, None otherwise.
        Used by ``TriggerService`` to produce status-aware 409 error messages before
        attempting the insert. The partial unique index on the DB is the
        safety net for concurrent races — this check provides clean UX.

        Decision tree (see also uq_evaluations_identity index on the model):
          - No match → None (caller proceeds with create)
          - Match with status pending/running → caller returns 409 "in progress"
          - Match with status completed/partial → caller returns 409 "use re-evaluate or refetch"
          - Match with invalidated=True → caller returns 409 "invalidated, use re-evaluate"
          - Failed evaluations are excluded (not matched here, not in the index)
        """
        q = select(SLOEvaluation).where(
            SLOEvaluation.asset_id == asset_id,
            SLOEvaluation.slo_name == slo_name,
            SLOEvaluation.evaluation_name == evaluation_name,
            SLOEvaluation.period_start == period_start,
            SLOEvaluation.period_end == period_end,
            SLOEvaluation.status != EvaluationStatus.FAILED,
        )
        result = await self._session.execute(q)
        return result.scalar_one_or_none()

    async def has_pending_predecessor(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        period_start: datetime,
        stale_running_cutoff: datetime | None = None,
    ) -> bool:
        """Check whether an earlier evaluation for the same asset+SLO is still pending or running.

        Used by the worker to defer processing until predecessors complete,
        ensuring baselines are available in chronological order.

        When ``stale_running_cutoff`` is given, a predecessor stuck in ``running``
        since before that time is treated as dead (crashed job) and does NOT count
        as pending, so successors stop deferring even before the watchdog recovers it.
        """
        running_predecessor: ColumnElement[bool] = SLOEvaluation.status == EvaluationStatus.RUNNING
        if stale_running_cutoff is not None:
            running_predecessor = and_(
                SLOEvaluation.status == EvaluationStatus.RUNNING,
                SLOEvaluation.started_at >= stale_running_cutoff,
            )
        q = (
            select(func.count())
            .select_from(SLOEvaluation)
            .where(
                SLOEvaluation.asset_id == asset_id,
                SLOEvaluation.slo_name == slo_name,
                SLOEvaluation.period_start < period_start,
                or_(SLOEvaluation.status == EvaluationStatus.PENDING, running_predecessor),
            )
        )
        result = await self._session.execute(q)
        return (result.scalar() or 0) > 0

    async def requeue_stuck(self, eval_id: uuid.UUID, *, stuck_job_retries: int) -> None:
        """Reset a stuck ``running`` evaluation to ``pending`` for re-execution.

        Records the stuck-job retry count in ``job_stats`` so the watchdog can cap
        retries. ``started_at`` is cleared so a re-run stamps it fresh via
        ``mark_running``. The counter is merged (JSONB ``||``) so the
        ``fetch_attempts`` history of earlier adapter retries survives.

        Args:
            eval_id: Evaluation to requeue.
            stuck_job_retries: Number of times the watchdog has now recovered this evaluation.
        """
        await self._session.execute(
            update(SLOEvaluation)
            .where(SLOEvaluation.id == eval_id)
            .values(
                status=EvaluationStatus.PENDING,
                started_at=None,
                job_stats=SLOEvaluation.job_stats.op('||')(
                    cast({'stuck_job_retries': stuck_job_retries}, JSONB),
                ),
            )
        )

    async def mark_pending_retry(self, eval_id: uuid.UUID, *, attempt_record: dict[str, Any]) -> None:
        """Return a running evaluation to pending after a transient fetch failure, appending the attempt.

        Merges into ``job_stats`` with JSONB ``||`` so ``stuck_job_retries`` and earlier
        ``fetch_attempts`` survive; ``started_at`` is cleared so the watchdog does not count the
        wait as a stuck job and the retried run's ``mark_running`` stamps it fresh.

        Args:
            eval_id: Evaluation to return to pending.
            attempt_record: The failed attempt, appended to ``job_stats['fetch_attempts']``.
        """
        job_stats = await self._session.scalar(select(SLOEvaluation.job_stats).where(SLOEvaluation.id == eval_id))
        attempts = [*(job_stats or {}).get('fetch_attempts', []), attempt_record]
        await self._session.execute(
            update(SLOEvaluation)
            .where(SLOEvaluation.id == eval_id)
            .values(
                status=EvaluationStatus.PENDING,
                started_at=None,
                job_stats=SLOEvaluation.job_stats.op('||')(cast({'fetch_attempts': attempts}, JSONB)),
            )
        )

    async def mark_running(self, eval_id: uuid.UUID, worker_id: str | None = None) -> None:
        """Transition evaluation to running status, recording worker and start time.

        Args:
            eval_id: Evaluation to update.
            worker_id: Identifier of the worker process claiming this job.
        """
        new_stats = {'worker_id': worker_id} if worker_id else {}
        await self._session.execute(
            update(SLOEvaluation)
            .where(SLOEvaluation.id == eval_id)
            .values(
                status=EvaluationStatus.RUNNING,
                started_at=datetime.now(tz=UTC),
                # Merge (JSONB ``||``) rather than replace so the watchdog's
                # ``stuck_job_retries`` counter survives the requeue → rerun
                # cycle. A wholesale overwrite here reset the counter to 0 every
                # rerun, so a hard-crashing job requeued forever and never hit
                # the cap.
                job_stats=SLOEvaluation.job_stats.op('||')(cast(new_stats, JSONB)),
            )
        )

    async def mark_completed(  # noqa: PLR0913
        self,
        eval_id: uuid.UUID,
        *,
        result: str,
        score: float,
        achieved_points: int | None = None,
        total_points: int | None = None,
        slo_name: str | None = None,
        slo_version: int | None = None,
        job_stats: dict[str, Any] | None = None,
        compared_evaluation_ids: list[str] | None = None,
        asset_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
    ) -> None:
        """Write final result and transition to completed.

        Args:
            eval_id: Evaluation to update.
            result: One of "pass", "warning", "fail", "error".
            score: Weighted score 0.0-100.0.
            achieved_points: Weighted points achieved by passing/warning objectives.
            total_points: Total weighted points possible.
            slo_name: Named SLO used, if any.
            slo_version: Version of the named SLO, if any.
            job_stats: Optional dict of job execution stats, merged into the stored ``job_stats`` (JSONB
                ``||``) so ``refetch``, ``fetch_attempts``, ``stuck_job_retries`` and ``worker_id`` survive;
                a stale ``error`` key is removed.
            compared_evaluation_ids: IDs of evaluations used for relative criteria.
            asset_id: Asset UUID for baseline cache invalidation.
            run_id: Parent EvaluationRun UUID for heatmap column cache invalidation.
        """
        merged_stats: dict[str, Any] = dict(job_stats or {})
        if compared_evaluation_ids is not None:
            merged_stats['compared_evaluation_ids'] = compared_evaluation_ids
        values: dict[str, Any] = {
            'status': EvaluationStatus.COMPLETED,
            'result': result,
            'score': score,
            'achieved_points': achieved_points,
            'total_points': total_points,
            'job_stats': _merged_job_stats(merged_stats, drop_error=True),
        }
        if slo_name is not None:
            values['slo_name'] = slo_name
        if slo_version is not None:
            values['slo_version'] = slo_version
        await self._session.execute(update(SLOEvaluation).where(SLOEvaluation.id == eval_id).values(**values))
        await self._invalidate_baseline_cache(asset_id, slo_name)
        await self._invalidate_heatmap_column(run_id)

    async def mark_failed(self, eval_id: uuid.UUID, job_stats: dict[str, Any] | None = None) -> None:
        """Transition evaluation to failed, recording error info.

        Args:
            eval_id: Evaluation to update.
            job_stats: Job stats dict may include error, retry_count, etc.; merged into the stored
                ``job_stats`` (JSONB ``||``) so the ``refetch`` audit block and earlier keys survive.
        """
        await self._session.execute(
            update(SLOEvaluation)
            .where(SLOEvaluation.id == eval_id)
            .values(
                status=EvaluationStatus.FAILED,
                job_stats=_merged_job_stats(job_stats or {}),
            )
        )

    async def mark_partial(self, eval_id: uuid.UUID, job_stats: dict[str, Any] | None = None) -> None:
        """Transition evaluation to partial — job crashed mid-execution.

        Args:
            eval_id: Evaluation to update.
            job_stats: Partial execution stats (indicators_attempted, _completed, etc.); merged into the
                stored ``job_stats`` (JSONB ``||``) with a stale ``error`` key removed.
        """
        await self._session.execute(
            update(SLOEvaluation)
            .where(SLOEvaluation.id == eval_id)
            .values(status=EvaluationStatus.PARTIAL, job_stats=_merged_job_stats(job_stats or {}, drop_error=True))
        )

    async def get_by_id(self, eval_id: uuid.UUID) -> SLOEvaluation | None:
        """Fetch a single evaluation with annotations eagerly loaded.

        Args:
            eval_id: Evaluation UUID.

        Returns:
            Evaluation with annotations, or None if not found.
        """
        result = await self._session.execute(
            select(SLOEvaluation)
            .options(
                selectinload(SLOEvaluation.annotations).selectinload(EvaluationAnnotation.category),
                selectinload(SLOEvaluation.indicator_rows).joinedload(IndicatorResultRow.objective),
            )
            .where(SLOEvaluation.id == eval_id)
        )
        return result.scalar_one_or_none()

    async def list_evaluations(
        self,
        *,
        evaluation_name: str | None = None,
        asset_name: str | None = None,
        result: str | None = None,
        from_: datetime | None = None,
        to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SLOEvaluation]:
        """List evaluations with optional filters.

        Args:
            evaluation_name: Filter by evaluation name.
            asset_name: Filter by asset_snapshot name (JSONB lookup).
            result: Filter by result value ("pass", "warning", "fail", "error").
            from_: Only include evaluations starting at or after this timestamp.
            to: Only include evaluations starting at or before this timestamp.
            limit: Maximum rows to return.
            offset: Number of rows to skip (for pagination).

        Returns:
            List of SLOEvaluation rows, newest first.
        """
        q = select(SLOEvaluation)
        if evaluation_name:
            q = q.where(SLOEvaluation.evaluation_name == evaluation_name)
        if asset_name:
            q = q.where(SLOEvaluation.asset_snapshot['name'].as_string() == asset_name)
        if result:
            q = q.where(SLOEvaluation.result == result)
        if from_:
            q = q.where(SLOEvaluation.period_start >= from_)
        if to:
            q = q.where(SLOEvaluation.period_start <= to)
        q = q.order_by(SLOEvaluation.period_start.desc()).limit(limit).offset(offset)
        rows = await self._session.execute(q)
        return list(rows.scalars().all())

    async def find_stuck(self, threshold_seconds: int) -> list[SLOEvaluation]:
        """Find evaluations stuck in running status for longer than the threshold.

        Used by the watchdog to detect and reschedule crashed jobs.

        Args:
            threshold_seconds: Jobs running longer than this (in seconds) are stuck.

        Returns:
            List of stuck Evaluation rows.
        """
        cutoff = datetime.now(tz=UTC) - timedelta(seconds=threshold_seconds)
        result = await self._session.execute(
            select(SLOEvaluation).where(
                SLOEvaluation.status == EvaluationStatus.RUNNING,
                SLOEvaluation.started_at < cutoff,
            )
        )
        return list(result.scalars().all())

    async def list_with_counts(  # noqa: PLR0913
        self,
        *,
        asset_id: uuid.UUID | None = None,
        slo_name: str | None = None,
        result: str | None = None,
        date_prefix: str | None = None,
        evaluation_name: list[str] | None = None,
        asset_ids: list[uuid.UUID] | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[
        list[SLOEvaluation],
        int,
        dict[uuid.UUID, int],
        dict[uuid.UUID, EvaluationAnnotation],
    ]:
        """Return (page, total, count_map, latest_annotation_map) with optional filters.

        asset_id and asset_ids are DB FK lookups (not JSONB snapshot).
        count_map: {eval_id -> visible annotation count} for the returned page.
        latest_annotation_map: {eval_id -> most recent visible annotation} for the page.
        """
        q = select(SLOEvaluation)
        if asset_id:
            q = q.where(SLOEvaluation.asset_id == asset_id)
        if slo_name:
            q = q.where(SLOEvaluation.slo_name == slo_name)
        if evaluation_name:
            q = q.where(SLOEvaluation.evaluation_name.in_(evaluation_name))
        if result:
            q = q.where(SLOEvaluation.result == result)
        if date_prefix:
            q = q.where(SLOEvaluation.period_start.cast(String).like(f'{date_prefix}%'))
        if asset_ids:
            q = q.where(SLOEvaluation.asset_id.in_(asset_ids))
        if from_ts:
            q = q.where(SLOEvaluation.period_start >= from_ts)
        if to_ts:
            q = q.where(SLOEvaluation.period_start <= to_ts)
        sub = q.subquery()
        count_q = select(func.count(func.distinct(sub.c.evaluation_id)))
        total_result = await self._session.execute(count_q)
        total = total_result.scalar_one()
        q = q.order_by(SLOEvaluation.period_start.desc()).limit(limit).offset(offset)
        rows = await self._session.execute(q)
        evals = list(rows.scalars().all())
        count_map: dict[uuid.UUID, int] = {}
        latest_map: dict[uuid.UUID, EvaluationAnnotation] = {}
        if evals:
            eval_ids = [ev.id for ev in evals]
            cnt_rows = await self._session.execute(
                select(EvaluationAnnotation.slo_evaluation_id, func.count().label('cnt'))
                .where(
                    EvaluationAnnotation.slo_evaluation_id.in_(eval_ids),
                    EvaluationAnnotation.hidden_at.is_(None),
                )
                .group_by(EvaluationAnnotation.slo_evaluation_id)
            )
            count_map = {row.slo_evaluation_id: row.cnt for row in cnt_rows}
            # Fetch latest visible annotation per evaluation using DISTINCT ON.
            latest_q = (
                select(EvaluationAnnotation)
                .options(selectinload(EvaluationAnnotation.category))
                .where(
                    EvaluationAnnotation.slo_evaluation_id.in_(eval_ids),
                    EvaluationAnnotation.hidden_at.is_(None),
                )
                .order_by(
                    EvaluationAnnotation.slo_evaluation_id,
                    EvaluationAnnotation.created_at.desc(),
                )
                .distinct(EvaluationAnnotation.slo_evaluation_id)
            )
            latest_rows = await self._session.execute(latest_q)
            latest_map = {
                a.slo_evaluation_id: a for a in latest_rows.scalars().all() if a.slo_evaluation_id is not None
            }
        return evals, total, count_map, latest_map

    async def invalidate(self, eval_id: uuid.UUID, *, note: str) -> SLOEvaluation | None:
        """Mark a single evaluation as invalidated.

        Per-SLO: only this row drops out of baselines; its siblings in the same
        run keep feeding them.
        """
        ev = await self.get_by_id(eval_id)
        if ev is None:
            return None
        await self._session.execute(
            update(SLOEvaluation).where(SLOEvaluation.id == eval_id).values(invalidated=True, invalidation_note=note)
        )
        await self._invalidate_baseline_cache(ev.asset_id, ev.slo_name)
        await self._invalidate_heatmap_column(ev.evaluation_id)
        return await self.get_by_id(eval_id)

    async def restore(self, eval_id: uuid.UUID) -> SLOEvaluation | None:
        """Clear the invalidation flag on a single evaluation (per-SLO)."""
        ev = await self.get_by_id(eval_id)
        if ev is None:
            return None
        await self._session.execute(
            update(SLOEvaluation).where(SLOEvaluation.id == eval_id).values(invalidated=False, invalidation_note=None)
        )
        await self._invalidate_baseline_cache(ev.asset_id, ev.slo_name)
        await self._invalidate_heatmap_column(ev.evaluation_id)
        return await self.get_by_id(eval_id)

    async def pin_baseline(
        self,
        eval_id: uuid.UUID,
        *,
        reason: str,
        author: str,
    ) -> SLOEvaluation | None:
        """Pin an evaluation as the baseline floor for its asset+SLO combination.

        Atomically unpins any existing active pin for the same (asset_id, slo_name).
        """
        ev = await self.get_by_id(eval_id)
        if ev is None:
            return None
        # Unpin any existing active pin for this asset+SLO
        if ev.asset_id and ev.slo_name:
            await self._session.execute(
                update(SLOEvaluation)
                .where(
                    SLOEvaluation.asset_id == ev.asset_id,
                    SLOEvaluation.slo_name == ev.slo_name,
                    SLOEvaluation.baseline_pinned_at.is_not(None),
                    SLOEvaluation.baseline_unpinned_at.is_(None),
                )
                .values(baseline_unpinned_at=func.now())
            )
        # Pin the target evaluation (reset unpinned_at in case it was previously unpinned)
        await self._session.execute(
            update(SLOEvaluation)
            .where(SLOEvaluation.id == eval_id)
            .values(
                baseline_pinned_at=func.now(),
                baseline_unpinned_at=None,
                baseline_pin_reason=reason,
                baseline_pin_author=author,
            )
        )
        await self._session.flush()
        await self._invalidate_baseline_cache(ev.asset_id, ev.slo_name)
        await self._invalidate_heatmap_column(ev.evaluation_id)
        return await self.get_by_id(eval_id)

    async def unpin_baseline(self, eval_id: uuid.UUID) -> SLOEvaluation | None:
        """Remove the baseline pin from an evaluation."""
        ev = await self.get_by_id(eval_id)
        if ev is None:
            return None
        await self._session.execute(
            update(SLOEvaluation).where(SLOEvaluation.id == eval_id).values(baseline_unpinned_at=func.now())
        )
        await self._session.flush()
        await self._invalidate_baseline_cache(ev.asset_id, ev.slo_name)
        await self._invalidate_heatmap_column(ev.evaluation_id)
        return await self.get_by_id(eval_id)

    async def override_status(
        self,
        eval_id: uuid.UUID,
        *,
        new_result: str,
        reason: str,
        author: str,
    ) -> SLOEvaluation | None:
        """Override the evaluation result, preserving the original."""
        ev = await self.get_by_id(eval_id)
        if ev is None:
            return None
        values: dict[str, Any] = {
            'result': new_result,
            'override_reason': reason,
            'override_author': author,
        }
        # Only set original on first override — preserve the true original
        if ev.original_result is None:
            values['original_result'] = ev.result
        await self._session.execute(update(SLOEvaluation).where(SLOEvaluation.id == eval_id).values(**values))
        await self._session.flush()
        await self._invalidate_baseline_cache(ev.asset_id, ev.slo_name)
        await self._invalidate_heatmap_column(ev.evaluation_id)
        return await self.get_by_id(eval_id)

    async def restore_override(self, eval_id: uuid.UUID) -> SLOEvaluation | None:
        """Restore the original result, clearing the override."""
        ev = await self.get_by_id(eval_id)
        if ev is None or ev.original_result is None:
            return ev
        await self._session.execute(
            update(SLOEvaluation)
            .where(SLOEvaluation.id == eval_id)
            .values(
                result=ev.original_result,
                original_result=None,
                override_reason=None,
                override_author=None,
            )
        )
        await self._session.flush()
        await self._invalidate_baseline_cache(ev.asset_id, ev.slo_name)
        await self._invalidate_heatmap_column(ev.evaluation_id)
        return await self.get_by_id(eval_id)

    async def invalidate_many(self, eval_ids: list[uuid.UUID], *, note: str) -> list[SLOEvaluation]:
        """Invalidate the selected evaluations in a single set-based statement.

        Per-SLO: only the selected rows drop out of baselines. Returns the
        affected rows (existing ids); unknown ids are simply not returned.
        """
        if not eval_ids:
            return []
        await self._session.execute(
            update(SLOEvaluation)
            .where(SLOEvaluation.id.in_(eval_ids))
            .values(invalidated=True, invalidation_note=note)
            .execution_options(synchronize_session='fetch')
        )
        rows = await self._fetch_by_ids(eval_ids)
        await self.invalidate_caches_for(rows)
        return rows

    async def restore_many(self, eval_ids: list[uuid.UUID]) -> list[SLOEvaluation]:
        """Clear the invalidation flag on the selected evaluations (per-SLO)."""
        if not eval_ids:
            return []
        await self._session.execute(
            update(SLOEvaluation)
            .where(SLOEvaluation.id.in_(eval_ids))
            .values(invalidated=False, invalidation_note=None)
            .execution_options(synchronize_session='fetch')
        )
        rows = await self._fetch_by_ids(eval_ids)
        await self.invalidate_caches_for(rows)
        return rows

    async def override_status_many(
        self,
        eval_ids: list[uuid.UUID],
        *,
        new_result: str,
        reason: str,
        author: str,
    ) -> list[SLOEvaluation]:
        """Override the result of the selected completed evaluations.

        Preserves ``original_result`` only where currently NULL via
        ``COALESCE(original_result, result)`` so "first override wins" holds in a
        single UPDATE. Non-completed rows are left untouched (reported as skipped
        by the caller).
        """
        if not eval_ids:
            return []
        eligible = await self._session.execute(
            select(SLOEvaluation.id).where(
                SLOEvaluation.id.in_(eval_ids),
                SLOEvaluation.status == EvaluationStatus.COMPLETED,
            )
        )
        eligible_ids = list(eligible.scalars().all())
        if not eligible_ids:
            return []
        await self._session.execute(
            update(SLOEvaluation)
            .where(SLOEvaluation.id.in_(eligible_ids))
            .values(
                result=new_result,
                override_reason=reason,
                override_author=author,
                original_result=func.coalesce(SLOEvaluation.original_result, SLOEvaluation.result),
            )
            .execution_options(synchronize_session='fetch')
        )
        rows = await self._fetch_by_ids(eligible_ids)
        await self.invalidate_caches_for(rows)
        return rows

    async def restore_override_many(self, eval_ids: list[uuid.UUID]) -> list[SLOEvaluation]:
        """Restore the original result on the selected overridden evaluations.

        Only rows with a non-NULL ``original_result`` are affected.
        """
        if not eval_ids:
            return []
        eligible = await self._session.execute(
            select(SLOEvaluation.id).where(
                SLOEvaluation.id.in_(eval_ids),
                SLOEvaluation.original_result.is_not(None),
            )
        )
        eligible_ids = list(eligible.scalars().all())
        if not eligible_ids:
            return []
        await self._session.execute(
            update(SLOEvaluation)
            .where(SLOEvaluation.id.in_(eligible_ids))
            .values(
                result=SLOEvaluation.original_result,
                original_result=None,
                override_reason=None,
                override_author=None,
            )
            .execution_options(synchronize_session='fetch')
        )
        rows = await self._fetch_by_ids(eligible_ids)
        await self.invalidate_caches_for(rows)
        return rows

    async def pin_baseline_many(
        self,
        eval_ids: list[uuid.UUID],
        *,
        reason: str,
        author: str,
    ) -> list[SLOEvaluation]:
        """Pin the selected completed, non-invalidated evaluations as baselines.

        For each affected ``(asset_id, slo_name)`` group the current active pin is
        unpinned first, so at most one active pin survives per group. When two
        selected ids share a group, only the one with the newest ``period_start``
        is pinned (the others are dropped) to keep that invariant.
        """
        if not eval_ids:
            return []
        eligible = await self._session.execute(
            select(SLOEvaluation).where(
                SLOEvaluation.id.in_(eval_ids),
                SLOEvaluation.status == EvaluationStatus.COMPLETED,
                SLOEvaluation.invalidated.is_(False),
            )
        )
        eligible_rows = list(eligible.scalars().all())
        if not eligible_rows:
            return []
        # Dedupe to one row per (asset_id, slo_name), keeping the newest period_start.
        newest_per_group: dict[tuple[uuid.UUID | None, str | None], SLOEvaluation] = {}
        for row in eligible_rows:
            group_key = (row.asset_id, row.slo_name)
            current = newest_per_group.get(group_key)
            if current is None or row.period_start > current.period_start:
                newest_per_group[group_key] = row
        pin_ids = [row.id for row in newest_per_group.values()]
        # Unpin the current active pin for each affected (asset, slo) group.
        affected_groups = select(SLOEvaluation.asset_id, SLOEvaluation.slo_name).where(SLOEvaluation.id.in_(pin_ids))
        await self._session.execute(
            update(SLOEvaluation)
            .where(
                tuple_(SLOEvaluation.asset_id, SLOEvaluation.slo_name).in_(affected_groups),
                SLOEvaluation.baseline_pinned_at.is_not(None),
                SLOEvaluation.baseline_unpinned_at.is_(None),
            )
            .values(baseline_unpinned_at=func.now())
            .execution_options(synchronize_session='fetch')
        )
        # Pin the selected rows (reset unpinned_at in case previously unpinned).
        await self._session.execute(
            update(SLOEvaluation)
            .where(SLOEvaluation.id.in_(pin_ids))
            .values(
                baseline_pinned_at=func.now(),
                baseline_unpinned_at=None,
                baseline_pin_reason=reason,
                baseline_pin_author=author,
            )
            .execution_options(synchronize_session='fetch')
        )
        rows = await self._fetch_by_ids(pin_ids)
        await self.invalidate_caches_for(rows)
        return rows

    async def unpin_baseline_many(self, eval_ids: list[uuid.UUID]) -> list[SLOEvaluation]:
        """Remove the baseline pin from the selected evaluations."""
        if not eval_ids:
            return []
        await self._session.execute(
            update(SLOEvaluation)
            .where(SLOEvaluation.id.in_(eval_ids))
            .values(baseline_unpinned_at=func.now())
            .execution_options(synchronize_session='fetch')
        )
        rows = await self._fetch_by_ids(eval_ids)
        await self.invalidate_caches_for(rows)
        return rows

    async def list_for_refetch(self, scope: RefetchScope) -> list[SLOEvaluation]:
        """List the asset's SLO evaluations that a refetch of ``scope`` would replace.

        A failed row is skipped when a non-failed row with the same identity (asset, SLO, evaluation
        name, period start and end) exists: the failed row was superseded by a retry, and resetting it
        to ``pending`` would violate the partial unique index ``uq_slo_evaluations_identity``.

        Args:
            scope: Asset, inclusive ``period_start`` range and optional narrowing filters (run, SLOs, failed only).

        Returns:
            Matching rows ordered by ``period_start`` then ``slo_name``.
        """
        sibling = aliased(SLOEvaluation)
        superseded = (
            select(sibling.id)
            .where(
                sibling.asset_id == SLOEvaluation.asset_id,
                sibling.slo_name == SLOEvaluation.slo_name,
                sibling.evaluation_name == SLOEvaluation.evaluation_name,
                sibling.period_start == SLOEvaluation.period_start,
                sibling.period_end == SLOEvaluation.period_end,
                sibling.status != EvaluationStatus.FAILED,
                sibling.id != SLOEvaluation.id,
            )
            .exists()
        )
        query = select(SLOEvaluation).where(
            SLOEvaluation.asset_id == scope.asset_id,
            SLOEvaluation.period_start >= scope.period_from,
            SLOEvaluation.period_start <= scope.period_to,
            SLOEvaluation.evaluation_name == scope.evaluation_name,
            or_(SLOEvaluation.status != EvaluationStatus.FAILED, ~superseded),
        )
        if scope.evaluation_id is not None:
            query = query.where(SLOEvaluation.evaluation_id == scope.evaluation_id)
        if scope.slo_names is not None:
            query = query.where(SLOEvaluation.slo_name.in_(scope.slo_names))
        if scope.only_failed:
            query = query.where(SLOEvaluation.status == EvaluationStatus.FAILED)
        result = await self._session.execute(query.order_by(SLOEvaluation.period_start, SLOEvaluation.slo_name))
        return list(result.scalars().all())

    async def reset_for_refetch(
        self,
        eval_ids: list[uuid.UUID],
        *,
        refetch_audit: dict[str, str | None],
    ) -> list[uuid.UUID]:
        """Return SLO evaluations to ``pending`` with their stored values and child rows removed.

        Clears the result, score, points, start time, override fields and the SLI metadata (kept
        inside ``job_stats``, which is replaced, not merged, by a ``refetch`` block). Deletes the
        indicator rows and SLI values. Keeps the row id, ``evaluation_id``, annotations,
        invalidation and baseline pin columns. Only a row still in a terminal status
        (``REFETCHABLE_STATUSES``) is reset, so a concurrent refetch that already re-opened it is
        not reset (and enqueued) a second time.

        One UPDATE and one DELETE per child table, whatever the number of rows. The ``refetch`` block
        is built in SQL, so ``previous_result`` and ``previous_status`` come from the row's own old values.

        Args:
            eval_ids: SLO evaluations to reset.
            refetch_audit: Text values for the ``refetch`` block of ``job_stats`` (``requested_at``,
                ``requested_by``, ``reason``); ``None`` becomes JSON ``null``.

        Returns:
            The ids reset; fewer than ``len(eval_ids)`` when a row left its terminal status.
        """
        if not eval_ids:
            return []
        audit_pairs: list[ColumnElement[Any]] = []
        for key, audit_value in refetch_audit.items():
            audit_pairs.extend([literal(key, String), literal(audit_value, String)])
        job_stats = func.jsonb_build_object(
            literal('refetch', String),
            func.jsonb_build_object(
                *audit_pairs,
                literal('previous_result', String),
                SLOEvaluation.result,
                literal('previous_status', String),
                SLOEvaluation.status,
            ),
        )
        reset_ids = list(
            (
                await self._session.scalars(
                    update(SLOEvaluation)
                    .where(SLOEvaluation.id.in_(eval_ids), SLOEvaluation.status.in_(REFETCHABLE_STATUSES))
                    .values(
                        status=EvaluationStatus.PENDING,
                        result=None,
                        score=None,
                        achieved_points=None,
                        total_points=None,
                        started_at=None,
                        original_result=None,
                        override_reason=None,
                        override_author=None,
                        job_stats=job_stats,
                    )
                    .returning(SLOEvaluation.id)
                    .execution_options(synchronize_session='fetch')
                )
            ).all()
        )
        if reset_ids:
            await IndicatorRepository(self._session).delete_for_evaluations(reset_ids)
            await SLIValueRepository(self._session).delete_sli_values_for_evaluations(reset_ids)
        return reset_ids

    async def get_by_run_id(self, run_id: uuid.UUID) -> list[SLOEvaluation]:
        """Fetch a run's SLO evaluations, each carrying only its non-hidden annotations.

        Read-only. The `annotations` collections come back deliberately partial (hidden
        rows are excluded in SQL), so these objects must never be used on a write path:
        `annotations` cascades delete-orphan, and mutating a partially loaded
        delete-orphan collection is unsafe.
        """
        query = (
            select(SLOEvaluation)
            .options(
                # Filter hidden notes in SQL rather than in the caller, matching
                # AnnotationRepository.list_for_run — one place decides what 'visible' means.
                selectinload(SLOEvaluation.annotations.and_(EvaluationAnnotation.hidden_at.is_(None))).selectinload(
                    EvaluationAnnotation.category
                ),
                # SLOEvaluation.indicator_rows is lazy='selectin' on the mapper, so without this
                # the caller pays an extra query for rows column-annotations never reads.
                # raiseload rather than noload: reading them here should fail loudly, not silently
                # yield an empty list.
                raiseload(SLOEvaluation.indicator_rows),
            )
            .where(SLOEvaluation.evaluation_id == run_id)
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def list_evaluation_names(
        self,
        *,
        asset_id: uuid.UUID | None = None,
        asset_ids: list[uuid.UUID] | None = None,
    ) -> list[tuple[str, int, datetime]]:
        """Return distinct evaluation names with count and last run timestamp.

        Returns tuples of (name, count, last_run) sorted by last_run DESC.
        """
        stmt = (
            select(
                SLOEvaluation.evaluation_name,
                func.count(SLOEvaluation.evaluation_id.distinct()).label('cnt'),
                func.max(SLOEvaluation.period_start).label('last_run'),
            )
            .where(SLOEvaluation.status == EvaluationStatus.COMPLETED)
            .group_by(SLOEvaluation.evaluation_name)
            .order_by(func.max(SLOEvaluation.period_start).desc())
        )
        if asset_id is not None:
            stmt = stmt.where(SLOEvaluation.asset_id == asset_id)
        if asset_ids:
            stmt = stmt.where(SLOEvaluation.asset_id.in_(asset_ids))
        rows = (await self._session.execute(stmt)).all()
        return [(r.evaluation_name, r.cnt, r.last_run) for r in rows]
