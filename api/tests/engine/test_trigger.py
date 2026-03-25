"""Unit tests for evaluation trigger resolution logic."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from app.modules.quality_gate.exceptions import AssetNotFoundError, SLONotConfiguredError
from app.modules.quality_gate.trigger import (
    resolve_all_bindings_for_asset,
    resolve_single_trigger,
)


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
            "tags": {"os": "linux"},
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
            "sli_name": None,
            "sli_version": None,
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


async def test_resolve_via_binding_fallback(mock_repos: dict) -> None:
    """When no legacy link exists, resolve via SLO binding (direct or group)."""
    # No legacy links
    mock_repos["slo_link_repo"].list_by_asset.return_value = []

    # SLO has sli_name set (new model)
    mock_repos["slo_repo"].get_latest.return_value = type(
        "SLO", (), {"name": "vm-slo", "version": 1, "sli_name": "vm-sli", "sli_version": 1}
    )()

    mock_repos["sli_repo"].get_version.return_value = type(
        "SLI", (), {"name": "vm-sli", "version": 1, "indicators": {"cpu": "q1"}}
    )()

    binding_repo = AsyncMock()
    binding_repo.find_for_asset.return_value = type(
        "Binding", (), {"slo_name": "vm-slo", "data_source_name": "prom-1"}
    )()

    ctx = await resolve_single_trigger(
        asset_name="vm-01",
        slo_name="vm-slo",
        binding_repo=binding_repo,
        **mock_repos,
    )
    assert ctx.slo_name == "vm-slo"
    assert ctx.sli_name == "vm-sli"
    assert ctx.data_source_name == "prom-1"


async def test_resolve_no_link_no_binding_raises(mock_repos: dict) -> None:
    """When neither legacy link nor binding exists, raise SLONotConfiguredError."""
    mock_repos["slo_link_repo"].list_by_asset.return_value = []

    binding_repo = AsyncMock()
    binding_repo.find_for_asset.return_value = None

    with pytest.raises(SLONotConfiguredError, match="no slo link or binding"):
        await resolve_single_trigger(
            asset_name="vm-01",
            slo_name="unknown-slo",
            binding_repo=binding_repo,
            **mock_repos,
        )


async def test_resolve_direct_and_template_bindings() -> None:
    """Asset with both direct and template bindings resolves all SLO names."""
    asset_id = uuid.uuid4()
    group_id = uuid.uuid4()
    group_ids: list[uuid.UUID] = []

    binding_repo = AsyncMock()
    binding_repo.list_for_asset_evaluation.return_value = [
        type(
            "Binding",
            (),
            {"slo_name": "direct-slo", "data_source_name": "prom-1", "target_type": "asset"},
        )(),
    ]

    template_binding_repo = AsyncMock()
    template_binding_repo.list_for_asset_evaluation.return_value = [
        type(
            "TemplateBinding",
            (),
            {
                "template_group_name": "my-group",
                "data_source_name": "prom-2",
                "target_type": "asset",
            },
        )(),
    ]

    slo_group_repo = AsyncMock()
    slo_group_repo.get_by_name.return_value = type(
        "Group", (), {"id": group_id, "name": "my-group"}
    )()

    slo_repo = AsyncMock()
    slo_repo.list_by_group_id.return_value = [
        type("SLO", (), {"name": "gen-slo-a", "version": 1})(),
        type("SLO", (), {"name": "gen-slo-b", "version": 1})(),
    ]

    result = await resolve_all_bindings_for_asset(
        asset_id=asset_id,
        group_ids=group_ids,
        binding_repo=binding_repo,
        template_binding_repo=template_binding_repo,
        slo_group_repo=slo_group_repo,
        slo_repo=slo_repo,
    )

    slo_names = [r.slo_name for r in result]
    assert "direct-slo" in slo_names
    assert "gen-slo-a" in slo_names
    assert "gen-slo-b" in slo_names
    assert len(result) == 3

    direct = next(r for r in result if r.slo_name == "direct-slo")
    assert direct.source == "direct_asset"
    assert direct.data_source_name == "prom-1"

    gen_a = next(r for r in result if r.slo_name == "gen-slo-a")
    assert gen_a.source == "template_asset"
    assert gen_a.data_source_name == "prom-2"


async def test_resolve_direct_wins_over_template() -> None:
    """When a direct binding and a template-generated SLO share the same name, direct wins."""
    asset_id = uuid.uuid4()
    group_id = uuid.uuid4()
    group_ids: list[uuid.UUID] = []

    # Direct binding for "shared-slo" pointing at prom-direct
    binding_repo = AsyncMock()
    binding_repo.list_for_asset_evaluation.return_value = [
        type(
            "Binding",
            (),
            {"slo_name": "shared-slo", "data_source_name": "prom-direct", "target_type": "asset"},
        )(),
    ]

    # Template binding whose group generates "shared-slo" pointing at prom-template
    template_binding_repo = AsyncMock()
    template_binding_repo.list_for_asset_evaluation.return_value = [
        type(
            "TemplateBinding",
            (),
            {
                "template_group_name": "overlap-group",
                "data_source_name": "prom-template",
                "target_type": "asset",
            },
        )(),
    ]

    slo_group_repo = AsyncMock()
    slo_group_repo.get_by_name.return_value = type(
        "Group", (), {"id": group_id, "name": "overlap-group"}
    )()

    slo_repo = AsyncMock()
    slo_repo.list_by_group_id.return_value = [
        type("SLO", (), {"name": "shared-slo", "version": 1})(),
    ]

    result = await resolve_all_bindings_for_asset(
        asset_id=asset_id,
        group_ids=group_ids,
        binding_repo=binding_repo,
        template_binding_repo=template_binding_repo,
        slo_group_repo=slo_group_repo,
        slo_repo=slo_repo,
    )

    assert len(result) == 1
    assert result[0].slo_name == "shared-slo"
    assert result[0].source == "direct_asset"
    assert result[0].data_source_name == "prom-direct"
