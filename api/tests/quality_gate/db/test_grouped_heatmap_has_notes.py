"""Integration tests for has_notes field on grouped metric heatmap columns."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import (
    Asset,
    AssetType,
    EvaluationAnnotation,
    EvaluationRun,
    SLOEvaluation,
)
from tropek.db.session import get_session
from tropek.main import app

_BASE = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)


@pytest_asyncio.fixture()
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """Yield an httpx AsyncClient bound to the FastAPI app with test DB session."""

    async def _override_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        yield client
    app.dependency_overrides.clear()


async def _setup_asset(session: AsyncSession, name: str) -> uuid.UUID:
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(Asset(id=asset_id, name=name, type_name=type_name))
    await session.flush()
    return asset_id


async def _create_run_with_slo(
    session: AsyncSession,
    asset_id: uuid.UUID,
    asset_name: str,
    *,
    hour_offset: int,
    slo_name: str = 'my-slo',
) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a completed EvaluationRun with one child SLOEvaluation.

    Returns (run_id, slo_evaluation_id).
    """
    start = _BASE + timedelta(hours=hour_offset)
    end = start + timedelta(hours=1)
    run = EvaluationRun(
        id=uuid.uuid4(),
        asset_id=asset_id,
        eval_name='daily',
        period_start=start,
        period_end=end,
        status='completed',
        result='pass',
        achieved_points=10,
        total_points=10,
    )
    session.add(run)
    await session.flush()

    slo_eval = SLOEvaluation(
        id=uuid.uuid4(),
        evaluation_id=run.id,
        evaluation_name='daily',
        asset_id=asset_id,
        asset_snapshot={'name': asset_name, 'tags': {}},
        period_start=start,
        period_end=end,
        slo_name=slo_name,
        ingestion_mode='push',
        status='completed',
        result='pass',
    )
    session.add(slo_eval)
    await session.flush()
    return run.id, slo_eval.id


@pytest.mark.integration
async def test_grouped_heatmap_has_notes_true_for_annotated_column(
    db_session: AsyncSession,
    async_client: AsyncClient,
    info_category_id: uuid.UUID,
) -> None:
    """has_notes is True for a run with an annotation, False for one without."""
    asset_name = 'hm-has-notes-asset'
    asset_id = await _setup_asset(db_session, asset_name)

    annotated_run_id, annotated_slo_id = await _create_run_with_slo(db_session, asset_id, asset_name, hour_offset=0)
    plain_run_id, _ = await _create_run_with_slo(db_session, asset_id, asset_name, hour_offset=1)

    db_session.add(
        EvaluationAnnotation(
            id=uuid.uuid4(),
            slo_evaluation_id=annotated_slo_id,
            content='investigated the spike',
            author='tester',
            category_id=info_category_id,
        )
    )
    await db_session.flush()

    resp = await async_client.get(
        '/evaluations/heatmap',
        params={'asset_name': asset_name},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    columns = data['columns']
    assert len(columns) == 2

    by_run_id = {col['evaluation_id']: col for col in columns}
    assert by_run_id[str(annotated_run_id)]['has_notes'] is True
    assert by_run_id[str(plain_run_id)]['has_notes'] is False


@pytest.mark.integration
async def test_grouped_heatmap_has_notes_false_when_annotation_hidden(
    db_session: AsyncSession,
    async_client: AsyncClient,
    info_category_id: uuid.UUID,
) -> None:
    """A run whose only annotation is soft-deleted reports has_notes=False."""
    asset_name = 'hm-hidden-notes-asset'
    asset_id = await _setup_asset(db_session, asset_name)

    run_id, slo_eval_id = await _create_run_with_slo(db_session, asset_id, asset_name, hour_offset=0)

    db_session.add(
        EvaluationAnnotation(
            id=uuid.uuid4(),
            slo_evaluation_id=slo_eval_id,
            content='hidden note',
            author='tester',
            category_id=info_category_id,
            hidden_at=datetime.now(UTC),
            hidden_by='admin',
            hidden_reason='spam',
        )
    )
    await db_session.flush()

    resp = await async_client.get(
        '/evaluations/heatmap',
        params={'asset_name': asset_name},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    columns = data['columns']
    assert len(columns) == 1
    assert columns[0]['evaluation_id'] == str(run_id)
    assert columns[0]['has_notes'] is False
