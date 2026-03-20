"""Tests for deadlock retry logic in run_evaluation_job."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.queue import _is_deadlock, run_evaluation_job
from sqlalchemy.exc import DBAPIError


def _make_deadlock_error() -> DBAPIError:
    """Create a DBAPIError that looks like a PostgreSQL deadlock."""
    orig = Exception("deadlock detected")
    return DBAPIError(
        statement="UPDATE evaluations SET ...",
        params={},
        orig=orig,
    )


def _make_non_deadlock_error() -> DBAPIError:
    """Create a DBAPIError that is not a deadlock."""
    orig = Exception("connection refused")
    return DBAPIError(
        statement="SELECT ...",
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


async def test_deadlock_retry_succeeds_on_second_attempt(mock_session_factory: tuple) -> None:
    """Job retries after deadlock and succeeds on the second attempt."""
    factory, session = mock_session_factory
    call_count = 0

    async def fake_run_evaluation(sess, eval_id):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _make_deadlock_error()

    with (
        patch("app.queue.get_session_factory", return_value=factory),
        patch("app.queue.run_evaluation", side_effect=fake_run_evaluation),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        await run_evaluation_job({}, "00000000-0000-0000-0000-000000000001")

    assert call_count == 2
    assert session.commit.await_count == 1


async def test_deadlock_retry_exhausted(mock_session_factory: tuple) -> None:
    """Job fails after all retries exhausted."""
    factory, _session = mock_session_factory

    with (
        patch("app.queue.get_session_factory", return_value=factory),
        patch("app.queue.run_evaluation", side_effect=_make_deadlock_error()),
        patch("asyncio.sleep", new_callable=AsyncMock),
        pytest.raises(DBAPIError),
    ):
        await run_evaluation_job({}, "00000000-0000-0000-0000-000000000001")


async def test_non_deadlock_error_not_retried(mock_session_factory: tuple) -> None:
    """Non-deadlock DBAPIError should not be retried."""
    factory, session = mock_session_factory

    with (
        patch("app.queue.get_session_factory", return_value=factory),
        patch("app.queue.run_evaluation", side_effect=_make_non_deadlock_error()),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        pytest.raises(DBAPIError),
    ):
        await run_evaluation_job({}, "00000000-0000-0000-0000-000000000001")

    # No sleep called because no retry happened
    mock_sleep.assert_not_awaited()
    # rollback called once (for the single failed attempt)
    session.rollback.assert_awaited_once()


async def test_non_dbapi_error_not_retried(mock_session_factory: tuple) -> None:
    """Non-DBAPIError exceptions should not be retried."""
    factory, session = mock_session_factory

    with (
        patch("app.queue.get_session_factory", return_value=factory),
        patch("app.queue.run_evaluation", side_effect=RuntimeError("unexpected")),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        pytest.raises(RuntimeError, match="unexpected"),
    ):
        await run_evaluation_job({}, "00000000-0000-0000-0000-000000000001")

    mock_sleep.assert_not_awaited()
    session.rollback.assert_awaited_once()


async def test_successful_job_no_retry(mock_session_factory: tuple) -> None:
    """Successful job runs once with no retries."""
    factory, session = mock_session_factory

    with (
        patch("app.queue.get_session_factory", return_value=factory),
        patch("app.queue.run_evaluation", new_callable=AsyncMock),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        await run_evaluation_job({}, "00000000-0000-0000-0000-000000000001")

    mock_sleep.assert_not_awaited()
    session.commit.assert_awaited_once()
