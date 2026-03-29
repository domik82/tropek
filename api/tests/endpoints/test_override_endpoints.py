"""Endpoint tests for evaluation result override and restore."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import _create_asset, _create_completed_eval


@pytest.mark.integration
async def test_override_status(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id, result='fail', score=30.0)

    resp = await async_client.patch(
        f'/evaluations/{eval_id}/override-status',
        json={'new_result': 'pass', 'reason': 'False alarm', 'author': 'alice'},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body['result'] == 'pass'
    assert body['original_result'] == 'fail'
    assert body['override_reason'] == 'False alarm'
    assert body['override_author'] == 'alice'


@pytest.mark.integration
async def test_restore_override(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id, result='fail', score=30.0)

    await async_client.patch(
        f'/evaluations/{eval_id}/override-status',
        json={'new_result': 'pass', 'reason': 'Override', 'author': 'alice'},
    )

    resp = await async_client.patch(f'/evaluations/{eval_id}/restore-override')
    assert resp.status_code == 200
    body = resp.json()
    assert body['result'] == 'fail'
    assert body['original_result'] is None
    assert body['override_reason'] is None


@pytest.mark.integration
async def test_double_override_preserves_true_original(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Overriding an already-overridden eval must keep the FIRST original."""
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id, result='fail', score=30.0)

    # First override: fail -> pass
    await async_client.patch(
        f'/evaluations/{eval_id}/override-status',
        json={'new_result': 'pass', 'reason': 'v1', 'author': 'alice'},
    )

    # Second override: pass -> warning
    resp = await async_client.patch(
        f'/evaluations/{eval_id}/override-status',
        json={'new_result': 'warning', 'reason': 'v2', 'author': 'bob'},
    )
    body = resp.json()
    assert body['result'] == 'warning'
    assert body['original_result'] == 'fail'  # True original preserved
    assert body['override_author'] == 'bob'
