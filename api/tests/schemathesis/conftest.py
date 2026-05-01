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

import queue
import socket
import threading
import time as _time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import fakeredis.aioredis
import schemathesis
from dotenv import load_dotenv
from fastapi import FastAPI
from schemathesis.generation.hypothesis import builder as _hypothesis_builder
from schemathesis.specs.openapi.schemas import OpenApiSchema
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

REPO_ROOT = Path(__file__).resolve().parents[3]
# Override any dev-env values (pytest-dotenv loads the repo-root .env first).
# Schemathesis talks to the test database on 5433 — dev creds must not leak in.
load_dotenv(REPO_ROOT / '.env.test', override=True)

# Import after env is loaded so pydantic-settings picks up the test DB config.
from tropek.cache.redis_cache import RedisCache  # noqa: E402
from tropek.config import get_settings  # noqa: E402
from tropek.db import session as db_session  # noqa: E402
from tropek.main import app  # noqa: E402

_settings = get_settings()


# ---------------------------------------------------------------------------
# Fail fast: verify the test database is reachable before collecting tests.
# Without this, every request silently fails with a connection error and the
# full 6-minute collection + execution runs for nothing.
# ---------------------------------------------------------------------------
def _check_test_database_reachable() -> None:
    host = _settings.database.host
    port = _settings.database.port
    try:
        with socket.create_connection((host, port), timeout=2):
            pass
    except OSError as exc:
        raise RuntimeError(f"test database not reachable at {host}:{port} — run 'just test-env' first") from exc


_check_test_database_reachable()


# ---------------------------------------------------------------------------
# Time-budget the coverage phase per operation.  Schemathesis 4.x generates
# boundary test cases at collection time via ``add_coverage`` →
# ``cover_schema_iter``.  For endpoints with deeply nested body schemas the
# recursive generation explodes — POST /assets/.../snapshots spends ~3 min
# on two ``cover_schema_iter`` calls that block *inside* a single yield.
# A between-yield check cannot interrupt that, so we drain the generator in
# a daemon thread and pull results through a queue with a timeout.
# ---------------------------------------------------------------------------
COVERAGE_TIME_BUDGET_SECONDS = 5.0

_SENTINEL = object()

_original_generate_coverage = _hypothesis_builder.generate_coverage_cases


def _budgeted_generate_coverage(**kwargs: Any) -> list[Any]:
    result_queue: queue.Queue[Any] = queue.Queue()

    def _drain() -> None:
        try:
            for case in _original_generate_coverage(**kwargs):
                result_queue.put(case)
        finally:
            result_queue.put(_SENTINEL)

    worker = threading.Thread(target=_drain, daemon=True)
    worker.start()

    cases: list[Any] = []
    start = _time.monotonic()
    while True:
        remaining = COVERAGE_TIME_BUDGET_SECONDS - (_time.monotonic() - start)
        if remaining <= 0:
            break
        try:
            item = result_queue.get(timeout=remaining)
        except queue.Empty:
            break
        if item is _SENTINEL:
            break
        cases.append(item)
    return cases


_hypothesis_builder.generate_coverage_cases = _budgeted_generate_coverage  # type: ignore[assignment]


def _fresh_engine():  # type: ignore[no-untyped-def]
    """Return a NullPool engine bound to whichever event loop is active now.

    Each Hypothesis example runs in its own event loop via anyio's blocking
    portal. A cached engine remembers the loop it was built on and raises
    "another operation is in progress" when reused from a later loop. The
    session middleware calls ``_get_engine``/``get_session_factory`` once per
    request; returning a fresh engine each call keeps every request on the
    current loop.
    """
    return create_async_engine(_settings.database.async_url, poolclass=NullPool)


def _fresh_session_factory():  # type: ignore[no-untyped-def]
    return async_sessionmaker(_fresh_engine(), expire_on_commit=False, class_=AsyncSession)


db_session._get_engine = _fresh_engine  # type: ignore[assignment]
db_session.get_session_factory = _fresh_session_factory  # type: ignore[assignment]


class _PerRequestSessionFactory:
    """Acts like ``async_sessionmaker`` but builds a fresh engine every call.

    The SessionMiddleware is wired at app import with a single sessionmaker
    instance. Swapping that instance here lets every request create a session
    on a NullPool engine bound to the current event loop.
    """

    def __call__(self) -> object:
        return _fresh_session_factory()()


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

# Rewire SessionMiddleware to use the per-request (per-loop) factory.
for middleware in app.user_middleware:
    if middleware.cls.__name__ == 'SessionMiddleware':
        middleware.kwargs['session_factory'] = _PerRequestSessionFactory()
app.middleware_stack = None  # force rebuild on next request


def load_schema() -> OpenApiSchema:
    """Load the OpenAPI schema from the FastAPI app via ASGI transport."""
    return schemathesis.openapi.from_asgi('/openapi.json', app)


schema = load_schema()
