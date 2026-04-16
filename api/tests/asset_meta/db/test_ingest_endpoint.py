"""Integration tests for POST /assets/{asset_id}/meta/snapshots."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import AssetMetaClosure, AssetMetaSnapshot, AssetMetaValue

pytestmark = pytest.mark.integration


async def test_post_snapshot_values_only_returns_201(
    api_client: AsyncClient,
    test_asset_id: uuid.UUID,
) -> None:
    response = await api_client.post(
        f'/assets/{test_asset_id}/meta/snapshots',
        json={
            'source': 'cicd',
            'observed_at': '2026-04-16T10:00:00Z',
            'values': [{'path': ['app-A'], 'value': '2.3.0'}],
        },
    )
    assert response.status_code == 201
    assert 'snapshot_id' in response.json()


async def test_post_snapshot_closed_only_returns_201(
    api_client: AsyncClient,
    test_asset_id: uuid.UUID,
) -> None:
    response = await api_client.post(
        f'/assets/{test_asset_id}/meta/snapshots',
        json={
            'source': 'cicd',
            'observed_at': '2026-04-16T10:00:00Z',
            'closed': [{'path': ['legacy']}],
        },
    )
    assert response.status_code == 201
    assert 'snapshot_id' in response.json()


async def test_post_snapshot_empty_body_returns_422(
    api_client: AsyncClient,
    test_asset_id: uuid.UUID,
) -> None:
    response = await api_client.post(
        f'/assets/{test_asset_id}/meta/snapshots',
        json={
            'source': 'cicd',
            'observed_at': '2026-04-16T10:00:00Z',
            'values': [],
            'closed': [],
        },
    )
    assert response.status_code == 422


async def test_post_snapshot_unknown_asset_returns_404(
    api_client: AsyncClient,
) -> None:
    fake_id = str(uuid.uuid4())
    response = await api_client.post(
        f'/assets/{fake_id}/meta/snapshots',
        json={
            'source': 'cicd',
            'observed_at': '2026-04-16T10:00:00Z',
            'values': [{'path': ['app'], 'value': '1.0'}],
        },
    )
    assert response.status_code == 404


async def test_post_snapshot_invalid_source_returns_422(
    api_client: AsyncClient,
    test_asset_id: uuid.UUID,
) -> None:
    response = await api_client.post(
        f'/assets/{test_asset_id}/meta/snapshots',
        json={
            'source': 'has space',
            'observed_at': '2026-04-16T10:00:00Z',
            'values': [{'path': ['app'], 'value': '1.0'}],
        },
    )
    assert response.status_code == 422


async def test_post_snapshot_naive_datetime_returns_422(
    api_client: AsyncClient,
    test_asset_id: uuid.UUID,
) -> None:
    response = await api_client.post(
        f'/assets/{test_asset_id}/meta/snapshots',
        json={
            'source': 'cicd',
            'observed_at': '2026-04-16T10:00:00',
            'values': [{'path': ['app'], 'value': '1.0'}],
        },
    )
    assert response.status_code == 422


async def test_post_snapshot_path_too_deep_returns_422(
    api_client: AsyncClient,
    test_asset_id: uuid.UUID,
) -> None:
    response = await api_client.post(
        f'/assets/{test_asset_id}/meta/snapshots',
        json={
            'source': 'cicd',
            'observed_at': '2026-04-16T10:00:00Z',
            'values': [{'path': ['a', 'b', 'c', 'd', 'e', 'f', 'g'], 'value': '1.0'}],
        },
    )
    assert response.status_code == 422


async def test_post_snapshot_duplicate_path_in_values_returns_422(
    api_client: AsyncClient,
    test_asset_id: uuid.UUID,
) -> None:
    response = await api_client.post(
        f'/assets/{test_asset_id}/meta/snapshots',
        json={
            'source': 'cicd',
            'observed_at': '2026-04-16T10:00:00Z',
            'values': [
                {'path': ['app'], 'value': '1.0'},
                {'path': ['app'], 'value': '2.0'},
            ],
        },
    )
    assert response.status_code == 422


async def test_post_snapshot_persists_values_and_closures_to_db(
    api_client: AsyncClient,
    test_asset_id: uuid.UUID,
    db_session: AsyncSession,
) -> None:
    response = await api_client.post(
        f'/assets/{test_asset_id}/meta/snapshots',
        json={
            'source': 'cicd',
            'observed_at': '2026-04-16T10:00:00Z',
            'values': [
                {'path': ['app-A'], 'value': '2.3.0'},
                {'path': ['cpu'], 'value': '4'},
            ],
            'closed': [{'path': ['legacy']}],
        },
    )
    assert response.status_code == 201

    snapshot_count_result = await db_session.execute(
        select(func.count())
        .select_from(AssetMetaSnapshot)
        .where(AssetMetaSnapshot.asset_id == test_asset_id),
    )
    assert snapshot_count_result.scalar() == 1

    snapshot_id = uuid.UUID(response.json()['snapshot_id'])

    value_count_result = await db_session.execute(
        select(func.count())
        .select_from(AssetMetaValue)
        .where(AssetMetaValue.snapshot_id == snapshot_id),
    )
    assert value_count_result.scalar() == 2

    closure_count_result = await db_session.execute(
        select(func.count())
        .select_from(AssetMetaClosure)
        .where(AssetMetaClosure.snapshot_id == snapshot_id),
    )
    assert closure_count_result.scalar() == 1
