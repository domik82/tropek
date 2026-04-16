"""Re-export shared DB fixtures and provide HTTP client fixture for asset_meta integration tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import fakeredis.aioredis
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import Asset, AssetType
from tropek.db.session import get_session
from tropek.main import app
from tropek.modules.quality_gate.shared.dependencies import get_heatmap_column_cache
from tropek.modules.quality_gate.workflows.presentation.heatmap_cache import HeatmapColumnCache

from tests.db.conftest import db_engine, db_session, db_url, redis_client  # noqa: F401


@pytest_asyncio.fixture()
async def api_client(
    db_session: AsyncSession,  # noqa: F811
    redis_client: fakeredis.aioredis.FakeRedis,  # noqa: F811
) -> AsyncGenerator[AsyncClient]:
    """Yield an httpx AsyncClient bound to the FastAPI app with the test DB session."""

    async def _override_get_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    async def _override_get_heatmap_column_cache() -> HeatmapColumnCache:
        return HeatmapColumnCache(redis_client)

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_heatmap_column_cache] = _override_get_heatmap_column_cache
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def test_asset_id(db_session: AsyncSession) -> uuid.UUID:  # noqa: F811
    """Create a real asset in the DB and return its UUID."""
    type_name = f'svc-{uuid.uuid4().hex[:8]}'
    db_session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await db_session.flush()

    asset_id = uuid.uuid4()
    db_session.add(Asset(id=asset_id, name=f'meta-test-{uuid.uuid4().hex[:8]}', type_name=type_name))
    await db_session.flush()
    return asset_id
