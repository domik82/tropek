"""Shared fixtures for endpoint integration tests.

These tests use a real test database (via db_session from conftest.py)
with FastAPI AsyncClient (httpx). The DB session dependency is overridden
to use the test session, so all changes are rolled back after each test.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest_asyncio
from app.db.models import Asset, AssetType
from app.db.session import get_session
from app.main import app
from app.modules.quality_gate.repository import EvaluationRepository
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# Re-use the db_session / db_engine / db_url fixtures from the db test package.
pytest_plugins = ["tests.db.conftest"]

_START = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
_END = datetime(2026, 3, 15, 10, 30, 0, tzinfo=UTC)


def _make_snapshot(name: str = "vm-test-01", os: str = "windows-11", arch: str = "x64") -> dict:
    return {"name": name, "tags": {"os": os, "arch": arch}}


async def _create_asset(session: AsyncSession, name: str | None = None) -> uuid.UUID:
    type_name = f"vm-{uuid.uuid4().hex[:8]}"
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    asset_name = name or f"asset-{asset_id.hex[:8]}"
    session.add(Asset(id=asset_id, name=asset_name, type_name=type_name))
    await session.flush()
    return asset_id


async def _create_completed_eval(
    session: AsyncSession,
    asset_id: uuid.UUID,
    *,
    result: str = "pass",
    score: float = 90.0,
    indicator_results: list | None = None,
    slo_name: str = "test-slo",
    evaluation_name: str = "compile-test",
    period_start: datetime = _START,
    period_end: datetime = _END,
) -> uuid.UUID:
    repo = EvaluationRepository(session)
    ev = await repo.create_pending(
        evaluation_name=evaluation_name,
        period_start=period_start,
        period_end=period_end,
        ingestion_mode="push",
        asset_snapshot=_make_snapshot(),
        metadata={},
        asset_id=asset_id,
        slo_name=slo_name,
    )
    await repo.mark_completed(
        ev.id,
        result=result,
        score=score,
        indicator_results=indicator_results or [],
        slo_name=slo_name,
    )
    return ev.id


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
