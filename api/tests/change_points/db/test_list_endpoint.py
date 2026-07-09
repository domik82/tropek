"""Integration tests for GET /change-points — one per filter query param, end-to-end.

These assert the router actually wires each query param through to the repository.
The bug they guard against: a query param declared under a name no consumer sends
(or a name FastAPI does not recognize) is silently ignored, returning unfiltered rows.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import ChangePoint

pytestmark = pytest.mark.integration

_BASE = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)


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


async def test_filter_by_metric_name(api_client: AsyncClient, db_session: AsyncSession) -> None:
    """?metric_name=X returns only change points for metric X."""
    asset_id = uuid.uuid4()
    db_session.add_all(
        [
            _make_change_point(asset_id, metric_name='errors_zero_origin_appear'),
            _make_change_point(asset_id, metric_name='response_time_p95'),
        ]
    )
    await db_session.flush()

    response = await api_client.get('/change-points', params={'metric_name': 'errors_zero_origin_appear'})

    assert response.status_code == 200
    metrics = {row['metric_name'] for row in response.json()}
    assert metrics == {'errors_zero_origin_appear'}


async def test_filter_by_slo_name(api_client: AsyncClient, db_session: AsyncSession) -> None:
    """?slo_name=X returns only change points for SLO X."""
    asset_id = uuid.uuid4()
    db_session.add_all(
        [
            _make_change_point(asset_id, slo_name='latency-slo'),
            _make_change_point(asset_id, slo_name='throughput-slo'),
        ]
    )
    await db_session.flush()

    response = await api_client.get('/change-points', params={'slo_name': 'latency-slo'})

    assert response.status_code == 200
    slo_names = {row['slo_name'] for row in response.json()}
    assert slo_names == {'latency-slo'}


async def test_filter_by_status(api_client: AsyncClient, db_session: AsyncSession) -> None:
    """?status=X returns only change points with triage status X."""
    asset_id = uuid.uuid4()
    db_session.add_all(
        [
            _make_change_point(asset_id, metric_name='m-unprocessed', status='unprocessed'),
            _make_change_point(asset_id, metric_name='m-acknowledged', status='acknowledged'),
        ]
    )
    await db_session.flush()

    response = await api_client.get('/change-points', params={'status': 'acknowledged'})

    assert response.status_code == 200
    statuses = {row['status'] for row in response.json()}
    assert statuses == {'acknowledged'}


async def test_filter_by_direction(api_client: AsyncClient, db_session: AsyncSession) -> None:
    """?direction=X returns only change points in direction X."""
    asset_id = uuid.uuid4()
    db_session.add_all(
        [
            _make_change_point(asset_id, metric_name='m-regression', direction='regression'),
            _make_change_point(asset_id, metric_name='m-improvement', direction='improvement'),
        ]
    )
    await db_session.flush()

    response = await api_client.get('/change-points', params={'direction': 'improvement'})

    assert response.status_code == 200
    directions = {row['direction'] for row in response.json()}
    assert directions == {'improvement'}


async def test_filter_by_asset_id(api_client: AsyncClient, db_session: AsyncSession) -> None:
    """?asset_id=X returns only change points for asset X."""
    wanted_asset_id = uuid.uuid4()
    other_asset_id = uuid.uuid4()
    db_session.add_all(
        [
            _make_change_point(wanted_asset_id),
            _make_change_point(other_asset_id),
        ]
    )
    await db_session.flush()

    response = await api_client.get('/change-points', params={'asset_id': str(wanted_asset_id)})

    assert response.status_code == 200
    asset_ids = {row['asset_id'] for row in response.json()}
    assert asset_ids == {str(wanted_asset_id)}


async def test_filter_by_created_at_range(api_client: AsyncClient, db_session: AsyncSession) -> None:
    """?from_ts / ?to_ts bound results by created_at."""
    asset_id = uuid.uuid4()
    db_session.add_all(
        [
            _make_change_point(asset_id, metric_name='m-old', created_at=_BASE),
            _make_change_point(asset_id, metric_name='m-mid', created_at=_BASE + timedelta(days=2)),
            _make_change_point(asset_id, metric_name='m-new', created_at=_BASE + timedelta(days=4)),
        ]
    )
    await db_session.flush()

    response = await api_client.get(
        '/change-points',
        params={
            'from_ts': (_BASE + timedelta(days=1)).isoformat(),
            'to_ts': (_BASE + timedelta(days=3)).isoformat(),
        },
    )

    assert response.status_code == 200
    metrics = {row['metric_name'] for row in response.json()}
    assert metrics == {'m-mid'}


async def test_no_filter_returns_all(api_client: AsyncClient, db_session: AsyncSession) -> None:
    """No filter params returns every change point for the seeded asset."""
    asset_id = uuid.uuid4()
    db_session.add_all(
        [
            _make_change_point(asset_id, metric_name='m-a'),
            _make_change_point(asset_id, metric_name='m-b'),
        ]
    )
    await db_session.flush()

    response = await api_client.get('/change-points', params={'asset_id': str(asset_id)})

    assert response.status_code == 200
    metrics = {row['metric_name'] for row in response.json()}
    assert metrics == {'m-a', 'm-b'}
