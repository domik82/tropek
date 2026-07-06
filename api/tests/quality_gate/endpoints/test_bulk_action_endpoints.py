"""Endpoint tests for the bulk (batch) evaluation-action endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import _create_asset, _create_completed_eval


@pytest.mark.integration
async def test_bulk_invalidate_applies_and_reports_not_found(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    asset_id = await _create_asset(db_session)
    id_one = await _create_completed_eval(db_session, asset_id, slo_name='slo-a', evaluation_name='run-a')
    id_two = await _create_completed_eval(db_session, asset_id, slo_name='slo-b', evaluation_name='run-b')
    unknown = uuid.uuid4()

    resp = await async_client.patch(
        '/evaluations/invalidate',
        json={'evaluation_ids': [str(id_one), str(id_two), str(unknown)], 'note': 'bad window'},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body['updated'] == 2
    assert body['not_found'] == [str(unknown)]
    assert {row['evaluation_id'] for row in body['results']} == {str(id_one), str(id_two)}

    # Both real rows are now invalidated.
    for eval_id in (id_one, id_two):
        detail = await async_client.get(f'/evaluation/{eval_id}')
        assert detail.json()['invalidated'] is True


@pytest.mark.integration
async def test_bulk_restore_inverts(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)
    await async_client.patch('/evaluations/invalidate', json={'evaluation_ids': [str(eval_id)], 'note': 'x'})

    resp = await async_client.patch('/evaluations/restore', json={'evaluation_ids': [str(eval_id)]})

    assert resp.status_code == 200
    assert resp.json()['updated'] == 1
    detail = await async_client.get(f'/evaluation/{eval_id}')
    assert detail.json()['invalidated'] is False


@pytest.mark.integration
async def test_bulk_override_status_rejects_bad_result(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    resp = await async_client.patch(
        '/evaluations/override-status',
        json={'evaluation_ids': [str(eval_id)], 'new_result': 'bogus', 'reason': 'r', 'author': 'a'},
    )

    assert resp.status_code == 422


@pytest.mark.integration
async def test_bulk_restore_override_reverts_result(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id, result='pass')
    await async_client.patch(
        '/evaluations/override-status',
        json={'evaluation_ids': [str(eval_id)], 'new_result': 'fail', 'reason': 'r', 'author': 'a'},
    )

    resp = await async_client.patch('/evaluations/restore-override', json={'evaluation_ids': [str(eval_id)]})

    assert resp.status_code == 200
    assert resp.json()['updated'] == 1
    detail = await async_client.get(f'/evaluation/{eval_id}')
    assert detail.json()['result'] == 'pass'
    assert detail.json()['original_result'] is None


@pytest.mark.integration
async def test_bulk_pin_baseline_pins_completed_evals(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    resp = await async_client.patch(
        '/evaluations/pin-baseline',
        json={'evaluation_ids': [str(eval_id)], 'reason': 'trusted window', 'author': 'alice'},
    )

    assert resp.status_code == 200
    assert resp.json()['updated'] == 1
    assert {row['evaluation_id'] for row in resp.json()['results']} == {str(eval_id)}
    detail = await async_client.get(f'/evaluation/{eval_id}')
    assert detail.json()['baseline_pinned_at'] is not None


@pytest.mark.integration
async def test_bulk_unpin_baseline_clears_pin(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)
    await async_client.patch(
        '/evaluations/pin-baseline',
        json={'evaluation_ids': [str(eval_id)], 'reason': 'r', 'author': 'alice'},
    )

    resp = await async_client.patch('/evaluations/unpin-baseline', json={'evaluation_ids': [str(eval_id)]})

    assert resp.status_code == 200
    assert resp.json()['updated'] == 1
    detail = await async_client.get(f'/evaluation/{eval_id}')
    assert detail.json()['baseline_unpinned_at'] is not None


@pytest.mark.integration
async def test_bulk_invalidate_empty_id_list_is_noop(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """An empty id list applies nothing and reports zero updates (guard against a full-table UPDATE)."""
    resp = await async_client.patch('/evaluations/invalidate', json={'evaluation_ids': [], 'note': 'x'})

    assert resp.status_code == 200
    body = resp.json()
    assert body['updated'] == 0
    assert body['results'] == []
    assert body['not_found'] == []
