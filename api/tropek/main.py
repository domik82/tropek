"""TROPEK API — FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI

from tropek.cache.redis_cache import RedisCache
from tropek.config import get_settings
from tropek.db.middleware import SessionMiddleware
from tropek.db.session import get_session_factory
from tropek.logging_config import configure_logging
from tropek.modules.asset_meta.router import router as asset_meta_router
from tropek.modules.assets.router import router as assets_router
from tropek.modules.assignments.router import router as assignments_router
from tropek.modules.common.exception_handlers import (
    conflict_handler,
    domain_validation_handler,
    not_found_handler,
)
from tropek.modules.common.exceptions import (
    ConflictError,
    DomainValidationError,
    NotFoundError,
)
from tropek.modules.datasource.router import router as datasource_router
from tropek.modules.display_groups.router import router as display_groups_router
from tropek.modules.quality_gate.router import router as quality_gate_router
from tropek.modules.sli_registry.router import router as sli_router
from tropek.modules.slo_groups.router import router as slo_groups_router
from tropek.modules.slo_registry.router import router as slo_router
from tropek.queue import create_arq_pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Validate config, configure logging, and open the arq pool at startup; close it on shutdown."""
    settings = get_settings()
    settings.validate_required()
    configure_logging()
    app.state.arq_pool = await create_arq_pool()
    cache_redis = aioredis.from_url(settings.cache.url)
    app.state.cache = RedisCache(cache_redis)
    yield
    await cache_redis.aclose()  # type: ignore[attr-defined]
    await app.state.arq_pool.close()


app = FastAPI(title='TROPEK API', version='0.2.0', lifespan=lifespan)
app.add_middleware(SessionMiddleware, session_factory=get_session_factory())

# Domain exception handlers — convert domain errors to HTTP responses
app.add_exception_handler(NotFoundError, not_found_handler)  # type: ignore[arg-type]
app.add_exception_handler(ConflictError, conflict_handler)  # type: ignore[arg-type]
app.add_exception_handler(DomainValidationError, domain_validation_handler)  # type: ignore[arg-type]

# No prefix= — every router defines full absolute paths
app.include_router(asset_meta_router)
app.include_router(assets_router)
app.include_router(datasource_router)
app.include_router(sli_router)
app.include_router(slo_router)
app.include_router(slo_groups_router)
app.include_router(quality_gate_router)
app.include_router(assignments_router)
app.include_router(display_groups_router)


@app.get('/health')
async def health() -> dict[str, str]:
    """Return service health status."""
    return {'status': 'ok'}


@app.get('/config/ui')
async def ui_config() -> dict[str, int | bool | str]:
    """Return UI-facing configuration limits."""
    settings = get_settings()
    return {
        'maxEvaluations': settings.ui.max_evaluations,
        'pageSize': settings.ui.page_size,
        'heatmapSloGroupsExpandedByDefault': settings.ui.heatmap_slo_groups_expanded_by_default,
        'dataStartDate': settings.ui.data_start_date,
    }
