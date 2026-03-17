"""arq job queue integration — pool management and worker settings."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import get_settings
from app.db.session import get_session_factory
from app.modules.quality_gate.worker import run_evaluation

_pool: ArqRedis | None = None


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


async def get_arq_pool() -> ArqRedis:
    """Return the shared arq connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        _pool = await create_pool(_redis_settings())
    return _pool


async def enqueue_evaluation(eval_id: uuid.UUID) -> None:
    """Enqueue a single evaluation job."""
    pool = await get_arq_pool()
    await pool.enqueue_job("run_evaluation_job", str(eval_id))


async def run_evaluation_job(ctx: dict[str, Any], eval_id_str: str) -> None:
    """Arq job function — wraps run_evaluation with a DB session."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            await run_evaluation(session, uuid.UUID(eval_id_str))
            await session.commit()
        except Exception:
            await session.rollback()
            raise


class WorkerSettings:
    """arq worker configuration — discovered by `arq app.queue.WorkerSettings`."""

    functions: ClassVar[list[Any]] = [run_evaluation_job]
    redis_settings = _redis_settings()
