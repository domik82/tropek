"""Re-export shared DB fixtures and provide an HTTP client for change-point router tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.session import get_session
from tropek.main import app

from tests.db.conftest import db_engine, db_session, db_url  # noqa: F401


@pytest_asyncio.fixture()
async def api_client(
    db_session: AsyncSession,  # noqa: F811
) -> AsyncGenerator[AsyncClient]:
    """Yield an httpx AsyncClient bound to the FastAPI app with the test DB session."""

    async def _override_get_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        yield client
    app.dependency_overrides.clear()
