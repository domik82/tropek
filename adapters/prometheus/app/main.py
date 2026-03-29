"""FastAPI application factory with lifespan management."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import fakeredis.aioredis
import redis.asyncio as aioredis
from fastapi import FastAPI

from app.api.routes import router as api_router
from app.api.routes import sync_router
from app.config import Settings
from app.core.coordinator import Coordinator
from app.core.job_manager import JobManager
from app.core.prometheus_client import PrometheusClient
from app.core.strategies.raw import RawQueryStrategy
from app.health.routes import router as health_router
from app.redis.repository import JobRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def create_app(use_fakeredis: bool = False) -> FastAPI:
    """Create and configure the FastAPI application with lifespan management."""
    settings = Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
        redis_client: aioredis.Redis[Any]
        if use_fakeredis:
            redis_client = fakeredis.aioredis.FakeRedis()
        else:
            redis_client = aioredis.from_url(
                settings.redis_url, decode_responses=True
            )

        repo = JobRepository(redis_client, prefix=settings.redis_key_prefix)

        auth = None
        if settings.prometheus_username and settings.prometheus_password:
            auth = (settings.prometheus_username, settings.prometheus_password)

        prom_client = PrometheusClient(
            base_url=settings.prometheus_url,
            timeout=settings.query_timeout_seconds,
            auth=auth,
        )

        strategies = {"raw": RawQueryStrategy(prom_client)}

        app.state.job_manager = JobManager(repo, settings)
        app.state.coordinator = Coordinator(repo, settings, strategies)

        coordinator_task = asyncio.create_task(app.state.coordinator.run())

        yield

        app.state.coordinator.stop()
        coordinator_task.cancel()
        if hasattr(redis_client, "aclose"):
            await redis_client.aclose()

    app = FastAPI(title="Prometheus SLI Adapter", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(api_router)
    app.include_router(sync_router)
    return app


app = create_app()
