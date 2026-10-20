"""Tests for phased evaluation job and finalize job in queue.py."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from arq import Retry
from tropek.config import JOB_TIMEOUT_MARGIN_SECONDS, get_settings
from tropek.modules.quality_gate.workflows.execution.adapter_client import AdapterFetchError
from tropek.modules.quality_gate.workflows.execution.evaluation_executor import DefinitionLoadError, EvaluationSnapshot
from tropek.queue import (
    WorkerSettings,
    _build_adapter_client,
    _run_change_point_phase,
    _sweeper_cron_seconds,
    _worker_startup,
    detect_change_points_for_objectives,
    finalize_run_job,
    finalize_sweeper_job,
    run_evaluation_job,
    watchdog_stuck_evaluations_job,
)


def _make_snapshot(
    eval_id: uuid.UUID | None = None,
    parent_run_id: uuid.UUID | None = None,
) -> EvaluationSnapshot:
    """Build a minimal EvaluationSnapshot for testing."""
    return EvaluationSnapshot(
        eval_id=eval_id or uuid.uuid4(),
        parent_run_id=parent_run_id or uuid.uuid4(),
        slo_name='response-time',
        slo_version=1,
        sli_name='prometheus-sli',
        sli_version=1,
        data_source_name='prometheus',
        evaluation_name='test-eval',
        period_start=datetime(2026, 1, 1, tzinfo=UTC),
        period_end=datetime(2026, 1, 2, tzinfo=UTC),
        asset_snapshot={'service': 'api'},
        asset_id=uuid.uuid4(),
        variables={},
    )


def _mock_session() -> AsyncMock:
    """Create a mock async session with commit/rollback."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


def _session_factory_from_list(sessions: list[AsyncMock]):
    """Build a factory that yields sessions from a list in order."""
    idx = {'i': 0}

    def factory():
        s = sessions[idx['i']]
        idx['i'] += 1
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=s)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    return factory


def _no_predecessor():
    """Patch that disables the predecessor check."""
    return patch('tropek.queue._has_pending_predecessor', new_callable=AsyncMock, return_value=False)


def _make_ctx(pool: AsyncMock | None = None) -> dict:
    """Build a minimal worker context dict."""
    return {
        'cache': None,
        'redis': pool or AsyncMock(),
        'job_id': 'test-job-1',
        'http_client': None,
    }


# --- Happy path ---


async def test_happy_path_three_phases() -> None:
    """Verify 3+ sessions created, each committed, finalize job enqueued."""
    eval_id = uuid.uuid4()
    parent_run_id = uuid.uuid4()
    snapshot = _make_snapshot(eval_id=eval_id, parent_run_id=parent_run_id)

    # Sessions: phase1, phase2a, phase2b, phase3a, phase3b
    sessions = [_mock_session() for _ in range(5)]
    factory = _session_factory_from_list(sessions)
    mock_pool = AsyncMock()

    mock_fetch_result = MagicMock()
    mock_fetch_result.eval_result.result = 'pass'

    mock_datasource = MagicMock()

    with (
        patch('tropek.queue.get_session_factory', return_value=factory),
        patch(
            'tropek.queue.load_evaluation_snapshot',
            new_callable=AsyncMock,
            return_value=snapshot,
        ),
        patch(
            'tropek.queue._load_definitions',
            new_callable=AsyncMock,
            return_value=(MagicMock(), MagicMock()),
        ),
        patch('tropek.queue.DataSourceRepository') as mock_ds_repo_cls,
        patch(
            'tropek.queue.fetch_and_evaluate',
            new_callable=AsyncMock,
            return_value=mock_fetch_result,
        ),
        patch('tropek.queue.write_results', new_callable=AsyncMock) as mock_write,
        patch('tropek.queue.write_sli_values_phase', new_callable=AsyncMock) as mock_sli,
        patch('tropek.queue.BaselineRepository'),
        patch('tropek.queue.HttpAdapterClient'),
        _no_predecessor(),
    ):
        mock_ds_repo_cls.return_value.get_by_name = AsyncMock(return_value=mock_datasource)

        await run_evaluation_job(_make_ctx(mock_pool), str(eval_id))

    # All 5 sessions committed
    for i, s in enumerate(sessions):
        s.commit.assert_awaited_once(), f'session {i} not committed'

    # Both write phases called
    mock_write.assert_awaited_once()
    mock_sli.assert_awaited_once()

    # Finalize job enqueued (no dedup key — each child enqueues its own attempt)
    mock_pool.enqueue_job.assert_awaited_once_with(
        'finalize_run_job',
        str(parent_run_id),
    )


# --- Snapshot None early exit ---


async def test_snapshot_none_skips_remaining_phases() -> None:
    """load_evaluation_snapshot returns None -> no further phases."""
    sessions = [_mock_session()]
    factory = _session_factory_from_list(sessions)

    with (
        patch('tropek.queue.get_session_factory', return_value=factory),
        patch(
            'tropek.queue.load_evaluation_snapshot',
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch('tropek.queue._load_definitions', new_callable=AsyncMock) as mock_load,
        patch('tropek.queue.fetch_and_evaluate', new_callable=AsyncMock) as mock_fetch,
        patch('tropek.queue.write_results', new_callable=AsyncMock) as mock_write,
        _no_predecessor(),
    ):
        await run_evaluation_job(_make_ctx(), str(uuid.uuid4()))

    sessions[0].commit.assert_awaited_once()
    mock_load.assert_not_awaited()
    mock_fetch.assert_not_awaited()
    mock_write.assert_not_awaited()


# --- Adapter fetch failure: retry, then fail ---


def _fetch_attempt(attempt: int) -> dict[str, Any]:
    """An attempt-history entry as ``mark_pending_retry`` stores it."""
    return {'attempt': attempt, 'cause': 'adapter returned 504', 'status': 504, 'elapsed_s': 1.0, 'at': 'earlier'}


async def _run_job_with_fetch_error(
    eval_id: uuid.UUID,
    previous_attempts: int,
    mock_eval_repo: AsyncMock,
    error: AdapterFetchError | None = None,
) -> None:
    """Run the job with ``fetch_and_evaluate`` raising, the row already holding ``previous_attempts`` records."""
    mock_eval_repo.get_by_id = AsyncMock(
        return_value=MagicMock(
            job_stats={'fetch_attempts': [_fetch_attempt(number) for number in range(1, previous_attempts + 1)]}
        )
    )
    if error is None:
        error = AdapterFetchError('adapter returned 504 after 3 attempts', attempts=3, last_status=504, elapsed_s=12.5)
    # Sessions: phase1, phase2a, phase2b (raises), retry handling
    factory = _session_factory_from_list([_mock_session() for _ in range(4)])
    with (
        patch('tropek.queue.get_session_factory', return_value=factory),
        patch('tropek.queue.load_evaluation_snapshot', new_callable=AsyncMock, return_value=_make_snapshot(eval_id)),
        patch('tropek.queue._load_definitions', new_callable=AsyncMock, return_value=(MagicMock(), MagicMock())),
        patch('tropek.queue.DataSourceRepository') as mock_ds_repo_cls,
        patch('tropek.queue.fetch_and_evaluate', new_callable=AsyncMock, side_effect=error),
        patch(
            'tropek.queue.write_results',
            new_callable=AsyncMock,
            side_effect=AssertionError('results must not be written after a failed fetch'),
        ),
        patch('tropek.queue.EvaluationRepository', return_value=mock_eval_repo),
        patch('tropek.queue.BaselineRepository'),
        patch('tropek.queue.HttpAdapterClient'),
        _no_predecessor(),
    ):
        mock_ds_repo_cls.return_value.get_by_name = AsyncMock(return_value=MagicMock())
        await run_evaluation_job(_make_ctx(), str(eval_id))


@pytest.mark.parametrize('previous_attempts', [0, get_settings().queue.max_retries - 1])
async def test_transient_fetch_raises_retry_and_resets_to_pending(previous_attempts: int) -> None:
    """Below the cap the evaluation goes back to pending and arq retries after a linear delay."""
    eval_id = uuid.uuid4()
    mock_eval_repo = AsyncMock()
    attempt = previous_attempts + 1

    with pytest.raises(Retry) as exc_info:
        await _run_job_with_fetch_error(eval_id, previous_attempts, mock_eval_repo)

    delay_ms = get_settings().queue.retry_delay_seconds * attempt * 1000
    assert exc_info.value.defer_score == delay_ms
    mock_eval_repo.mark_pending_retry.assert_awaited_once()
    assert mock_eval_repo.mark_pending_retry.await_args.args == (eval_id,)
    record = mock_eval_repo.mark_pending_retry.await_args.kwargs['attempt_record']
    assert record['attempt'] == attempt
    assert record['status'] == 504
    assert record['cause'] == 'adapter returned 504 after 3 attempts'
    mock_eval_repo.mark_failed.assert_not_awaited()


async def test_data_errors_only_do_not_retry() -> None:
    """A 200 whose errors are all ``data`` errors is evaluated and written, never retried (a bad query)."""
    eval_id = uuid.uuid4()
    slo_def = MagicMock(comparison=None, variables={}, total_score_pass_threshold=90.0)
    slo_def.objectives = [
        MagicMock(sli='rt', display_name='RT', pass_threshold=['<600'], warning_threshold=[], weight=1, key_sli=False)
    ]
    sli_def = MagicMock(mode='raw', indicators={'rt': 'up'})
    mock_eval_repo = AsyncMock()
    factory = _session_factory_from_list([_mock_session() for _ in range(5)])

    with (
        patch('tropek.queue.get_session_factory', return_value=factory),
        patch('tropek.queue.load_evaluation_snapshot', new_callable=AsyncMock, return_value=_make_snapshot(eval_id)),
        patch('tropek.queue._load_definitions', new_callable=AsyncMock, return_value=(slo_def, sli_def)),
        patch('tropek.queue.DataSourceRepository') as mock_ds_repo_cls,
        patch('tropek.queue.write_results', new_callable=AsyncMock) as mock_write,
        patch('tropek.queue.write_sli_values_phase', new_callable=AsyncMock),
        patch('tropek.queue._run_change_point_phase', new_callable=AsyncMock),
        patch('tropek.queue.EvaluationRepository', return_value=mock_eval_repo),
        patch('tropek.queue.BaselineRepository') as mock_baseline_repo_cls,
        patch('tropek.queue.HttpAdapterClient') as mock_client_cls,
        _no_predecessor(),
    ):
        mock_ds_repo_cls.return_value.get_by_name = AsyncMock(return_value=MagicMock())
        mock_baseline_repo_cls.return_value.get_evaluation_baselines = AsyncMock(return_value=[])
        mock_client_cls.return_value.query = AsyncMock(
            return_value=({'rt': None}, {'rt': 'bad_data: parse error'}, {}, {'rt': 'data'})
        )
        await run_evaluation_job(_make_ctx(), str(eval_id))

    mock_eval_repo.mark_pending_retry.assert_not_awaited()
    mock_eval_repo.mark_failed.assert_not_awaited()
    mock_write.assert_awaited_once()
    assert mock_write.await_args.kwargs['fetch_result'].metrics_fetched == {'rt': None}


async def test_retry_cap_marks_failed_with_attempt_history() -> None:
    """With ``max_retries`` attempts already recorded the evaluation is failed with the full history."""
    eval_id = uuid.uuid4()
    mock_eval_repo = AsyncMock()
    max_retries = get_settings().queue.max_retries

    await _run_job_with_fetch_error(eval_id, max_retries, mock_eval_repo)

    mock_eval_repo.mark_pending_retry.assert_not_awaited()
    mock_eval_repo.mark_failed.assert_awaited_once()
    assert mock_eval_repo.mark_failed.await_args.args == (eval_id,)
    stats = mock_eval_repo.mark_failed.await_args.kwargs['job_stats']
    assert stats['error'] == (
        f'adapter query failed after {max_retries + 1} attempts: adapter returned 504 after 3 attempts'
    )
    assert [entry['attempt'] for entry in stats['fetch_attempts']] == list(range(1, max_retries + 2))


async def test_non_retryable_fetch_error_marks_failed_on_the_first_attempt() -> None:
    """A 4xx from the adapter will not change on a rerun, so the job is not retried."""
    eval_id = uuid.uuid4()
    mock_eval_repo = AsyncMock()
    error = AdapterFetchError('adapter returned 400', attempts=1, last_status=400, elapsed_s=0.1, retryable=False)

    await _run_job_with_fetch_error(eval_id, 0, mock_eval_repo, error=error)

    mock_eval_repo.mark_pending_retry.assert_not_awaited()
    mock_eval_repo.mark_failed.assert_awaited_once()
    stats = mock_eval_repo.mark_failed.await_args.kwargs['job_stats']
    assert stats['error'] == 'adapter query failed after 1 attempts: adapter returned 400'
    assert len(stats['fetch_attempts']) == 1
    assert stats['fetch_attempts'][0]['status'] == 400


def test_adapter_client_is_built_with_the_job_deadline() -> None:
    """The client stops starting attempts a margin before arq's job timeout would kill the job."""
    with patch('tropek.queue.HttpAdapterClient') as mock_client_cls:
        _build_adapter_client(None)

    assert mock_client_cls.call_args.kwargs['deadline_seconds'] == (
        get_settings().queue.job_timeout_seconds - JOB_TIMEOUT_MARGIN_SECONDS
    )


# --- Definition load error ---


async def test_definition_load_error_marks_failed() -> None:
    """_load_definitions raises DefinitionLoadError -> mark_failed called."""
    eval_id = uuid.uuid4()
    snapshot = _make_snapshot(eval_id=eval_id)

    # Sessions: phase1, phase2a (fails), mark_failed
    sessions = [_mock_session() for _ in range(3)]
    factory = _session_factory_from_list(sessions)

    mock_eval_repo = AsyncMock()

    with (
        patch('tropek.queue.get_session_factory', return_value=factory),
        patch(
            'tropek.queue.load_evaluation_snapshot',
            new_callable=AsyncMock,
            return_value=snapshot,
        ),
        patch(
            'tropek.queue._load_definitions',
            new_callable=AsyncMock,
            side_effect=DefinitionLoadError("slo 'x' v1 not found"),
        ),
        patch('tropek.queue.EvaluationRepository', return_value=mock_eval_repo),
        _no_predecessor(),
    ):
        await run_evaluation_job(_make_ctx(), str(eval_id))

    mock_eval_repo.mark_failed.assert_awaited_once_with(eval_id, job_stats={'error': "slo 'x' v1 not found"})


# --- Finalize run job ---


async def test_finalize_run_job_completes_parent() -> None:
    """finalize_if_all_done returns finalized run -> logged."""
    run_id = uuid.uuid4()
    sessions = [_mock_session()]
    factory = _session_factory_from_list(sessions)

    mock_run_repo = AsyncMock()
    mock_finalized = MagicMock()
    mock_finalized.result = 'pass'
    mock_run_repo.finalize_if_all_done.return_value = mock_finalized

    with (
        patch('tropek.queue.get_session_factory', return_value=factory),
        patch('tropek.queue.EvaluationRunRepository', return_value=mock_run_repo),
    ):
        await finalize_run_job({}, str(run_id))

    mock_run_repo.finalize_if_all_done.assert_awaited_once_with(run_id)
    sessions[0].commit.assert_awaited_once()


async def test_finalize_run_job_warms_heatmap_column_cache_when_redis_available() -> None:
    """When finalize succeeds and Redis is configured, the warm helper fires
    with a fresh session. This pins the wiring contract — the warm hook must
    run on the fast path, not only on the sweeper rescue path.
    """
    run_id = uuid.uuid4()
    # Two sessions: one for finalize, one for the warm helper.
    sessions = [_mock_session(), _mock_session()]
    factory = _session_factory_from_list(sessions)

    mock_run_repo = AsyncMock()
    mock_finalized = MagicMock()
    mock_finalized.result = 'pass'
    mock_run_repo.finalize_if_all_done.return_value = mock_finalized
    mock_warm = AsyncMock()
    mock_cache = MagicMock()

    with (
        patch('tropek.queue.get_session_factory', return_value=factory),
        patch('tropek.queue.EvaluationRunRepository', return_value=mock_run_repo),
        patch('tropek.queue.warm_heatmap_column_cache', new=mock_warm),
    ):
        await finalize_run_job({'cache': mock_cache}, str(run_id))

    mock_warm.assert_awaited_once()
    warm_args = mock_warm.await_args
    assert warm_args.args[0] is sessions[1]
    assert warm_args.args[1] == run_id
    assert warm_args.kwargs['redis_cache'] is mock_cache


async def test_finalize_run_job_noop_when_children_pending() -> None:
    """finalize_if_all_done returns None -> no logging, still commits."""
    run_id = uuid.uuid4()
    sessions = [_mock_session()]
    factory = _session_factory_from_list(sessions)

    mock_run_repo = AsyncMock()
    mock_run_repo.finalize_if_all_done.return_value = None

    with (
        patch('tropek.queue.get_session_factory', return_value=factory),
        patch('tropek.queue.EvaluationRunRepository', return_value=mock_run_repo),
    ):
        await finalize_run_job({}, str(run_id))

    mock_run_repo.finalize_if_all_done.assert_awaited_once_with(run_id)
    sessions[0].commit.assert_awaited_once()


# --- Predecessor deferral ---


async def test_predecessor_defers_job() -> None:
    """Predecessor check returns True -> job re-enqueued, no phases run."""
    mock_pool = AsyncMock()
    eval_id_str = '00000000-0000-0000-0000-000000000001'

    sessions = [_mock_session()]
    factory = _session_factory_from_list(sessions)

    with (
        patch('tropek.queue.get_session_factory', return_value=factory),
        patch(
            'tropek.queue._has_pending_predecessor',
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch('tropek.queue.load_evaluation_snapshot', new_callable=AsyncMock) as mock_snapshot,
    ):
        await run_evaluation_job(
            _make_ctx(mock_pool),
            eval_id_str,
        )

    mock_snapshot.assert_not_awaited()
    mock_pool.enqueue_job.assert_awaited_once()


# --- Sweeper cron helper ---


def test_sweeper_cron_seconds_30() -> None:
    assert _sweeper_cron_seconds(30) == {0, 30}


def test_sweeper_cron_seconds_15() -> None:
    assert _sweeper_cron_seconds(15) == {0, 15, 30, 45}


def test_sweeper_cron_seconds_60() -> None:
    assert _sweeper_cron_seconds(60) == {0}


def test_sweeper_cron_seconds_5() -> None:
    assert _sweeper_cron_seconds(5) == {0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}


def test_sweeper_cron_seconds_rejects_non_divisor() -> None:
    with pytest.raises(ValueError, match='must divide 60'):
        _sweeper_cron_seconds(45)


def test_worker_settings_apply_queue_timeouts() -> None:
    queue_settings = get_settings().queue
    assert WorkerSettings.job_timeout == queue_settings.job_timeout_seconds
    # One spare try beyond the database-counted retries makes it unlikely that arq's own cap pre-empts
    # mark_failed (cancellation reruns also count toward ``max_tries``).
    assert WorkerSettings.max_tries == queue_settings.max_retries + 2
    assert WorkerSettings.retry_jobs is True
    assert WorkerSettings.keep_result == queue_settings.keep_result_seconds


async def test_worker_startup_refuses_inconsistent_settings() -> None:
    """The worker validates secrets and the timeout chain before opening any connection."""
    settings = MagicMock()
    settings.validate_required.side_effect = RuntimeError('required secrets not set: TK_SECRET_KEY')
    ctx: dict[str, Any] = {}

    with (
        patch('tropek.queue.configure_logging'),
        patch('tropek.queue.get_settings', return_value=settings),
        pytest.raises(RuntimeError, match='required secrets not set'),
    ):
        await _worker_startup(ctx)

    settings.validate_required.assert_called_once_with()
    assert ctx == {}


def test_worker_settings_registers_sweeper_job() -> None:
    assert finalize_sweeper_job in WorkerSettings.functions
    assert any(getattr(cj, 'coroutine', None) is finalize_sweeper_job for cj in WorkerSettings.cron_jobs)


# --- Stuck-evaluation watchdog ---


def _stuck_eval(stuck_job_retries: int) -> MagicMock:
    """A minimal stand-in for a stuck SLOEvaluation row."""
    stuck = MagicMock()
    stuck.id = uuid.uuid4()
    stuck.job_stats = {'stuck_job_retries': stuck_job_retries} if stuck_job_retries else {}
    return stuck


def _watchdog_ctx(pool: AsyncMock) -> dict:
    return {'redis': pool}


async def test_watchdog_requeues_stuck_eval_below_cap() -> None:
    """A stuck eval below the retry cap is requeued and re-enqueued, not failed."""
    stuck = _stuck_eval(stuck_job_retries=0)
    repo = AsyncMock()
    repo.find_stuck = AsyncMock(return_value=[stuck])
    mock_pool = AsyncMock()
    factory = _session_factory_from_list([_mock_session(), _mock_session()])

    with (
        patch('tropek.queue.get_session_factory', return_value=factory),
        patch('tropek.queue.EvaluationRepository', return_value=repo),
    ):
        await watchdog_stuck_evaluations_job(_watchdog_ctx(mock_pool))

    repo.requeue_stuck.assert_awaited_once_with(stuck.id, stuck_job_retries=1)
    repo.mark_failed.assert_not_awaited()
    mock_pool.enqueue_job.assert_awaited_once_with('run_evaluation_job', str(stuck.id))


async def test_watchdog_marks_failed_at_cap() -> None:
    """A stuck eval that has hit max_stuck_job_retries is marked failed, not requeued."""
    stuck = _stuck_eval(stuck_job_retries=get_settings().reliability.max_stuck_job_retries)
    repo = AsyncMock()
    repo.find_stuck = AsyncMock(return_value=[stuck])
    mock_pool = AsyncMock()
    factory = _session_factory_from_list([_mock_session(), _mock_session()])

    with (
        patch('tropek.queue.get_session_factory', return_value=factory),
        patch('tropek.queue.EvaluationRepository', return_value=repo),
    ):
        await watchdog_stuck_evaluations_job(_watchdog_ctx(mock_pool))

    repo.mark_failed.assert_awaited_once()
    repo.requeue_stuck.assert_not_awaited()
    mock_pool.enqueue_job.assert_not_awaited()


async def test_watchdog_noop_when_nothing_stuck() -> None:
    """No stuck evals -> no requeue, no failed, no enqueue."""
    repo = AsyncMock()
    repo.find_stuck = AsyncMock(return_value=[])
    mock_pool = AsyncMock()
    factory = _session_factory_from_list([_mock_session()])

    with (
        patch('tropek.queue.get_session_factory', return_value=factory),
        patch('tropek.queue.EvaluationRepository', return_value=repo),
    ):
        await watchdog_stuck_evaluations_job(_watchdog_ctx(mock_pool))

    repo.requeue_stuck.assert_not_awaited()
    repo.mark_failed.assert_not_awaited()
    mock_pool.enqueue_job.assert_not_awaited()


def test_worker_settings_registers_watchdog_job() -> None:
    assert watchdog_stuck_evaluations_job in WorkerSettings.functions


async def test_change_point_phase_decouples_read_compute_write() -> None:
    """Read fetch and write inserts run in separate sessions; compute holds none."""
    read_session = AsyncMock()
    write_session = AsyncMock()

    class _FactoryCM:
        def __init__(self, session: AsyncMock) -> None:
            self._session = session

        async def __aenter__(self) -> AsyncMock:
            return self._session

        async def __aexit__(self, *args: object) -> bool:
            return False

    sessions = [read_session, write_session]
    session_factory = MagicMock(side_effect=lambda: _FactoryCM(sessions.pop(0)))

    snapshot = MagicMock()
    snapshot.eval_id = uuid.uuid4()
    fake_inputs = MagicMock()
    fake_batches = [MagicMock()]

    with (
        patch('tropek.queue.IndicatorRepository') as mock_indicator_cls,
        patch('tropek.queue.load_change_point_inputs', new=AsyncMock(return_value=fake_inputs)) as mock_load,
        patch('tropek.queue.detect_change_points_for_objectives', return_value=fake_batches) as mock_detect,
        patch('tropek.queue.persist_detected_change_points', new=AsyncMock()) as mock_persist,
    ):
        mock_indicator_cls.return_value.get_for_evaluation = AsyncMock(return_value=[])
        await _run_change_point_phase(session_factory, snapshot, MagicMock(), None, MagicMock())

    assert mock_load.await_args.kwargs['session'] is read_session
    assert mock_persist.await_args.kwargs['session'] is write_session
    assert 'session' not in mock_detect.call_args.kwargs
    assert any(getattr(cj, 'coroutine', None) is watchdog_stuck_evaluations_job for cj in WorkerSettings.cron_jobs)


@pytest.mark.asyncio
async def test_change_point_compute_is_offloaded_off_the_event_loop() -> None:
    """Detection is CPU-bound; it must run via ``asyncio.to_thread`` so it never blocks the worker's
    event loop (a blocked loop holds other evals' transactions open and stalls the whole worker)."""
    read_session = AsyncMock()
    write_session = AsyncMock()

    class _FactoryCM:
        def __init__(self, session: AsyncMock) -> None:
            self._session = session

        async def __aenter__(self) -> AsyncMock:
            return self._session

        async def __aexit__(self, *args: object) -> bool:
            return False

    sessions = [read_session, write_session]
    session_factory = MagicMock(side_effect=lambda: _FactoryCM(sessions.pop(0)))

    snapshot = MagicMock()
    snapshot.eval_id = uuid.uuid4()
    fake_inputs = MagicMock()
    fake_batches = [MagicMock()]

    with (
        patch('tropek.queue.IndicatorRepository') as mock_indicator_cls,
        patch('tropek.queue.load_change_point_inputs', new=AsyncMock(return_value=fake_inputs)),
        patch('tropek.queue.persist_detected_change_points', new=AsyncMock()),
        patch('tropek.queue.asyncio.to_thread', new_callable=AsyncMock, return_value=fake_batches) as mock_to_thread,
    ):
        mock_indicator_cls.return_value.get_for_evaluation = AsyncMock(return_value=[])
        await _run_change_point_phase(session_factory, snapshot, MagicMock(), None, MagicMock())

    # The detection function is dispatched to a worker thread, not called inline on the loop.
    assert mock_to_thread.await_args.args[0] is detect_change_points_for_objectives
