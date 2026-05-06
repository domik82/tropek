"""Integration tests for DELETE /assets/{asset_id}/meta/snapshots/{snapshot_id}."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import AssetMetaClosure, AssetMetaSnapshot, AssetMetaValue

pytestmark = pytest.mark.integration


async def test_delete_snapshot_returns_204(api_client: AsyncClient, test_asset_id: uuid.UUID) -> None:
    create_response = await api_client.post(
        f'/assets/{test_asset_id}/meta/snapshots',
        json={
            'source': 'cicd',
            'observed_at': '2026-04-16T10:00:00Z',
            'values': [{'label_path': ['app'], 'value': '1.0'}],
        },
    )
    snapshot_id = create_response.json()['snapshot_id']

    response = await api_client.delete(f'/assets/{test_asset_id}/meta/snapshots/{snapshot_id}')
    assert response.status_code == 204
    assert response.content == b''


async def test_delete_snapshot_cascades_children(
    api_client: AsyncClient, test_asset_id: uuid.UUID, db_session: AsyncSession
) -> None:
    create_response = await api_client.post(
        f'/assets/{test_asset_id}/meta/snapshots',
        json={
            'source': 'cicd',
            'observed_at': '2026-04-16T10:00:00Z',
            'values': [{'label_path': ['app'], 'value': '1.0'}],
            'closed': [{'label_path': ['old']}],
        },
    )
    snapshot_id = create_response.json()['snapshot_id']

    await api_client.delete(f'/assets/{test_asset_id}/meta/snapshots/{snapshot_id}')

    value_count = await db_session.scalar(
        select(func.count()).where(AssetMetaValue.snapshot_id == uuid.UUID(snapshot_id))
    )
    closure_count = await db_session.scalar(
        select(func.count()).where(AssetMetaClosure.snapshot_id == uuid.UUID(snapshot_id))
    )
    snapshot_count = await db_session.scalar(select(func.count()).where(AssetMetaSnapshot.id == uuid.UUID(snapshot_id)))
    assert value_count == 0
    assert closure_count == 0
    assert snapshot_count == 0


async def test_delete_snapshot_not_found(api_client: AsyncClient, test_asset_id: uuid.UUID) -> None:
    response = await api_client.delete(f'/assets/{test_asset_id}/meta/snapshots/{uuid.uuid4()}')
    assert response.status_code == 404


async def test_delete_snapshot_wrong_asset(api_client: AsyncClient, test_asset_id: uuid.UUID) -> None:
    create_response = await api_client.post(
        f'/assets/{test_asset_id}/meta/snapshots',
        json={
            'source': 'cicd',
            'observed_at': '2026-04-16T10:00:00Z',
            'values': [{'label_path': ['app'], 'value': '1.0'}],
        },
    )
    snapshot_id = create_response.json()['snapshot_id']
    response = await api_client.delete(f'/assets/{uuid.uuid4()}/meta/snapshots/{snapshot_id}')
    assert response.status_code == 404
