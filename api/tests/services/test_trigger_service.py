"""Unit tests for TriggerService."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.modules.quality_gate.dependencies import QualityGateRepos
from app.modules.quality_gate.exceptions import (
    AssetNotFoundError,
    DuplicateEvaluationError,
    SLONotConfiguredError,
)
from app.modules.quality_gate.schemas import TriggerRequest
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


def _make_link(slo_name: str = 'perf-slo') -> MagicMock:
    link = MagicMock()
    link.slo_name = slo_name
    link.sli_name = 'system-sli'
    link.data_source_name = 'prom-1'
    return link


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
    slo.sli_name = None
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
        slo_link_repo=AsyncMock(),
        group_link_repo=AsyncMock(),
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
    repos.slo_link_repo.list_by_asset.return_value = [_make_link()]
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
    repos.slo_link_repo.list_by_asset.return_value = []  # no links
    repos.binding_repo.find_for_asset.return_value = None  # no bindings either
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


async def test_trigger_batch_group_not_found() -> None:
    repos = _make_repos()
    repos.asset_group_repo.get_by_name.return_value = None
    pool = AsyncMock()

    from app.modules.quality_gate.schemas import BatchTriggerRequest

    request = BatchTriggerRequest(
        group_name='nonexistent',
        evaluation_name='nightly',
        period_start=_START,
        period_end=_END,
    )
    service = TriggerService(repos, pool)
    with pytest.raises(AssetNotFoundError, match='asset group'):
        await service.trigger_batch(request)
