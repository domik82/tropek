"""Integration tests for GET /assets/{asset_id}/meta/timeline."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def post_snapshot(
    api_client: AsyncClient,
    asset_id: uuid.UUID,
    source: str = 'cicd',
    observed_at: str = '2026-04-16T10:00:00Z',
    values: list[dict] | None = None,
    closed: list[dict] | None = None,
) -> dict:
    """Helper to POST a metadata snapshot and assert 201."""
    payload: dict = {'source': source, 'observed_at': observed_at}
    if values is not None:
        payload['values'] = values
    if closed is not None:
        payload['closed'] = closed
    # Must have at least one of values or closed
    if 'values' not in payload and 'closed' not in payload:
        payload['values'] = []
    response = await api_client.post(
        f'/assets/{asset_id}/meta/snapshots',
        json=payload,
    )
    assert response.status_code == 201, f'POST failed: {response.text}'
    return response.json()


async def test_round_trip_single_snapshot_shows_up_in_timeline(
    api_client: AsyncClient,
    test_asset_id: uuid.UUID,
) -> None:
    """POST one snapshot with one value, GET timeline — assert 1 item."""
    await post_snapshot(
        api_client,
        test_asset_id,
        values=[{'path': ['app-A'], 'value': '2.3.0'}],
    )

    response = await api_client.get(
        f'/assets/{test_asset_id}/meta/timeline',
        params={
            'from': '2026-04-16T09:00:00Z',
            'to': '2026-04-16T11:00:00Z',
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert 'groups' in body
    assert 'items' in body
    assert len(body['items']) == 1


async def test_validation_errors_for_missing_from_or_to(
    api_client: AsyncClient,
    test_asset_id: uuid.UUID,
) -> None:
    """GET without from or to returns 422."""
    missing_to = await api_client.get(
        f'/assets/{test_asset_id}/meta/timeline',
        params={'from': '2026-04-16T09:00:00Z'},
    )
    assert missing_to.status_code == 422

    missing_from = await api_client.get(
        f'/assets/{test_asset_id}/meta/timeline',
        params={'to': '2026-04-16T11:00:00Z'},
    )
    assert missing_from.status_code == 422


async def test_validation_error_when_from_equals_or_exceeds_to(
    api_client: AsyncClient,
    test_asset_id: uuid.UUID,
) -> None:
    """GET with from=to or from>to returns 422."""
    equal_response = await api_client.get(
        f'/assets/{test_asset_id}/meta/timeline',
        params={
            'from': '2026-04-16T10:00:00Z',
            'to': '2026-04-16T10:00:00Z',
        },
    )
    assert equal_response.status_code == 422

    reversed_response = await api_client.get(
        f'/assets/{test_asset_id}/meta/timeline',
        params={
            'from': '2026-04-16T11:00:00Z',
            'to': '2026-04-16T10:00:00Z',
        },
    )
    assert reversed_response.status_code == 422


async def test_unknown_asset_returns_404(
    api_client: AsyncClient,
) -> None:
    """GET for a random UUID returns 404."""
    fake_id = str(uuid.uuid4())
    response = await api_client.get(
        f'/assets/{fake_id}/meta/timeline',
        params={
            'from': '2026-04-16T09:00:00Z',
            'to': '2026-04-16T11:00:00Z',
        },
    )
    assert response.status_code == 404


async def test_multi_source_spans_both_appear(
    api_client: AsyncClient,
    test_asset_id: uuid.UUID,
) -> None:
    """Two sources push different paths — both appear in the timeline."""
    await post_snapshot(
        api_client,
        test_asset_id,
        source='cicd',
        values=[{'path': ['app-A'], 'value': '2.3.0'}],
    )
    await post_snapshot(
        api_client,
        test_asset_id,
        source='monitoring',
        values=[{'path': ['cpu-usage'], 'value': '75%'}],
    )

    response = await api_client.get(
        f'/assets/{test_asset_id}/meta/timeline',
        params={
            'from': '2026-04-16T09:00:00Z',
            'to': '2026-04-16T11:00:00Z',
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body['items']) == 2


async def test_cascading_closure_round_trip(
    api_client: AsyncClient,
    test_asset_id: uuid.UUID,
) -> None:
    """POST values at T0, close parent at T1 — all children close at T1."""
    t0 = '2026-04-16T10:00:00Z'
    t1 = '2026-04-16T10:30:00Z'

    await post_snapshot(
        api_client,
        test_asset_id,
        observed_at=t0,
        values=[
            {'path': ['app'], 'value': 'root'},
            {'path': ['app', 'plug-1'], 'value': 'v1'},
            {'path': ['app', 'plug-2'], 'value': 'v2'},
        ],
    )
    await post_snapshot(
        api_client,
        test_asset_id,
        observed_at=t1,
        closed=[{'path': ['app']}],
    )

    response = await api_client.get(
        f'/assets/{test_asset_id}/meta/timeline',
        params={
            'from': '2026-04-16T09:00:00Z',
            'to': '2026-04-16T11:00:00Z',
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body['items']) == 3
    for item in body['items']:
        # Check the className field — try both alias and field name
        class_name = item.get('className', item.get('class_name', ''))
        assert 'meta-span-closed' in class_name, (
            f'expected meta-span-closed in className, got: {class_name}'
        )


async def test_large_snapshot_roundtrips(
    api_client: AsyncClient,
    test_asset_id: uuid.UUID,
) -> None:
    """POST a snapshot with 500 values — all appear in the timeline."""
    values = [{'path': [f'key-{i}'], 'value': f'v{i}'} for i in range(500)]
    await post_snapshot(
        api_client,
        test_asset_id,
        values=values,
    )

    response = await api_client.get(
        f'/assets/{test_asset_id}/meta/timeline',
        params={
            'from': '2026-04-16T09:00:00Z',
            'to': '2026-04-16T11:00:00Z',
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body['items']) == 500


async def test_window_clipping_left_and_open_right(
    api_client: AsyncClient,
    test_asset_id: uuid.UUID,
) -> None:
    """A span started 60 days ago with no close, queried for last 30 days — clipped left and open right."""
    sixty_days_ago = (datetime.now(UTC) - timedelta(days=60)).isoformat()
    thirty_days_ago = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    now = datetime.now(UTC).isoformat()

    await post_snapshot(
        api_client,
        test_asset_id,
        observed_at=sixty_days_ago,
        values=[{'path': ['long-lived'], 'value': 'stable'}],
    )

    response = await api_client.get(
        f'/assets/{test_asset_id}/meta/timeline',
        params={
            'from': thirty_days_ago,
            'to': now,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body['items']) == 1
    item = body['items'][0]
    class_name = item.get('className', item.get('class_name', ''))
    assert 'meta-span-clipped-left' in class_name, (
        f'expected meta-span-clipped-left in className, got: {class_name}'
    )
    assert 'meta-span-open' in class_name, (
        f'expected meta-span-open in className, got: {class_name}'
    )


async def test_closed_only_snapshot_round_trip(
    api_client: AsyncClient,
    test_asset_id: uuid.UUID,
) -> None:
    """POST values at T0, close at T1 — single closed item in timeline."""
    t0 = '2026-04-16T10:00:00Z'
    t1 = '2026-04-16T10:30:00Z'

    await post_snapshot(
        api_client,
        test_asset_id,
        observed_at=t0,
        values=[{'path': ['legacy'], 'value': 'old'}],
    )
    await post_snapshot(
        api_client,
        test_asset_id,
        observed_at=t1,
        closed=[{'path': ['legacy']}],
    )

    response = await api_client.get(
        f'/assets/{test_asset_id}/meta/timeline',
        params={
            'from': '2026-04-16T09:00:00Z',
            'to': '2026-04-16T11:00:00Z',
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body['items']) == 1
    item = body['items'][0]
    class_name = item.get('className', item.get('class_name', ''))
    assert 'meta-span-closed' in class_name, (
        f'expected meta-span-closed in className, got: {class_name}'
    )
