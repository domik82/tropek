"""arq job queue — worker settings and pool dependency."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar, cast

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from fastapi import Request

from app.config import get_settings
from app.db.session import get_session_factory
from app.modules.quality_gate.worker import run_evaluation


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
    pool = getattr(request.app.state, "arq_pool", None)
    if pool is None:
        raise RuntimeError("arq pool not initialised — lifespan did not run")
    return cast(ArqRedis, pool)


async def create_arq_pool() -> ArqRedis:
    """Create and return an arq connection pool using application config."""
    return await create_pool(_redis_settings())


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
