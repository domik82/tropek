"""Endpoint tests for heatmap result transformation (router-level)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import _create_asset, _create_completed_eval

_INDICATORS = [
    {
        "metric": "cpu_usage",
        "display_name": "CPU Usage",
        "value": 72.0,
        "compared_value": None,
        "change_absolute": None,
        "change_relative_pct": None,
        "status": "pass",
        "score": 1.0,
        "weight": 1,
        "key_sli": False,
        "pass_targets": [{"criteria": "<80", "target_value": 80, "violated": False}],
        "warning_targets": None,
    },
]


@pytest.mark.integration
async def test_heatmap_invalidated_eval_shows_invalidated_result(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Router transforms invalidated completed eval cells to result='invalidated'."""
    asset_id = await _create_asset(db_session, name="hm-router-inv")
    eval_id = await _create_completed_eval(
        db_session,
        asset_id,
        result="pass",
        score=90.0,
        indicator_results=_INDICATORS,
    )

    # Invalidate via endpoint
    await async_client.patch(
        f"/evaluations/{eval_id}/invalidate",
        json={"invalidation_note": "bad data"},
    )

    # Fetch heatmap — the router should show "invalidated" not "pass"
    resp = await async_client.get(
        "/evaluations/metric-heatmap",
        params={"asset_name": "hm-router-inv"},
    )
    assert resp.status_code == 200
    cells = resp.json()["cells"]
    assert len(cells) >= 1
    assert all(c["result"] == "invalidated" for c in cells)


@pytest.mark.integration
async def test_heatmap_overridden_eval_shows_overridden_result(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Overridden evaluation cells show the overridden result in heatmap."""
    asset_id = await _create_asset(db_session, name="hm-router-ovr")
    await _create_completed_eval(
        db_session,
        asset_id,
        result="fail",
        score=30.0,
        indicator_results=_INDICATORS,
        evaluation_name="hm-ovr-test",
    )

    # The eval was created with result="fail" but indicator status="pass"
    # After override to "pass", the router should use ev.result (overridden)
    # because ev.original_result is not None
    evals_resp = await async_client.get(
        "/evaluations",
        params={"asset_name": "hm-router-ovr"},
    )
    eval_id = evals_resp.json()["items"][0]["id"]

    # Override via endpoint: fail -> pass
    await async_client.patch(
        f"/evaluations/{eval_id}/override-status",
        json={"new_result": "pass", "reason": "false alarm", "author": "alice"},
    )

    resp = await async_client.get(
        "/evaluations/metric-heatmap",
        params={"asset_name": "hm-router-ovr"},
    )
    assert resp.status_code == 200
    cells = resp.json()["cells"]
    assert len(cells) >= 1
    # Router uses ev.result (overridden) when ev.original_result is not None
    assert all(c["result"] == "pass" for c in cells)
