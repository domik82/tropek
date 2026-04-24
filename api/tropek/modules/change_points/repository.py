"""Change point repository — CRUD, dedup, and config queries."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, cast

from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import ChangePoint, ChangePointConfig
from tropek.modules.change_points.detector import (
    DEFAULT_ENABLED,
    DEFAULT_MAX_PVALUE,
    DEFAULT_MIN_MAGNITUDE,
    DEFAULT_MIN_SAMPLE_SIZE,
    DEFAULT_WINDOW_SIZE,
)


class ResolvedConfig(BaseModel):
    """Config for a single metric after merging DB override with defaults."""

    enabled: bool
    window_size: int
    max_pvalue: float
    min_magnitude: float
    min_sample_size: int


def _default_resolved_config() -> ResolvedConfig:
    return ResolvedConfig(
        enabled=DEFAULT_ENABLED,
        window_size=DEFAULT_WINDOW_SIZE,
        max_pvalue=DEFAULT_MAX_PVALUE,
        min_magnitude=DEFAULT_MIN_MAGNITUDE,
        min_sample_size=DEFAULT_MIN_SAMPLE_SIZE,
    )


def _resolve_from_row(row: ChangePointConfig) -> ResolvedConfig:
    return ResolvedConfig(
        enabled=row.enabled,
        window_size=row.window_size,
        max_pvalue=row.max_pvalue,
        min_magnitude=row.min_magnitude,
        min_sample_size=row.min_sample_size,
    )


class ChangePointRepository:
    """Data access layer for change points and detection config."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_configs_for_slo(self, slo_name: str) -> dict[str, ChangePointConfig]:
        """Return all change point configs for an SLO, keyed by metric_name."""
        query = select(ChangePointConfig).where(ChangePointConfig.slo_name == slo_name)
        result = await self._session.execute(query)
        return {config.metric_name: config for config in result.scalars().all()}

    async def delete_config(
        self,
        *,
        slo_name: str,
        metric_name: str,
    ) -> bool:
        """Delete an override row. Returns True if a row was deleted."""
        cursor = cast(
            'CursorResult[Any]',
            await self._session.execute(
                delete(ChangePointConfig).where(
                    ChangePointConfig.slo_name == slo_name,
                    ChangePointConfig.metric_name == metric_name,
                )
            ),
        )
        await self._session.flush()
        return cursor.rowcount > 0

    async def upsert_config(
        self,
        *,
        slo_name: str,
        metric_name: str,
        enabled: bool = DEFAULT_ENABLED,
        window_size: int = DEFAULT_WINDOW_SIZE,
        max_pvalue: float = DEFAULT_MAX_PVALUE,
        min_magnitude: float = DEFAULT_MIN_MAGNITUDE,
        min_sample_size: int = DEFAULT_MIN_SAMPLE_SIZE,
    ) -> ChangePointConfig:
        """Create or update detection config for a specific SLO+metric."""
        query = select(ChangePointConfig).where(
            ChangePointConfig.slo_name == slo_name,
            ChangePointConfig.metric_name == metric_name,
        )
        result = await self._session.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            existing.enabled = enabled
            existing.window_size = window_size
            existing.max_pvalue = max_pvalue
            existing.min_magnitude = min_magnitude
            existing.min_sample_size = min_sample_size
            await self._session.flush()
            return existing

        config = ChangePointConfig(
            slo_name=slo_name,
            metric_name=metric_name,
            enabled=enabled,
            window_size=window_size,
            max_pvalue=max_pvalue,
            min_magnitude=min_magnitude,
            min_sample_size=min_sample_size,
        )
        self._session.add(config)
        await self._session.flush()
        return config

    async def has_nearby_change_point(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        metric_name: str,
        period_start: datetime,
        nearby_timestamps: list[datetime],
    ) -> bool:
        """Check if a change point exists for this metric within the nearby window.

        The nearby_timestamps list represents the ±2 ordinal evaluation positions
        around the candidate change point. If any existing change point (any status)
        falls on one of these timestamps, return True to skip insertion.
        """
        query = select(ChangePoint.id).where(
            ChangePoint.asset_id == asset_id,
            ChangePoint.slo_name == slo_name,
            ChangePoint.metric_name == metric_name,
            ChangePoint.period_start.in_(nearby_timestamps),
        ).limit(1)
        result = await self._session.execute(query)
        return result.scalar_one_or_none() is not None

    async def insert_change_point(
        self,
        *,
        indicator_result_id: uuid.UUID | None,
        asset_id: uuid.UUID,
        slo_name: str,
        metric_name: str,
        period_start: datetime,
        detector: str,
        direction: str,
        change_relative_pct: float,
        change_absolute: float,
        t_statistic: float,
        pre_segment_mean: float,
        post_segment_mean: float,
    ) -> ChangePoint:
        """Insert a new change point row."""
        change_point = ChangePoint(
            indicator_result_id=indicator_result_id,
            asset_id=asset_id,
            slo_name=slo_name,
            metric_name=metric_name,
            period_start=period_start,
            detector=detector,
            direction=direction,
            change_relative_pct=change_relative_pct,
            change_absolute=change_absolute,
            t_statistic=t_statistic,
            pre_segment_mean=pre_segment_mean,
            post_segment_mean=post_segment_mean,
        )
        self._session.add(change_point)
        await self._session.flush()
        return change_point

    async def list_change_points(
        self,
        *,
        status: str | None = None,
        direction: str | None = None,
        asset_id: uuid.UUID | None = None,
        slo_name: str | None = None,
        metric_name: str | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ChangePoint]:
        """List change points with optional filters, newest first."""
        query = select(ChangePoint).order_by(ChangePoint.created_at.desc())
        if status:
            query = query.where(ChangePoint.status == status)
        if direction:
            query = query.where(ChangePoint.direction == direction)
        if asset_id:
            query = query.where(ChangePoint.asset_id == asset_id)
        if slo_name:
            query = query.where(ChangePoint.slo_name == slo_name)
        if metric_name:
            query = query.where(ChangePoint.metric_name == metric_name)
        if from_ts:
            query = query.where(ChangePoint.created_at >= from_ts)
        if to_ts:
            query = query.where(ChangePoint.created_at <= to_ts)
        query = query.limit(limit).offset(offset)
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
    ) -> dict[tuple[str, datetime], ChangePoint]:
        """Batch-load change points for a set of evaluation timestamps.

        Returns a dict keyed by (metric_name, period_start) for O(1) lookup
        in the heatmap/trend presenters.
        """
        if not period_starts:
            return {}
        query = select(ChangePoint).where(
            ChangePoint.asset_id == asset_id,
            ChangePoint.period_start.in_(period_starts),
            ChangePoint.status != 'hidden',
        )
        if slo_name is not None:
            query = query.where(ChangePoint.slo_name == slo_name)
        result = await self._session.execute(query)
        return {
            (change_point.metric_name, change_point.period_start): change_point
            for change_point in result.scalars().all()
        }

    async def get_change_points_for_range(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
        metric_name: str,
        from_ts: datetime,
        to_ts: datetime | None = None,
    ) -> dict[tuple[str, datetime], ChangePoint]:
        """Load change points for a metric within a time range."""
        query = select(ChangePoint).where(
            ChangePoint.asset_id == asset_id,
            ChangePoint.slo_name == slo_name,
            ChangePoint.metric_name == metric_name,
            ChangePoint.period_start >= from_ts,
            ChangePoint.status != 'hidden',
        )
        if to_ts is not None:
            query = query.where(ChangePoint.period_start <= to_ts)
        result = await self._session.execute(query)
        return {
            (change_point.metric_name, change_point.period_start): change_point
            for change_point in result.scalars().all()
        }

    async def resolve_config(
        self,
        *,
        slo_name: str,
        metric_name: str,
    ) -> ResolvedConfig:
        """Return the effective config for a metric.

        Looks up an override row in change_point_config. If absent, returns
        the hardcoded defaults — detection is enabled everywhere by default.
        """
        query = select(ChangePointConfig).where(
            ChangePointConfig.slo_name == slo_name,
            ChangePointConfig.metric_name == metric_name,
        )
        result = await self._session.execute(query)
        row = result.scalar_one_or_none()
        if row is None:
            return _default_resolved_config()
        return _resolve_from_row(row)

    async def resolve_configs_for_metrics(
        self,
        *,
        slo_name: str,
        metric_names: list[str],
    ) -> dict[str, ResolvedConfig]:
        """Batch-resolve configs for a list of metrics in one query."""
        if not metric_names:
            return {}
        query = select(ChangePointConfig).where(
            ChangePointConfig.slo_name == slo_name,
            ChangePointConfig.metric_name.in_(metric_names),
        )
        result = await self._session.execute(query)
        overrides = {row.metric_name: row for row in result.scalars().all()}

        resolved: dict[str, ResolvedConfig] = {}
        for metric_name in metric_names:
            row = overrides.get(metric_name)
            if row is None:
                resolved[metric_name] = _default_resolved_config()
            else:
                resolved[metric_name] = _resolve_from_row(row)
        return resolved
