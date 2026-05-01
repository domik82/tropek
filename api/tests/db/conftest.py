"""Database fixtures for integration tests.

Requires a running test database. Start it with:
    ./start_test_infra.sh

The .env.test file is loaded automatically from the repo root when this
conftest is imported, so no env var injection or shell sourcing is needed.

Usage:
    uv run pytest api/tests/ -m integration -v
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import fakeredis.aioredis
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from tropek.db.models import AnnotationCategory, Base

# Load .env.test (repo root) so TEST_DATABASE_URL and TK_DB_* are available.
# override=False: shell env vars take precedence if already set.
# Must come after imports but before fixtures — pydantic-settings reads env vars
# lazily when settings objects are instantiated inside test fixtures, not here.
load_dotenv(Path(__file__).parents[3] / '.env.test', override=False)


@pytest.fixture(scope='session')
def db_url() -> str:
    """Return the test database URL, skipping if not configured."""
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL not set — skipping integration tests')
    return url


@pytest_asyncio.fixture(scope='session')
async def db_engine(db_url: str) -> AsyncGenerator[AsyncEngine, None]:  # noqa: UP043
    """Create a throwaway database inside the shared test container.

    Each pytest session gets its own freshly-created database
    (``tropek_test_<uuid>``) on the shared TimescaleDB container, so parallel
    sessions on different branches/worktrees never collide and every run
    starts from a clean schema — no drift between ``create_all`` and a
    pre-existing ``alembic``-migrated layout. The database is dropped on
    teardown, so nothing accumulates across runs.
    """
    base_url, _, _ = db_url.rpartition('/')
    admin_url = f'{base_url}/postgres'
    ephemeral_name = f'tropek_test_{uuid.uuid4().hex[:12]}'
    ephemeral_url = f'{base_url}/{ephemeral_name}'

    admin = create_async_engine(admin_url, isolation_level='AUTOCOMMIT')
    try:
        async with admin.connect() as conn:
            await conn.execute(text(f'CREATE DATABASE "{ephemeral_name}"'))
    finally:
        await admin.dispose()

    engine = create_async_engine(ephemeral_url, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        # Seed the default annotation categories that migration 002 inserts
        # in real deployments; integration tests rely on create_all, which
        # does not run data migrations.
        async with AsyncSession(engine) as seed_session:
            for name, label, color, show_on_graph, is_system in (
                ('failure', 'Failure', 'red', True, False),
                ('info', 'Info', 'sky', True, False),
                ('investigation', 'Investigation', 'amber', True, False),
                ('re-evaluation', 'Re-eval', 'gray', False, True),
            ):
                seed_session.add(
                    AnnotationCategory(
                        id=uuid.uuid4(),
                        name=name,
                        label=label,
                        color=color,
                        show_on_graph=show_on_graph,
                        is_system=is_system,
                    )
                )
            await seed_session.commit()
        yield engine
    finally:
        await engine.dispose()
        admin = create_async_engine(admin_url, isolation_level='AUTOCOMMIT')
        try:
            async with admin.connect() as conn:
                await conn.execute(text(f'DROP DATABASE IF EXISTS "{ephemeral_name}" WITH (FORCE)'))
        finally:
            await admin.dispose()


@pytest_asyncio.fixture()
async def redis_client() -> AsyncGenerator[fakeredis.aioredis.FakeRedis, None]:  # noqa: UP043
    """In-memory async Redis for integration tests.

    Uses fakeredis so cache tests don't require a real Redis container — the
    dedicated test-env profile only runs TimescaleDB. Each test gets a fresh
    instance; tear-down flushes all keys.
    """
    client = fakeredis.aioredis.FakeRedis()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest_asyncio.fixture()
async def info_category_id(db_session: AsyncSession) -> uuid.UUID:
    """Return the id of the seeded 'info' annotation category."""
    result = await db_session.execute(select(AnnotationCategory.id).where(AnnotationCategory.name == 'info'))
    return result.scalar_one()


@pytest_asyncio.fixture()
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:  # noqa: UP043
    """Yield a session bound to a rolled-back connection — no DB pollution between tests.

    join_transaction_mode="create_savepoint" ensures the session joins the outer
    transaction rather than starting its own, which is required for asyncpg compatibility
    when queries use SELECT ... FOR UPDATE.
    """
    async with db_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode='create_savepoint',
        )
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()
