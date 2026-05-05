"""Integration tests for GET /assets/{asset_id}/meta/snapshots."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_list_snapshots_empty(api_client: AsyncClient, test_asset_id: uuid.UUID) -> None:
    response = await api_client.get(f'/assets/{test_asset_id}/meta/snapshots')
    assert response.status_code == 200
    assert response.json() == []


async def test_list_snapshots_returns_summaries(api_client: AsyncClient, test_asset_id: uuid.UUID) -> None:
    await api_client.post(
        f'/assets/{test_asset_id}/meta/snapshots',
        json={
            'source': 'cicd',
            'observed_at': '2026-04-16T10:00:00Z',
            'values': [{'label_path': ['app'], 'value': '1.0'}],
        },
    )
    await api_client.post(
        f'/assets/{test_asset_id}/meta/snapshots',
        json={
            'source': 'cicd',
            'observed_at': '2026-04-16T11:00:00Z',
            'values': [{'label_path': ['app'], 'value': '2.0'}],
        },
    )
    response = await api_client.get(f'/assets/{test_asset_id}/meta/snapshots')
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    assert items[0]['value_count'] == 1
    assert items[0]['observed_at'] > items[1]['observed_at']


async def test_list_snapshots_filter_by_source(api_client: AsyncClient, test_asset_id: uuid.UUID) -> None:
    await api_client.post(
        f'/assets/{test_asset_id}/meta/snapshots',
        json={
            'source': 'cicd',
            'observed_at': '2026-04-16T10:00:00Z',
            'values': [{'label_path': ['app'], 'value': '1.0'}],
        },
    )
    await api_client.post(
        f'/assets/{test_asset_id}/meta/snapshots',
        json={
            'source': 'os-agent',
            'observed_at': '2026-04-16T10:00:00Z',
            'values': [{'label_path': ['os'], 'value': 'linux'}],
        },
    )
    response = await api_client.get(f'/assets/{test_asset_id}/meta/snapshots', params={'source': 'cicd'})
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]['source'] == 'cicd'


async def test_list_snapshots_filter_by_time_range(api_client: AsyncClient, test_asset_id: uuid.UUID) -> None:
    await api_client.post(
        f'/assets/{test_asset_id}/meta/snapshots',
        json={
            'source': 'cicd',
            'observed_at': '2026-04-16T10:00:00Z',
            'values': [{'label_path': ['app'], 'value': '1.0'}],
        },
    )
    await api_client.post(
        f'/assets/{test_asset_id}/meta/snapshots',
        json={
            'source': 'cicd',
            'observed_at': '2026-04-17T10:00:00Z',
            'values': [{'label_path': ['app'], 'value': '2.0'}],
        },
    )
    response = await api_client.get(
        f'/assets/{test_asset_id}/meta/snapshots',
        params={'from': '2026-04-17T00:00:00Z', 'to': '2026-04-18T00:00:00Z'},
    )
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1


async def test_list_snapshots_invalid_window_returns_422(api_client: AsyncClient, test_asset_id: uuid.UUID) -> None:
    response = await api_client.get(
        f'/assets/{test_asset_id}/meta/snapshots',
        params={'from': '2026-04-18T00:00:00Z', 'to': '2026-04-16T00:00:00Z'},
    )
    assert response.status_code == 422


async def test_list_snapshots_unknown_asset_returns_404(api_client: AsyncClient) -> None:
    response = await api_client.get(f'/assets/{uuid.uuid4()}/meta/snapshots')
    assert response.status_code == 404
