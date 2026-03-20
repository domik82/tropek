"""Unit tests for evaluation trigger resolution logic."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from app.modules.quality_gate.exceptions import AssetNotFoundError
from app.modules.quality_gate.trigger import resolve_single_trigger


@pytest.fixture
def mock_repos() -> dict:
    asset_repo = AsyncMock()
    slo_link_repo = AsyncMock()
    sli_repo = AsyncMock()
    slo_repo = AsyncMock()
    ds_repo = AsyncMock()

    asset_repo.get_by_name.return_value = type(
        "Asset",
        (),
        {
            "id": uuid.uuid4(),
            "name": "vm-01",
            "labels": {"os": "linux"},
        },
    )()

    slo_link_repo.list_by_asset.return_value = [
        type(
            "Link",
            (),
            {
                "slo_name": "perf-slo",
                "sli_name": "system-sli",
                "data_source_name": "prom-1",
            },
        )(),
    ]

    sli_repo.get_latest.return_value = type(
        "SLI",
        (),
        {
            "name": "system-sli",
            "version": 1,
            "indicators": {"cpu": "query"},
        },
    )()

    slo_repo.get_latest.return_value = type(
        "SLO",
        (),
        {
            "name": "perf-slo",
            "version": 1,
        },
    )()

    ds_repo.get_by_name.return_value = type(
        "DS",
        (),
        {
            "name": "prom-1",
            "adapter_url": "http://prom:8081",
            "adapter_type": "prometheus",
        },
    )()

    return {
        "asset_repo": asset_repo,
        "slo_link_repo": slo_link_repo,
        "sli_repo": sli_repo,
        "slo_repo": slo_repo,
        "ds_repo": ds_repo,
    }


async def test_resolve_single_trigger(mock_repos: dict) -> None:
    ctx = await resolve_single_trigger(
        asset_name="vm-01",
        slo_name="perf-slo",
        **mock_repos,
    )
    assert ctx.asset_name == "vm-01"
    assert ctx.slo_name == "perf-slo"
    assert ctx.sli_name == "system-sli"
    assert ctx.data_source_name == "prom-1"
    assert ctx.adapter_url == "http://prom:8081"
    assert ctx.indicators == {"cpu": "query"}


async def test_resolve_single_trigger_asset_not_found(mock_repos: dict) -> None:
    mock_repos["asset_repo"].get_by_name.return_value = None
    with pytest.raises(AssetNotFoundError, match="asset"):
        await resolve_single_trigger(
            asset_name="nonexistent",
            slo_name="perf-slo",
            **mock_repos,
        )
