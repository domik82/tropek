"""arq job queue — worker settings and pool dependency."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any, ClassVar, cast

import httpx
import redis.asyncio as aioredis
import structlog
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from fastapi import Request

from app.cache.redis_cache import RedisCache
from app.config import get_settings
from app.db.session import get_session_factory
from app.logging_config import configure_logging
from app.modules.datasource.repository import DataSourceRepository
from app.modules.quality_gate.adapter_client import HttpAdapterClient
from app.modules.quality_gate.baseline_repository import BaselineRepository
from app.modules.quality_gate.evaluation_run_repository import EvaluationRunRepository
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.quality_gate.worker import (
    DefinitionLoadError,
    fetch_and_evaluate,
    load_evaluation_snapshot,
    write_results,
)
from app.modules.quality_gate.worker import _load_definitions

logger = structlog.get_logger()

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
    """Initialize Redis cache, httpx client, and logging for worker processes."""
    configure_logging(service_name='worker')
    settings = get_settings()
    redis_client = aioredis.from_url(settings.cache.url)
    ctx['cache'] = RedisCache(redis_client)
    ctx['http_client'] = httpx.AsyncClient(
        timeout=settings.reliability.adapter_timeout_seconds,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )


async def _worker_shutdown(ctx: dict[str, Any]) -> None:
    """Close Redis cache and httpx client connections."""
    cache: RedisCache | None = ctx.get('cache')
    if cache and cache._redis:
        await cache._redis.close()
    http_client: httpx.AsyncClient | None = ctx.get('http_client')
    if http_client:
        await http_client.aclose()


async def run_evaluation_job(ctx: dict[str, Any], eval_id_str: str, defer_count: int = 0) -> None:
    """Arq job — run evaluation in three phases with separate DB sessions.

    Phase 1: Mark running + snapshot (COMMIT immediately).
    Phase 2a: Load definitions (short read session).
    Phase 2b: HTTP query + evaluate (baselines need a read session).
    Phase 3: Write results (COMMIT immediately).
    Then enqueue a deduped finalize job for the parent run.
    """
    session_factory = get_session_factory()
    eval_id = uuid.UUID(eval_id_str)
    cache: RedisCache | None = ctx.get('cache')
    log = logger.bind(evaluation_id=eval_id_str)

    # Predecessor deferral
    if defer_count < _MAX_PREDECESSOR_DEFERS and await _has_pending_predecessor(
        session_factory, eval_id
    ):
        log.info('deferring evaluation — predecessor still pending', defer_count=defer_count + 1)
        pool: ArqRedis = ctx['redis']
        await pool.enqueue_job(
            'run_evaluation_job',
            eval_id_str,
            defer_count + 1,
            _defer_by=timedelta(seconds=2),
        )
        return

    # Phase 1: Mark running + snapshot (COMMIT immediately)
    async with session_factory() as session:
        snapshot = await load_evaluation_snapshot(session, eval_id, worker_id=ctx.get('job_id'))
        await session.commit()

    if snapshot is None:
        return

    # Phase 2a: Load definitions (short read session)
    try:
        async with session_factory() as session:
            slo_def, sli_def = await _load_definitions(session, snapshot, cache=cache)
            datasource = await DataSourceRepository(session).get_by_name(
                snapshot.data_source_name
            )
            if datasource is None:
                raise DefinitionLoadError(
                    f"datasource '{snapshot.data_source_name}' not found"
                )
            await session.commit()
    except DefinitionLoadError as exc:
        log.warning('definitions not found', reason=str(exc))
        async with session_factory() as session:
            await EvaluationRepository(session).mark_failed(
                eval_id, job_stats={'error': str(exc)}
            )
            await session.commit()
        return

    # Phase 2b: HTTP query + evaluate (baselines need a read session)
    http_client: httpx.AsyncClient | None = ctx.get('http_client')
    adapter_client = HttpAdapterClient(
        timeout=get_settings().reliability.adapter_timeout_seconds,
        http_client=http_client,
    )

    async with session_factory() as session:
        baseline_repo = BaselineRepository(session, cache=cache)
        fetch_result = await fetch_and_evaluate(
            snapshot=snapshot,
            slo_def=slo_def,
            sli_def=sli_def,
            datasource=datasource,
            adapter_client=adapter_client,
            baseline_repo=baseline_repo,
        )
        await session.commit()

    if fetch_result is None:
        async with session_factory() as session:
            await EvaluationRepository(session).mark_failed(
                eval_id, job_stats={'error': 'adapter query failed'}
            )
            await session.commit()
        return

    # Phase 3: Write results (COMMIT immediately)
    async with session_factory() as session:
        await write_results(
            session=session,
            snapshot=snapshot,
            slo_def=slo_def,
            sli_def=sli_def,
            fetch_result=fetch_result,
        )
        await session.commit()

    log.info('evaluation completed', result=fetch_result.eval_result.result)

    # Enqueue deduped finalize for parent run
    pool = ctx['redis']
    await pool.enqueue_job(
        'finalize_run_job',
        str(snapshot.parent_run_id),
        _job_id=f'finalize:{snapshot.parent_run_id}',
    )


async def finalize_run_job(ctx: dict[str, Any], run_id_str: str) -> None:
    """Arq job — finalize parent evaluation run if all children are done."""
    session_factory = get_session_factory()
    run_id = uuid.UUID(run_id_str)

    async with session_factory() as session:
        run_repo = EvaluationRunRepository(session)
        finalized = await run_repo.finalize_if_all_done(run_id)
        await session.commit()

    if finalized is not None:
        logger.info(
            'parent evaluation run completed',
            evaluation_id=run_id_str,
            result=finalized.result,
        )


class WorkerSettings:
    """arq worker configuration — discovered by `arq app.queue.WorkerSettings`."""

    functions: ClassVar[list[Any]] = [run_evaluation_job, finalize_run_job]
    on_startup = _worker_startup
    on_shutdown = _worker_shutdown
    max_jobs = get_settings().queue.max_jobs
    redis_settings = _redis_settings()
