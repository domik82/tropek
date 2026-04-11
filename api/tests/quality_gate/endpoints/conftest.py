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
from app.db.models import Asset, AssetType, IndicatorResultRow, SLODefinition, SLOObjective
from app.db.session import get_session
from app.main import app
from app.modules.quality_gate.repositories.evaluation import EvaluationRepository
from app.modules.quality_gate.shared.params import EvalCreateParams
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# Re-export db fixtures so pytest discovers them in this directory.
from tests.db.conftest import db_engine, db_session, db_url  # noqa: F401

_START = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
_END = datetime(2026, 3, 15, 10, 30, 0, tzinfo=UTC)


def _make_snapshot(name: str = 'vm-test-01', os: str = 'windows-11', arch: str = 'x64') -> dict:
    return {'name': name, 'tags': {'os': os, 'arch': arch}}


async def _create_asset(session: AsyncSession, name: str | None = None) -> uuid.UUID:
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    asset_name = name or f'asset-{asset_id.hex[:8]}'
    session.add(Asset(id=asset_id, name=asset_name, type_name=type_name))
    await session.flush()
    return asset_id


async def _create_completed_eval(
    session: AsyncSession,
    asset_id: uuid.UUID,
    *,
    result: str = 'pass',
    score: float = 90.0,
    slo_name: str = 'test-slo',
    evaluation_name: str = 'compile-test',
    period_start: datetime = _START,
    period_end: datetime = _END,
) -> uuid.UUID:
    repo = EvaluationRepository(session)
    ev = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name=evaluation_name,
            period_start=period_start,
            period_end=period_end,
            ingestion_mode='push',
            asset_snapshot=_make_snapshot(),
            variables={},
            asset_id=asset_id,
            slo_name=slo_name,
        )
    )
    await repo.mark_completed(
        ev.id,
        result=result,
        score=score,
        slo_name=slo_name,
    )
    return ev.id


async def _ensure_slo_objective(
    session: AsyncSession,
    slo_name: str = 'test-slo',
    sli: str = 'response_time',
) -> SLOObjective:
    """Create a minimal SLO definition with one objective if it doesn't exist, return the objective."""
    slo_id = uuid.uuid4()
    slo = SLODefinition(
        id=slo_id,
        name=slo_name,
        version=1,
        display_name=slo_name,
        comparison={},
        total_score_pass_threshold=90.0,
        total_score_warning_threshold=75.0,
        tags={},
        variables={},
    )
    session.add(slo)
    obj = SLOObjective(
        id=uuid.uuid4(),
        slo_definition_id=slo_id,
        sli=sli,
        display_name=sli,
        weight=1,
        key_sli=False,
        sort_order=0,
        pass_threshold=['<600'],
        warning_threshold=[],
    )
    session.add(obj)
    await session.flush()
    return obj


async def _seed_indicator_row(
    session: AsyncSession,
    evaluation_id: uuid.UUID,
    objective: SLOObjective,
    *,
    value: float = 250.0,
    status: str = 'pass',
    score: float = 1.0,
) -> None:
    """Seed a single IndicatorResultRow for an evaluation."""
    session.add(
        IndicatorResultRow(
            slo_evaluation_id=evaluation_id,
            slo_objective_id=objective.id,
            value=value,
            compared_value=None,
            change_absolute=None,
            change_relative_pct=None,
            status=status,
            score=score,
        )
    )
    await session.flush()


@pytest_asyncio.fixture()
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:  # noqa: F811
    """Yield an httpx AsyncClient bound to the FastAPI app with test DB session."""

    async def _override_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        yield client
    app.dependency_overrides.clear()
