"""Unit tests for the deadlock retry helper (no database required)."""

from __future__ import annotations

import asyncpg
import pytest
from sqlalchemy.exc import DBAPIError
from tropek.config import QualityGateInvalidateSettings
from tropek.db.retry import run_with_deadlock_retry

_SETTINGS = QualityGateInvalidateSettings(max_retries=3, base_backoff_ms=1, max_backoff_ms=2)


class _FakeSession:
    """Minimal async session stub that only counts rollbacks."""

    def __init__(self) -> None:
        self.rollback_count = 0

    async def rollback(self) -> None:
        self.rollback_count += 1


def _deadlock_error() -> DBAPIError:
    return DBAPIError('UPDATE slo_evaluations ...', {}, asyncpg.exceptions.DeadlockDetectedError('deadlock detected'))


async def test_retries_on_deadlock_then_succeeds() -> None:
    session = _FakeSession()
    attempts = {'count': 0}

    async def operation() -> str:
        attempts['count'] += 1
        if attempts['count'] <= 2:
            raise _deadlock_error()
        return 'ok'

    result = await run_with_deadlock_retry(session, operation, settings=_SETTINGS)

    assert result == 'ok'
    assert attempts['count'] == 3  # 2 failures + 1 success
    assert session.rollback_count == 2  # one rollback per retry


async def test_reraises_original_error_after_exhausting_retries() -> None:
    session = _FakeSession()
    settings = QualityGateInvalidateSettings(max_retries=2, base_backoff_ms=1, max_backoff_ms=2)
    deadlock = _deadlock_error()

    async def operation() -> str:
        raise deadlock

    with pytest.raises(DBAPIError) as excinfo:
        await run_with_deadlock_retry(session, operation, settings=settings)

    assert excinfo.value is deadlock  # the original error, not swallowed or wrapped
    assert session.rollback_count == 2  # initial + 2 retries = 3 attempts, 2 rollbacks


async def test_backoff_called_once_per_retry_and_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    settings = QualityGateInvalidateSettings(max_retries=3, base_backoff_ms=10, max_backoff_ms=40)
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr('tropek.db.retry.asyncio.sleep', fake_sleep)

    async def operation() -> str:
        raise _deadlock_error()

    with pytest.raises(DBAPIError):
        await run_with_deadlock_retry(session, operation, settings=settings)

    # 3 retries between 4 attempts → one bounded backoff per retry (none after the final raise).
    assert len(sleeps) == 3
    assert all(0 <= seconds <= settings.max_backoff_ms / 1000 for seconds in sleeps)


async def test_no_retry_when_max_retries_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    settings = QualityGateInvalidateSettings(max_retries=0, base_backoff_ms=10, max_backoff_ms=40)
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr('tropek.db.retry.asyncio.sleep', fake_sleep)
    attempts = {'count': 0}

    async def operation() -> str:
        attempts['count'] += 1
        raise _deadlock_error()

    with pytest.raises(DBAPIError):
        await run_with_deadlock_retry(session, operation, settings=settings)

    assert attempts['count'] == 1  # exactly one attempt, no retry
    assert session.rollback_count == 0  # deadlock re-raised immediately
    assert sleeps == []


async def test_non_deadlock_error_reraised_immediately() -> None:
    session = _FakeSession()

    async def operation() -> str:
        raise DBAPIError('UPDATE ...', {}, ValueError('boom'))

    with pytest.raises(DBAPIError):
        await run_with_deadlock_retry(session, operation, settings=_SETTINGS)

    assert session.rollback_count == 0  # no rollback loop for non-deadlock errors
