"""Unit tests for resolve_all_slos_for_asset."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

from app.modules.quality_gate.trigger import resolve_all_slos_for_asset


def _make_link(slo_name: str) -> MagicMock:
    link = MagicMock()
    link.slo_name = slo_name
    return link


def _make_binding(slo_name: str) -> MagicMock:
    binding = MagicMock()
    binding.slo_name = slo_name
    return binding


async def test_collects_from_asset_slo_links() -> None:
    """Direct AssetSLOLinks are included."""
    slo_link_repo = AsyncMock()
    slo_link_repo.list_by_asset.return_value = [_make_link('slo-a'), _make_link('slo-b')]
    group_link_repo = AsyncMock()
    group_link_repo.list_by_group.return_value = []
    binding_repo = AsyncMock()
    binding_repo.list_for_asset_evaluation.return_value = []

    result = await resolve_all_slos_for_asset(
        asset_id=uuid.uuid4(),
        slo_link_repo=slo_link_repo,
        group_link_repo=group_link_repo,
        binding_repo=binding_repo,
        group_ids=[],
    )

    assert result == ['slo-a', 'slo-b']


async def test_collects_from_group_slo_links() -> None:
    """AssetGroupSLOLinks from groups the asset belongs to are included."""
    group_id = uuid.uuid4()
    slo_link_repo = AsyncMock()
    slo_link_repo.list_by_asset.return_value = []
    group_link_repo = AsyncMock()
    group_link_repo.list_by_group.return_value = [_make_link('group-slo')]
    binding_repo = AsyncMock()
    binding_repo.list_for_asset_evaluation.return_value = []

    result = await resolve_all_slos_for_asset(
        asset_id=uuid.uuid4(),
        slo_link_repo=slo_link_repo,
        group_link_repo=group_link_repo,
        binding_repo=binding_repo,
        group_ids=[group_id],
    )

    assert result == ['group-slo']
    group_link_repo.list_by_group.assert_awaited_once_with(group_id)


async def test_collects_from_slo_bindings() -> None:
    """SLOBindings (direct + via group) are included."""
    slo_link_repo = AsyncMock()
    slo_link_repo.list_by_asset.return_value = []
    group_link_repo = AsyncMock()
    group_link_repo.list_by_group.return_value = []
    binding_repo = AsyncMock()
    binding_repo.list_for_asset_evaluation.return_value = [_make_binding('binding-slo')]

    result = await resolve_all_slos_for_asset(
        asset_id=uuid.uuid4(),
        slo_link_repo=slo_link_repo,
        group_link_repo=group_link_repo,
        binding_repo=binding_repo,
        group_ids=[],
    )

    assert result == ['binding-slo']


async def test_deduplicates_across_sources() -> None:
    """Same SLO name from multiple sources appears only once."""
    slo_link_repo = AsyncMock()
    slo_link_repo.list_by_asset.return_value = [_make_link('shared-slo')]
    group_link_repo = AsyncMock()
    group_link_repo.list_by_group.return_value = [_make_link('shared-slo')]
    binding_repo = AsyncMock()
    binding_repo.list_for_asset_evaluation.return_value = [_make_binding('shared-slo')]

    result = await resolve_all_slos_for_asset(
        asset_id=uuid.uuid4(),
        slo_link_repo=slo_link_repo,
        group_link_repo=group_link_repo,
        binding_repo=binding_repo,
        group_ids=[uuid.uuid4()],
    )

    assert result == ['shared-slo']


async def test_all_three_sources_combined() -> None:
    """SLOs from all 3 sources are collected and sorted."""
    slo_link_repo = AsyncMock()
    slo_link_repo.list_by_asset.return_value = [_make_link('c-direct')]
    group_link_repo = AsyncMock()
    group_link_repo.list_by_group.return_value = [_make_link('a-group')]
    binding_repo = AsyncMock()
    binding_repo.list_for_asset_evaluation.return_value = [_make_binding('b-binding')]

    result = await resolve_all_slos_for_asset(
        asset_id=uuid.uuid4(),
        slo_link_repo=slo_link_repo,
        group_link_repo=group_link_repo,
        binding_repo=binding_repo,
        group_ids=[uuid.uuid4()],
    )

    assert result == ['a-group', 'b-binding', 'c-direct']


async def test_no_sources_returns_empty() -> None:
    """No links from any source returns empty list."""
    slo_link_repo = AsyncMock()
    slo_link_repo.list_by_asset.return_value = []
    group_link_repo = AsyncMock()
    binding_repo = AsyncMock()
    binding_repo.list_for_asset_evaluation.return_value = []

    result = await resolve_all_slos_for_asset(
        asset_id=uuid.uuid4(),
        slo_link_repo=slo_link_repo,
        group_link_repo=group_link_repo,
        binding_repo=binding_repo,
        group_ids=[],
    )

    assert result == []


async def test_multiple_groups() -> None:
    """SLO links from multiple groups are all collected."""
    g1, g2 = uuid.uuid4(), uuid.uuid4()
    slo_link_repo = AsyncMock()
    slo_link_repo.list_by_asset.return_value = []

    async def group_links_side_effect(gid: uuid.UUID) -> list[MagicMock]:
        if gid == g1:
            return [_make_link('slo-from-g1')]
        return [_make_link('slo-from-g2')]

    group_link_repo = AsyncMock()
    group_link_repo.list_by_group.side_effect = group_links_side_effect
    binding_repo = AsyncMock()
    binding_repo.list_for_asset_evaluation.return_value = []

    result = await resolve_all_slos_for_asset(
        asset_id=uuid.uuid4(),
        slo_link_repo=slo_link_repo,
        group_link_repo=group_link_repo,
        binding_repo=binding_repo,
        group_ids=[g1, g2],
    )

    assert result == ['slo-from-g1', 'slo-from-g2']
