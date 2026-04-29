"""Change point repository — CRUD, dedup, and config queries."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, cast

from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import (
    ChangePoint,
    ChangePointConfig,
    EvaluationRun,
    IndicatorResultRow,
    SLOEvaluation,
    SLOObjective,
)
from tropek.modules.change_points.detector import Direction


class ResolvedConfig(BaseModel):
    """Config for a single metric after merging DB override with defaults."""

    enabled: bool
    higher_is_better: bool
    window_size: int
    max_pvalue: float
    min_magnitude: float
    min_sample_size: int
    pvalue_strict_threshold: float
    pvalue_moderate_threshold: float


class ChangePointInsertParams(BaseModel):
    """Parameters for inserting a detected change point."""

    indicator_result_id: uuid.UUID | None
    evaluation_run_id: uuid.UUID | None
    asset_id: uuid.UUID
    slo_name: str
    metric_name: str
    period_start: datetime
    detector: str
    direction: Direction
    change_relative_pct: float
    change_absolute: float
    pvalue: float
    pre_segment_mean: float
    post_segment_mean: float
    post_segment_std: float


class ChangePointListParams(BaseModel):
    """Filter parameters for listing change points."""

    status: str | None = None
    direction: Direction | None = None
    asset_id: uuid.UUID | None = None
    slo_name: str | None = None
    metric_name: str | None = None
    from_ts: datetime | None = None
    to_ts: datetime | None = None
    limit: int = 50
    offset: int = 0


class ChangePointRepository:
    """Data access layer for change points and detection config."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def has_nearby_change_point(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        metric_name: str,
        period_start: datetime,
        nearby_timestamps: list[datetime],
        evaluation_name: str | None = None,
    ) -> bool:
        """Check if any change point exists nearby, regardless of direction.

        The nearby_timestamps list represents the ±2 ordinal evaluation positions
        around the candidate change point. A CP at a given position should only
        be recorded once — the first detection wins.
        """
        query = select(ChangePoint.id).where(
            ChangePoint.asset_id == asset_id,
            ChangePoint.slo_name == slo_name,
            ChangePoint.metric_name == metric_name,
            ChangePoint.period_start.in_(nearby_timestamps),
        )
        if evaluation_name is not None:
            query = query.join(
                IndicatorResultRow,
                ChangePoint.indicator_result_id == IndicatorResultRow.id,
            ).join(
                SLOEvaluation,
                IndicatorResultRow.slo_evaluation_id == SLOEvaluation.id,
            ).join(
                EvaluationRun,
                SLOEvaluation.evaluation_id == EvaluationRun.id,
            ).where(
                EvaluationRun.eval_name == evaluation_name,
            )
        query = query.limit(1)
        result = await self._session.execute(query)
        return result.scalar_one_or_none() is not None

    async def get_latest_change_point(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        metric_name: str,
        evaluation_name: str | None = None,
    ) -> ChangePoint | None:
        """Return the most recent change point for this metric, if any."""
        query = (
            select(ChangePoint)
            .where(
                ChangePoint.asset_id == asset_id,
                ChangePoint.slo_name == slo_name,
                ChangePoint.metric_name == metric_name,
            )
        )
        if evaluation_name is not None:
            query = query.join(
                IndicatorResultRow,
                ChangePoint.indicator_result_id == IndicatorResultRow.id,
            ).join(
                SLOEvaluation,
                IndicatorResultRow.slo_evaluation_id == SLOEvaluation.id,
            ).join(
                EvaluationRun,
                SLOEvaluation.evaluation_id == EvaluationRun.id,
            ).where(
                EvaluationRun.eval_name == evaluation_name,
            )
        query = query.order_by(ChangePoint.period_start.desc()).limit(1)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def insert_change_point(self, params: ChangePointInsertParams) -> ChangePoint:
        """Insert a new change point row."""
        change_point = ChangePoint(**params.model_dump())
        self._session.add(change_point)
        await self._session.flush()
        return change_point

    async def list_change_points(self, params: ChangePointListParams) -> list[ChangePoint]:
        """List change points with optional filters, newest first."""
        query = select(ChangePoint).order_by(ChangePoint.created_at.desc())
        if params.status:
            query = query.where(ChangePoint.status == params.status)
        if params.direction:
            query = query.where(ChangePoint.direction == params.direction)
        if params.asset_id:
            query = query.where(ChangePoint.asset_id == params.asset_id)
        if params.slo_name:
            query = query.where(ChangePoint.slo_name == params.slo_name)
        if params.metric_name:
            query = query.where(ChangePoint.metric_name == params.metric_name)
        if params.from_ts:
            query = query.where(ChangePoint.created_at >= params.from_ts)
        if params.to_ts:
            query = query.where(ChangePoint.created_at <= params.to_ts)
        query = query.limit(params.limit).offset(params.offset)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, change_point_id: uuid.UUID) -> ChangePoint | None:
        """Return a single change point by ID."""
        result = await self._session.execute(
            select(ChangePoint).where(ChangePoint.id == change_point_id)
        )
        return result.scalar_one_or_none()

    async def triage(
        self,
        change_point_id: uuid.UUID,
        *,
        status: str,
        triage_note: str | None = None,
        linked_ticket: str | None = None,
        triage_author: str | None = None,
    ) -> ChangePoint | None:
        """Update triage state of a change point."""
        await self._session.execute(
            update(ChangePoint)
            .where(ChangePoint.id == change_point_id)
            .values(
                status=status,
                triage_note=triage_note,
                linked_ticket=linked_ticket,
                triage_author=triage_author,
                triage_at=func.now(),
            )
        )
        await self._session.flush()
        return await self.get_by_id(change_point_id)

    async def bulk_triage(
        self,
        ids: list[uuid.UUID],
        *,
        status: str,
        triage_note: str | None = None,
        triage_author: str | None = None,
    ) -> int:
        """Bulk-update triage state. Returns number of rows affected."""
        cursor = cast(
            'CursorResult[Any]',
            await self._session.execute(
                update(ChangePoint)
                .where(ChangePoint.id.in_(ids))
                .values(
                    status=status,
                    triage_note=triage_note,
                    triage_author=triage_author,
                    triage_at=func.now(),
                )
            ),
        )
        await self._session.flush()
        return cursor.rowcount

    async def get_change_points_for_evaluations(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str | None = None,
        period_starts: list[datetime],
    ) -> dict[tuple[str, datetime, str], ChangePoint]:
        """Batch-load change points for a set of evaluation timestamps.

        Returns a dict keyed by (metric_name, period_start, eval_name) for O(1)
        lookup in the heatmap/trend presenters.
        """
        if not period_starts:
            return {}
        query = (
            select(ChangePoint, EvaluationRun.eval_name)
            .join(EvaluationRun, ChangePoint.evaluation_run_id == EvaluationRun.id)
            .where(
                ChangePoint.asset_id == asset_id,
                ChangePoint.period_start.in_(period_starts),
                ChangePoint.status != 'hidden',
            )
        )
        if slo_name is not None:
            query = query.where(ChangePoint.slo_name == slo_name)
        result = await self._session.execute(query)
        return {
            (row.ChangePoint.metric_name, row.ChangePoint.period_start, row.eval_name): row.ChangePoint
            for row in result.all()
        }

    async def get_change_points_for_range(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        metric_name: str,
        from_ts: datetime,
        to_ts: datetime | None = None,
    ) -> dict[tuple[str, datetime, str], ChangePoint]:
        """Load change points for a metric within a time range."""
        query = (
            select(ChangePoint, EvaluationRun.eval_name)
            .join(EvaluationRun, ChangePoint.evaluation_run_id == EvaluationRun.id)
            .where(
                ChangePoint.asset_id == asset_id,
                ChangePoint.slo_name == slo_name,
                ChangePoint.metric_name == metric_name,
                ChangePoint.period_start >= from_ts,
                ChangePoint.status != 'hidden',
            )
        )
        if to_ts is not None:
            query = query.where(ChangePoint.period_start <= to_ts)
        result = await self._session.execute(query)
        return {
            (row.ChangePoint.metric_name, row.ChangePoint.period_start, row.eval_name): row.ChangePoint
            for row in result.all()
        }

    @staticmethod
    def resolve_from_objective(
        objective: SLOObjective,
        system_defaults: dict[str, bool | int | float | str],
    ) -> ResolvedConfig:
        """Resolve config for an objective — per-objective override merged with system defaults.

        Per-objective config (from the SLO YAML change_point block) overrides detection
        thresholds. Algorithm tuning parameters (pvalue_strict_threshold, pvalue_moderate_threshold)
        always come from system defaults since they control the two-pass split/merge behavior
        rather than per-metric sensitivity.
        """
        pvalue_strict = float(system_defaults.get('pvalue_strict_threshold', 0.05))
        pvalue_moderate = float(system_defaults.get('pvalue_moderate_threshold', 0.5))

        config = objective.change_point_config
        if config is not None:
            return ResolvedConfig(
                enabled=config.enabled,
                higher_is_better=config.higher_is_better,
                window_size=config.window_size,
                max_pvalue=config.max_pvalue,
                min_magnitude=config.min_magnitude,
                min_sample_size=config.min_sample_size,
                pvalue_strict_threshold=pvalue_strict,
                pvalue_moderate_threshold=pvalue_moderate,
            )
        return ResolvedConfig(
            enabled=bool(system_defaults.get('enabled', True)),
            higher_is_better=bool(system_defaults.get('higher_is_better', False)),
            window_size=int(system_defaults.get('window_size', 30)),
            max_pvalue=float(system_defaults.get('max_pvalue', 0.001)),
            min_magnitude=float(system_defaults.get('min_magnitude', 0.0)),
            min_sample_size=int(system_defaults.get('min_sample_size', 10)),
            pvalue_strict_threshold=pvalue_strict,
            pvalue_moderate_threshold=pvalue_moderate,
        )

    async def upsert_config_for_objective(
        self,
        *,
        slo_objective_id: uuid.UUID,
        enabled: bool,
        higher_is_better: bool,
        window_size: int,
        max_pvalue: float,
        min_magnitude: float,
        min_sample_size: int,
    ) -> ChangePointConfig:
        """Create or update change point config for an objective."""
        query = select(ChangePointConfig).where(
            ChangePointConfig.slo_objective_id == slo_objective_id,
        )
        result = await self._session.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            existing.enabled = enabled
            existing.higher_is_better = higher_is_better
            existing.window_size = window_size
            existing.max_pvalue = max_pvalue
            existing.min_magnitude = min_magnitude
            existing.min_sample_size = min_sample_size
            await self._session.flush()
            return existing

        config = ChangePointConfig(
            slo_objective_id=slo_objective_id,
            enabled=enabled,
            higher_is_better=higher_is_better,
            window_size=window_size,
            max_pvalue=max_pvalue,
            min_magnitude=min_magnitude,
            min_sample_size=min_sample_size,
        )
        self._session.add(config)
        await self._session.flush()
        return config

    async def delete_config_for_objective(self, slo_objective_id: uuid.UUID) -> bool:
        """Delete change point config for an objective. Returns True if deleted."""
        cursor = cast(
            'CursorResult[Any]',
            await self._session.execute(
                delete(ChangePointConfig).where(
                    ChangePointConfig.slo_objective_id == slo_objective_id,
                )
            ),
        )
        await self._session.flush()
        return cursor.rowcount > 0

    async def get_config_for_objective(
        self, slo_objective_id: uuid.UUID,
    ) -> ChangePointConfig | None:
        """Return change point config for an objective, if any."""
        result = await self._session.execute(
            select(ChangePointConfig).where(
                ChangePointConfig.slo_objective_id == slo_objective_id,
            )
        )
        return result.scalar_one_or_none()
