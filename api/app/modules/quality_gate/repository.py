"""Evaluation repository — all DB access for the quality gate module."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Evaluation, EvaluationAnnotation, SLIValue
from app.modules.quality_gate.engine.constants import EvaluationStatus


class EvaluationRepository:
    """Data access layer for evaluations, annotations, SLI values, and trend queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_pending(
        self,
        *,
        name: str,
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
            name: Test identifier (e.g. "compilation-test").
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
        ev = Evaluation(
            id=uuid.uuid4(),
            name=name,
            period_start=period_start,
            period_end=period_end,
            ingestion_mode=ingestion_mode,
            asset_snapshot=asset_snapshot,
            evaluation_metadata=metadata,
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
        slo_yaml: str,
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
            slo_yaml: Resolved SLO YAML (after variable substitution).
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
                slo_yaml=slo_yaml,
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
        name: str | None = None,
        asset_name: str | None = None,
        result: str | None = None,
        from_: datetime | None = None,
        to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Evaluation]:
        """List evaluations with optional filters.

        Args:
            name: Filter by test name.
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
        if name:
            q = q.where(Evaluation.name == name)
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
        name: str,
        scope_tags: list[str],
        asset_snapshot: dict[str, Any],
        include_result_with_score: str,
        limit: int,
        sli_name: str | None = None,
    ) -> list[Evaluation]:
        """Fetch previous completed evaluations for relative criteria comparison.

        Scoped by test name, result filter, and JSONB tag matching.

        Args:
            name: Test name to match.
            scope_tags: Asset snapshot tag keys to match (e.g. ["os", "arch"]).
            asset_snapshot: Current evaluation's asset snapshot — provides tag values to match.
            include_result_with_score: "pass", "pass_or_warn", or "all".
            limit: Maximum number of baseline evaluations to return.
            sli_name: Optional SLI name to match (for filtering baselines by metric).

        Returns:
            Matching completed evaluations ordered by period_start descending.
        """
        q = select(Evaluation).where(
            Evaluation.name == name,
            Evaluation.status == EvaluationStatus.COMPLETED,
            Evaluation.invalidated == False,  # noqa: E712
        )
        if include_result_with_score == "pass":
            q = q.where(Evaluation.result == "pass")
        elif include_result_with_score == "pass_or_warn":
            q = q.where(Evaluation.result.in_(["pass", "warning"]))
        # "all" — no result filter

        if sli_name:
            q = q.where(Evaluation.sli_name == sli_name)

        # Scope by asset snapshot tags
        current_tags = asset_snapshot.get("tags", {})
        for tag in scope_tags:
            tag_value = current_tags.get(tag)
            if tag_value is not None:
                q = q.where(Evaluation.asset_snapshot[("tags", tag)].as_string() == tag_value)

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

    # --- SLI Values ---

    async def write_sli_values(self, rows: list[dict[str, Any]]) -> None:
        """Batch insert SLI value rows.

        Args:
            rows: List of dicts matching SLIValue columns (eval_id, eval_start,
                  metric_name, aggregation, value, asset_name, test_name, os_tag).
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
        test_name: str,
        metric_name: str,
        asset_name: str | None = None,
        from_: datetime | None = None,
        to: datetime | None = None,
        result_filter: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return time-series data points for the trend endpoint.

        Args:
            test_name: Test identifier to query.
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
                SLIValue.test_name == test_name,
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
