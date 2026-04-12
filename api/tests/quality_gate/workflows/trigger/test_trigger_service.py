"""Unit tests for TriggerService."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tropek.modules.common.exceptions import NotFoundError
from tropek.modules.quality_gate.schemas import EvaluateSingleRequest
from tropek.modules.quality_gate.shared.dependencies import QualityGateRepos
from tropek.modules.quality_gate.shared.exceptions import EvaluationError
from tropek.modules.quality_gate.workflows.trigger.trigger_service import TriggerService

_START = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
_END = datetime(2026, 3, 15, 10, 30, 0, tzinfo=UTC)


def _make_asset(name: str = 'vm-01') -> MagicMock:
    asset = MagicMock()
    asset.id = uuid.uuid4()
    asset.name = name
    asset.tags = {'env': 'prod'}
    return asset


def _make_evaluation(eval_id: uuid.UUID | None = None, status: str = 'pending') -> MagicMock:
    ev = MagicMock()
    ev.id = eval_id or uuid.uuid4()
    ev.status = status
    return ev


def _make_repos() -> QualityGateRepos:
    """Build a QualityGateRepos with all mock repositories."""
    return QualityGateRepos(
        eval_repo=AsyncMock(),
        eval_run_repo=AsyncMock(),
        annotation_repo=AsyncMock(),
        sli_repo=AsyncMock(),
        trend_repo=AsyncMock(),
        baseline_repo=AsyncMock(),
        asset_repo=AsyncMock(),
        asset_group_repo=AsyncMock(),
        assignment_repo=AsyncMock(),
        sli_def_repo=AsyncMock(),
        slo_repo=AsyncMock(),
        ds_repo=AsyncMock(),
        session=AsyncMock(),
    )


# -- trigger_evaluate ----------------------------------------------------------


def _make_evaluate_request(
    asset_name: str = 'vm-01',
    eval_name: str = 'nightly',
) -> EvaluateSingleRequest:
    return EvaluateSingleRequest(
        asset_name=asset_name,
        eval_name=eval_name,
        period_start=_START,
        period_end=_END,
    )


async def test_trigger_evaluate_happy_path() -> None:
    """trigger_evaluate resolves SLOs, creates run + children, enqueues jobs."""
    repos = _make_repos()
    asset = _make_asset()
    repos.asset_repo.get_by_name.return_value = asset
    repos.asset_group_repo.list_group_ids_for_asset.return_value = []

    run = MagicMock()
    run.id = uuid.uuid4()
    repos.eval_run_repo.create.return_value = run

    slo_ev = _make_evaluation()
    repos.eval_repo.create_pending.return_value = slo_ev
    pool = AsyncMock()

    async def resolve_side_effect(**kwargs):
        return MagicMock(
            asset_id=asset.id,
            asset_name=asset.name,
            asset_display_name=None,
            asset_tags={},
            asset_variables={},
            slo_name=kwargs['slo_name'],
            slo_version=1,
            slo_definition_id=uuid.uuid4(),
            sli_name='sys-sli',
            sli_version=1,
            sli_definition_id=None,
            data_source_name='prom-1',
            adapter_type='prometheus',
        )

    service = TriggerService(repos, pool)
    with (
        patch(
            'tropek.modules.quality_gate.workflows.trigger.trigger_service.resolve_all_slos_for_asset',
            new_callable=AsyncMock,
            return_value=['perf-slo', 'latency-slo'],
        ),
        patch(
            'tropek.modules.quality_gate.workflows.trigger.trigger_service.resolve_single_trigger',
            side_effect=resolve_side_effect,
        ),
    ):
        result = await service.trigger_evaluate(_make_evaluate_request())

    assert result.evaluation_id == run.id
    assert len(result.slo_evaluation_ids) == 2
    repos.eval_run_repo.create.assert_awaited_once()
    assert pool.enqueue_job.await_count == 2


async def test_trigger_evaluate_asset_not_found() -> None:
    repos = _make_repos()
    repos.asset_repo.get_by_name.return_value = None
    pool = AsyncMock()

    service = TriggerService(repos, pool)
    with pytest.raises(NotFoundError, match='asset'):
        await service.trigger_evaluate(_make_evaluate_request())


async def test_trigger_evaluate_no_slos() -> None:
    """No SLO assignments raises EvaluationError."""
    repos = _make_repos()
    asset = _make_asset()
    repos.asset_repo.get_by_name.return_value = asset
    repos.asset_group_repo.list_group_ids_for_asset.return_value = []
    pool = AsyncMock()

    service = TriggerService(repos, pool)
    with (
        patch(
            'tropek.modules.quality_gate.workflows.trigger.trigger_service.resolve_all_slos_for_asset',
            new_callable=AsyncMock,
            return_value=[],
        ),
        pytest.raises(EvaluationError, match='no slo assignments'),
    ):
        await service.trigger_evaluate(_make_evaluate_request())


async def test_trigger_evaluate_skips_unresolvable_slos() -> None:
    """SLOs that fail resolution are skipped; remaining are still created."""
    repos = _make_repos()
    asset = _make_asset()
    repos.asset_repo.get_by_name.return_value = asset
    repos.asset_group_repo.list_group_ids_for_asset.return_value = []

    run = MagicMock()
    run.id = uuid.uuid4()
    repos.eval_run_repo.create.return_value = run

    slo_ev = _make_evaluation()
    repos.eval_repo.create_pending.return_value = slo_ev
    pool = AsyncMock()

    async def resolve_side_effect(**kwargs):
        if kwargs['slo_name'] == 'bad-slo':
            raise EvaluationError('slo not found')
        return MagicMock(
            asset_id=asset.id,
            asset_name=asset.name,
            asset_display_name=None,
            asset_tags={},
            asset_variables={},
            slo_name=kwargs['slo_name'],
            slo_version=1,
            slo_definition_id=uuid.uuid4(),
            sli_name='sys-sli',
            sli_version=1,
            sli_definition_id=None,
            data_source_name='prom-1',
            adapter_type='prometheus',
        )

    service = TriggerService(repos, pool)
    with (
        patch(
            'tropek.modules.quality_gate.workflows.trigger.trigger_service.resolve_all_slos_for_asset',
            new_callable=AsyncMock,
            return_value=['bad-slo', 'good-slo'],
        ),
        patch(
            'tropek.modules.quality_gate.workflows.trigger.trigger_service.resolve_single_trigger',
            side_effect=resolve_side_effect,
        ),
    ):
        result = await service.trigger_evaluate(_make_evaluate_request())

    assert len(result.slo_evaluation_ids) == 1
    assert pool.enqueue_job.await_count == 1


async def test_trigger_evaluate_enqueues_per_child() -> None:
    """One job is enqueued per SLO evaluation child."""
    repos = _make_repos()
    asset = _make_asset()
    repos.asset_repo.get_by_name.return_value = asset
    repos.asset_group_repo.list_group_ids_for_asset.return_value = []

    run = MagicMock()
    run.id = uuid.uuid4()
    repos.eval_run_repo.create.return_value = run

    eval_ids = [uuid.uuid4() for _ in range(3)]
    call_count = 0

    async def create_pending_side_effect(params):
        nonlocal call_count
        ev = MagicMock()
        ev.id = eval_ids[call_count]
        call_count += 1
        return ev

    repos.eval_repo.create_pending.side_effect = create_pending_side_effect
    pool = AsyncMock()

    async def resolve_side_effect(**kwargs):
        return MagicMock(
            asset_id=asset.id,
            asset_name=asset.name,
            asset_display_name=None,
            asset_tags={},
            asset_variables={},
            slo_name=kwargs['slo_name'],
            slo_version=1,
            slo_definition_id=uuid.uuid4(),
            sli_name='sys-sli',
            sli_version=1,
            sli_definition_id=None,
            data_source_name='prom-1',
            adapter_type='prometheus',
        )

    service = TriggerService(repos, pool)
    with (
        patch(
            'tropek.modules.quality_gate.workflows.trigger.trigger_service.resolve_all_slos_for_asset',
            new_callable=AsyncMock,
            return_value=['slo-a', 'slo-b', 'slo-c'],
        ),
        patch(
            'tropek.modules.quality_gate.workflows.trigger.trigger_service.resolve_single_trigger',
            side_effect=resolve_side_effect,
        ),
    ):
        result = await service.trigger_evaluate(_make_evaluate_request())

    assert len(result.slo_evaluation_ids) == 3
    assert pool.enqueue_job.await_count == 3
    enqueued_ids = [call.args[1] for call in pool.enqueue_job.await_args_list]
    assert enqueued_ids == [str(eid) for eid in eval_ids]
