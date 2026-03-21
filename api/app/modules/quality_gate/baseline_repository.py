"""Baseline repository — DB access for baselines and re-evaluation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Evaluation, IndicatorResultRow, SLOObjective
from app.modules.quality_gate.annotation_repository import AnnotationRepository
from app.modules.quality_gate.engine.constants import EvaluationStatus
from app.modules.quality_gate.engine.result_models import IndicatorResult
from app.modules.quality_gate.indicator_repository import IndicatorRepository


class BaselineRepository:
    """Data access layer for baselines and re-evaluation results."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_evaluation_baselines(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        period_start_before: datetime,
        include_result_with_score: str,
        limit: int,
    ) -> list[Evaluation]:
        """Fetch previous completed evaluations for baseline comparison during scoring.

        Used by the worker when evaluating a new run against previous results.
        Pin-aware: restricts the baseline window to evaluations after the active pin.

        Args:
            asset_id: Asset UUID to scope baselines to.
            slo_name: SLO name to scope baselines to.
            period_start_before: Only include evaluations before this timestamp.
            include_result_with_score: "pass", "pass_or_warn", or "all".
            limit: Maximum number of baseline evaluations to return.

        Returns:
            Matching completed evaluations ordered by period_start descending.
        """
        q = self._base_baseline_query(
            asset_id=asset_id,
            slo_name=slo_name,
            period_start_before=period_start_before,
            include_result_with_score=include_result_with_score,
        )
        q = q.options(
            selectinload(Evaluation.indicator_rows).joinedload(IndicatorResultRow.objective),
        )
        q = await self._apply_pin_filter(q, asset_id=asset_id, slo_name=slo_name)
        q = q.order_by(Evaluation.period_start.desc()).limit(limit)
        rows = await self._session.execute(q)
        return list(rows.scalars().all())

    async def get_reeval_baselines(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        period_start_before: datetime,
        include_result_with_score: str,
        limit: int,
        sli_version_range: tuple[int, int] | None = None,
        restrict_to_ids: list[uuid.UUID] | None = None,
        tag_filters: dict[str, str] | None = None,
    ) -> list[Evaluation]:
        """Fetch previous completed evaluations for re-evaluation baseline comparison.

        Used by the re-evaluator with SLI version filtering and ID restriction
        for cascading re-evaluation.

        Args:
            asset_id: Asset UUID to scope baselines to.
            slo_name: SLO name to scope baselines to.
            period_start_before: Only include evaluations before this timestamp.
            include_result_with_score: "pass", "pass_or_warn", or "all".
            limit: Maximum number of baseline evaluations to return.
            sli_version_range: Optional (min, max) inclusive version range for sli_version.
            restrict_to_ids: Optional list of evaluation IDs to restrict results to.
            tag_filters: Optional JSONB key-value filters on variables.

        Returns:
            Matching completed evaluations ordered by period_start descending.
        """
        q = self._base_baseline_query(
            asset_id=asset_id,
            slo_name=slo_name,
            period_start_before=period_start_before,
            include_result_with_score=include_result_with_score,
        )
        q = q.options(
            selectinload(Evaluation.indicator_rows).joinedload(IndicatorResultRow.objective),
        )

        if sli_version_range:
            q = q.where(Evaluation.sli_version.is_not(None))
            q = q.where(Evaluation.sli_version >= sli_version_range[0])
            q = q.where(Evaluation.sli_version <= sli_version_range[1])

        if restrict_to_ids is not None:
            q = q.where(Evaluation.id.in_(restrict_to_ids))

        if tag_filters:
            for key, value in tag_filters.items():
                q = q.where(Evaluation.variables[key].astext == value)

        q = await self._apply_pin_filter(q, asset_id=asset_id, slo_name=slo_name)
        q = q.order_by(Evaluation.period_start.desc()).limit(limit)
        rows = await self._session.execute(q)
        return list(rows.scalars().all())

    @staticmethod
    def _base_baseline_query(
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        period_start_before: datetime,
        include_result_with_score: str,
    ) -> Any:
        """Build the shared base query for baseline lookups."""
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
        return q

    async def _apply_pin_filter(
        self,
        q: Any,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
    ) -> Any:
        """Restrict baseline window to evaluations after the active pin, if any."""
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
        return q

    async def load_evaluations_for_reeval(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        from_date: datetime,
    ) -> list[Evaluation]:
        """Load completed, non-invalidated evaluations for re-evaluation.

        Returns evaluations in chronological order (period_start ASC)
        for cascading baseline resolution.

        Args:
            asset_id: Asset UUID to scope results to.
            slo_name: SLO name to scope results to.
            from_date: Only include evaluations at or after this timestamp.

        Returns:
            Matching completed evaluations ordered by period_start ascending.
        """
        q = (
            select(Evaluation)
            .where(
                Evaluation.asset_id == asset_id,
                Evaluation.slo_name == slo_name,
                Evaluation.period_start >= from_date,
                Evaluation.status == EvaluationStatus.COMPLETED,
                Evaluation.invalidated == False,  # noqa: E712
            )
            .options(
                selectinload(Evaluation.indicator_rows).joinedload(IndicatorResultRow.objective),
            )
            .order_by(Evaluation.period_start)
        )
        rows = await self._session.execute(q)
        return list(rows.scalars().all())

    async def update_reeval_result(
        self,
        eval_id: uuid.UUID,
        *,
        new_result: str,
        new_score: float,
        new_indicator_results: list[Any],
        new_engine_results: list[IndicatorResult] | None = None,
        slo_objectives: list[SLOObjective] | None = None,
        old_result: str,
        old_score: float,
        slo_version: int | None = None,
    ) -> None:
        """Overwrite evaluation result from re-evaluation, preserving original on first call.

        Args:
            eval_id: Evaluation to update.
            new_result: Re-evaluated result value ("pass", "warning", "fail", "error").
            new_score: Re-evaluated weighted score 0.0-100.0.
            new_indicator_results: Full per-SLI breakdown from re-evaluation (JSONB dual-write).
            new_engine_results: Engine IndicatorResult objects for normalized row writing.
            slo_objectives: SLOObjective ORM instances for objective ID lookup.
            old_result: Previous result value (stored in job_stats on first call only).
            old_score: Previous score (stored in job_stats on first call only).
            slo_version: SLO version used for re-evaluation, if any.
        """
        result = await self._session.execute(
            select(Evaluation)
            .options(selectinload(Evaluation.annotations))
            .where(Evaluation.id == eval_id)
        )
        ev = result.scalar_one_or_none()
        if ev is None:
            return

        stats = dict(ev.job_stats)
        if "original_result" not in stats:
            stats["original_result"] = old_result
            stats["original_score"] = old_score
        stats["re_evaluated_at"] = datetime.now(tz=UTC).isoformat()
        stats["re_eval_slo_version"] = slo_version

        values: dict[str, Any] = {
            "result": new_result,
            "score": new_score,
            "indicator_results": new_indicator_results,
            "job_stats": stats,
        }
        if slo_version is not None:
            values["slo_version"] = slo_version

        await self._session.execute(
            update(Evaluation).where(Evaluation.id == eval_id).values(**values)
        )

        annotation_content = (
            f"re-evaluated: {old_result} -> {new_result}, score {old_score} -> {new_score}"
        )
        ann_repo = AnnotationRepository(self._session)
        await ann_repo.add_annotation(
            eval_id,
            content=annotation_content,
            author="system",
            category="re-evaluation",
        )

        # Write to normalized table (dual-write)
        if new_engine_results and slo_objectives:
            indicator_repo = IndicatorRepository(self._session)
            await indicator_repo.delete_for_evaluation(eval_id)
            obj_lookup = {obj.sli: obj.id for obj in slo_objectives}
            rows: list[dict[str, Any]] = []
            for ir in new_engine_results:
                obj_id = obj_lookup.get(ir.metric)
                if obj_id is None:
                    continue
                rows.append(
                    {
                        "evaluation_id": eval_id,
                        "slo_objective_id": obj_id,
                        "value": ir.value,
                        "compared_value": ir.compared_value,
                        "change_absolute": ir.change_absolute,
                        "change_relative_pct": ir.change_relative_pct,
                        "status": ir.status,
                        "score": ir.score,
                    }
                )
            if rows:
                await indicator_repo.bulk_insert(eval_id, rows)
