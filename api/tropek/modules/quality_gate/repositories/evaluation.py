"""Evaluation repository — core CRUD and status mutations for evaluations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from asyncpg import UniqueViolationError
from sqlalchemy import String, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tropek.cache.redis_cache import RedisCache
from tropek.db.models import Asset, EvaluationAnnotation, EvaluationRun, IndicatorResultRow, SLOEvaluation
from tropek.modules.common.exceptions import ConflictError
from tropek.modules.quality_gate.evaluation_engine.constants import EvaluationStatus
from tropek.modules.quality_gate.shared.params import EvalCreateParams
from tropek.modules.quality_gate.workflows.presentation.heatmap_cache import HeatmapColumnCache


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
        Used by the router to produce status-aware 409 error messages before
        attempting the insert. The partial unique index on the DB is the
        safety net for concurrent races — this check provides clean UX.

        Decision tree (see also uq_evaluations_identity index on the model):
          - No match → None (caller proceeds with create)
          - Match with status pending/running → caller returns 409 "in progress"
          - Match with status completed/partial → caller returns 409 "use re-evaluate"
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
    ) -> bool:
        """Check whether an earlier evaluation for the same asset+SLO is still pending or running.

        Used by the worker to defer processing until predecessors complete,
        ensuring baselines are available in chronological order.
        """
        q = (
            select(func.count())
            .select_from(SLOEvaluation)
            .where(
                SLOEvaluation.asset_id == asset_id,
                SLOEvaluation.slo_name == slo_name,
                SLOEvaluation.period_start < period_start,
                SLOEvaluation.status.in_([EvaluationStatus.PENDING, EvaluationStatus.RUNNING]),
            )
        )
        result = await self._session.execute(q)
        return (result.scalar() or 0) > 0

    async def mark_running(self, eval_id: uuid.UUID, worker_id: str | None = None) -> None:
        """Transition evaluation to running status, recording worker and start time.

        Args:
            eval_id: Evaluation to update.
            worker_id: Identifier of the worker process claiming this job.
        """
        await self._session.execute(
            update(SLOEvaluation)
            .where(SLOEvaluation.id == eval_id)
            .values(
                status=EvaluationStatus.RUNNING,
                started_at=datetime.now(tz=UTC),
                job_stats={'worker_id': worker_id} if worker_id else {},
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
            job_stats: Optional dict of job execution stats to merge.
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
            'job_stats': merged_stats,
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
            job_stats: Job stats dict may include error, retry_count, etc.
        """
        await self._session.execute(
            update(SLOEvaluation)
            .where(SLOEvaluation.id == eval_id)
            .values(
                status=EvaluationStatus.FAILED,
                job_stats=job_stats or {},
            )
        )

    async def mark_partial(self, eval_id: uuid.UUID, job_stats: dict[str, Any] | None = None) -> None:
        """Transition evaluation to partial — job crashed mid-execution.

        Args:
            eval_id: Evaluation to update.
            job_stats: Partial execution stats (indicators_attempted, _completed, etc.).
        """
        await self._session.execute(
            update(SLOEvaluation)
            .where(SLOEvaluation.id == eval_id)
            .values(status=EvaluationStatus.PARTIAL, job_stats=job_stats or {})
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
                selectinload(SLOEvaluation.annotations).selectinload(
                    EvaluationAnnotation.category
                ),
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
        """Mark an evaluation and all its siblings in the same run as invalidated."""
        ev = await self.get_by_id(eval_id)
        if ev is None:
            return None
        await self._session.execute(
            update(SLOEvaluation)
            .where(SLOEvaluation.evaluation_id == ev.evaluation_id)
            .values(invalidated=True, invalidation_note=note)
        )
        await self._invalidate_baseline_cache(ev.asset_id, ev.slo_name)
        await self._invalidate_heatmap_column(ev.evaluation_id)
        return await self.get_by_id(eval_id)

    async def restore(self, eval_id: uuid.UUID) -> SLOEvaluation | None:
        """Clear invalidation flag on an evaluation and all its siblings in the same run."""
        ev = await self.get_by_id(eval_id)
        if ev is None:
            return None
        await self._session.execute(
            update(SLOEvaluation)
            .where(SLOEvaluation.evaluation_id == ev.evaluation_id)
            .values(invalidated=False, invalidation_note=None)
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

    async def get_by_run_id(self, run_id: uuid.UUID) -> list[SLOEvaluation]:
        """Fetch all SLO evaluations for a parent run, with annotations eagerly loaded."""
        q = (
            select(SLOEvaluation)
            .options(
                selectinload(SLOEvaluation.annotations).selectinload(
                    EvaluationAnnotation.category
                )
            )
            .where(SLOEvaluation.evaluation_id == run_id)
        )
        result = await self._session.execute(q)
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
