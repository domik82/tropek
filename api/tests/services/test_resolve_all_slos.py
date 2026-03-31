"""Unit tests for resolve_all_slos_for_asset (single slo_bindings source)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

from app.modules.quality_gate.trigger import resolve_all_slos_for_asset


def _make_binding(slo_name: str) -> MagicMock:
    b = MagicMock()
    b.slo_name = slo_name
    return b


async def test_collects_from_slo_bindings() -> None:
    """SLOBindings (direct + via group) are returned sorted."""
    binding_repo = AsyncMock()
    binding_repo.list_for_asset_evaluation.return_value = [
        _make_binding('slo-b'),
        _make_binding('slo-a'),
    ]

    result = await resolve_all_slos_for_asset(
        asset_id=uuid.uuid4(),
        binding_repo=binding_repo,
        group_ids=[],
    )

    assert result == ['slo-a', 'slo-b']


async def test_deduplicates_same_slo_from_multiple_bindings() -> None:
    """Same SLO name appearing twice is deduplicated."""
    binding_repo = AsyncMock()
    binding_repo.list_for_asset_evaluation.return_value = [
        _make_binding('shared-slo'),
        _make_binding('shared-slo'),
    ]

    result = await resolve_all_slos_for_asset(
        asset_id=uuid.uuid4(),
        binding_repo=binding_repo,
        group_ids=[uuid.uuid4()],
    )

    assert result == ['shared-slo']


async def test_no_bindings_returns_empty() -> None:
    binding_repo = AsyncMock()
    binding_repo.list_for_asset_evaluation.return_value = []

    result = await resolve_all_slos_for_asset(
        asset_id=uuid.uuid4(),
        binding_repo=binding_repo,
        group_ids=[],
    )

    assert result == []


async def test_passes_group_ids_to_repo() -> None:
    """group_ids are forwarded to the binding repo."""
    group_ids = [uuid.uuid4(), uuid.uuid4()]
    asset_id = uuid.uuid4()
    binding_repo = AsyncMock()
    binding_repo.list_for_asset_evaluation.return_value = []

    await resolve_all_slos_for_asset(
        asset_id=asset_id,
        binding_repo=binding_repo,
        group_ids=group_ids,
    )

    binding_repo.list_for_asset_evaluation.assert_awaited_once_with(asset_id, group_ids)
