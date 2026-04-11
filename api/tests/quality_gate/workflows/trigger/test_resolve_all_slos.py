"""Unit tests for resolve_all_slos_for_asset (assignment_repo source)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

from tropek.modules.assignments.repository import ResolvedAssignment
from tropek.modules.quality_gate.workflows.trigger.trigger_resolver import resolve_all_slos_for_asset


def _make_resolved(slo_name: str, source: str = 'direct_asset') -> ResolvedAssignment:
    return ResolvedAssignment(
        slo_name=slo_name,
        slo_definition_id=uuid.uuid4(),
        data_source_id=uuid.uuid4(),
        comparison_rules=None,
        source=source,
    )


async def test_collects_from_slo_assignments() -> None:
    """Assignments (direct + via group) are returned sorted."""
    assignment_repo = AsyncMock()
    assignment_repo.resolve_for_asset.return_value = [
        _make_resolved('slo-b'),
        _make_resolved('slo-a'),
    ]

    result = await resolve_all_slos_for_asset(
        asset_id=uuid.uuid4(),
        assignment_repo=assignment_repo,
        group_ids=[],
    )

    assert result == ['slo-a', 'slo-b']


async def test_deduplicates_same_slo_from_multiple_assignments() -> None:
    """The assignment_repo already deduplicates by precedence; result has distinct names."""
    assignment_repo = AsyncMock()
    # assignment_repo DISTINCT ON slo_name ensures only one row per slo_name
    assignment_repo.resolve_for_asset.return_value = [
        _make_resolved('shared-slo'),
    ]

    result = await resolve_all_slos_for_asset(
        asset_id=uuid.uuid4(),
        assignment_repo=assignment_repo,
        group_ids=[uuid.uuid4()],
    )

    assert result == ['shared-slo']


async def test_no_assignments_returns_empty() -> None:
    assignment_repo = AsyncMock()
    assignment_repo.resolve_for_asset.return_value = []

    result = await resolve_all_slos_for_asset(
        asset_id=uuid.uuid4(),
        assignment_repo=assignment_repo,
        group_ids=[],
    )

    assert result == []


async def test_passes_group_ids_to_repo() -> None:
    """group_ids are forwarded to the assignment repo."""
    group_ids = [uuid.uuid4(), uuid.uuid4()]
    asset_id = uuid.uuid4()
    assignment_repo = AsyncMock()
    assignment_repo.resolve_for_asset.return_value = []

    await resolve_all_slos_for_asset(
        asset_id=asset_id,
        assignment_repo=assignment_repo,
        group_ids=group_ids,
    )

    assignment_repo.resolve_for_asset.assert_awaited_once_with(asset_id, group_ids)
