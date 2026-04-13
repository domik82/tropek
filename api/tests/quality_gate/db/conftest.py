"""Re-export shared DB fixtures and provide HTTP client fixture for DB integration tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import Asset, AssetType
from tropek.db.session import get_session
from tropek.main import app
from tropek.modules.quality_gate.repositories.evaluation import EvaluationRepository
from tropek.modules.quality_gate.repositories.evaluation_run import EvaluationRunRepository
from tropek.modules.quality_gate.shared.params import EvalCreateParams

from tests.db.conftest import db_engine, db_session, db_url  # noqa: F401

_BASE_TS = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)


@dataclass
class SeededAsset:
    """Minimal asset descriptor returned by the seed fixture."""

    id: uuid.UUID
    name: str


@pytest_asyncio.fixture()
async def api_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:  # noqa: F811
    """Yield an httpx AsyncClient bound to the FastAPI app with the test DB session.

    Overrides the ``get_session`` dependency so every handler call shares the
    same rolled-back session managed by ``db_session``.
    """

    async def _override_get_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
def seed_asset_with_indicators(db_session: AsyncSession):  # noqa: F811
    """Return a factory that seeds an asset with N completed EvaluationRuns.

    Usage::

        asset = await seed_asset_with_indicators(cell_count=5)
        # asset.name  →  unique asset name usable in ?asset_name= query param
    """

    async def _factory(*, cell_count: int = 3) -> SeededAsset:
        type_name = f'vm-{uuid.uuid4().hex[:8]}'
        db_session.add(AssetType(id=uuid.uuid4(), name=type_name))
        await db_session.flush()

        asset_id = uuid.uuid4()
        asset_name = f'cache-test-{uuid.uuid4().hex[:8]}'
        db_session.add(Asset(id=asset_id, name=asset_name, type_name=type_name))
        await db_session.flush()

        run_repo = EvaluationRunRepository(db_session)
        eval_repo = EvaluationRepository(db_session)

        for index in range(cell_count):
            start = _BASE_TS + timedelta(hours=index)
            run = await run_repo.create(
                asset_id=asset_id,
                eval_name='perf-eval',
                period_start=start,
                period_end=start + timedelta(hours=1),
            )
            await eval_repo.create_pending(
                EvalCreateParams(
                    evaluation_id=run.id,
                    evaluation_name='perf-eval',
                    period_start=start,
                    period_end=start + timedelta(hours=1),
                    ingestion_mode='push',
                    asset_snapshot={'name': asset_name, 'tags': {}},
                    variables={},
                    asset_id=asset_id,
                    slo_name='perf-slo',
                )
            )
            await run_repo.mark_completed(
                run.id,
                result='pass',
                achieved_points=10,
                total_points=10,
            )

        return SeededAsset(id=asset_id, name=asset_name)

    return _factory
