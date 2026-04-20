"""Integration tests for ChangePointRepository — dedup and config queries."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import Asset, AssetType, ChangePoint, ChangePointConfig
from tropek.modules.change_points.repository import ChangePointRepository

_BASE = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)


async def _create_asset(session: AsyncSession) -> uuid.UUID:
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(Asset(id=asset_id, name='cp-test-asset', type_name=type_name))
    await session.flush()
    return asset_id


@pytest.mark.integration
async def test_dedup_skips_nearby_change_point(db_session: AsyncSession) -> None:
    """A change point within ±2 ordinal positions should be deduped."""
    asset_id = await _create_asset(db_session)
    repo = ChangePointRepository(db_session)

    existing = ChangePoint(
        asset_id=asset_id,
        slo_name='perf-slo',
        metric_name='response_time_p95',
        period_start=_BASE + timedelta(hours=2),
        direction='regression',
        change_relative_pct=15.0,
        change_absolute=30.0,
        t_statistic=5.2,
        pre_segment_mean=200.0,
        post_segment_mean=230.0,
    )
    db_session.add(existing)
    await db_session.flush()

    nearby_timestamps = [_BASE + timedelta(hours=h) for h in [1, 2, 3, 4]]
    for timestamp in nearby_timestamps:
        has_nearby = await repo.has_nearby_change_point(
            asset_id=asset_id,
            slo_name='perf-slo',
            metric_name='response_time_p95',
            period_start=timestamp,
            nearby_timestamps=nearby_timestamps,
        )
        assert has_nearby is True


@pytest.mark.integration
async def test_dedup_allows_distant_change_point(db_session: AsyncSession) -> None:
    """A change point far from existing ones should not be deduped."""
    asset_id = await _create_asset(db_session)
    repo = ChangePointRepository(db_session)

    existing = ChangePoint(
        asset_id=asset_id,
        slo_name='perf-slo',
        metric_name='response_time_p95',
        period_start=_BASE,
        direction='regression',
        change_relative_pct=15.0,
        change_absolute=30.0,
        t_statistic=5.2,
        pre_segment_mean=200.0,
        post_segment_mean=230.0,
    )
    db_session.add(existing)
    await db_session.flush()

    distant_timestamps = [_BASE + timedelta(hours=h) for h in [10, 11, 12, 13, 14]]
    has_nearby = await repo.has_nearby_change_point(
        asset_id=asset_id,
        slo_name='perf-slo',
        metric_name='response_time_p95',
        period_start=_BASE + timedelta(hours=12),
        nearby_timestamps=distant_timestamps,
    )
    assert has_nearby is False


@pytest.mark.integration
async def test_get_configs_for_slo(db_session: AsyncSession) -> None:
    """Fetching configs returns a dict keyed by metric name."""
    repo = ChangePointRepository(db_session)

    db_session.add(ChangePointConfig(
        slo_name='perf-slo',
        metric_name='response_time_p95',
        enabled=True,
        window_size=50,
        min_sample_size=15,
    ))
    db_session.add(ChangePointConfig(
        slo_name='perf-slo',
        metric_name='error_rate',
        enabled=False,
    ))
    await db_session.flush()

    configs = await repo.get_configs_for_slo('perf-slo')
    assert 'response_time_p95' in configs
    assert configs['response_time_p95'].enabled is True
    assert configs['response_time_p95'].window_size == 50
    assert 'error_rate' in configs
    assert configs['error_rate'].enabled is False


@pytest.mark.integration
async def test_dedup_respects_hidden_status(db_session: AsyncSession) -> None:
    """Hidden (triaged) change points still block dedup — no re-detection."""
    asset_id = await _create_asset(db_session)
    repo = ChangePointRepository(db_session)

    existing = ChangePoint(
        asset_id=asset_id,
        slo_name='perf-slo',
        metric_name='latency',
        period_start=_BASE + timedelta(hours=5),
        direction='regression',
        change_relative_pct=10.0,
        change_absolute=20.0,
        t_statistic=3.1,
        pre_segment_mean=100.0,
        post_segment_mean=120.0,
        status='hidden',
    )
    db_session.add(existing)
    await db_session.flush()

    nearby_timestamps = [_BASE + timedelta(hours=h) for h in [4, 5, 6]]
    has_nearby = await repo.has_nearby_change_point(
        asset_id=asset_id,
        slo_name='perf-slo',
        metric_name='latency',
        period_start=_BASE + timedelta(hours=5),
        nearby_timestamps=nearby_timestamps,
    )
    assert has_nearby is True


@pytest.mark.integration
async def test_resolve_config_uses_defaults_when_no_row(db_session: AsyncSession) -> None:
    """No override row → detection enabled with default params."""
    repo = ChangePointRepository(db_session)

    resolved = await repo.resolve_config(slo_name='perf-slo', metric_name='latency_p95')

    assert resolved.enabled is True
    assert resolved.window_size == 30
    assert resolved.max_pvalue == 0.001
    assert resolved.min_magnitude == 0.0
    assert resolved.min_sample_size == 10


@pytest.mark.integration
async def test_resolve_config_honors_disable_override(db_session: AsyncSession) -> None:
    """Row with enabled=False disables detection for that metric."""
    repo = ChangePointRepository(db_session)

    db_session.add(ChangePointConfig(
        slo_name='perf-slo',
        metric_name='noisy_metric',
        enabled=False,
    ))
    await db_session.flush()

    resolved = await repo.resolve_config(slo_name='perf-slo', metric_name='noisy_metric')
    assert resolved.enabled is False


@pytest.mark.integration
async def test_resolve_config_honors_all_otava_overrides(db_session: AsyncSession) -> None:
    """All three Otava params plus the wrapper guard can be overridden per-metric."""
    repo = ChangePointRepository(db_session)

    db_session.add(ChangePointConfig(
        slo_name='perf-slo',
        metric_name='slow_drift',
        enabled=True,
        window_size=60,
        max_pvalue=0.0001,
        min_magnitude=0.05,
        min_sample_size=20,
    ))
    await db_session.flush()

    resolved = await repo.resolve_config(slo_name='perf-slo', metric_name='slow_drift')
    assert resolved.enabled is True
    assert resolved.window_size == 60
    assert resolved.max_pvalue == 0.0001
    assert resolved.min_magnitude == 0.05
    assert resolved.min_sample_size == 20
