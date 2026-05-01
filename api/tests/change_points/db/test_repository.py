"""Integration tests for ChangePointRepository — dedup, config, and query methods."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import (
    Asset,
    AssetType,
    ChangePoint,
    ChangePointConfig,
    SLODefinition,
    SLOObjective,
)
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


async def _create_objective(session: AsyncSession) -> SLOObjective:
    slo_def = SLODefinition(name=f'slo-{uuid.uuid4().hex[:8]}', version=1, active=True)
    session.add(slo_def)
    await session.flush()
    objective = SLOObjective(
        slo_definition_id=slo_def.id,
        sli='response_time_p95',
        sort_order=0,
    )
    session.add(objective)
    await session.flush()
    return objective


def _make_change_point(asset_id: uuid.UUID, **overrides: object) -> ChangePoint:
    defaults: dict[str, object] = {
        'asset_id': asset_id,
        'slo_name': 'perf-slo',
        'metric_name': 'response_time_p95',
        'period_start': _BASE,
        'direction': 'regression',
        'change_relative_pct': 15.0,
        'change_absolute': 30.0,
        'pvalue': 5.2,
        'pre_segment_mean': 200.0,
        'post_segment_mean': 230.0,
        'post_segment_std': 12.5,
    }
    defaults.update(overrides)
    return ChangePoint(**defaults)


@pytest.mark.integration
async def test_dedup_skips_nearby_change_point(db_session: AsyncSession) -> None:
    """A change point within ±2 ordinal positions should be deduped."""
    asset_id = await _create_asset(db_session)
    repo = ChangePointRepository(db_session)

    db_session.add(_make_change_point(asset_id, period_start=_BASE + timedelta(hours=2)))
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

    db_session.add(_make_change_point(asset_id))
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
async def test_dedup_respects_hidden_status(db_session: AsyncSession) -> None:
    """Hidden (triaged) change points still block dedup — no re-detection."""
    asset_id = await _create_asset(db_session)
    repo = ChangePointRepository(db_session)

    db_session.add(_make_change_point(
        asset_id,
        metric_name='latency',
        period_start=_BASE + timedelta(hours=5),
        status='hidden',
    ))
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
async def test_dedup_blocks_different_direction_at_same_position(
    db_session: AsyncSession,
) -> None:
    """An improvement near an existing regression IS deduped — first detection wins."""
    asset_id = await _create_asset(db_session)
    repo = ChangePointRepository(db_session)

    db_session.add(_make_change_point(
        asset_id,
        period_start=_BASE + timedelta(hours=2),
        direction='regression',
    ))
    await db_session.flush()

    nearby_timestamps = [_BASE + timedelta(hours=h) for h in [1, 2, 3, 4]]
    has_nearby = await repo.has_nearby_change_point(
        asset_id=asset_id,
        slo_name='perf-slo',
        metric_name='response_time_p95',
        period_start=_BASE + timedelta(hours=3),
        nearby_timestamps=nearby_timestamps,
    )
    assert has_nearby is True


@pytest.mark.integration
async def test_upsert_config_creates_new_row(db_session: AsyncSession) -> None:
    """Upserting config for an objective without existing config creates a row."""
    objective = await _create_objective(db_session)
    repo = ChangePointRepository(db_session)

    config = await repo.upsert_config_for_objective(
        slo_objective_id=objective.id,
        enabled=True,
        higher_is_better=False,
        window_size=50,
        max_pvalue=0.001,
        min_magnitude=0.0,
        min_sample_size=15,
    )

    assert config.slo_objective_id == objective.id
    assert config.enabled is True
    assert config.window_size == 50
    assert config.min_sample_size == 15


@pytest.mark.integration
async def test_upsert_config_updates_existing_row(db_session: AsyncSession) -> None:
    """Upserting config for an objective with existing config updates in place."""
    objective = await _create_objective(db_session)
    repo = ChangePointRepository(db_session)

    await repo.upsert_config_for_objective(
        slo_objective_id=objective.id,
        enabled=True,
        higher_is_better=False,
        window_size=30,
        max_pvalue=0.001,
        min_magnitude=0.0,
        min_sample_size=10,
    )

    updated = await repo.upsert_config_for_objective(
        slo_objective_id=objective.id,
        enabled=False,
        higher_is_better=True,
        window_size=60,
        max_pvalue=0.01,
        min_magnitude=0.05,
        min_sample_size=20,
    )

    assert updated.enabled is False
    assert updated.higher_is_better is True
    assert updated.window_size == 60
    assert updated.max_pvalue == 0.01
    assert updated.min_magnitude == 0.05
    assert updated.min_sample_size == 20


@pytest.mark.integration
async def test_get_config_for_objective_returns_none_when_absent(
    db_session: AsyncSession,
) -> None:
    """No config row → returns None (system defaults apply at query time)."""
    objective = await _create_objective(db_session)
    repo = ChangePointRepository(db_session)

    config = await repo.get_config_for_objective(objective.id)
    assert config is None


@pytest.mark.integration
async def test_get_config_for_objective_returns_row(db_session: AsyncSession) -> None:
    """Existing config row → returns the ChangePointConfig instance."""
    objective = await _create_objective(db_session)
    repo = ChangePointRepository(db_session)

    db_session.add(ChangePointConfig(
        slo_objective_id=objective.id,
        enabled=True,
        higher_is_better=False,
        window_size=40,
        max_pvalue=0.005,
        min_magnitude=0.01,
        min_sample_size=12,
    ))
    await db_session.flush()

    config = await repo.get_config_for_objective(objective.id)
    assert config is not None
    assert config.window_size == 40
    assert config.max_pvalue == 0.005


@pytest.mark.integration
async def test_delete_config_for_objective(db_session: AsyncSession) -> None:
    """Deleting config removes the row and returns True."""
    objective = await _create_objective(db_session)
    repo = ChangePointRepository(db_session)

    db_session.add(ChangePointConfig(
        slo_objective_id=objective.id,
        enabled=True,
        higher_is_better=False,
        window_size=30,
        max_pvalue=0.001,
        min_magnitude=0.0,
        min_sample_size=10,
    ))
    await db_session.flush()

    assert await repo.delete_config_for_objective(objective.id) is True
    assert await repo.get_config_for_objective(objective.id) is None


@pytest.mark.integration
async def test_delete_config_returns_false_when_absent(db_session: AsyncSession) -> None:
    """Deleting config for an objective without config returns False."""
    objective = await _create_objective(db_session)
    repo = ChangePointRepository(db_session)

    assert await repo.delete_config_for_objective(objective.id) is False


@pytest.mark.integration
async def test_resolve_from_objective_uses_config(db_session: AsyncSession) -> None:
    """resolve_from_objective returns per-objective config when present."""
    objective = await _create_objective(db_session)

    db_session.add(ChangePointConfig(
        slo_objective_id=objective.id,
        enabled=True,
        higher_is_better=True,
        window_size=60,
        max_pvalue=0.01,
        min_magnitude=0.05,
        min_sample_size=20,
    ))
    await db_session.flush()
    await db_session.refresh(objective)

    system_defaults: dict[str, bool | int | float | str] = {
        'enabled': True,
        'higher_is_better': False,
        'window_size': 30,
        'max_pvalue': 0.001,
        'min_magnitude': 0.0,
        'min_sample_size': 10,
    }

    resolved = ChangePointRepository.resolve_from_objective(objective, system_defaults)
    assert resolved.higher_is_better is True
    assert resolved.window_size == 60
    assert resolved.max_pvalue == 0.01
    assert resolved.min_magnitude == 0.05
    assert resolved.min_sample_size == 20


@pytest.mark.integration
async def test_resolve_from_objective_falls_back_to_defaults(
    db_session: AsyncSession,
) -> None:
    """resolve_from_objective falls back to system defaults when no config row."""
    objective = await _create_objective(db_session)
    await db_session.refresh(objective)

    system_defaults: dict[str, bool | int | float | str] = {
        'enabled': True,
        'higher_is_better': False,
        'window_size': 30,
        'max_pvalue': 0.001,
        'min_magnitude': 0.0,
        'min_sample_size': 10,
    }

    resolved = ChangePointRepository.resolve_from_objective(objective, system_defaults)
    assert resolved.enabled is True
    assert resolved.higher_is_better is False
    assert resolved.window_size == 30
    assert resolved.max_pvalue == 0.001
    assert resolved.min_magnitude == 0.0
    assert resolved.min_sample_size == 10
