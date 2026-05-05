"""Integration tests for GET /assets/{asset_id}/meta/snapshots/{snapshot_id}."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_get_snapshot_detail(api_client: AsyncClient, test_asset_id: uuid.UUID) -> None:
    create_response = await api_client.post(
        f'/assets/{test_asset_id}/meta/snapshots',
        json={
            'source': 'cicd',
            'observed_at': '2026-04-16T10:00:00Z',
            'values': [
                {'label_path': ['app'], 'value': '1.0'},
                {'label_path': ['app', 'plugin'], 'value': '0.5'},
            ],
            'closed': [{'label_path': ['legacy']}],
        },
    )
    snapshot_id = create_response.json()['snapshot_id']

    response = await api_client.get(f'/assets/{test_asset_id}/meta/snapshots/{snapshot_id}')
    assert response.status_code == 200
    detail = response.json()
    assert detail['id'] == snapshot_id
    assert detail['source'] == 'cicd'
    assert len(detail['values']) == 2
    assert len(detail['closures']) == 1
    assert detail['values'][0]['label_path'] == ['app']
    assert detail['closures'][0]['label_path'] == ['legacy']


async def test_get_snapshot_not_found(api_client: AsyncClient, test_asset_id: uuid.UUID) -> None:
    response = await api_client.get(f'/assets/{test_asset_id}/meta/snapshots/{uuid.uuid4()}')
    assert response.status_code == 404


async def test_get_snapshot_wrong_asset(api_client: AsyncClient, test_asset_id: uuid.UUID) -> None:
    create_response = await api_client.post(
        f'/assets/{test_asset_id}/meta/snapshots',
        json={
            'source': 'cicd',
            'observed_at': '2026-04-16T10:00:00Z',
            'values': [{'label_path': ['app'], 'value': '1.0'}],
        },
    )
    snapshot_id = create_response.json()['snapshot_id']
    response = await api_client.get(f'/assets/{uuid.uuid4()}/meta/snapshots/{snapshot_id}')
    assert response.status_code == 404
