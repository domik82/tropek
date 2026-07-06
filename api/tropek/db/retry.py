"""Deadlock retry helper for evaluation mutation actions.

A Postgres deadlock (``asyncpg`` ``DeadlockDetectedError``, SQLSTATE ``40P01``)
aborts the *entire* transaction, so a savepoint cannot rescue it — the unit of
work must be rolled back and re-run. Because ``SessionMiddleware`` commits the
per-request session only after the handler returns, this helper wraps the repo
call inside the handler (where the error surfaces at ``execute``/``flush``),
rolls the session back, and retries with jittered exponential backoff.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable

import asyncpg
import structlog
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.config import QualityGateInvalidateSettings

logger = structlog.get_logger()

_DEADLOCK_SQLSTATE = '40P01'

# SystemRandom avoids the pseudo-random weakness lint (S311); the strength is
# irrelevant here — jitter only needs concurrent retriers to desync.
_jitter = random.SystemRandom()


def _is_deadlock(error: DBAPIError) -> bool:
    """Return True when a SQLAlchemy DBAPIError wraps a Postgres deadlock."""
    cause = error.orig
    if isinstance(cause, asyncpg.exceptions.DeadlockDetectedError):
        return True
    return getattr(cause, 'sqlstate', None) == _DEADLOCK_SQLSTATE


def _backoff_seconds(attempt: int, settings: QualityGateInvalidateSettings) -> float:
    """Jittered exponential backoff in seconds for the given attempt (0-indexed)."""
    capped_ms = min(settings.base_backoff_ms * 2**attempt, settings.max_backoff_ms)
    return _jitter.uniform(0, capped_ms) / 1000


async def run_with_deadlock_retry[T](
    session: AsyncSession,
    operation: Callable[[], Awaitable[T]],
    *,
    settings: QualityGateInvalidateSettings,
) -> T:
    """Run ``operation`` (the repo write), retrying on Postgres deadlock.

    On a ``DeadlockDetectedError`` / SQLSTATE ``40P01`` the aborted transaction is
    rolled back to a clean state, a jittered backoff is awaited, and ``operation``
    is re-run. The original error is re-raised once attempts are exhausted; any
    non-deadlock ``DBAPIError`` is re-raised immediately without a rollback loop.

    Args:
        session: The per-request session to roll back between attempts.
        operation: Zero-arg async callable performing the read-modify-write.
        settings: Retry tuning (``max_retries``, ``base_backoff_ms``, ``max_backoff_ms``).

    Returns:
        The value returned by ``operation`` on the first successful attempt.
    """
    for attempt in range(settings.max_retries + 1):
        try:
            return await operation()
        except DBAPIError as error:
            if not _is_deadlock(error) or attempt == settings.max_retries:
                raise
            await session.rollback()
            backoff = _backoff_seconds(attempt, settings)
            logger.warning(
                'deadlock on evaluation action, retrying',
                attempt=attempt + 1,
                max_retries=settings.max_retries,
                backoff_seconds=backoff,
                error=str(error),
            )
            await asyncio.sleep(backoff)
    # Unreachable: the loop either returns or raises, but satisfies the type checker.
    msg = 'run_with_deadlock_retry exhausted its loop without returning or raising'
    raise RuntimeError(msg)
