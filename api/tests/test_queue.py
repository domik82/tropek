"""Tests for deadlock retry and post-commit finalization logic in run_evaluation_job."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from app.queue import _is_deadlock, run_evaluation_job
from sqlalchemy.exc import DBAPIError


def _make_deadlock_error() -> DBAPIError:
    """Create a DBAPIError that looks like a PostgreSQL deadlock."""
    orig = Exception('deadlock detected')
    return DBAPIError(
        statement='UPDATE evaluations SET ...',
        params={},
        orig=orig,
    )


def _make_non_deadlock_error() -> DBAPIError:
    """Create a DBAPIError that is not a deadlock."""
    orig = Exception('connection refused')
    return DBAPIError(
        statement='SELECT ...',
        params={},
        orig=orig,
    )


# --- _is_deadlock detection ---


def test_is_deadlock_with_deadlock_message() -> None:
    """Detect deadlock from exception message containing 'deadlock'."""
    exc = _make_deadlock_error()
    assert _is_deadlock(exc) is True


def test_is_deadlock_with_non_deadlock_message() -> None:
    """Non-deadlock errors return False."""
    exc = _make_non_deadlock_error()
    assert _is_deadlock(exc) is False


# --- run_evaluation_job retry behavior ---


@pytest.fixture
def mock_session_factory():
    """Create a mock session factory that returns an async context manager session."""
    session = AsyncMock()
    ctx_manager = AsyncMock()
    ctx_manager.__aenter__ = AsyncMock(return_value=session)
    ctx_manager.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=ctx_manager)
    return factory, session


def _no_predecessor():
    """Patch context that disables the predecessor check."""
    return patch('app.queue._has_pending_predecessor', new_callable=AsyncMock, return_value=False)


async def test_deadlock_retry_succeeds_on_second_attempt(mock_session_factory: tuple) -> None:
    """Job retries after deadlock and succeeds on the second attempt."""
    factory, session = mock_session_factory
    call_count = 0

    async def fake_run_evaluation(sess, eval_id, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _make_deadlock_error()
        return None  # no parent run — skip finalization

    with (
        patch('app.queue.get_session_factory', return_value=factory),
        patch('app.queue.run_evaluation', side_effect=fake_run_evaluation),
        patch('asyncio.sleep', new_callable=AsyncMock),
        _no_predecessor(),
    ):
        await run_evaluation_job({}, '00000000-0000-0000-0000-000000000001')

    assert call_count == 2
    assert session.commit.await_count == 1


async def test_deadlock_retry_exhausted(mock_session_factory: tuple) -> None:
    """Job fails after all retries exhausted."""
    factory, _session = mock_session_factory

    with (
        patch('app.queue.get_session_factory', return_value=factory),
        patch('app.queue.run_evaluation', side_effect=_make_deadlock_error()),
        patch('asyncio.sleep', new_callable=AsyncMock),
        _no_predecessor(),
        pytest.raises(DBAPIError),
    ):
        await run_evaluation_job({}, '00000000-0000-0000-0000-000000000001')


async def test_non_deadlock_error_not_retried(mock_session_factory: tuple) -> None:
    """Non-deadlock DBAPIError should not be retried."""
    factory, session = mock_session_factory

    with (
        patch('app.queue.get_session_factory', return_value=factory),
        patch('app.queue.run_evaluation', side_effect=_make_non_deadlock_error()),
        patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep,
        _no_predecessor(),
        pytest.raises(DBAPIError),
    ):
        await run_evaluation_job({}, '00000000-0000-0000-0000-000000000001')

    # No sleep called because no retry happened
    mock_sleep.assert_not_awaited()
    # rollback called once (for the single failed attempt)
    session.rollback.assert_awaited_once()


async def test_non_dbapi_error_not_retried(mock_session_factory: tuple) -> None:
    """Non-DBAPIError exceptions should not be retried."""
    factory, session = mock_session_factory

    with (
        patch('app.queue.get_session_factory', return_value=factory),
        patch('app.queue.run_evaluation', side_effect=RuntimeError('unexpected')),
        patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep,
        _no_predecessor(),
        pytest.raises(RuntimeError, match='unexpected'),
    ):
        await run_evaluation_job({}, '00000000-0000-0000-0000-000000000001')

    mock_sleep.assert_not_awaited()
    session.rollback.assert_awaited_once()


async def test_successful_job_no_retry(mock_session_factory: tuple) -> None:
    """Successful job runs once with no retries."""
    factory, session = mock_session_factory

    with (
        patch('app.queue.get_session_factory', return_value=factory),
        patch('app.queue.run_evaluation', new_callable=AsyncMock, return_value=None),
        patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep,
        _no_predecessor(),
    ):
        await run_evaluation_job({}, '00000000-0000-0000-0000-000000000001')

    mock_sleep.assert_not_awaited()
    session.commit.assert_awaited_once()


async def test_predecessor_defers_job(mock_session_factory: tuple) -> None:
    """Job is deferred when a predecessor evaluation is still pending."""
    factory, _session = mock_session_factory
    mock_pool = AsyncMock()

    with (
        patch('app.queue.get_session_factory', return_value=factory),
        patch('app.queue._has_pending_predecessor', new_callable=AsyncMock, return_value=True),
        patch('app.queue.run_evaluation', new_callable=AsyncMock) as mock_run,
    ):
        await run_evaluation_job(
            {'redis': mock_pool},
            '00000000-0000-0000-0000-000000000001',
        )

    mock_run.assert_not_awaited()
    mock_pool.enqueue_job.assert_awaited_once()


async def test_predecessor_max_defers_exceeded(mock_session_factory: tuple) -> None:
    """Job proceeds when max defer count is exceeded, even with pending predecessor."""
    factory, session = mock_session_factory

    with (
        patch('app.queue.get_session_factory', return_value=factory),
        patch('app.queue._has_pending_predecessor', new_callable=AsyncMock, return_value=True) as mock_check,
        patch('app.queue.run_evaluation', new_callable=AsyncMock, return_value=None) as mock_run,
        patch('asyncio.sleep', new_callable=AsyncMock),
    ):
        await run_evaluation_job(
            {},
            '00000000-0000-0000-0000-000000000001',
            defer_count=999,
        )

    mock_check.assert_not_awaited()
    mock_run.assert_awaited_once()
    session.commit.assert_awaited_once()


# --- Post-commit finalization tests ---


@pytest.fixture
def finalize_session_factory():
    """Session factory that tracks separate sessions for eval and finalization.

    Returns (factory_func, eval_session, finalize_session, call_order) where
    call_order records 'eval_commit' and 'finalize_commit' in invocation order.
    """
    call_order: list[str] = []

    eval_session = AsyncMock()
    eval_session.commit = AsyncMock(side_effect=lambda: call_order.append('eval_commit'))
    eval_session.rollback = AsyncMock()

    finalize_session = AsyncMock()
    finalize_session.commit = AsyncMock(side_effect=lambda: call_order.append('finalize_commit'))

    sessions = iter([eval_session, finalize_session])

    def factory():
        s = next(sessions)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=s)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    return factory, eval_session, finalize_session, call_order


async def test_finalize_skipped_when_no_parent_run(mock_session_factory: tuple) -> None:
    """No finalization session created when run_evaluation returns None (early exit)."""
    factory, session = mock_session_factory

    with (
        patch('app.queue.get_session_factory', return_value=factory),
        patch('app.queue.run_evaluation', new_callable=AsyncMock, return_value=None),
        patch('app.queue.EvaluationRunRepository') as mock_repo_cls,
        _no_predecessor(),
    ):
        await run_evaluation_job({}, '00000000-0000-0000-0000-000000000001')

    session.commit.assert_awaited_once()
    mock_repo_cls.assert_not_called()


async def test_finalize_happens_after_eval_commit(finalize_session_factory: tuple) -> None:
    """Finalization session opens only after eval session commits — never inside it."""
    factory, eval_session, finalize_session, call_order = finalize_session_factory
    parent_run_id = uuid.uuid4()
    mock_repo = AsyncMock()
    mock_repo.finalize_if_all_done.return_value = None

    with (
        patch('app.queue.get_session_factory', return_value=factory),
        patch('app.queue.run_evaluation', new_callable=AsyncMock, return_value=parent_run_id),
        patch('app.queue.EvaluationRunRepository', return_value=mock_repo),
        _no_predecessor(),
    ):
        await run_evaluation_job({}, str(uuid.uuid4()))

    assert call_order == ['eval_commit', 'finalize_commit']
    mock_repo.finalize_if_all_done.assert_awaited_once_with(parent_run_id)


async def test_finalize_error_preserves_child_commit() -> None:
    """If finalization fails after all retries, the child evaluation commit is preserved."""
    parent_run_id = uuid.uuid4()
    call_order: list[str] = []
    sessions_created = 0

    mock_repo = AsyncMock()
    mock_repo.finalize_if_all_done.side_effect = OSError('connection lost')

    def session_factory():
        nonlocal sessions_created
        sessions_created += 1
        s = AsyncMock()
        if sessions_created == 1:
            s.commit = AsyncMock(side_effect=lambda: call_order.append('eval_commit'))
        else:
            s.commit = AsyncMock(side_effect=lambda: call_order.append('finalize_commit'))
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=s)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    with (
        patch('app.queue.get_session_factory', return_value=session_factory),
        patch('app.queue.run_evaluation', new_callable=AsyncMock, return_value=parent_run_id),
        patch('app.queue.EvaluationRunRepository', return_value=mock_repo),
        patch('asyncio.sleep', new_callable=AsyncMock),
        _no_predecessor(),
    ):
        await run_evaluation_job({}, str(uuid.uuid4()))

    # Child committed, finalization retried 3 times and gave up (no raise — just logs)
    assert call_order[0] == 'eval_commit'
    assert mock_repo.finalize_if_all_done.await_count == 3


async def test_finalize_retries_then_succeeds() -> None:
    """Finalization succeeds on second attempt after transient failure."""
    parent_run_id = uuid.uuid4()
    finalize_call_count = 0

    mock_repo = AsyncMock()

    async def flaky_finalize(run_id):
        nonlocal finalize_call_count
        finalize_call_count += 1
        if finalize_call_count == 1:
            raise OSError('connection reset')
        return None

    mock_repo.finalize_if_all_done.side_effect = flaky_finalize

    def session_factory():
        s = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=s)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    with (
        patch('app.queue.get_session_factory', return_value=session_factory),
        patch('app.queue.run_evaluation', new_callable=AsyncMock, return_value=parent_run_id),
        patch('app.queue.EvaluationRunRepository', return_value=mock_repo),
        patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep,
        _no_predecessor(),
    ):
        await run_evaluation_job({}, str(uuid.uuid4()))

    assert finalize_call_count == 2
    mock_sleep.assert_awaited_once()  # one backoff sleep between attempts


async def test_deadlock_retry_then_finalize() -> None:
    """After deadlock retry succeeds, finalization still runs in a fresh session."""
    parent_run_id = uuid.uuid4()
    call_count = 0
    sessions_created = 0

    async def fake_run_evaluation(sess, eval_id, **_kw):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _make_deadlock_error()
        return parent_run_id

    mock_repo = AsyncMock()
    mock_repo.finalize_if_all_done.return_value = None

    def session_factory():
        nonlocal sessions_created
        sessions_created += 1
        s = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=s)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    with (
        patch('app.queue.get_session_factory', return_value=session_factory),
        patch('app.queue.run_evaluation', side_effect=fake_run_evaluation),
        patch('app.queue.EvaluationRunRepository', return_value=mock_repo),
        patch('asyncio.sleep', new_callable=AsyncMock),
        _no_predecessor(),
    ):
        await run_evaluation_job({}, str(uuid.uuid4()))

    assert call_count == 2
    # 3 sessions: attempt 1 (deadlock), attempt 2 (success), finalization
    assert sessions_created == 3
    mock_repo.finalize_if_all_done.assert_awaited_once_with(parent_run_id)
