"""Endpoint tests for evaluation invalidation and restore."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import _create_asset, _create_completed_eval


@pytest.mark.integration
async def test_invalidate_evaluation(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id, result='pass', score=90.0)

    resp = await async_client.patch(
        f'/evaluations/{eval_id}/invalidate',
        json={'invalidation_note': 'Wrong time window'},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body['invalidated'] is True


@pytest.mark.integration
async def test_restore_invalidated_evaluation(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    await async_client.patch(
        f'/evaluations/{eval_id}/invalidate',
        json={'invalidation_note': 'Mistake'},
    )

    resp = await async_client.patch(f'/evaluations/{eval_id}/restore')
    assert resp.status_code == 200
    body = resp.json()
    assert body['invalidated'] is False


@pytest.mark.integration
async def test_invalidate_restore_cycle(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Full cycle: valid -> invalidated -> restored to valid."""
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id, result='pass', score=85.0)

    # Invalidate
    await async_client.patch(
        f'/evaluations/{eval_id}/invalidate',
        json={'invalidation_note': 'Under review'},
    )

    # Verify invalidated in detail
    detail_resp = await async_client.get(f'/evaluations/{eval_id}')
    assert detail_resp.json()['invalidated'] is True
    assert detail_resp.json()['invalidation_note'] == 'Under review'

    # Restore
    await async_client.patch(f'/evaluations/{eval_id}/restore')

    # Verify restored
    detail_resp2 = await async_client.get(f'/evaluations/{eval_id}')
    assert detail_resp2.json()['invalidated'] is False
    assert detail_resp2.json()['result'] == 'pass'
    assert detail_resp2.json()['score'] == 85.0
