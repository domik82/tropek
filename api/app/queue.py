"""arq job queue — worker settings and pool dependency."""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import timedelta
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
from app.logging_config import configure_logging
from app.modules.quality_gate.evaluation_run_repository import EvaluationRunRepository
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.quality_gate.worker import run_evaluation

logger = structlog.get_logger()

_MAX_DEADLOCK_RETRIES = 8
_MAX_PREDECESSOR_DEFERS = 60


async def _has_pending_predecessor(session_factory: Any, eval_id: uuid.UUID) -> bool:
    """Check if an earlier eval for the same asset+SLO is still pending/running.

    Returns False on any error so the evaluation proceeds normally.
    """
    try:
        async with session_factory() as session:
            repo = EvaluationRepository(session)
            ev = await repo.get_by_id(eval_id)
            if ev is None or ev.status not in ('pending', 'running'):
                return False
            return await repo.has_pending_predecessor(
                asset_id=ev.asset_id,
                slo_name=ev.slo_name,
                period_start=ev.period_start,
            )
    except (OSError, ValueError, AttributeError):
        logger.warning('predecessor check failed, proceeding', evaluation_id=str(eval_id))
        return False


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
    """Initialize Redis cache and logging for worker processes."""
    configure_logging(service_name='worker')
    settings = get_settings()
    redis_client = aioredis.from_url(settings.cache.url)
    ctx['cache'] = RedisCache(redis_client)


async def _worker_shutdown(ctx: dict[str, Any]) -> None:
    """Close Redis cache connection."""
    cache: RedisCache | None = ctx.get('cache')
    if cache and cache._redis:
        await cache._redis.close()


async def run_evaluation_job(ctx: dict[str, Any], eval_id_str: str, defer_count: int = 0) -> None:
    """Arq job function — wraps run_evaluation with a DB session.

    Ensures chronological ordering: if an earlier evaluation for the same
    asset+SLO is still pending/running, this job is re-enqueued with a delay
    so that baselines are always available when needed.

    Retries up to _MAX_DEADLOCK_RETRIES times on PostgreSQL deadlock errors.
    Deadlocks are safe to retry because the entire transaction is rolled back
    before the error surfaces, leaving the evaluation in its original PENDING state.
    """
    session_factory = get_session_factory()
    eval_id = uuid.UUID(eval_id_str)
    cache: RedisCache | None = ctx.get('cache')

    # Check for pending predecessors (same asset+SLO, earlier period_start)
    if defer_count < _MAX_PREDECESSOR_DEFERS and await _has_pending_predecessor(session_factory, eval_id):
            logger.info(
                'deferring evaluation — predecessor still pending',
                evaluation_id=eval_id_str,
                defer_count=defer_count + 1,
            )
            pool: ArqRedis = ctx['redis']
            await pool.enqueue_job(
                'run_evaluation_job',
                eval_id_str,
                defer_count + 1,
                _defer_by=timedelta(seconds=2),
            )
            return

    parent_run_id: uuid.UUID | None = None

    for attempt in range(_MAX_DEADLOCK_RETRIES):
        async with session_factory() as session:
            try:
                parent_run_id = await run_evaluation(
                    session, eval_id, worker_id=ctx.get('job_id'), cache=cache,
                )
                await session.commit()
                break
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

    # Finalize parent EvaluationRun AFTER commit, in a fresh session.
    # This ensures all sibling SLO evaluations' committed states are visible,
    # avoiding a race where two workers finish their last children concurrently
    # and neither sees the other's uncommitted changes during finalization.
    if parent_run_id is not None:
        await _finalize_parent_run(session_factory, parent_run_id)


_MAX_FINALIZE_RETRIES = 3


async def _finalize_parent_run(
    session_factory: Any,
    parent_run_id: uuid.UUID,
) -> None:
    """Finalize parent run with retries — child data is already committed."""
    for attempt in range(_MAX_FINALIZE_RETRIES):
        try:
            async with session_factory() as session:
                run_repo = EvaluationRunRepository(session)
                finalized = await run_repo.finalize_if_all_done(parent_run_id)
                await session.commit()
                if finalized is not None:
                    logger.info(
                        'parent evaluation run completed',
                        evaluation_id=str(parent_run_id),
                        result=finalized.result,
                    )
                return
        except Exception:
            if attempt < _MAX_FINALIZE_RETRIES - 1:
                backoff = 0.5 * 2**attempt
                logger.warning(
                    'finalize parent run failed, retrying',
                    evaluation_id=str(parent_run_id),
                    attempt=attempt + 1,
                    max_attempts=_MAX_FINALIZE_RETRIES,
                    backoff_seconds=backoff,
                )
                await asyncio.sleep(backoff)
            else:
                logger.exception(
                    'finalize parent run failed after all retries',
                    evaluation_id=str(parent_run_id),
                    attempts=_MAX_FINALIZE_RETRIES,
                )


class WorkerSettings:
    """arq worker configuration — discovered by `arq app.queue.WorkerSettings`."""

    functions: ClassVar[list[Any]] = [run_evaluation_job]
    max_jobs: ClassVar[int] = 12
    on_startup = _worker_startup
    on_shutdown = _worker_shutdown
    redis_settings = _redis_settings()
