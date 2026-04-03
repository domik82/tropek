"""Integration tests for EvaluationRunRepository."""

import uuid
from datetime import UTC, datetime

import pytest
from app.db.models import Asset, AssetType, SLOEvaluation
from app.modules.quality_gate.evaluation_run_repository import (
    EvaluationRunRepository,
)


@pytest.fixture
async def asset(db_session):
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    asset_type = AssetType(name=type_name, is_default=False)
    db_session.add(asset_type)
    await db_session.flush()
    a = Asset(name=f'test-asset-{uuid.uuid4().hex[:8]}', type_name=type_name)
    db_session.add(a)
    await db_session.flush()
    return a


@pytest.mark.integration
async def test_create_and_get(db_session, asset):
    repo = EvaluationRunRepository(db_session)
    start = datetime(2026, 1, 15, tzinfo=UTC)
    end = datetime(2026, 1, 16, tzinfo=UTC)

    run = await repo.create(
        asset_id=asset.id,
        eval_name='daily',
        period_start=start,
        period_end=end,
    )
    await db_session.flush()

    fetched = await repo.get_by_id(run.id)
    assert fetched is not None
    assert fetched.eval_name == 'daily'
    assert fetched.status == 'pending'
    assert fetched.result is None


@pytest.mark.integration
async def test_finalize_worst_case_result(db_session, asset):
    repo = EvaluationRunRepository(db_session)
    start = datetime(2026, 1, 15, tzinfo=UTC)
    end = datetime(2026, 1, 16, tzinfo=UTC)

    run = await repo.create(asset_id=asset.id, eval_name='daily', period_start=start, period_end=end)
    await db_session.flush()

    for result, pts_a, pts_t in [('pass', 10, 10), ('warning', 8, 10)]:
        slo_ev = SLOEvaluation(
            evaluation_id=run.id,
            evaluation_name='daily',
            asset_id=asset.id,
            asset_snapshot={},
            period_start=start,
            period_end=end,
            slo_name=f'slo-{result}',
            ingestion_mode='pull',
            status='completed',
            result=result,
            score=float(pts_a),
            achieved_points=pts_a,
            total_points=pts_t,
        )
        db_session.add(slo_ev)
    await db_session.flush()

    rolled_up = await repo.finalize_if_all_done(run.id)
    assert rolled_up is not None
    assert rolled_up.status == 'completed'
    assert rolled_up.result == 'warning'
    assert rolled_up.achieved_points == 18
    assert rolled_up.total_points == 20


@pytest.mark.integration
async def test_finalize_skips_when_not_all_done(db_session, asset):
    repo = EvaluationRunRepository(db_session)
    start = datetime(2026, 1, 15, tzinfo=UTC)
    end = datetime(2026, 1, 16, tzinfo=UTC)

    run = await repo.create(asset_id=asset.id, eval_name='daily', period_start=start, period_end=end)
    await db_session.flush()

    for status, result in [('completed', 'pass'), ('running', None)]:
        slo_ev = SLOEvaluation(
            evaluation_id=run.id,
            evaluation_name='daily',
            asset_id=asset.id,
            asset_snapshot={},
            period_start=start,
            period_end=end,
            slo_name=f'slo-{status}',
            ingestion_mode='pull',
            status=status,
            result=result,
        )
        db_session.add(slo_ev)
    await db_session.flush()

    result = await repo.finalize_if_all_done(run.id)
    assert result is None
