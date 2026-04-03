"""Trend repository — DB access for trend queries and metric heatmaps."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import EvaluationRun, IndicatorResultRow, SLIValue, SLOEvaluation, SLOObjective
from app.modules.quality_gate.engine.constants import EvaluationStatus


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
    ) -> list[EvaluationRun]:
        """Fetch completed EvaluationRun rows with all child SLO evaluations and indicator results.

        Returns rows ordered period_start DESC (caller reverses to oldest-first for display).
        When no date range is provided, falls back to the most recent 100 runs as a safety cap.
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
        if not from_ts and not to_ts:
            q = q.limit(100)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def get_trend_by_domain(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        metric_name: str,
        from_ts: datetime,
        to_ts: datetime | None = None,
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
                SLIValue.value,
                SLIValue.slo_evaluation_id,
                IndicatorResultRow.status.label('result'),
                IndicatorResultRow.compared_value,
                IndicatorResultRow.score,
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
        inner = inner.subquery()
        rows = await self._session.execute(select(inner).order_by(inner.c.period_start))
        return [
            {
                'timestamp': r.period_start.isoformat(),
                'value': r.value,
                # Percentage contribution: stacks to 100% when all indicators pass
                'score': round(r.score / r.total_weight * 100, 2) if r.total_weight else 0,
                'eval_id': str(r.slo_evaluation_id),
                'result': r.result,
                'baseline': r.compared_value,
            }
            for r in rows
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
                'timestamp': r.eval_start.isoformat(),
                'value': r.value,
                'eval_id': str(r.slo_evaluation_id),
                'result': r.result,
            }
            for r in rows
        ]
