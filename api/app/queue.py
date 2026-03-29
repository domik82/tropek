"""arq job queue — worker settings and pool dependency."""

from __future__ import annotations

import asyncio
import random
import uuid
from typing import Any, ClassVar, cast

import redis.asyncio as aioredis
import structlog
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from fastapi import Request
from sqlalchemy.exc import DBAPIError

from app.cache.redis_cache import RedisCache
from app.config import get_settings
from app.db.session import get_session_factory
from app.modules.quality_gate.worker import run_evaluation

logger = structlog.get_logger()

_MAX_DEADLOCK_RETRIES = 8


def _is_deadlock(exc: DBAPIError) -> bool:
    """Return True if the exception is a PostgreSQL deadlock (SQLSTATE 40P01)."""
    return 'deadlock' in str(exc).lower()


def _redis_settings() -> RedisSettings:
    """Build arq RedisSettings from application config."""
    settings = get_settings()
    pw = settings.cache.password.get_secret_value()
    return RedisSettings(
        host=settings.cache.host,
        port=settings.cache.port,
        password=pw or None,
        database=settings.queue.db_index,
    )


def get_arq_pool(request: Request) -> ArqRedis:
    """FastAPI dependency — returns the arq pool stored on app.state at startup."""
    pool = getattr(request.app.state, 'arq_pool', None)
    if pool is None:
        raise RuntimeError('arq pool not initialised — lifespan did not run')
    return cast('ArqRedis', pool)


async def create_arq_pool() -> ArqRedis:
    """Create and return an arq connection pool using application config."""
    return await create_pool(_redis_settings())


async def _worker_startup(ctx: dict[str, Any]) -> None:
    """Initialize Redis cache for worker processes."""
    settings = get_settings()
    redis_client = aioredis.from_url(settings.cache.url)
    ctx['cache'] = RedisCache(redis_client)


async def _worker_shutdown(ctx: dict[str, Any]) -> None:
    """Close Redis cache connection."""
    cache: RedisCache | None = ctx.get('cache')
    if cache and cache._redis:
        await cache._redis.close()


async def run_evaluation_job(ctx: dict[str, Any], eval_id_str: str) -> None:
    """Arq job function — wraps run_evaluation with a DB session.

    Retries up to _MAX_DEADLOCK_RETRIES times on PostgreSQL deadlock errors.
    Deadlocks are safe to retry because the entire transaction is rolled back
    before the error surfaces, leaving the evaluation in its original PENDING state.
    """
    session_factory = get_session_factory()
    eval_id = uuid.UUID(eval_id_str)
    cache: RedisCache | None = ctx.get('cache')

    for attempt in range(_MAX_DEADLOCK_RETRIES):
        async with session_factory() as session:
            try:
                await run_evaluation(session, eval_id, cache=cache)
                await session.commit()
                return
            except DBAPIError as exc:
                await session.rollback()
                if _is_deadlock(exc) and attempt < _MAX_DEADLOCK_RETRIES - 1:
                    backoff = 0.1 * 2**attempt
                    jittered = backoff + random.uniform(0, backoff)  # noqa: S311
                    logger.warning(
                        'deadlock detected, retrying',
                        evaluation_id=eval_id_str,
                        attempt=attempt + 1,
                        max_attempts=_MAX_DEADLOCK_RETRIES,
                        backoff_seconds=round(jittered, 3),
                    )
                    await asyncio.sleep(jittered)
                    continue
                logger.exception(
                    'all deadlock retries exhausted',
                    evaluation_id=eval_id_str,
                    attempts=_MAX_DEADLOCK_RETRIES,
                )
                raise
            except Exception:
                await session.rollback()
                raise


class WorkerSettings:
    """arq worker configuration — discovered by `arq app.queue.WorkerSettings`."""

    functions: ClassVar[list[Any]] = [run_evaluation_job]
    on_startup = _worker_startup
    on_shutdown = _worker_shutdown
    redis_settings = _redis_settings()
