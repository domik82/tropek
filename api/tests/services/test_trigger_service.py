"""Unit tests for TriggerService."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.modules.quality_gate.dependencies import QualityGateRepos
from app.modules.quality_gate.exceptions import (
    AssetNotFoundError,
    DuplicateEvaluationError,
    EvaluationError,
    SLONotConfiguredError,
)
from app.modules.quality_gate.schemas import AssetTriggerRequest, BatchTriggerRequest, TriggerRequest
from app.modules.quality_gate.trigger_service import TriggerService

_START = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
_END = datetime(2026, 3, 15, 10, 30, 0, tzinfo=UTC)


def _make_request(
    asset_name: str = 'vm-01',
    slo_name: str = 'perf-slo',
    evaluation_name: str = 'nightly',
) -> TriggerRequest:
    return TriggerRequest(
        asset_name=asset_name,
        slo_name=slo_name,
        evaluation_name=evaluation_name,
        period_start=_START,
        period_end=_END,
        variables={},
    )


def _make_asset(name: str = 'vm-01') -> MagicMock:
    asset = MagicMock()
    asset.id = uuid.uuid4()
    asset.name = name
    asset.tags = {'env': 'prod'}
    return asset


def _make_sli_def() -> MagicMock:
    sli = MagicMock()
    sli.name = 'system-sli'
    sli.version = 1
    sli.indicators = {'cpu': 'query'}
    return sli


def _make_slo_def() -> MagicMock:
    slo = MagicMock()
    slo.name = 'perf-slo'
    slo.version = 1
    slo.sli_name = 'system-sli'
    slo.sli_version = None
    return slo


def _make_ds() -> MagicMock:
    ds = MagicMock()
    ds.name = 'prom-1'
    ds.adapter_url = 'http://prom:8081'
    ds.adapter_type = 'prometheus'
    return ds


def _make_evaluation(eval_id: uuid.UUID | None = None, status: str = 'pending') -> MagicMock:
    ev = MagicMock()
    ev.id = eval_id or uuid.uuid4()
    ev.status = status
    return ev


def _make_repos() -> QualityGateRepos:
    """Build a QualityGateRepos with all mock repositories."""
    return QualityGateRepos(
        eval_repo=AsyncMock(),
        annotation_repo=AsyncMock(),
        sli_repo=AsyncMock(),
        trend_repo=AsyncMock(),
        baseline_repo=AsyncMock(),
        asset_repo=AsyncMock(),
        asset_group_repo=AsyncMock(),
        binding_repo=AsyncMock(),
        sli_def_repo=AsyncMock(),
        slo_repo=AsyncMock(),
        ds_repo=AsyncMock(),
        session=AsyncMock(),
    )


def _configure_happy_path(repos: QualityGateRepos) -> None:
    """Set up mocks for a successful single trigger resolution."""
    asset = _make_asset()
    repos.asset_repo.get_by_name.return_value = asset
    # Binding replaces legacy link
    binding = MagicMock()
    binding.slo_name = 'perf-slo'
    binding.data_source_name = 'prom-1'
    repos.binding_repo.find_for_asset.return_value = binding
    repos.sli_def_repo.get_latest.return_value = _make_sli_def()
    repos.slo_repo.get_latest.return_value = _make_slo_def()
    repos.ds_repo.get_by_name.return_value = _make_ds()
    repos.eval_repo.find_duplicate.return_value = None
    ev = _make_evaluation()
    repos.eval_repo.create_pending.return_value = ev


async def test_trigger_single_happy_path() -> None:
    repos = _make_repos()
    _configure_happy_path(repos)
    pool = AsyncMock()

    service = TriggerService(repos, pool)
    result = await service.trigger_single(_make_request())

    assert result.status == 'pending'
    assert result.id is not None
    pool.enqueue_job.assert_awaited_once()


async def test_trigger_single_asset_not_found() -> None:
    repos = _make_repos()
    repos.asset_repo.get_by_name.return_value = None
    pool = AsyncMock()

    service = TriggerService(repos, pool)
    with pytest.raises(AssetNotFoundError, match='asset'):
        await service.trigger_single(_make_request())


async def test_trigger_single_slo_not_configured() -> None:
    repos = _make_repos()
    asset = _make_asset()
    repos.asset_repo.get_by_name.return_value = asset
    repos.binding_repo.find_for_asset.return_value = None
    pool = AsyncMock()

    service = TriggerService(repos, pool)
    with pytest.raises(SLONotConfiguredError):
        await service.trigger_single(_make_request())


async def test_trigger_single_duplicate_in_progress() -> None:
    repos = _make_repos()
    _configure_happy_path(repos)
    existing = _make_evaluation(status='pending')
    repos.eval_repo.find_duplicate.return_value = existing
    pool = AsyncMock()

    service = TriggerService(repos, pool)
    with pytest.raises(DuplicateEvaluationError, match='already in progress'):
        await service.trigger_single(_make_request())


async def test_trigger_single_duplicate_completed() -> None:
    repos = _make_repos()
    _configure_happy_path(repos)
    existing = _make_evaluation(status='completed')
    repos.eval_repo.find_duplicate.return_value = existing
    pool = AsyncMock()

    service = TriggerService(repos, pool)
    with pytest.raises(DuplicateEvaluationError, match='already exists'):
        await service.trigger_single(_make_request())


def _make_asset_trigger_request(
    asset_name: str = 'vm-01',
    evaluation_name: str = 'nightly',
) -> AssetTriggerRequest:
    return AssetTriggerRequest(
        asset_name=asset_name,
        evaluation_name=evaluation_name,
        period_start=_START,
        period_end=_END,
        variables={},
    )


async def test_trigger_asset_happy_path() -> None:
    """Asset trigger resolves all SLOs and creates one evaluation per SLO."""
    repos = _make_repos()
    _configure_happy_path(repos)
    repos.asset_group_repo.list_group_ids_for_asset.return_value = []
    pool = AsyncMock()

    asset = repos.asset_repo.get_by_name.return_value

    async def resolve_side_effect(**kwargs):
        return MagicMock(
            asset_id=asset.id,
            asset_name=asset.name,
            asset_display_name=None,
            asset_tags={},
            asset_variables={},
            slo_name=kwargs['slo_name'],
            slo_version=1,
            sli_name='sys-sli',
            sli_version=1,
            data_source_name='prom-1',
            adapter_type='prometheus',
        )

    service = TriggerService(repos, pool)
    with (
        patch(
            'app.modules.quality_gate.trigger_service.resolve_all_slos_for_asset',
            new_callable=AsyncMock, return_value=['perf-slo', 'latency-slo'],
        ),
        patch(
            'app.modules.quality_gate.trigger_service.resolve_single_trigger',
            side_effect=resolve_side_effect,
        ),
    ):
        result = await service.trigger_asset(_make_asset_trigger_request())

    assert result.status == 'pending'
    assert len(result.evaluation_ids) == 2
    assert result.slo_names == ['perf-slo', 'latency-slo']
    assert pool.enqueue_job.await_count == 2


async def test_trigger_asset_not_found() -> None:
    repos = _make_repos()
    repos.asset_repo.get_by_name.return_value = None
    pool = AsyncMock()

    service = TriggerService(repos, pool)
    with pytest.raises(AssetNotFoundError, match='asset'):
        await service.trigger_asset(_make_asset_trigger_request())


async def test_trigger_asset_no_slos() -> None:
    """Asset with no SLO links/bindings raises EvaluationError."""
    repos = _make_repos()
    asset = _make_asset()
    repos.asset_repo.get_by_name.return_value = asset
    repos.asset_group_repo.list_group_ids_for_asset.return_value = []
    pool = AsyncMock()

    service = TriggerService(repos, pool)
    with (
        patch(
            'app.modules.quality_gate.trigger_service.resolve_all_slos_for_asset',
            return_value=[],
        ),
        pytest.raises(EvaluationError, match='no slo links'),
    ):
        await service.trigger_asset(_make_asset_trigger_request())


async def test_trigger_asset_skips_duplicates() -> None:
    """Existing evaluations are silently skipped, not raised."""
    repos = _make_repos()
    _configure_happy_path(repos)
    repos.asset_group_repo.list_group_ids_for_asset.return_value = []
    existing = _make_evaluation(status='completed')
    repos.eval_repo.find_duplicate.return_value = existing
    pool = AsyncMock()

    service = TriggerService(repos, pool)
    with patch(
        'app.modules.quality_gate.trigger_service.resolve_all_slos_for_asset',
        new_callable=AsyncMock, return_value=['perf-slo'],
    ):
        result = await service.trigger_asset(_make_asset_trigger_request())

    assert result.evaluation_ids == []
    assert result.slo_names == []
    pool.enqueue_job.assert_not_awaited()


async def test_trigger_asset_skips_unresolvable_slos() -> None:
    """SLOs that fail resolution are silently skipped."""
    repos = _make_repos()
    _configure_happy_path(repos)
    repos.asset_group_repo.list_group_ids_for_asset.return_value = []
    pool = AsyncMock()

    async def resolve_side_effect(**kwargs):
        if kwargs['slo_name'] == 'bad-slo':
            raise EvaluationError('slo not found')
        # Return a valid context for other SLOs
        asset = repos.asset_repo.get_by_name.return_value
        return MagicMock(
            asset_id=asset.id,
            asset_name=asset.name,
            asset_display_name=None,
            asset_tags={},
            asset_variables={},
            slo_name=kwargs['slo_name'],
            slo_version=1,
            sli_name='sys-sli',
            sli_version=1,
            data_source_name='prom-1',
            adapter_type='prometheus',
        )

    service = TriggerService(repos, pool)
    with patch(
        'app.modules.quality_gate.trigger_service.resolve_all_slos_for_asset',
        new_callable=AsyncMock, return_value=['bad-slo', 'good-slo'],
    ), patch(
        'app.modules.quality_gate.trigger_service.resolve_single_trigger',
        side_effect=resolve_side_effect,
    ):
        result = await service.trigger_asset(_make_asset_trigger_request())

    assert len(result.evaluation_ids) == 1
    assert result.slo_names == ['good-slo']


async def test_trigger_batch_group_not_found() -> None:
    repos = _make_repos()
    repos.asset_group_repo.get_by_name.return_value = None
    pool = AsyncMock()

    request = BatchTriggerRequest(
        group_name='nonexistent',
        evaluation_name='nightly',
        period_start=_START,
        period_end=_END,
    )
    service = TriggerService(repos, pool)
    with pytest.raises(AssetNotFoundError, match='asset group'):
        await service.trigger_batch(request)
