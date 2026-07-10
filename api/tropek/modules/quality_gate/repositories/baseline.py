"""Baseline repository — DB access for baseline queries."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tropek.cache.redis_cache import RedisCache
from tropek.db.models import IndicatorResultRow, SLOEvaluation
from tropek.modules.quality_gate.evaluation_engine.constants import EvaluationStatus


class BaselineRepository:
    """Data access layer for baseline queries."""

    def __init__(self, session: AsyncSession, cache: RedisCache | None = None) -> None:
        self._session = session
        self._cache = cache

    async def get_active_pin(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
    ) -> tuple[datetime, uuid.UUID] | None:
        """Return (period_start, evaluation_id) of the active baseline pin, or None."""
        q = select(SLOEvaluation.period_start, SLOEvaluation.id).where(
            SLOEvaluation.asset_id == asset_id,
            SLOEvaluation.slo_name == slo_name,
            SLOEvaluation.baseline_pinned_at.is_not(None),
            SLOEvaluation.baseline_unpinned_at.is_(None),
        )
        row = await self._session.execute(q)
        result = row.one_or_none()
        if result is None:
            return None
        return result.period_start, result.id

    async def get_evaluation_baselines(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        period_start_before: datetime,
        include_result_with_score: str,
        limit: int,
        evaluation_name: str | None = None,
    ) -> list[SLOEvaluation]:
        """Fetch previous completed evaluations for baseline comparison during scoring.

        Used by the worker when evaluating a new run against previous results.
        Pin-aware: restricts the baseline window to evaluations after the active pin.

        Args:
            asset_id: Asset UUID to scope baselines to.
            slo_name: SLO name to scope baselines to.
            period_start_before: Only include evaluations before this timestamp.
            include_result_with_score: "pass", "pass_or_warn", or "all".
            limit: Maximum number of baseline evaluations to return.
            evaluation_name: Optional evaluation series name to restrict baselines to.

        Returns:
            Matching completed evaluations ordered by period_start descending.
        """
        q = self._base_baseline_query(
            asset_id=asset_id,
            slo_name=slo_name,
            period_start_before=period_start_before,
            include_result_with_score=include_result_with_score,
            evaluation_name=evaluation_name,
        )
        q = q.options(
            selectinload(SLOEvaluation.indicator_rows).joinedload(IndicatorResultRow.objective),
        )
        q = self._apply_pin_filter(q, asset_id=asset_id, slo_name=slo_name)
        q = q.order_by(SLOEvaluation.period_start.desc()).limit(limit)
        rows = await self._session.execute(q)
        return list(rows.scalars().all())

    async def get_reeval_baselines(  # noqa: PLR0913
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
        skip_pin_filter: bool = False,
        evaluation_name: str | None = None,
    ) -> list[SLOEvaluation]:
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
            skip_pin_filter: When True, skip baseline pin filtering for this query.
            evaluation_name: Optional evaluation series name to restrict baselines to.

        Returns:
            Matching completed evaluations ordered by period_start descending.
        """
        q = self._base_baseline_query(
            asset_id=asset_id,
            slo_name=slo_name,
            period_start_before=period_start_before,
            include_result_with_score=include_result_with_score,
            evaluation_name=evaluation_name,
        )
        q = q.options(
            selectinload(SLOEvaluation.indicator_rows).joinedload(IndicatorResultRow.objective),
        )

        if sli_version_range:
            q = q.where(SLOEvaluation.sli_version.is_not(None))
            q = q.where(SLOEvaluation.sli_version >= sli_version_range[0])
            q = q.where(SLOEvaluation.sli_version <= sli_version_range[1])

        if restrict_to_ids is not None:
            q = q.where(SLOEvaluation.id.in_(restrict_to_ids))

        if tag_filters:
            for key, value in tag_filters.items():
                q = q.where(SLOEvaluation.variables[key].astext == value)

        if not skip_pin_filter:
            q = self._apply_pin_filter(q, asset_id=asset_id, slo_name=slo_name)
        q = q.order_by(SLOEvaluation.period_start.desc()).limit(limit)
        rows = await self._session.execute(q)
        return list(rows.scalars().all())

    @staticmethod
    def _base_baseline_query(
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        period_start_before: datetime,
        include_result_with_score: str,
        evaluation_name: str | None = None,
    ) -> Any:
        """Build the shared base query for baseline lookups."""
        q = select(SLOEvaluation).where(
            SLOEvaluation.asset_id == asset_id,
            SLOEvaluation.slo_name == slo_name,
            SLOEvaluation.period_start < period_start_before,
            SLOEvaluation.status == EvaluationStatus.COMPLETED,
            SLOEvaluation.invalidated == False,  # noqa: E712
        )
        if evaluation_name is not None:
            q = q.where(SLOEvaluation.evaluation_name == evaluation_name)
        if include_result_with_score == 'pass':
            q = q.where(SLOEvaluation.result == 'pass')
        elif include_result_with_score == 'pass_or_warn':
            q = q.where(SLOEvaluation.result.in_(['pass', 'warning']))
        return q

    def _apply_pin_filter(
        self,
        q: Any,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
    ) -> Any:
        """Restrict baseline window to evaluations at/after the active pin, if any.

        Folded into the main query as a scalar subquery (not a separate SELECT), so a
        baseline fetch is a single round-trip. When no active pin exists the subquery is
        NULL and the OR keeps every row (no restriction).
        """
        active_pin_start = (
            select(func.max(SLOEvaluation.period_start))
            .where(
                SLOEvaluation.asset_id == asset_id,
                SLOEvaluation.slo_name == slo_name,
                SLOEvaluation.baseline_pinned_at.is_not(None),
                SLOEvaluation.baseline_unpinned_at.is_(None),
            )
            .scalar_subquery()
        )
        return q.where(
            or_(
                active_pin_start.is_(None),
                SLOEvaluation.period_start >= active_pin_start,
            )
        )

    async def load_evaluations_for_reeval(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        from_date: datetime,
        evaluation_name: str | None = None,
    ) -> list[SLOEvaluation]:
        """Load completed, non-invalidated evaluations for re-evaluation.

        Returns evaluations in chronological order (period_start ASC)
        for cascading baseline resolution.

        Args:
            asset_id: Asset UUID to scope results to.
            slo_name: SLO name to scope results to.
            from_date: Only include evaluations at or after this timestamp.
            evaluation_name: Optional evaluation series name to scope results to.

        Returns:
            Matching completed evaluations ordered by period_start ascending.
        """
        q = (
            select(SLOEvaluation)
            .where(
                SLOEvaluation.asset_id == asset_id,
                SLOEvaluation.slo_name == slo_name,
                SLOEvaluation.period_start >= from_date,
                SLOEvaluation.status == EvaluationStatus.COMPLETED,
                SLOEvaluation.invalidated == False,  # noqa: E712
            )
            .options(
                selectinload(SLOEvaluation.indicator_rows).joinedload(IndicatorResultRow.objective),
            )
            .order_by(SLOEvaluation.period_start)
        )
        if evaluation_name is not None:
            q = q.where(SLOEvaluation.evaluation_name == evaluation_name)
        rows = await self._session.execute(q)
        return list(rows.scalars().all())
