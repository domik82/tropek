"""Unit tests for the refetch service (repositories mocked)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from structlog.testing import capture_logs
from tropek.modules.common.exceptions import ConflictError
from tropek.modules.quality_gate.schemas.refetch import RefetchRequest, RefetchRunRequest
from tropek.modules.quality_gate.shared.dependencies import QualityGateRepos
from tropek.modules.quality_gate.shared.params import RefetchScope
from tropek.modules.quality_gate.workflows.refetch.refetch_service import refetch, refetch_run

_DAY_ONE = datetime(2026, 10, 15, tzinfo=UTC)
_DAY_TWO = _DAY_ONE + timedelta(days=1)
_CHANGE_POINT_REPO = 'tropek.modules.quality_gate.workflows.refetch.refetch_service.ChangePointRepository'


def _make_row(
    *,
    run_id: uuid.UUID,
    status: str = 'completed',
    slo_name: str = 'slo-a',
    period_start: datetime = _DAY_ONE,
    asset_id: uuid.UUID | None = None,
) -> MagicMock:
    row = MagicMock()
    row.id = uuid.uuid4()
    row.evaluation_id = run_id
    row.asset_id = asset_id or uuid.uuid4()
    row.slo_name = slo_name
    row.period_start = period_start
    row.status = status
    row.result = 'pass' if status == 'completed' else None
    return row


def _make_repos(rows: list[MagicMock]) -> QualityGateRepos:
    repos = QualityGateRepos(
        eval_repo=AsyncMock(),
        eval_run_repo=AsyncMock(),
        annotation_repo=AsyncMock(),
        category_repo=AsyncMock(),
        sli_repo=AsyncMock(),
        trend_repo=AsyncMock(),
        heatmap_repo=AsyncMock(),
        baseline_repo=AsyncMock(),
        asset_repo=AsyncMock(),
        asset_group_repo=AsyncMock(),
        assignment_repo=AsyncMock(),
        sli_def_repo=AsyncMock(),
        slo_repo=AsyncMock(),
        ds_repo=AsyncMock(),
        session=AsyncMock(),
        trend_cache=AsyncMock(),
    )
    repos.asset_repo.get_by_name.return_value = MagicMock(id=uuid.uuid4())
    repos.eval_repo.list_for_refetch.return_value = rows
    repos.eval_repo.reset_for_refetch.side_effect = lambda eval_ids, **_kwargs: list(eval_ids)
    return repos


def _make_request(**overrides: object) -> RefetchRequest:
    return RefetchRequest.model_validate(
        {
            'asset_name': 'asset-a',
            'evaluation_name': 'daily',
            'from': _DAY_ONE,
            'to': _DAY_TWO,
            'reason': 'adapter outage',
            **overrides,
        }
    )


def _assert_nothing_written(repos: QualityGateRepos, pool: AsyncMock, change_point_repo: MagicMock) -> None:
    repos.eval_repo.reset_for_refetch.assert_not_awaited()
    repos.eval_repo.invalidate_caches_for.assert_not_awaited()
    repos.eval_run_repo.mark_pending.assert_not_awaited()
    repos.annotation_repo.add_run_annotation.assert_not_awaited()
    repos.session.commit.assert_not_awaited()
    change_point_repo.return_value.delete_for_run_slo_pairs.assert_not_awaited()
    pool.enqueue_job.assert_not_awaited()


async def test_dry_run_counts_without_changes() -> None:
    run_id = uuid.uuid4()
    rows = [_make_row(run_id=run_id), _make_row(run_id=run_id, status='failed', slo_name='slo-b')]
    repos = _make_repos(rows)
    pool = AsyncMock()

    with patch(_CHANGE_POINT_REPO) as change_point_repo:
        change_point_repo.return_value.delete_for_run_slo_pairs = AsyncMock()
        response = await refetch(_make_request(dry_run=True), repos, pool)

    assert response.model_dump() == {
        'matched': 2,
        'refetched': 2,
        'run_ids': [run_id],
        'dry_run': True,
    }
    _assert_nothing_written(repos, pool, change_point_repo)


@pytest.mark.parametrize('dry_run', [False, True])
@pytest.mark.parametrize('blocking_status', ['pending', 'running'])
async def test_running_row_raises_conflict_before_any_write(blocking_status: str, dry_run: bool) -> None:
    run_id = uuid.uuid4()
    blocking = _make_row(run_id=run_id, status=blocking_status, slo_name='slo-b')
    repos = _make_repos([_make_row(run_id=run_id), blocking])
    pool = AsyncMock()

    with patch(_CHANGE_POINT_REPO) as change_point_repo:
        change_point_repo.return_value.delete_for_run_slo_pairs = AsyncMock()
        with pytest.raises(ConflictError, match=str(blocking.id)):
            await refetch(_make_request(dry_run=dry_run), repos, pool)

    _assert_nothing_written(repos, pool, change_point_repo)


async def test_request_maps_to_scope() -> None:
    asset_id = uuid.uuid4()
    run_id = uuid.uuid4()
    repos = _make_repos([])
    repos.asset_repo.get_by_name.return_value = MagicMock(id=asset_id)
    run = MagicMock(id=run_id, asset_id=asset_id, eval_name='daily', period_start=_DAY_ONE, period_end=_DAY_TWO)
    repos.eval_run_repo.get_by_id.return_value = run

    await refetch(_make_request(only_failed=True, slo_names=['slo-a']), repos, AsyncMock())
    await refetch_run(run_id, RefetchRunRequest(only_failed=True), repos, AsyncMock())

    by_period, by_run = [call.args[0] for call in repos.eval_repo.list_for_refetch.await_args_list]
    assert by_period == RefetchScope(
        asset_id=asset_id,
        period_from=_DAY_ONE,
        period_to=_DAY_TWO,
        evaluation_name='daily',
        slo_names=['slo-a'],
        only_failed=True,
    )
    assert by_run == RefetchScope(
        asset_id=asset_id,
        period_from=_DAY_ONE,
        period_to=_DAY_TWO,
        evaluation_name='daily',
        evaluation_id=run_id,
        only_failed=True,
    )


async def test_reset_enqueues_one_job_per_row_and_one_run_note() -> None:
    first_run, second_run = uuid.uuid4(), uuid.uuid4()
    asset_id = uuid.uuid4()
    rows = [
        _make_row(run_id=first_run, asset_id=asset_id, slo_name='slo-a'),
        _make_row(run_id=first_run, asset_id=asset_id, slo_name='slo-b', status='failed'),
        _make_row(run_id=second_run, asset_id=asset_id, slo_name='slo-a', status='partial', period_start=_DAY_TWO),
    ]
    repos = _make_repos(rows)
    category_id = uuid.uuid4()
    repos.category_repo.get_by_name.return_value = MagicMock(id=category_id)
    events: list[str] = []
    repos.session.commit.side_effect = lambda: events.append('commit')
    pool = AsyncMock()
    pool.enqueue_job.side_effect = lambda *args: events.append('enqueue')

    with patch(_CHANGE_POINT_REPO) as change_point_repo:
        change_point_repo.return_value.delete_for_run_slo_pairs = AsyncMock()
        response = await refetch(_make_request(requested_by='operator'), repos, pool)

    assert (response.matched, response.refetched, response.dry_run) == (3, 3, False)
    assert set(response.run_ids) == {first_run, second_run}

    reset_call = repos.eval_repo.reset_for_refetch.await_args
    assert reset_call.args[0] == [row.id for row in rows]
    audit = reset_call.kwargs['refetch_audit']
    assert (audit['requested_by'], audit['reason']) == ('operator', 'adapter outage')
    assert set(audit) == {'requested_at', 'requested_by', 'reason'}

    change_point_repo.return_value.delete_for_run_slo_pairs.assert_awaited_once_with(
        pairs=sorted([(first_run, 'slo-a'), (first_run, 'slo-b'), (second_run, 'slo-a')])
    )

    assert {call.args[0] for call in repos.eval_run_repo.mark_pending.await_args_list} == {first_run, second_run}
    notes = {
        call.args[0]: (call.kwargs['content'], call.kwargs['category_id'], call.kwargs['author'])
        for call in repos.annotation_repo.add_run_annotation.await_args_list
    }
    assert notes == {
        first_run: ('refetched from source: 2 SLO evaluation(s) — adapter outage', category_id, 'operator'),
        second_run: ('refetched from source: 1 SLO evaluation(s) — adapter outage', category_id, 'operator'),
    }

    enqueued = [call.args for call in pool.enqueue_job.await_args_list]
    assert enqueued == [('run_evaluation_job', str(row.id)) for row in rows]
    assert events == ['commit', 'enqueue', 'enqueue', 'enqueue']
    repos.eval_repo.invalidate_caches_for.assert_awaited_once_with(rows)
    repos.trend_cache.delete_many.assert_awaited_once()


async def test_row_reopened_concurrently_raises_conflict_before_commit() -> None:
    """A second refetch that lost the race resets fewer rows than it listed and must not enqueue them again."""
    run_id = uuid.uuid4()
    rows = [_make_row(run_id=run_id), _make_row(run_id=run_id, slo_name='slo-b')]
    repos = _make_repos(rows)
    repos.eval_repo.reset_for_refetch.side_effect = lambda eval_ids, **_kwargs: list(eval_ids)[:-1]
    pool = AsyncMock()

    with patch(_CHANGE_POINT_REPO) as change_point_repo:
        change_point_repo.return_value.delete_for_run_slo_pairs = AsyncMock()
        with pytest.raises(ConflictError, match='changed status during the refetch'):
            await refetch(_make_request(), repos, pool)

    repos.session.commit.assert_not_awaited()
    repos.eval_repo.invalidate_caches_for.assert_not_awaited()
    pool.enqueue_job.assert_not_awaited()


async def test_failed_enqueue_logs_the_evaluations_left_without_a_job() -> None:
    run_id = uuid.uuid4()
    rows = [_make_row(run_id=run_id, slo_name=name) for name in ('slo-a', 'slo-b', 'slo-c')]
    repos = _make_repos(rows)
    pool = AsyncMock()
    pool.enqueue_job.side_effect = [None, ConnectionError('redis gone'), None]

    with patch(_CHANGE_POINT_REPO) as change_point_repo, capture_logs() as logs:
        change_point_repo.return_value.delete_for_run_slo_pairs = AsyncMock()
        with pytest.raises(ConnectionError):
            await refetch(_make_request(), repos, pool)

    failures = [entry for entry in logs if entry['log_level'] == 'error']
    assert len(failures) == 1
    assert failures[0]['evaluation_ids'] == [str(rows[1].id), str(rows[2].id)]
