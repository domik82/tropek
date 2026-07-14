"""Heatmap repository — DB access for the metric and grouped heatmap views."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, selectinload

from tropek.db.models import (
    EvaluationAnnotation,
    EvaluationRun,
    IndicatorResultRow,
    SLOEvaluation,
)
from tropek.modules.quality_gate.evaluation_engine.constants import EvaluationStatus


def _apply_window_filters(
    query: Select[Any],
    *,
    name_column: InstrumentedAttribute[str],
    period_start_column: InstrumentedAttribute[datetime],
    names: list[str] | None,
    from_ts: datetime | None,
    to_ts: datetime | None,
) -> Select[Any]:
    """Apply the shared eval-name / period-start window filters to a heatmap query.

    Every heatmap read narrows by an optional list of evaluation names and an
    optional ``[from_ts, to_ts]`` period-start range. Sharing it here keeps the
    metric, grouped, and inventory queries filtering identically so they return
    the same run set for the same window.
    """
    if names:
        query = query.where(name_column.in_(names))
    if from_ts:
        query = query.where(period_start_column >= from_ts)
    if to_ts:
        query = query.where(period_start_column <= to_ts)
    return query


class HeatmapRepository:
    """Data access layer for the metric and grouped heatmap views."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_metric_heatmap(
        self,
        *,
        asset_id: uuid.UUID,
        evaluation_name: list[str] | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ) -> list[SLOEvaluation]:
        """Fetch completed evaluations for an asset within a date range.

        When no date range is provided, falls back to the most recent 500
        evaluations as a safety cap.
        """
        query = (
            select(SLOEvaluation)
            .options(
                selectinload(SLOEvaluation.indicator_rows).joinedload(IndicatorResultRow.objective),
            )
            .where(
                SLOEvaluation.asset_id == asset_id,
                SLOEvaluation.status == EvaluationStatus.COMPLETED,
            )
            .order_by(SLOEvaluation.period_start.desc())
        )
        query = _apply_window_filters(
            query,
            name_column=SLOEvaluation.evaluation_name,
            period_start_column=SLOEvaluation.period_start,
            names=evaluation_name,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        if not from_ts and not to_ts:
            query = query.limit(500)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_grouped_metric_heatmap(
        self,
        *,
        asset_id: uuid.UUID,
        eval_name: list[str] | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        run_id_filter: list[uuid.UUID] | None = None,
    ) -> list[EvaluationRun]:
        """Fetch completed EvaluationRun rows with all child SLO evaluations and indicator results.

        Returns rows ordered period_start DESC (caller reverses to oldest-first for display).
        When no date range is provided, falls back to the most recent 100 runs as a safety cap.

        When ``run_id_filter`` is provided, only runs whose id is in that list are
        returned (and the 100-run safety cap is skipped — the caller already decided
        which ids to load). This is how the cached read path refetches exactly the
        columns that missed the Redis column cache.
        """
        query = (
            select(EvaluationRun)
            .options(
                selectinload(EvaluationRun.slo_evaluations)
                .selectinload(SLOEvaluation.indicator_rows)
                .joinedload(IndicatorResultRow.objective),
            )
            .where(
                EvaluationRun.asset_id == asset_id,
                EvaluationRun.status == EvaluationStatus.COMPLETED,
            )
            .order_by(EvaluationRun.period_start.desc())
        )
        query = _apply_window_filters(
            query,
            name_column=EvaluationRun.eval_name,
            period_start_column=EvaluationRun.period_start,
            names=eval_name,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        if run_id_filter is not None:
            query = query.where(EvaluationRun.id.in_(run_id_filter))
        elif not from_ts and not to_ts:
            query = query.limit(100)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_run_with_slo_evaluations(self, run_id: uuid.UUID) -> EvaluationRun | None:
        """Return one ``EvaluationRun`` with all relationships needed by the fragment builder.

        Eagerly loads ``slo_evaluations`` and their ``indicator_rows`` joined to
        ``SLOObjective``, mirroring the loader chain in
        :meth:`get_grouped_metric_heatmap` so the worker warm path produces an
        identical fragment to the read path's rebuild.
        """
        query = (
            select(EvaluationRun)
            .options(
                selectinload(EvaluationRun.slo_evaluations)
                .selectinload(SLOEvaluation.indicator_rows)
                .joinedload(IndicatorResultRow.objective),
            )
            .where(EvaluationRun.id == run_id)
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def list_runs_for_heatmap(
        self,
        *,
        asset_id: uuid.UUID,
        eval_name: list[str] | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ) -> list[EvaluationRun]:
        """Return completed EvaluationRun rows in the window with no joined relationships.

        This is the lightweight cache-key inventory query for the grouped heatmap
        read path: cheaper than ``get_grouped_metric_heatmap`` because it skips
        the JOIN to ``slo_evaluations`` / ``indicator_rows`` / ``slo_objectives``.
        Rows are ordered period_start DESC to match the heavy query, so the
        caller can treat the two as returning the same run set for the same
        window. When no date range is provided, falls back to the most recent
        100 runs as a safety cap — again mirroring ``get_grouped_metric_heatmap``.
        """
        query = (
            select(EvaluationRun)
            .where(
                EvaluationRun.asset_id == asset_id,
                EvaluationRun.status == EvaluationStatus.COMPLETED,
            )
            .order_by(EvaluationRun.period_start.desc())
        )
        query = _apply_window_filters(
            query,
            name_column=EvaluationRun.eval_name,
            period_start_column=EvaluationRun.period_start,
            names=eval_name,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        if not from_ts and not to_ts:
            query = query.limit(100)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_run_ids_with_notes(self, run_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        """Return the subset of `run_ids` with at least one non-hidden annotation.

        Annotations attach polymorphically (XOR) to either a child SLOEvaluation
        (re-eval deltas, per-SLO notes) or directly to the EvaluationRun
        (column-level notes created from the UI). Both forms must count toward
        the heatmap's note indicator, so this runs a UNION: SLO-level hits
        resolved via `slo_evaluations.evaluation_id`, run-level hits resolved
        directly from `evaluation_annotations.evaluation_run_id`.
        """
        if not run_ids:
            return set()
        slo_level_hits = (
            select(SLOEvaluation.evaluation_id.label('run_id'))
            .join(
                EvaluationAnnotation,
                EvaluationAnnotation.slo_evaluation_id == SLOEvaluation.id,
            )
            .where(
                SLOEvaluation.evaluation_id.in_(run_ids),
                EvaluationAnnotation.hidden_at.is_(None),
            )
        )
        run_level_hits = select(EvaluationAnnotation.evaluation_run_id.label('run_id')).where(
            EvaluationAnnotation.evaluation_run_id.in_(run_ids),
            EvaluationAnnotation.hidden_at.is_(None),
        )
        result = await self._session.execute(slo_level_hits.union(run_level_hits))
        return {row[0] for row in result.all()}
