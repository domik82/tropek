"""Evaluation repository — all DB access for the quality gate module."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import String, delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Asset, Evaluation, EvaluationAnnotation, SLIValue
from app.modules.quality_gate.engine.constants import EvaluationStatus


class EvaluationRepository:
    """Data access layer for evaluations, annotations, SLI values, and trend queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_pending(
        self,
        *,
        evaluation_name: str,
        period_start: datetime,
        period_end: datetime,
        ingestion_mode: str,
        asset_snapshot: dict[str, Any],
        metadata: dict[str, Any],
        asset_id: uuid.UUID | None = None,
        slo_name: str | None = None,
        slo_version: int | None = None,
        adapter_used: str | None = None,
        sli_name: str | None = None,
        sli_version: int | None = None,
        data_source_name: str | None = None,
    ) -> Evaluation:
        """Create a new evaluation record in pending status.

        Args:
            evaluation_name: Evaluation identifier (e.g. "compilation-test").
            period_start: Evaluation window start.
            period_end: Evaluation window end.
            ingestion_mode: One of "pull", "push", "file".
            asset_snapshot: Denormalised asset state at trigger time.
            metadata: Caller-provided key-value pairs.
            asset_id: Optional UUID of the associated asset.
            slo_name: Named SLO used, if any.
            slo_version: Version of the named SLO, if any.
            adapter_used: Adapter name, if pull mode (e.g. "prometheus").
            sli_name: Named SLI definition used, if any.
            sli_version: Version of the named SLI definition, if any.
            data_source_name: Data source used for metric collection, if any.

        Returns:
            Newly created Evaluation in pending status.
        """
        # Merge asset labels as defaults into metadata (caller values take precedence)
        merged_metadata = dict(metadata)
        if asset_id is not None:
            asset_row = await self._session.get(Asset, asset_id)
            if asset_row is not None and asset_row.labels:
                for key, value in asset_row.labels.items():
                    merged_metadata.setdefault(str(key), str(value))

        ev = Evaluation(
            id=uuid.uuid4(),
            evaluation_name=evaluation_name,
            period_start=period_start,
            period_end=period_end,
            ingestion_mode=ingestion_mode,
            asset_snapshot=asset_snapshot,
            evaluation_metadata=merged_metadata,
            asset_id=asset_id,
            slo_name=slo_name,
            slo_version=slo_version,
            adapter_used=adapter_used,
            sli_name=sli_name,
            sli_version=sli_version,
            data_source_name=data_source_name,
            status=EvaluationStatus.PENDING,
        )
        self._session.add(ev)
        await self._session.flush()
        return ev

    async def mark_running(self, eval_id: uuid.UUID, worker_id: str | None = None) -> None:
        """Transition evaluation to running status, recording worker and start time.

        Args:
            eval_id: Evaluation to update.
            worker_id: Identifier of the worker process claiming this job.
        """
        await self._session.execute(
            update(Evaluation)
            .where(Evaluation.id == eval_id)
            .values(
                status=EvaluationStatus.RUNNING,
                started_at=datetime.now(tz=UTC),
                job_stats={"worker_id": worker_id} if worker_id else {},
            )
        )

    async def mark_completed(
        self,
        eval_id: uuid.UUID,
        *,
        result: str,
        score: float,
        indicator_results: list[Any],
        slo_name: str | None = None,
        slo_version: int | None = None,
        job_stats: dict[str, Any] | None = None,
        compared_evaluation_ids: list[str] | None = None,
    ) -> None:
        """Write final result and transition to completed.

        Args:
            eval_id: Evaluation to update.
            result: One of "pass", "warning", "fail", "error".
            score: Weighted score 0.0-100.0.
            indicator_results: Full per-SLI breakdown as serialisable list.
            slo_name: Named SLO used, if any.
            slo_version: Version of the named SLO, if any.
            job_stats: Optional dict of job execution stats to merge.
            compared_evaluation_ids: IDs of evaluations used for relative criteria.
        """
        merged_stats: dict[str, Any] = dict(job_stats or {})
        if compared_evaluation_ids is not None:
            merged_stats["compared_evaluation_ids"] = compared_evaluation_ids
        await self._session.execute(
            update(Evaluation)
            .where(Evaluation.id == eval_id)
            .values(
                status=EvaluationStatus.COMPLETED,
                result=result,
                score=score,
                slo_name=slo_name,
                slo_version=slo_version,
                indicator_results=indicator_results,
                job_stats=merged_stats,
            )
        )

    async def mark_failed(
        self, eval_id: uuid.UUID, job_stats: dict[str, Any] | None = None
    ) -> None:
        """Transition evaluation to failed, recording error info.

        Args:
            eval_id: Evaluation to update.
            job_stats: Job stats dict may include error, retry_count, etc.
        """
        await self._session.execute(
            update(Evaluation)
            .where(Evaluation.id == eval_id)
            .values(
                status=EvaluationStatus.FAILED,
                job_stats=job_stats or {},
            )
        )

    async def mark_partial(
        self, eval_id: uuid.UUID, job_stats: dict[str, Any] | None = None
    ) -> None:
        """Transition evaluation to partial — job crashed mid-execution.

        Args:
            eval_id: Evaluation to update.
            job_stats: Partial execution stats (indicators_attempted, _completed, etc.).
        """
        await self._session.execute(
            update(Evaluation)
            .where(Evaluation.id == eval_id)
            .values(status=EvaluationStatus.PARTIAL, job_stats=job_stats or {})
        )

    async def get_by_id(self, eval_id: uuid.UUID) -> Evaluation | None:
        """Fetch a single evaluation with annotations eagerly loaded.

        Args:
            eval_id: Evaluation UUID.

        Returns:
            Evaluation with annotations, or None if not found.
        """
        result = await self._session.execute(
            select(Evaluation)
            .options(selectinload(Evaluation.annotations))
            .where(Evaluation.id == eval_id)
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
    ) -> list[Evaluation]:
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
            List of Evaluation rows, newest first.
        """
        q = select(Evaluation)
        if evaluation_name:
            q = q.where(Evaluation.evaluation_name == evaluation_name)
        if asset_name:
            q = q.where(Evaluation.asset_snapshot["name"].as_string() == asset_name)
        if result:
            q = q.where(Evaluation.result == result)
        if from_:
            q = q.where(Evaluation.period_start >= from_)
        if to:
            q = q.where(Evaluation.period_start <= to)
        q = q.order_by(Evaluation.period_start.desc()).limit(limit).offset(offset)
        rows = await self._session.execute(q)
        return list(rows.scalars().all())

    async def get_baselines(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        period_start_before: datetime,
        include_result_with_score: str,
        limit: int,
        tag_filters: dict[str, str] | None = None,
        sli_version_range: tuple[int, int] | None = None,
        restrict_to_ids: list[uuid.UUID] | None = None,
    ) -> list[Evaluation]:
        """Fetch previous completed evaluations for baseline comparison.

        Scoped by asset + SLO, with optional tag filtering, version range,
        and ID restriction (for cascading re-evaluation).

        Args:
            asset_id: Asset UUID to scope baselines to.
            slo_name: SLO name to scope baselines to.
            period_start_before: Only include evaluations before this timestamp.
            include_result_with_score: "pass", "pass_or_warn", or "all".
            limit: Maximum number of baseline evaluations to return.
            tag_filters: Optional tag key-value pairs to match in evaluation_metadata.
            sli_version_range: Optional (min, max) inclusive version range for sli_version.
            restrict_to_ids: Optional list of evaluation IDs to restrict results to.

        Returns:
            Matching completed evaluations ordered by period_start descending.
        """
        q = select(Evaluation).where(
            Evaluation.asset_id == asset_id,
            Evaluation.slo_name == slo_name,
            Evaluation.period_start < period_start_before,
            Evaluation.status == EvaluationStatus.COMPLETED,
            Evaluation.invalidated == False,  # noqa: E712
        )
        if include_result_with_score == "pass":
            q = q.where(Evaluation.result == "pass")
        elif include_result_with_score == "pass_or_warn":
            q = q.where(Evaluation.result.in_(["pass", "warning"]))

        if tag_filters:
            for key, value in tag_filters.items():
                q = q.where(Evaluation.evaluation_metadata[(key,)].as_string() == value)

        if sli_version_range:
            q = q.where(Evaluation.sli_version.is_not(None))
            q = q.where(Evaluation.sli_version >= sli_version_range[0])
            q = q.where(Evaluation.sli_version <= sli_version_range[1])

        if restrict_to_ids is not None:
            q = q.where(Evaluation.id.in_(restrict_to_ids))

        # Pin-aware: restrict baseline window to evaluations after the active pin
        if asset_id and slo_name:
            pin_q = select(Evaluation.period_start).where(
                Evaluation.asset_id == asset_id,
                Evaluation.slo_name == slo_name,
                Evaluation.baseline_pinned_at.is_not(None),
                Evaluation.baseline_unpinned_at.is_(None),
            )
            pin_row = await self._session.execute(pin_q)
            pin_start = pin_row.scalar_one_or_none()
            if pin_start is not None:
                q = q.where(Evaluation.period_start >= pin_start)

        q = q.order_by(Evaluation.period_start.desc()).limit(limit)
        rows = await self._session.execute(q)
        return list(rows.scalars().all())

    async def find_stuck(self, threshold_seconds: int) -> list[Evaluation]:
        """Find evaluations stuck in running status for longer than the threshold.

        Used by the watchdog to detect and reschedule crashed jobs.

        Args:
            threshold_seconds: Jobs running longer than this (in seconds) are stuck.

        Returns:
            List of stuck Evaluation rows.
        """
        cutoff = datetime.now(tz=UTC) - timedelta(seconds=threshold_seconds)
        result = await self._session.execute(
            select(Evaluation).where(
                Evaluation.status == EvaluationStatus.RUNNING,
                Evaluation.started_at < cutoff,
            )
        )
        return list(result.scalars().all())

    async def list_with_counts(
        self,
        *,
        asset_id: uuid.UUID | None = None,
        slo_name: str | None = None,
        result: str | None = None,
        date_prefix: str | None = None,
        asset_ids: list[uuid.UUID] | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Evaluation], int, dict[uuid.UUID, int]]:
        """Return (page, total_count, annotation_count_map) with optional filters.

        asset_id and asset_ids are DB FK lookups (not JSONB snapshot).
        annotation_count_map: {eval_id -> count} for the returned page only.
        """
        q = select(Evaluation)
        if asset_id:
            q = q.where(Evaluation.asset_id == asset_id)
        if slo_name:
            q = q.where(Evaluation.slo_name == slo_name)
        if result:
            q = q.where(Evaluation.result == result)
        if date_prefix:
            q = q.where(Evaluation.period_start.cast(String).like(f"{date_prefix}%"))
        if asset_ids:
            q = q.where(Evaluation.asset_id.in_(asset_ids))
        if from_ts:
            q = q.where(Evaluation.period_start >= from_ts)
        if to_ts:
            q = q.where(Evaluation.period_start <= to_ts)
        count_q = select(func.count()).select_from(q.subquery())
        total_result = await self._session.execute(count_q)
        total = total_result.scalar_one()
        q = q.order_by(Evaluation.period_start.desc()).limit(limit).offset(offset)
        rows = await self._session.execute(q)
        evals = list(rows.scalars().all())
        count_map: dict[uuid.UUID, int] = {}
        if evals:
            eval_ids = [ev.id for ev in evals]
            cnt_rows = await self._session.execute(
                select(EvaluationAnnotation.evaluation_id, func.count().label("cnt"))
                .where(EvaluationAnnotation.evaluation_id.in_(eval_ids))
                .group_by(EvaluationAnnotation.evaluation_id)
            )
            count_map = {row.evaluation_id: row.cnt for row in cnt_rows}
        return evals, total, count_map

    async def invalidate(self, eval_id: uuid.UUID, *, note: str) -> Evaluation | None:
        """Mark an evaluation as invalidated."""
        await self._session.execute(
            update(Evaluation)
            .where(Evaluation.id == eval_id)
            .values(invalidated=True, invalidation_note=note)
        )
        return await self.get_by_id(eval_id)

    async def restore(self, eval_id: uuid.UUID) -> Evaluation | None:
        """Clear invalidation flag."""
        await self._session.execute(
            update(Evaluation)
            .where(Evaluation.id == eval_id)
            .values(invalidated=False, invalidation_note=None)
        )
        return await self.get_by_id(eval_id)

    async def pin_baseline(
        self,
        eval_id: uuid.UUID,
        *,
        reason: str,
        author: str,
    ) -> Evaluation | None:
        """Pin an evaluation as the baseline floor for its asset+SLO combination.

        Atomically unpins any existing active pin for the same (asset_id, slo_name).
        """
        ev = await self.get_by_id(eval_id)
        if ev is None:
            return None
        # Unpin any existing active pin for this asset+SLO
        if ev.asset_id and ev.slo_name:
            await self._session.execute(
                update(Evaluation)
                .where(
                    Evaluation.asset_id == ev.asset_id,
                    Evaluation.slo_name == ev.slo_name,
                    Evaluation.baseline_pinned_at.is_not(None),
                    Evaluation.baseline_unpinned_at.is_(None),
                )
                .values(baseline_unpinned_at=func.now())
            )
        # Pin the target evaluation
        await self._session.execute(
            update(Evaluation)
            .where(Evaluation.id == eval_id)
            .values(
                baseline_pinned_at=func.now(),
                baseline_pin_reason=reason,
                baseline_pin_author=author,
            )
        )
        await self._session.flush()
        return await self.get_by_id(eval_id)

    async def unpin_baseline(self, eval_id: uuid.UUID) -> Evaluation | None:
        """Remove the baseline pin from an evaluation."""
        await self._session.execute(
            update(Evaluation)
            .where(Evaluation.id == eval_id)
            .values(baseline_unpinned_at=func.now())
        )
        await self._session.flush()
        return await self.get_by_id(eval_id)

    async def override_status(
        self,
        eval_id: uuid.UUID,
        *,
        new_result: str,
        reason: str,
        author: str,
    ) -> Evaluation | None:
        """Override the evaluation result, preserving the original."""
        ev = await self.get_by_id(eval_id)
        if ev is None:
            return None
        await self._session.execute(
            update(Evaluation)
            .where(Evaluation.id == eval_id)
            .values(
                original_result=ev.result,
                result=new_result,
                override_reason=reason,
                override_author=author,
            )
        )
        await self._session.flush()
        return await self.get_by_id(eval_id)

    async def restore_override(self, eval_id: uuid.UUID) -> Evaluation | None:
        """Restore the original result, clearing the override."""
        ev = await self.get_by_id(eval_id)
        if ev is None or ev.original_result is None:
            return ev
        await self._session.execute(
            update(Evaluation)
            .where(Evaluation.id == eval_id)
            .values(
                result=ev.original_result,
                original_result=None,
                override_reason=None,
                override_author=None,
            )
        )
        await self._session.flush()
        return await self.get_by_id(eval_id)

    async def get_metric_heatmap(
        self,
        *,
        asset_id: uuid.UUID,
        limit: int = 20,
    ) -> list[Evaluation]:
        """Fetch the last N completed evaluations for an asset, ordered by period_start DESC."""
        q = (
            select(Evaluation)
            .where(
                Evaluation.asset_id == asset_id,
                Evaluation.status == EvaluationStatus.COMPLETED,
            )
            .order_by(Evaluation.period_start.desc())
            .limit(limit)
        )
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def get_annotation_by_id(self, annotation_id: uuid.UUID) -> EvaluationAnnotation | None:
        """Fetch a single annotation by its ID."""
        result = await self._session.execute(
            select(EvaluationAnnotation).where(EvaluationAnnotation.id == annotation_id)
        )
        return result.scalar_one_or_none()

    async def update_annotation(
        self,
        annotation_id: uuid.UUID,
        *,
        content: str | None = None,
        author: str | None = None,
        category: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> EvaluationAnnotation | None:
        """Update mutable annotation fields."""
        values: dict[str, Any] = {}
        if content is not None:
            values["content"] = content
        if author is not None:
            values["author"] = author
        if category is not None:
            values["category"] = category
        if meta is not None:
            values["meta"] = meta
        if values:
            await self._session.execute(
                update(EvaluationAnnotation)
                .where(EvaluationAnnotation.id == annotation_id)
                .values(**values)
            )
        return await self.get_annotation_by_id(annotation_id)

    async def get_trend_by_domain(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        metric_name: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return time-series trend points for a specific asset+SLO+metric combination.

        Fetches the most recent `limit` evaluations DESC, then returns them ASC.
        Baseline extracted from indicator_results JSONB array.
        Excludes invalidated evaluations and those with asset_id=NULL.
        """
        inner = (
            select(
                Evaluation.period_start,
                SLIValue.value,
                SLIValue.eval_id,
                Evaluation.result,
                Evaluation.indicator_results,
            )
            .join(Evaluation, SLIValue.eval_id == Evaluation.id)
            .where(
                Evaluation.asset_id == asset_id,
                Evaluation.slo_name == slo_name,
                SLIValue.metric_name == metric_name,
                Evaluation.invalidated == False,  # noqa: E712
                Evaluation.result.is_not(None),
            )
            .order_by(Evaluation.period_start.desc())
            .limit(limit)
            .subquery()
        )
        rows = await self._session.execute(select(inner).order_by(inner.c.period_start))
        points = []
        for r in rows:
            baseline: float | None = None
            for ind in r.indicator_results or []:
                if ind.get("metric") == metric_name:
                    baseline = ind.get("compared_value")
                    break
            points.append(
                {
                    "timestamp": r.period_start.isoformat(),
                    "value": r.value,
                    "eval_id": str(r.eval_id),
                    "result": r.result,
                    "baseline": baseline,
                }
            )
        return points

    # --- SLI Values ---

    async def write_sli_values(self, rows: list[dict[str, Any]]) -> None:
        """Batch insert SLI value rows.

        Args:
            rows: List of dicts matching SLIValue columns (eval_id, eval_start,
                  metric_name, aggregation, value, asset_name, evaluation_name, os_tag).
        """
        if not rows:
            return
        await self._session.execute(insert(SLIValue).values(rows))

    async def delete_sli_values(self, eval_id: uuid.UUID) -> None:
        """Delete all SLI values for an evaluation (hard rerun).

        Args:
            eval_id: Evaluation whose SLI values should be deleted.
        """
        await self._session.execute(delete(SLIValue).where(SLIValue.eval_id == eval_id))

    async def get_sli_values_for_eval(self, eval_id: uuid.UUID) -> list[SLIValue]:
        """Fetch all SLI values for a given evaluation.

        Args:
            eval_id: Evaluation UUID.

        Returns:
            All SLIValue rows for this evaluation.
        """
        result = await self._session.execute(select(SLIValue).where(SLIValue.eval_id == eval_id))
        return list(result.scalars().all())

    async def get_trend(
        self,
        *,
        evaluation_name: str,
        metric_name: str,
        asset_name: str | None = None,
        from_: datetime | None = None,
        to: datetime | None = None,
        result_filter: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return time-series data points for the trend endpoint.

        Args:
            evaluation_name: Evaluation identifier to query.
            metric_name: SLI metric name (e.g. "response_time_p99").
            asset_name: Optional filter by asset name.
            from_: Optional start of time range.
            to: Optional end of time range.
            result_filter: Optional list of result values to include.

        Returns:
            List of {timestamp, value, eval_id, result} dicts, ordered by time ascending.
        """
        q = (
            select(
                SLIValue.eval_start,
                SLIValue.value,
                SLIValue.eval_id,
                Evaluation.result,
            )
            .join(Evaluation, SLIValue.eval_id == Evaluation.id)
            .where(
                SLIValue.evaluation_name == evaluation_name,
                SLIValue.metric_name == metric_name,
                Evaluation.invalidated == False,  # noqa: E712
            )
        )
        if asset_name:
            q = q.where(SLIValue.asset_name == asset_name)
        if from_:
            q = q.where(SLIValue.eval_start >= from_)
        if to:
            q = q.where(SLIValue.eval_start <= to)
        if result_filter:
            q = q.where(Evaluation.result.in_(result_filter))
        q = q.order_by(SLIValue.eval_start)
        rows = await self._session.execute(q)
        return [
            {
                "timestamp": r.eval_start.isoformat(),
                "value": r.value,
                "eval_id": str(r.eval_id),
                "result": r.result,
            }
            for r in rows
        ]

    # --- Annotations ---

    async def add_annotation(
        self,
        eval_id: uuid.UUID,
        *,
        content: str,
        author: str | None = None,
        category: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> EvaluationAnnotation:
        """Append an annotation to an evaluation.

        Args:
            eval_id: Evaluation to annotate.
            content: Note text (required).
            author: Optional identifier of who wrote the annotation.
            category: Optional free label (e.g. "environment", "deployment").
            meta: Optional arbitrary metadata.

        Returns:
            Newly created EvaluationAnnotation.
        """
        ann = EvaluationAnnotation(
            id=uuid.uuid4(),
            evaluation_id=eval_id,
            content=content,
            author=author,
            category=category,
            meta=meta or {},
        )
        self._session.add(ann)
        await self._session.flush()
        return ann

    async def delete_annotation(self, annotation_id: uuid.UUID) -> None:
        """Delete an annotation by ID.

        Args:
            annotation_id: Annotation to delete.
        """
        await self._session.execute(
            delete(EvaluationAnnotation).where(EvaluationAnnotation.id == annotation_id)
        )
