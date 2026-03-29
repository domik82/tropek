"""Endpoint tests for heatmap result transformation (router-level)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import (
    _create_asset,
    _create_completed_eval,
    _ensure_slo_objective,
    _seed_indicator_row,
)


@pytest.mark.integration
async def test_heatmap_invalidated_eval_shows_invalidated_result(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Router transforms invalidated completed eval cells to result='invalidated'."""
    asset_id = await _create_asset(db_session, name='hm-router-inv')
    obj = await _ensure_slo_objective(db_session)
    eval_id = await _create_completed_eval(
        db_session,
        asset_id,
        result='pass',
        score=90.0,
    )
    await _seed_indicator_row(db_session, eval_id, obj, status='pass')

    # Invalidate via endpoint
    await async_client.patch(
        f'/evaluations/{eval_id}/invalidate',
        json={'invalidation_note': 'bad data'},
    )

    # Fetch heatmap — the router should show "invalidated" not "pass"
    resp = await async_client.get(
        '/evaluations/metric-heatmap',
        params={'asset_name': 'hm-router-inv'},
    )
    assert resp.status_code == 200
    cells = resp.json()['cells']
    assert len(cells) >= 1
    assert all(c['result'] == 'invalidated' for c in cells)


@pytest.mark.integration
async def test_heatmap_overridden_eval_shows_overridden_result(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Overridden evaluation cells show the overridden result in heatmap."""
    asset_id = await _create_asset(db_session, name='hm-router-ovr')
    obj = await _ensure_slo_objective(db_session, slo_name='hm-ovr-slo')
    eval_id = await _create_completed_eval(
        db_session,
        asset_id,
        result='fail',
        score=30.0,
        evaluation_name='hm-ovr-test',
        slo_name='hm-ovr-slo',
    )
    await _seed_indicator_row(db_session, eval_id, obj, status='fail', score=0.0)

    # Override via endpoint: fail -> pass
    await async_client.patch(
        f'/evaluations/{eval_id}/override-status',
        json={'new_result': 'pass', 'reason': 'false alarm', 'author': 'alice'},
    )

    resp = await async_client.get(
        '/evaluations/metric-heatmap',
        params={'asset_name': 'hm-router-ovr'},
    )
    assert resp.status_code == 200
    cells = resp.json()['cells']
    assert len(cells) >= 1
    # Router uses ev.result (overridden) when ev.original_result is not None
    assert all(c['result'] == 'pass' for c in cells)
