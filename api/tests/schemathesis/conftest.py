"""Conftest for Schemathesis property-based tests.

Loads the OpenAPI schema directly from the FastAPI app via ASGI. The schema
exposed at ``/openapi.json`` matches the committed ``api/openapi.json`` file
(kept fresh by Phase 1 codegen), and binding to the app lets ``case.call()``
dispatch through the ASGI layer without opening a network port.

The production lifespan opens an arq (Redis) pool and a Redis cache client;
neither is available during a property-based test run that targets only the
TimescaleDB test instance on port 5433. We swap the lifespan for a stub that
seeds ``app.state`` with a fakeredis-backed cache and a no-op arq pool so
routes that touch those attributes can still serialise a response. Endpoints
that *invoke* arq (POST /api/evaluations, /api/evaluations/re-evaluate) are
excluded from fuzzing in ``test_schema.py``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import fakeredis.aioredis
import schemathesis
from dotenv import load_dotenv
from fastapi import FastAPI
from schemathesis.specs.openapi.schemas import OpenApiSchema

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / '.env.test', override=False)

# Import after env is loaded so pydantic-settings picks up the test DB config.
from tropek.cache.redis_cache import RedisCache  # noqa: E402
from tropek.main import app  # noqa: E402


class _NoopArqPool:
    """Stand-in for the arq Redis pool used by evaluation enqueue endpoints."""

    async def enqueue_job(self, *_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(job_id='schemathesis-stub')

    async def close(self) -> None:
        return None


@asynccontextmanager
async def _test_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan replacement that avoids external Redis/arq connections."""
    cache_redis = fakeredis.aioredis.FakeRedis()
    app.state.arq_pool = _NoopArqPool()
    app.state.cache = RedisCache(cache_redis)
    try:
        yield
    finally:
        await cache_redis.aclose()  # type: ignore[attr-defined]


app.router.lifespan_context = _test_lifespan


def load_schema() -> OpenApiSchema:
    """Load the OpenAPI schema from the FastAPI app via ASGI transport."""
    return schemathesis.openapi.from_asgi('/openapi.json', app)


schema = load_schema()
