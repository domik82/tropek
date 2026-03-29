"""FastAPI application factory with lifespan management."""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import fakeredis.aioredis
import httpx
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

logger = logging.getLogger(__name__)

LOG_FORMAT = '%(asctime)s [%(levelname)-7s] %(name)s: %(message)s'
LOG_DATEFMT = '%Y-%m-%d %H:%M:%S'


def _configure_logging(settings: Settings) -> None:
    """Set up logging to stderr and optionally to a file."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    # httpx logs every request at INFO with URL-encoded params — noisy and unreadable.
    # The adapter logs its own readable version at INFO via prometheus_client.
    logging.getLogger('httpx').setLevel(logging.WARNING)

    # Always log to stderr (Docker picks this up)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(level)
    stderr_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))
    root.addHandler(stderr_handler)

    # Optionally log to file (LOG_DIR env var)
    if settings.log_dir:
        log_path = Path(settings.log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path / 'adapter.log')
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))
        root.addHandler(file_handler)
        logger.info('file logging enabled: %s/adapter.log', log_path)


async def _check_prometheus(base_url: str, timeout: float = 5.0) -> bool:
    """Probe Prometheus readiness at startup. Returns True if reachable."""
    url = f'{base_url.rstrip("/")}/-/ready'
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            if resp.is_success:
                logger.info('prometheus reachable at %s (status=%d)', base_url, resp.status_code)
                return True
            logger.warning('prometheus responded but not ready: %s (status=%d)', base_url, resp.status_code)
            return False
    except httpx.ConnectError:
        logger.warning('prometheus unreachable at %s (connection refused)', base_url)
        return False
    except httpx.TimeoutException:
        logger.warning('prometheus unreachable at %s (timeout after %.0fs)', base_url, timeout)
        return False


def create_app(use_fakeredis: bool = False) -> FastAPI:
    """Create and configure the FastAPI application with lifespan management."""
    settings = Settings()
    _configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
        logger.info(
            'adapter starting: prometheus_url=%s redis_url=%s',
            settings.prometheus_url,
            settings.redis_url,
        )

        redis_client: aioredis.Redis[Any]
        if use_fakeredis:
            redis_client = fakeredis.aioredis.FakeRedis()
        else:
            redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)

        # Verify Redis connectivity
        try:
            pong = await redis_client.ping()
            logger.info('redis connected: %s (ping=%s)', settings.redis_url, pong)
        except Exception:
            logger.exception('redis connection failed: %s', settings.redis_url)

        # Probe Prometheus connectivity (non-blocking, adapter starts either way)
        prom_ok = await _check_prometheus(settings.prometheus_url)
        if not prom_ok:
            logger.warning(
                'adapter will start but queries will fail until prometheus is available at %s',
                settings.prometheus_url,
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

        strategies = {'raw': RawQueryStrategy(prom_client)}

        app.state.job_manager = JobManager(repo, settings)
        app.state.coordinator = Coordinator(repo, settings, strategies)
        app.state.prometheus_ok = prom_ok

        coordinator_task = asyncio.create_task(app.state.coordinator.run())
        logger.info('adapter ready')

        yield

        app.state.coordinator.stop()
        coordinator_task.cancel()
        if hasattr(redis_client, 'aclose'):
            await redis_client.aclose()
        logger.info('adapter shut down')

    app = FastAPI(title='Prometheus SLI Adapter', lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(api_router)
    app.include_router(sync_router)
    return app


app = create_app()
