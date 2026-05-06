"""Integration tests for GET /assets/{asset_id}/meta/timeline/summary."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def post_snapshot(
    api_client: AsyncClient,
    asset_id: uuid.UUID,
    values: list[dict] | None = None,
    closed: list[dict] | None = None,
    observed_at: str = '2026-04-16T10:00:00Z',
) -> None:
    payload: dict = {'source': 'cicd', 'observed_at': observed_at}
    if values is not None:
        payload['values'] = values
    if closed is not None:
        payload['closed'] = closed
    response = await api_client.post(f'/assets/{asset_id}/meta/snapshots', json=payload)
    assert response.status_code == 201


def _get_item_count(data: dict) -> int:
    count = data.get('itemCount', data.get('item_count'))
    assert count is not None, f'neither itemCount nor item_count found in: {data}'
    return int(count)


async def test_summary_returns_zero_for_empty_asset(
    api_client: AsyncClient,
    test_asset_id: uuid.UUID,
) -> None:
    """GET summary for an asset with no snapshots — item count is 0."""
    response = await api_client.get(
        f'/assets/{test_asset_id}/meta/timeline/summary',
        params={
            'from': '2026-04-16T09:00:00Z',
            'to': '2026-04-16T11:00:00Z',
        },
    )
    assert response.status_code == 200
    assert _get_item_count(response.json()) == 0


async def test_summary_count_grows_with_distinct_paths(
    api_client: AsyncClient,
    test_asset_id: uuid.UUID,
) -> None:
    """POST 3 distinct paths → count 3; POST a 4th → count 4."""
    await post_snapshot(
        api_client,
        test_asset_id,
        values=[
            {'label_path': ['key-a'], 'value': '1'},
            {'label_path': ['key-b'], 'value': '2'},
            {'label_path': ['key-c'], 'value': '3'},
        ],
    )

    response = await api_client.get(
        f'/assets/{test_asset_id}/meta/timeline/summary',
        params={
            'from': '2026-04-16T09:00:00Z',
            'to': '2026-04-16T11:00:00Z',
        },
    )
    assert response.status_code == 200
    assert _get_item_count(response.json()) == 3

    await post_snapshot(
        api_client,
        test_asset_id,
        values=[{'label_path': ['key-d'], 'value': '4'}],
        observed_at='2026-04-16T10:05:00Z',
    )

    response = await api_client.get(
        f'/assets/{test_asset_id}/meta/timeline/summary',
        params={
            'from': '2026-04-16T09:00:00Z',
            'to': '2026-04-16T11:00:00Z',
        },
    )
    assert response.status_code == 200
    assert _get_item_count(response.json()) == 4


async def test_summary_404_for_unknown_asset(
    api_client: AsyncClient,
) -> None:
    """GET summary for a random UUID returns 404."""
    fake_id = str(uuid.uuid4())
    response = await api_client.get(
        f'/assets/{fake_id}/meta/timeline/summary',
        params={
            'from': '2026-04-16T09:00:00Z',
            'to': '2026-04-16T11:00:00Z',
        },
    )
    assert response.status_code == 404


async def test_summary_and_timeline_count_parity(
    api_client: AsyncClient,
    test_asset_id: uuid.UUID,
) -> None:
    """summary itemCount == number of distinct group values in full timeline items."""
    await post_snapshot(
        api_client,
        test_asset_id,
        values=[
            {'label_path': ['alpha'], 'value': 'v1'},
            {'label_path': ['beta'], 'value': 'v2'},
            {'label_path': ['gamma'], 'value': 'v3'},
            {'label_path': ['delta'], 'value': 'v4'},
        ],
    )

    params = {
        'from': '2026-04-16T09:00:00Z',
        'to': '2026-04-16T11:00:00Z',
    }

    summary_response = await api_client.get(
        f'/assets/{test_asset_id}/meta/timeline/summary',
        params=params,
    )
    timeline_response = await api_client.get(
        f'/assets/{test_asset_id}/meta/timeline',
        params=params,
    )

    assert summary_response.status_code == 200
    assert timeline_response.status_code == 200

    summary_count = _get_item_count(summary_response.json())
    timeline_body = timeline_response.json()
    distinct_groups = len({item['group'] for item in timeline_body['items']})

    assert summary_count == distinct_groups


async def test_summary_validation_error_when_from_equals_or_exceeds_to(
    api_client: AsyncClient,
    test_asset_id: uuid.UUID,
) -> None:
    """GET summary with from == to or from > to returns 422."""
    equal_response = await api_client.get(
        f'/assets/{test_asset_id}/meta/timeline/summary',
        params={
            'from': '2026-04-16T10:00:00Z',
            'to': '2026-04-16T10:00:00Z',
        },
    )
    assert equal_response.status_code == 422

    reversed_response = await api_client.get(
        f'/assets/{test_asset_id}/meta/timeline/summary',
        params={
            'from': '2026-04-16T11:00:00Z',
            'to': '2026-04-16T10:00:00Z',
        },
    )
    assert reversed_response.status_code == 422
