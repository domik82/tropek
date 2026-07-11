"""Trend repository — DB access for trend queries and metric heatmaps."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tropek.db.models import (
    EvaluationAnnotation,
    EvaluationRun,
    IndicatorResultRow,
    SLIValue,
    SLOEvaluation,
    SLOObjective,
)
from tropek.modules.change_points.repository import ChangePointKey
from tropek.modules.quality_gate.evaluation_engine.constants import EvaluationStatus
from tropek.modules.quality_gate.schemas.trend import TrendColumnFragment
from tropek.modules.quality_gate.workflows.presentation.trend_assembler import TrendRow, build_trend_fragment


def _trend_change_point(
    lookup: dict[ChangePointKey, Any] | None,
    slo_name: str,
    metric_name: str,
    period_start: datetime,
    period_end: datetime | None,
    evaluation_name: str,
) -> dict[str, Any] | None:
    if not lookup:
        return None
    key = ChangePointKey(slo_name, metric_name, period_start, period_end, evaluation_name)
    change_point = lookup.get(key)
    if change_point is None:
        return None
    return {
        'direction': change_point.direction,
        'change_relative_pct': change_point.change_relative_pct,
        'transition': change_point.transition,
        'change_absolute': change_point.change_absolute,
    }


class TrendRepository:
    """Data access layer for trend queries and metric heatmaps."""

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
        q = (
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
        if evaluation_name:
            q = q.where(SLOEvaluation.evaluation_name.in_(evaluation_name))
        if from_ts:
            q = q.where(SLOEvaluation.period_start >= from_ts)
        if to_ts:
            q = q.where(SLOEvaluation.period_start <= to_ts)
        if not from_ts and not to_ts:
            q = q.limit(500)
        result = await self._session.execute(q)
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
        q = (
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
        if eval_name:
            q = q.where(EvaluationRun.eval_name.in_(eval_name))
        if from_ts:
            q = q.where(EvaluationRun.period_start >= from_ts)
        if to_ts:
            q = q.where(EvaluationRun.period_start <= to_ts)
        if run_id_filter is not None:
            q = q.where(EvaluationRun.id.in_(run_id_filter))
        elif not from_ts and not to_ts:
            q = q.limit(100)
        result = await self._session.execute(q)
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
        q = (
            select(EvaluationRun)
            .where(
                EvaluationRun.asset_id == asset_id,
                EvaluationRun.status == EvaluationStatus.COMPLETED,
            )
            .order_by(EvaluationRun.period_start.desc())
        )
        if eval_name:
            q = q.where(EvaluationRun.eval_name.in_(eval_name))
        if from_ts:
            q = q.where(EvaluationRun.period_start >= from_ts)
        if to_ts:
            q = q.where(EvaluationRun.period_start <= to_ts)
        if not from_ts and not to_ts:
            q = q.limit(100)
        result = await self._session.execute(q)
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

    async def get_trend_by_domain(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        metric_name: str,
        from_ts: datetime,
        to_ts: datetime | None = None,
        change_point_lookup: dict[ChangePointKey, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return time-series trend points for a specific asset+SLO+metric combination.

        Filters by ``from_ts`` (required) and optional ``to_ts``.
        Returns rows ordered ASC.
        Baseline from IndicatorResultRow.compared_value via JOIN.
        Excludes invalidated evaluations and those with asset_id=NULL.
        """
        # Scalar subquery: total weight of all objectives for the same evaluation.
        # Used to convert raw weighted score → percentage that stacks to 100%.
        total_weight_sq = (
            select(func.coalesce(func.sum(SLOObjective.weight), 1))
            .join(IndicatorResultRow, IndicatorResultRow.slo_objective_id == SLOObjective.id)
            .where(IndicatorResultRow.slo_evaluation_id == SLOEvaluation.id)
            .correlate(SLOEvaluation)
            .scalar_subquery()
            .label('total_weight')
        )

        inner = (
            select(
                SLOEvaluation.period_start,
                SLOEvaluation.period_end,
                SLOEvaluation.evaluation_name,
                SLIValue.value,
                SLIValue.slo_evaluation_id,
                IndicatorResultRow.status.label('result'),
                IndicatorResultRow.compared_value,
                IndicatorResultRow.score,
                IndicatorResultRow.targets.label('targets'),
                total_weight_sq,
            )
            .join(SLOEvaluation, SLIValue.slo_evaluation_id == SLOEvaluation.id)
            .join(
                IndicatorResultRow,
                IndicatorResultRow.slo_evaluation_id == SLOEvaluation.id,
            )
            .join(
                SLOObjective,
                IndicatorResultRow.slo_objective_id == SLOObjective.id,
            )
            .where(
                SLOEvaluation.asset_id == asset_id,
                SLOEvaluation.slo_name == slo_name,
                SLIValue.metric_name == metric_name,
                SLOObjective.sli == metric_name,
                SLOEvaluation.invalidated == False,  # noqa: E712
                SLOEvaluation.result.is_not(None),
            )
            .order_by(SLOEvaluation.period_start.desc())
        )
        inner = inner.where(SLOEvaluation.period_start >= from_ts)
        if to_ts:
            inner = inner.where(SLOEvaluation.period_start <= to_ts)
        inner_sq = inner.subquery()
        # Secondary sort on evaluation_name so points sharing a period_start
        # arrive in a deterministic order — must match the heatmap column
        # tie-breaker so x-indices align across every chart.
        rows = await self._session.execute(
            select(inner_sq).order_by(inner_sq.c.period_start, inner_sq.c.evaluation_name)
        )
        return [
            {
                'timestamp': row.period_start.isoformat(),
                'value': row.value,
                # Percentage contribution: stacks to 100% when all indicators pass
                'score': round(row.score / row.total_weight * 100, 2) if row.total_weight else 0,
                'eval_id': str(row.slo_evaluation_id),
                'result': row.result,
                'baseline': row.compared_value,
                'evaluation_name': row.evaluation_name,
                'targets': row.targets,
                'change_point': _trend_change_point(
                    change_point_lookup,
                    slo_name,
                    metric_name,
                    row.period_start,
                    row.period_end,
                    row.evaluation_name,
                ),
            }
            for row in rows
        ]

    async def list_slo_evaluation_ids_for_trend(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        from_ts: datetime,
        to_ts: datetime | None = None,
    ) -> list[uuid.UUID]:
        """Return SLO-evaluation ids for a trend range, oldest first.

        Same filter set as ``get_trend_by_domain`` so the batched endpoint covers
        exactly the same evaluations as the single-metric endpoint.
        """
        query = (
            select(SLOEvaluation.id)
            .where(
                SLOEvaluation.asset_id == asset_id,
                SLOEvaluation.slo_name == slo_name,
                SLOEvaluation.invalidated == False,  # noqa: E712
                SLOEvaluation.result.is_not(None),
                SLOEvaluation.period_start >= from_ts,
            )
            .order_by(SLOEvaluation.period_start)
        )
        if to_ts:
            query = query.where(SLOEvaluation.period_start <= to_ts)
        result = await self._session.execute(query)
        return [row[0] for row in result.all()]

    async def get_trend_fragment_rows(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        slo_evaluation_ids: list[uuid.UUID],
    ) -> list[TrendColumnFragment]:
        """Build trend fragments for the given SLO-evaluations from the DB."""
        if not slo_evaluation_ids:
            return []
        total_weight_subquery = (
            select(func.coalesce(func.sum(SLOObjective.weight), 1))
            .join(IndicatorResultRow, IndicatorResultRow.slo_objective_id == SLOObjective.id)
            .where(IndicatorResultRow.slo_evaluation_id == SLOEvaluation.id)
            .correlate(SLOEvaluation)
            .scalar_subquery()
            .label('total_weight')
        )
        query = (
            select(
                SLOEvaluation.id.label('slo_evaluation_id'),
                SLOEvaluation.period_start,
                SLOEvaluation.period_end,
                SLOEvaluation.evaluation_name,
                SLIValue.value,
                SLIValue.metric_name,
                IndicatorResultRow.status.label('result'),
                IndicatorResultRow.compared_value,
                IndicatorResultRow.score,
                IndicatorResultRow.targets.label('targets'),
                total_weight_subquery,
            )
            .join(SLOEvaluation, SLIValue.slo_evaluation_id == SLOEvaluation.id)
            .join(IndicatorResultRow, IndicatorResultRow.slo_evaluation_id == SLOEvaluation.id)
            .join(SLOObjective, IndicatorResultRow.slo_objective_id == SLOObjective.id)
            .where(
                SLOEvaluation.asset_id == asset_id,
                SLOEvaluation.id.in_(slo_evaluation_ids),
                SLOObjective.sli == SLIValue.metric_name,
            )
            .order_by(SLOEvaluation.period_start, SLIValue.metric_name)
        )
        result = await self._session.execute(query)
        grouped: dict[uuid.UUID, dict[str, Any]] = {}
        for row in result.all():
            entry = grouped.setdefault(
                row.slo_evaluation_id,
                {
                    'slo_name': slo_name,
                    'period_start': row.period_start,
                    'period_end': row.period_end,
                    'evaluation_name': row.evaluation_name,
                    'total_weight': row.total_weight,
                    'rows': [],
                },
            )
            entry['rows'].append(
                TrendRow(
                    metric=row.metric_name,
                    value=row.value,
                    raw_score=row.score,
                    result=row.result,
                    compared_value=row.compared_value,
                    targets=row.targets,
                )
            )
        return [
            build_trend_fragment(
                slo_evaluation_id=slo_evaluation_id,
                slo_name=entry['slo_name'],
                period_start=entry['period_start'],
                period_end=entry['period_end'],
                evaluation_name=entry['evaluation_name'],
                total_weight=entry['total_weight'],
                rows=entry['rows'],
            )
            for slo_evaluation_id, entry in grouped.items()
        ]

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
                SLIValue.slo_evaluation_id,
                SLOEvaluation.result,
            )
            .join(SLOEvaluation, SLIValue.slo_evaluation_id == SLOEvaluation.id)
            .where(
                SLIValue.evaluation_name == evaluation_name,
                SLIValue.metric_name == metric_name,
                SLOEvaluation.invalidated == False,  # noqa: E712
            )
        )
        if asset_name:
            q = q.where(SLIValue.asset_name == asset_name)
        if from_:
            q = q.where(SLIValue.eval_start >= from_)
        if to:
            q = q.where(SLIValue.eval_start <= to)
        if result_filter:
            q = q.where(SLOEvaluation.result.in_(result_filter))
        q = q.order_by(SLIValue.eval_start)
        rows = await self._session.execute(q)
        return [
            {
                'timestamp': row.eval_start.isoformat(),
                'value': row.value,
                'eval_id': str(row.slo_evaluation_id),
                'result': row.result,
            }
            for row in rows
        ]
