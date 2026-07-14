"""Trend repository — DB access for per-metric and per-SLO trend queries."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import (
    IndicatorResultRow,
    SLIValue,
    SLOEvaluation,
    SLOObjective,
)
from tropek.modules.change_points.repository import ChangePointKey
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
    """Data access layer for per-metric and per-SLO trend queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
        total_weight_subquery = (
            select(func.coalesce(func.sum(SLOObjective.weight), 1))
            .join(IndicatorResultRow, IndicatorResultRow.slo_objective_id == SLOObjective.id)
            .where(IndicatorResultRow.slo_evaluation_id == SLOEvaluation.id)
            .correlate(SLOEvaluation)
            .scalar_subquery()
            .label('total_weight')
        )

        base_query = (
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
                total_weight_subquery,
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
        base_query = base_query.where(SLOEvaluation.period_start >= from_ts)
        if to_ts:
            base_query = base_query.where(SLOEvaluation.period_start <= to_ts)
        windowed_subquery = base_query.subquery()
        # Secondary sort on evaluation_name so points sharing a period_start
        # arrive in a deterministic order — must match the heatmap column
        # tie-breaker so x-indices align across every chart.
        rows = await self._session.execute(
            select(windowed_subquery).order_by(windowed_subquery.c.period_start, windowed_subquery.c.evaluation_name)
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
        # Total objective weight per SLO-evaluation, computed once via a grouped
        # aggregate rather than a per-row correlated subquery. The correlated form
        # re-executed for every (indicator x run) row returned by the main query
        # (~metrics x runs per SLO) and dominated query time at scale — a single
        # SLO's batched fetch hit multiple seconds. Summing the weight of every
        # objective that produced an indicator result for the evaluation (whether
        # or not each metric has an SLI value) keeps the normalized-score
        # denominator byte-for-byte identical to ``get_trend_by_domain``.
        total_weight_query = (
            select(
                IndicatorResultRow.slo_evaluation_id.label('slo_evaluation_id'),
                func.coalesce(func.sum(SLOObjective.weight), 1).label('total_weight'),
            )
            .join(SLOObjective, IndicatorResultRow.slo_objective_id == SLOObjective.id)
            .where(IndicatorResultRow.slo_evaluation_id.in_(slo_evaluation_ids))
            .group_by(IndicatorResultRow.slo_evaluation_id)
        )
        total_weight_result = await self._session.execute(total_weight_query)
        total_weight_by_evaluation: dict[uuid.UUID, float] = {
            row.slo_evaluation_id: row.total_weight for row in total_weight_result.all()
        }

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
                    'total_weight': total_weight_by_evaluation.get(row.slo_evaluation_id, 1),
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
        query = (
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
            query = query.where(SLIValue.asset_name == asset_name)
        if from_:
            query = query.where(SLIValue.eval_start >= from_)
        if to:
            query = query.where(SLIValue.eval_start <= to)
        if result_filter:
            query = query.where(SLOEvaluation.result.in_(result_filter))
        query = query.order_by(SLIValue.eval_start)
        rows = await self._session.execute(query)
        return [
            {
                'timestamp': row.eval_start.isoformat(),
                'value': row.value,
                'eval_id': str(row.slo_evaluation_id),
                'result': row.result,
            }
            for row in rows
        ]
