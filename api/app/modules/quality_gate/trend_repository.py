"""Trend repository — DB access for trend queries and metric heatmaps."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Evaluation, IndicatorResultRow, SLIValue, SLOObjective
from app.modules.quality_gate.engine.constants import EvaluationStatus


class TrendRepository:
    """Data access layer for trend queries and metric heatmaps."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_metric_heatmap(
        self,
        *,
        asset_id: uuid.UUID,
        limit: int = 500,
        evaluation_name: list[str] | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ) -> list[Evaluation]:
        """Fetch the last N completed evaluations for an asset, ordered by period_start DESC."""
        q = (
            select(Evaluation)
            .options(
                selectinload(Evaluation.indicator_rows).joinedload(IndicatorResultRow.objective),
            )
            .where(
                Evaluation.asset_id == asset_id,
                Evaluation.status == EvaluationStatus.COMPLETED,
            )
            .order_by(Evaluation.period_start.desc())
            .limit(limit)
        )
        if evaluation_name:
            q = q.where(Evaluation.evaluation_name.in_(evaluation_name))
        if from_ts:
            q = q.where(Evaluation.period_start >= from_ts)
        if to_ts:
            q = q.where(Evaluation.period_start <= to_ts)
        result = await self._session.execute(q)
        return list(result.scalars().all())

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
        Baseline from IndicatorResultRow.compared_value via JOIN.
        Excludes invalidated evaluations and those with asset_id=NULL.
        """
        inner = (
            select(
                Evaluation.period_start,
                SLIValue.value,
                SLIValue.eval_id,
                Evaluation.result,
                IndicatorResultRow.compared_value,
            )
            .join(Evaluation, SLIValue.eval_id == Evaluation.id)
            .join(
                IndicatorResultRow,
                IndicatorResultRow.evaluation_id == Evaluation.id,
            )
            .join(
                SLOObjective,
                IndicatorResultRow.slo_objective_id == SLOObjective.id,
            )
            .where(
                Evaluation.asset_id == asset_id,
                Evaluation.slo_name == slo_name,
                SLIValue.metric_name == metric_name,
                SLOObjective.sli == metric_name,
                Evaluation.invalidated == False,  # noqa: E712
                Evaluation.result.is_not(None),
            )
            .order_by(Evaluation.period_start.desc())
            .limit(limit)
            .subquery()
        )
        rows = await self._session.execute(select(inner).order_by(inner.c.period_start))
        return [
            {
                "timestamp": r.period_start.isoformat(),
                "value": r.value,
                "eval_id": str(r.eval_id),
                "result": r.result,
                "baseline": r.compared_value,
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
