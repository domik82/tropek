"""Integration tests for GET /evaluations/names endpoint."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from app.db.session import get_session
from app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture()
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """Yield an httpx AsyncClient bound to the FastAPI app with test DB session."""

    async def _override_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def test_evaluation_names_returns_distinct_names(
    async_client: AsyncClient,
) -> None:
    """Endpoint returns distinct names with count and last_run, sorted by last_run DESC."""
    resp = await async_client.get("/evaluations/names")
    assert resp.status_code == 200
    names = resp.json()
    assert isinstance(names, list)
    for entry in names:
        assert "name" in entry
        assert "count" in entry
        assert "last_run" in entry
        assert entry["count"] > 0
    # Sorted by last_run descending
    runs = [e["last_run"] for e in names]
    assert runs == sorted(runs, reverse=True)


async def test_evaluation_names_empty_when_no_evals(
    async_client: AsyncClient,
) -> None:
    """Returns empty list when no evaluations match."""
    resp = await async_client.get(
        "/evaluations/names",
        params={"asset_name": "nonexistent-asset"},
    )
    assert resp.status_code == 200
    assert resp.json() == []
