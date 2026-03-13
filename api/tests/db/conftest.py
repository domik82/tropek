"""Database fixtures for integration tests.

Requires TEST_DATABASE_URL env var pointing to a real TimescaleDB instance.
Tables are created fresh per test session and dropped on teardown.

Usage:
    export TEST_DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/tropek_test"
    uv run pytest api/tests/db/ -m integration -v
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from app.db.models import Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture(scope="session")
def db_url() -> str:
    """Return the test database URL, skipping if not configured."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set — skipping integration tests")
    return url


@pytest_asyncio.fixture(scope="session")
async def db_engine(db_url: str):
    """Create engine and tables once per test session, drop on teardown."""
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a session that is rolled back after each test — no DB pollution."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session, session.begin():
        yield session
        await session.rollback()
