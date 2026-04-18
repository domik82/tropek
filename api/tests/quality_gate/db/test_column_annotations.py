"""Integration tests for the column-annotations endpoint."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
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


async def _setup_run_with_annotations(
    session: AsyncSession,
    asset_id: uuid.UUID,
    category_id: uuid.UUID,
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """Create an EvaluationRun with 2 SLOEvaluations, each with 1 annotation."""
    run = EvaluationRun(
        id=uuid.uuid4(),
        asset_id=asset_id,
        eval_name='daily',
        period_start=_BASE,
        period_end=_BASE + timedelta(hours=1),
        status='completed',
        result='pass',
        achieved_points=10,
        total_points=10,
    )
    session.add(run)
    await session.flush()

    ann_ids = []
    for slo_name in ('slo-a', 'slo-b'):
        slo_eval = SLOEvaluation(
            id=uuid.uuid4(),
            evaluation_id=run.id,
            evaluation_name='daily',
            asset_id=asset_id,
            asset_snapshot={'name': 'test-asset', 'tags': {}},
            period_start=_BASE,
            period_end=_BASE + timedelta(hours=1),
            slo_name=slo_name,
            ingestion_mode='push',
            status='completed',
            result='pass',
        )
        session.add(slo_eval)
        await session.flush()

        ann = EvaluationAnnotation(
            id=uuid.uuid4(),
            slo_evaluation_id=slo_eval.id,
            content=f'note for {slo_name}',
            author='tester',
            category_id=category_id,
        )
        session.add(ann)
        ann_ids.append(ann.id)

    await session.flush()
    return run.id, ann_ids


@pytest.mark.integration
async def test_column_annotations_returns_all_slo_annotations(
    db_session: AsyncSession,
    async_client: AsyncClient,
    info_category_id: uuid.UUID,
) -> None:
    """GET /evaluations/column-annotations returns annotations from all SLOs in the run."""
    asset_id = await _setup_asset(db_session, 'col-ann-asset')
    run_id, ann_ids = await _setup_run_with_annotations(db_session, asset_id, info_category_id)

    resp = await async_client.get(
        '/evaluations/column-annotations',
        params={'evaluation_id': str(run_id)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    returned_ids = {a['id'] for a in data}
    assert returned_ids == {str(aid) for aid in ann_ids}


@pytest.mark.integration
async def test_column_annotations_excludes_hidden(
    db_session: AsyncSession,
    async_client: AsyncClient,
    info_category_id: uuid.UUID,
) -> None:
    """Hidden annotations are excluded from the response."""
    asset_id = await _setup_asset(db_session, 'col-ann-hidden-asset')
    run_id, ann_ids = await _setup_run_with_annotations(db_session, asset_id, info_category_id)

    await db_session.execute(
        update(EvaluationAnnotation)
        .where(EvaluationAnnotation.id == ann_ids[0])
        .values(hidden_at=datetime.now(UTC), hidden_by='admin', hidden_reason='spam')
    )
    await db_session.flush()

    resp = await async_client.get(
        '/evaluations/column-annotations',
        params={'evaluation_id': str(run_id)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]['id'] == str(ann_ids[1])


@pytest.mark.integration
async def test_column_annotations_empty_when_no_annotations(
    db_session: AsyncSession,
    async_client: AsyncClient,
) -> None:
    """Returns empty list when the run has no annotations."""
    asset_id = await _setup_asset(db_session, 'col-ann-empty-asset')
    run = EvaluationRun(
        id=uuid.uuid4(),
        asset_id=asset_id,
        eval_name='daily',
        period_start=_BASE,
        period_end=_BASE + timedelta(hours=1),
        status='completed',
        result='pass',
        achieved_points=10,
        total_points=10,
    )
    db_session.add(run)
    await db_session.flush()

    resp = await async_client.get(
        '/evaluations/column-annotations',
        params={'evaluation_id': str(run.id)},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.integration
async def test_column_annotations_404_for_unknown_run(
    async_client: AsyncClient,
) -> None:
    """Returns 404 when the evaluation_id does not exist."""
    resp = await async_client.get(
        '/evaluations/column-annotations',
        params={'evaluation_id': str(uuid.uuid4())},
    )
    assert resp.status_code == 404


@pytest.mark.integration
async def test_column_annotations_unions_run_level_and_slo_level(
    db_session: AsyncSession,
    async_client: AsyncClient,
    info_category_id: uuid.UUID,
) -> None:
    """Run-level notes (new UI form) and SLO-level notes (re-eval) are both returned."""
    asset_id = await _setup_asset(db_session, 'col-ann-union-asset')
    run_id, slo_ann_ids = await _setup_run_with_annotations(db_session, asset_id, info_category_id)

    run_ann = EvaluationAnnotation(
        id=uuid.uuid4(),
        evaluation_run_id=run_id,
        content='column-level note',
        author='daisy',
        category_id=info_category_id,
    )
    db_session.add(run_ann)
    await db_session.flush()

    resp = await async_client.get(
        '/evaluations/column-annotations',
        params={'evaluation_id': str(run_id)},
    )
    assert resp.status_code == 200
    data = resp.json()
    returned_ids = {a['id'] for a in data}
    assert returned_ids == {str(run_ann.id), *(str(aid) for aid in slo_ann_ids)}
    run_ann_entry = next(a for a in data if a['id'] == str(run_ann.id))
    assert run_ann_entry['evaluation_run_id'] == str(run_id)
    assert run_ann_entry['slo_evaluation_id'] is None
    slo_ann_entry = next(a for a in data if a['id'] == str(slo_ann_ids[0]))
    assert slo_ann_entry['evaluation_run_id'] is None
    assert slo_ann_entry['slo_evaluation_id'] is not None
