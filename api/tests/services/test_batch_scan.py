"""Tests for TriggerService._scan_batch_members conflict detection."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.modules.quality_gate.dependencies import QualityGateRepos
from app.modules.quality_gate.exceptions import EvaluationError
from app.modules.quality_gate.schemas import BatchTriggerRequest
from app.modules.quality_gate.trigger import TriggerContext
from app.modules.quality_gate.trigger_service import TriggerService

_START = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
_END = datetime(2026, 3, 15, 10, 30, 0, tzinfo=UTC)


def _make_repos() -> QualityGateRepos:
    return QualityGateRepos(
        eval_repo=AsyncMock(),
        annotation_repo=AsyncMock(),
        sli_repo=AsyncMock(),
        trend_repo=AsyncMock(),
        baseline_repo=AsyncMock(),
        asset_repo=AsyncMock(),
        asset_group_repo=AsyncMock(),
        slo_link_repo=AsyncMock(),
        group_link_repo=AsyncMock(),
        binding_repo=AsyncMock(),
        sli_def_repo=AsyncMock(),
        slo_repo=AsyncMock(),
        ds_repo=AsyncMock(),
        session=AsyncMock(),
    )


def _make_batch_request() -> BatchTriggerRequest:
    return BatchTriggerRequest(
        group_name="linux-boxes",
        evaluation_name="nightly",
        period_start=_START,
        period_end=_END,
    )


def _make_member(asset_name: str) -> MagicMock:
    member = MagicMock()
    member.asset_name = asset_name
    return member


def _make_asset(name: str) -> MagicMock:
    asset = MagicMock()
    asset.id = uuid.uuid4()
    asset.name = name
    return asset


def _make_link(slo_name: str) -> MagicMock:
    link = MagicMock()
    link.slo_name = slo_name
    return link


def _make_trigger_context(asset_name: str, slo_name: str) -> TriggerContext:
    return TriggerContext(
        asset_id=uuid.uuid4(),
        asset_name=asset_name,
        asset_display_name=None,
        asset_tags={},
        asset_variables={},
        slo_name=slo_name,
        slo_version=1,
        sli_name="system-sli",
        sli_version=1,
        data_source_name="prom-1",
        adapter_url="http://prom:8081",
        adapter_type="prometheus",
        indicators={"cpu": "query"},
    )


async def test_scan_no_conflicts() -> None:
    """All batch members resolve cleanly with no duplicates."""
    repos = _make_repos()
    asset = _make_asset("vm-01")
    repos.asset_repo.get_by_name.return_value = asset
    repos.slo_link_repo.list_by_asset.return_value = [_make_link("perf-slo")]
    repos.eval_repo.find_duplicate.return_value = None

    ctx = _make_trigger_context("vm-01", "perf-slo")
    service = TriggerService(repos, AsyncMock())

    with patch(
        "app.modules.quality_gate.trigger_service.resolve_single_trigger",
        return_value=ctx,
    ):
        resolved, conflicts = await service._scan_batch_members(
            members=[_make_member("vm-01")],
            request=_make_batch_request(),
            group_links=[],
        )

    assert len(resolved) == 1
    assert len(conflicts) == 0
    assert resolved[0][1] == "vm-01"


async def test_scan_detects_duplicate() -> None:
    """Existing evaluation for same asset/SLO/period reports as conflict."""
    repos = _make_repos()
    asset = _make_asset("vm-01")
    repos.asset_repo.get_by_name.return_value = asset
    repos.slo_link_repo.list_by_asset.return_value = [_make_link("perf-slo")]

    existing = MagicMock()
    existing.status = "completed"
    repos.eval_repo.find_duplicate.return_value = existing

    ctx = _make_trigger_context("vm-01", "perf-slo")
    service = TriggerService(repos, AsyncMock())

    with patch(
        "app.modules.quality_gate.trigger_service.resolve_single_trigger",
        return_value=ctx,
    ):
        resolved, conflicts = await service._scan_batch_members(
            members=[_make_member("vm-01")],
            request=_make_batch_request(),
            group_links=[],
        )

    assert len(resolved) == 0
    assert len(conflicts) == 1
    assert conflicts[0].asset_name == "vm-01"
    assert conflicts[0].existing_status == "completed"


async def test_scan_skips_missing_asset() -> None:
    """Asset that does not exist in the DB is silently skipped."""
    repos = _make_repos()
    repos.asset_repo.get_by_name.return_value = None

    service = TriggerService(repos, AsyncMock())
    resolved, conflicts = await service._scan_batch_members(
        members=[_make_member("missing-asset")],
        request=_make_batch_request(),
        group_links=[],
    )

    assert len(resolved) == 0
    assert len(conflicts) == 0


async def test_scan_empty_batch() -> None:
    """Empty batch members list returns empty results."""
    repos = _make_repos()
    service = TriggerService(repos, AsyncMock())
    resolved, conflicts = await service._scan_batch_members(
        members=[],
        request=_make_batch_request(),
        group_links=[],
    )

    assert resolved == []
    assert conflicts == []


async def test_scan_skips_unresolvable_trigger() -> None:
    """If resolve_single_trigger raises EvaluationError, that SLO is skipped."""
    repos = _make_repos()
    asset = _make_asset("vm-01")
    repos.asset_repo.get_by_name.return_value = asset
    repos.slo_link_repo.list_by_asset.return_value = [_make_link("bad-slo")]

    service = TriggerService(repos, AsyncMock())

    with patch(
        "app.modules.quality_gate.trigger_service.resolve_single_trigger",
        side_effect=EvaluationError("slo not found"),
    ):
        resolved, conflicts = await service._scan_batch_members(
            members=[_make_member("vm-01")],
            request=_make_batch_request(),
            group_links=[],
        )

    assert len(resolved) == 0
    assert len(conflicts) == 0


async def test_scan_merges_group_links() -> None:
    """Group-level SLO links are used when asset has no direct link for that SLO."""
    repos = _make_repos()
    asset = _make_asset("vm-01")
    repos.asset_repo.get_by_name.return_value = asset
    repos.slo_link_repo.list_by_asset.return_value = []  # no asset-level links
    repos.eval_repo.find_duplicate.return_value = None

    group_link = _make_link("group-slo")
    ctx = _make_trigger_context("vm-01", "group-slo")
    service = TriggerService(repos, AsyncMock())

    with patch(
        "app.modules.quality_gate.trigger_service.resolve_single_trigger",
        return_value=ctx,
    ):
        resolved, _conflicts = await service._scan_batch_members(
            members=[_make_member("vm-01")],
            request=_make_batch_request(),
            group_links=[group_link],
        )

    assert len(resolved) == 1
    assert resolved[0][0].slo_name == "group-slo"
