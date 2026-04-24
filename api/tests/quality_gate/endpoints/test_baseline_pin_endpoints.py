"""Endpoint tests for baseline pin and unpin operations."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import _create_asset, _create_completed_eval


@pytest.mark.integration
async def test_pin_baseline(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    resp = await async_client.patch(
        f'/evaluation/{eval_id}/pin-baseline',
        json={'reason': 'Golden run', 'author': 'alice'},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body['baseline_pinned_at'] is not None
    assert body['baseline_pin_reason'] == 'Golden run'
    assert body['baseline_pin_author'] == 'alice'


@pytest.mark.integration
async def test_unpin_baseline(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    await async_client.patch(
        f'/evaluation/{eval_id}/pin-baseline',
        json={'reason': 'Golden run', 'author': 'alice'},
    )

    resp = await async_client.patch(f'/evaluation/{eval_id}/unpin-baseline')
    assert resp.status_code == 200
    body = resp.json()
    assert body['baseline_unpinned_at'] is not None


@pytest.mark.integration
async def test_pin_new_unpins_previous(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Pinning eval B for the same asset+SLO must atomically unpin eval A."""
    asset_id = await _create_asset(db_session)
    eval_a = await _create_completed_eval(
        db_session,
        asset_id,
        evaluation_name='run-a',
    )
    eval_b = await _create_completed_eval(
        db_session,
        asset_id,
        evaluation_name='run-b',
    )

    # Pin A
    await async_client.patch(
        f'/evaluation/{eval_a}/pin-baseline',
        json={'reason': 'First pin', 'author': 'alice'},
    )

    # Pin B — should unpin A
    await async_client.patch(
        f'/evaluation/{eval_b}/pin-baseline',
        json={'reason': 'Better run', 'author': 'bob'},
    )

    # Verify A is unpinned
    resp_a = await async_client.get(f'/evaluation/{eval_a}')
    assert resp_a.json()['baseline_unpinned_at'] is not None

    # Verify B is pinned
    resp_b = await async_client.get(f'/evaluation/{eval_b}')
    assert resp_b.json()['baseline_pinned_at'] is not None
    assert resp_b.json()['baseline_unpinned_at'] is None
