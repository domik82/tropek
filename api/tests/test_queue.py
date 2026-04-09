"""Tests for phased evaluation job and finalize job in queue.py."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.modules.quality_gate.worker import DefinitionLoadError, EvaluationSnapshot
from app.queue import finalize_run_job, run_evaluation_job


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
    return patch(
        'app.queue._has_pending_predecessor', new_callable=AsyncMock, return_value=False
    )


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
        patch('app.queue.get_session_factory', return_value=factory),
        patch(
            'app.queue.load_evaluation_snapshot',
            new_callable=AsyncMock,
            return_value=snapshot,
        ),
        patch(
            'app.queue._load_definitions',
            new_callable=AsyncMock,
            return_value=(MagicMock(), MagicMock()),
        ),
        patch('app.queue.DataSourceRepository') as mock_ds_repo_cls,
        patch(
            'app.queue.fetch_and_evaluate',
            new_callable=AsyncMock,
            return_value=mock_fetch_result,
        ),
        patch('app.queue.write_results', new_callable=AsyncMock) as mock_write,
        patch('app.queue.write_sli_values_phase', new_callable=AsyncMock) as mock_sli,
        patch('app.queue.BaselineRepository'),
        patch('app.queue.HttpAdapterClient'),
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
        patch('app.queue.get_session_factory', return_value=factory),
        patch(
            'app.queue.load_evaluation_snapshot',
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch('app.queue._load_definitions', new_callable=AsyncMock) as mock_load,
        patch('app.queue.fetch_and_evaluate', new_callable=AsyncMock) as mock_fetch,
        patch('app.queue.write_results', new_callable=AsyncMock) as mock_write,
        _no_predecessor(),
    ):
        await run_evaluation_job(_make_ctx(), str(uuid.uuid4()))

    sessions[0].commit.assert_awaited_once()
    mock_load.assert_not_awaited()
    mock_fetch.assert_not_awaited()
    mock_write.assert_not_awaited()


# --- Adapter failure ---


async def test_adapter_failure_marks_failed() -> None:
    """fetch_and_evaluate returns None -> mark_failed called."""
    eval_id = uuid.uuid4()
    snapshot = _make_snapshot(eval_id=eval_id)

    # Sessions: phase1, phase2a, phase2b, mark_failed
    sessions = [_mock_session() for _ in range(4)]
    factory = _session_factory_from_list(sessions)

    mock_eval_repo = AsyncMock()

    with (
        patch('app.queue.get_session_factory', return_value=factory),
        patch(
            'app.queue.load_evaluation_snapshot',
            new_callable=AsyncMock,
            return_value=snapshot,
        ),
        patch(
            'app.queue._load_definitions',
            new_callable=AsyncMock,
            return_value=(MagicMock(), MagicMock()),
        ),
        patch('app.queue.DataSourceRepository') as mock_ds_repo_cls,
        patch(
            'app.queue.fetch_and_evaluate',
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch('app.queue.EvaluationRepository', return_value=mock_eval_repo),
        patch('app.queue.BaselineRepository'),
        patch('app.queue.HttpAdapterClient'),
        _no_predecessor(),
    ):
        mock_ds_repo_cls.return_value.get_by_name = AsyncMock(return_value=MagicMock())

        await run_evaluation_job(_make_ctx(), str(eval_id))

    mock_eval_repo.mark_failed.assert_awaited_once_with(
        eval_id, job_stats={'error': 'adapter query failed'}
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
        patch('app.queue.get_session_factory', return_value=factory),
        patch(
            'app.queue.load_evaluation_snapshot',
            new_callable=AsyncMock,
            return_value=snapshot,
        ),
        patch(
            'app.queue._load_definitions',
            new_callable=AsyncMock,
            side_effect=DefinitionLoadError("slo 'x' v1 not found"),
        ),
        patch('app.queue.EvaluationRepository', return_value=mock_eval_repo),
        _no_predecessor(),
    ):
        await run_evaluation_job(_make_ctx(), str(eval_id))

    mock_eval_repo.mark_failed.assert_awaited_once_with(
        eval_id, job_stats={'error': "slo 'x' v1 not found"}
    )


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
        patch('app.queue.get_session_factory', return_value=factory),
        patch('app.queue.EvaluationRunRepository', return_value=mock_run_repo),
    ):
        await finalize_run_job({}, str(run_id))

    mock_run_repo.finalize_if_all_done.assert_awaited_once_with(run_id)
    sessions[0].commit.assert_awaited_once()


async def test_finalize_run_job_noop_when_children_pending() -> None:
    """finalize_if_all_done returns None -> no logging, still commits."""
    run_id = uuid.uuid4()
    sessions = [_mock_session()]
    factory = _session_factory_from_list(sessions)

    mock_run_repo = AsyncMock()
    mock_run_repo.finalize_if_all_done.return_value = None

    with (
        patch('app.queue.get_session_factory', return_value=factory),
        patch('app.queue.EvaluationRunRepository', return_value=mock_run_repo),
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
        patch('app.queue.get_session_factory', return_value=factory),
        patch(
            'app.queue._has_pending_predecessor',
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            'app.queue.load_evaluation_snapshot', new_callable=AsyncMock
        ) as mock_snapshot,
    ):
        await run_evaluation_job(
            _make_ctx(mock_pool),
            eval_id_str,
        )

    mock_snapshot.assert_not_awaited()
    mock_pool.enqueue_job.assert_awaited_once()
