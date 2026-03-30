"""Tests for TriggerService.trigger_batch conflict detection and unified SLO resolution."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.modules.quality_gate.dependencies import QualityGateRepos
from app.modules.quality_gate.exceptions import DuplicateEvaluationError, EvaluationError
from app.modules.quality_gate.schemas import BatchTriggerRequest
from app.modules.quality_gate.trigger import TriggerContext
from app.modules.quality_gate.trigger_service import TriggerService

_START = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
_END = datetime(2026, 3, 15, 10, 30, 0, tzinfo=UTC)


def _make_repos() -> QualityGateRepos:
    session = AsyncMock()
    session.add = MagicMock()
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
        session=session,
    )


def _make_batch_request() -> BatchTriggerRequest:
    return BatchTriggerRequest(
        group_name='linux-boxes',
        evaluation_name='nightly',
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


def _make_group(members: list[MagicMock]) -> MagicMock:
    group = MagicMock()
    group.id = uuid.uuid4()
    group.members = members
    return group


def _make_trigger_context(asset_name: str, slo_name: str) -> TriggerContext:
    return TriggerContext(
        asset_id=uuid.uuid4(),
        asset_name=asset_name,
        asset_display_name=None,
        asset_tags={},
        asset_variables={},
        slo_name=slo_name,
        slo_version=1,
        sli_name='system-sli',
        sli_version=1,
        data_source_name='prom-1',
        adapter_url='http://prom:8081',
        adapter_type='prometheus',
        indicators={'cpu': 'query'},
    )


async def test_batch_no_conflicts() -> None:
    """All batch members resolve cleanly with no duplicates."""
    repos = _make_repos()
    asset = _make_asset('vm-01')
    group = _make_group([_make_member('vm-01')])
    repos.asset_group_repo.get_by_name.return_value = group
    repos.asset_repo.get_by_name.return_value = asset
    repos.asset_group_repo.list_group_ids_for_asset.return_value = [group.id]
    repos.eval_repo.find_duplicate.return_value = None

    ctx = _make_trigger_context('vm-01', 'perf-slo')
    ev = MagicMock()
    ev.id = uuid.uuid4()
    repos.eval_repo.create_pending.return_value = ev
    pool = AsyncMock()

    service = TriggerService(repos, pool)
    with (
        patch(
            'app.modules.quality_gate.trigger_service.resolve_all_slos_for_asset',
            new_callable=AsyncMock, return_value=['perf-slo'],
        ),
        patch(
            'app.modules.quality_gate.trigger_service.resolve_single_trigger',
            new_callable=AsyncMock, return_value=ctx,
        ),
    ):
        result = await service.trigger_batch(_make_batch_request())

    assert len(result.evaluation_ids) == 1
    assert result.status == 'pending'
    pool.enqueue_job.assert_awaited_once()


async def test_batch_detects_duplicate() -> None:
    """Existing evaluation for same asset/SLO/period raises DuplicateEvaluationError."""
    repos = _make_repos()
    asset = _make_asset('vm-01')
    group = _make_group([_make_member('vm-01')])
    repos.asset_group_repo.get_by_name.return_value = group
    repos.asset_repo.get_by_name.return_value = asset
    repos.asset_group_repo.list_group_ids_for_asset.return_value = [group.id]

    existing = MagicMock()
    existing.status = 'completed'
    repos.eval_repo.find_duplicate.return_value = existing

    ctx = _make_trigger_context('vm-01', 'perf-slo')
    pool = AsyncMock()

    service = TriggerService(repos, pool)
    with (
        patch(
            'app.modules.quality_gate.trigger_service.resolve_all_slos_for_asset',
            new_callable=AsyncMock, return_value=['perf-slo'],
        ),
        patch(
            'app.modules.quality_gate.trigger_service.resolve_single_trigger',
            new_callable=AsyncMock, return_value=ctx,
        ),
        pytest.raises(DuplicateEvaluationError, match='batch contains duplicate'),
    ):
        await service.trigger_batch(_make_batch_request())


async def test_batch_skips_missing_asset() -> None:
    """Asset that does not exist in the DB is silently skipped."""
    repos = _make_repos()
    group = _make_group([_make_member('missing-asset')])
    repos.asset_group_repo.get_by_name.return_value = group
    repos.asset_repo.get_by_name.return_value = None

    ev = MagicMock()
    ev.id = uuid.uuid4()
    repos.eval_repo.create_pending.return_value = ev
    pool = AsyncMock()

    service = TriggerService(repos, pool)
    result = await service.trigger_batch(_make_batch_request())

    assert result.evaluation_ids == []


async def test_batch_empty_members() -> None:
    """Empty batch members list returns empty results."""
    repos = _make_repos()
    group = _make_group([])
    repos.asset_group_repo.get_by_name.return_value = group

    ev = MagicMock()
    ev.id = uuid.uuid4()
    repos.eval_repo.create_pending.return_value = ev
    pool = AsyncMock()

    service = TriggerService(repos, pool)
    result = await service.trigger_batch(_make_batch_request())

    assert result.evaluation_ids == []


async def test_batch_skips_unresolvable_trigger() -> None:
    """If resolve_single_trigger raises EvaluationError, that SLO is skipped."""
    repos = _make_repos()
    asset = _make_asset('vm-01')
    group = _make_group([_make_member('vm-01')])
    repos.asset_group_repo.get_by_name.return_value = group
    repos.asset_repo.get_by_name.return_value = asset
    repos.asset_group_repo.list_group_ids_for_asset.return_value = []

    ev = MagicMock()
    ev.id = uuid.uuid4()
    repos.eval_repo.create_pending.return_value = ev
    pool = AsyncMock()

    service = TriggerService(repos, pool)
    with (
        patch(
            'app.modules.quality_gate.trigger_service.resolve_all_slos_for_asset',
            new_callable=AsyncMock, return_value=['bad-slo'],
        ),
        patch(
            'app.modules.quality_gate.trigger_service.resolve_single_trigger',
            new_callable=AsyncMock, side_effect=EvaluationError('slo not found'),
        ),
    ):
        result = await service.trigger_batch(_make_batch_request())

    assert result.evaluation_ids == []


async def test_batch_uses_unified_resolution() -> None:
    """Batch trigger now uses resolve_all_slos_for_asset which includes SLOBindings."""
    repos = _make_repos()
    asset = _make_asset('vm-01')
    group = _make_group([_make_member('vm-01')])
    repos.asset_group_repo.get_by_name.return_value = group
    repos.asset_repo.get_by_name.return_value = asset
    repos.asset_group_repo.list_group_ids_for_asset.return_value = [group.id]
    repos.eval_repo.find_duplicate.return_value = None

    ev = MagicMock()
    ev.id = uuid.uuid4()
    repos.eval_repo.create_pending.return_value = ev
    pool = AsyncMock()

    resolve_all_mock = AsyncMock(return_value=['direct-slo', 'binding-slo'])
    ctx_direct = _make_trigger_context('vm-01', 'direct-slo')
    ctx_binding = _make_trigger_context('vm-01', 'binding-slo')

    async def resolve_side_effect(**kwargs):
        if kwargs['slo_name'] == 'direct-slo':
            return ctx_direct
        return ctx_binding

    service = TriggerService(repos, pool)
    with (
        patch(
            'app.modules.quality_gate.trigger_service.resolve_all_slos_for_asset',
            resolve_all_mock,
        ),
        patch(
            'app.modules.quality_gate.trigger_service.resolve_single_trigger',
            side_effect=resolve_side_effect,
        ),
    ):
        result = await service.trigger_batch(_make_batch_request())

    assert len(result.evaluation_ids) == 2
    resolve_all_mock.assert_awaited_once()
