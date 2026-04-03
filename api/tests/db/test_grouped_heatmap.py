"""Integration tests for the grouped metric heatmap query."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.db.models import Asset, AssetType, EvaluationRun, SLOEvaluation
from app.modules.quality_gate.evaluation_run_repository import EvaluationRunRepository
from app.modules.quality_gate.params import EvalCreateParams
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.quality_gate.trend_repository import TrendRepository
from sqlalchemy.ext.asyncio import AsyncSession

_BASE = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)


async def _create_asset(session: AsyncSession, name: str) -> uuid.UUID:
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(Asset(id=asset_id, name=name, type_name=type_name))
    await session.flush()
    return asset_id


@pytest.mark.integration
async def test_grouped_heatmap_returns_completed_runs(db_session: AsyncSession) -> None:
    """Each completed EvaluationRun becomes one column in the grouped response."""
    asset_id = await _create_asset(db_session, 'grouped-hm-asset')
    run_repo = EvaluationRunRepository(db_session)
    eval_repo = EvaluationRepository(db_session)
    trend_repo = TrendRepository(db_session)

    # Create 3 parent EvaluationRuns
    for i in range(3):
        start = _BASE + timedelta(hours=i)
        run = await run_repo.create(
            asset_id=asset_id,
            eval_name='daily',
            period_start=start,
            period_end=start + timedelta(hours=1),
        )
        # Create a child SLO evaluation
        await eval_repo.create_pending(
            EvalCreateParams(
                evaluation_name='daily',
                period_start=start,
                period_end=start + timedelta(hours=1),
                ingestion_mode='push',
                asset_snapshot={'name': 'grouped-hm-asset', 'tags': {}},
                variables={},
                asset_id=asset_id,
                slo_name='my-slo',
                evaluation_id=run.id,
            )
        )
        await run_repo.mark_completed(
            run.id,
            result='pass',
            achieved_points=10,
            total_points=10,
        )

    runs = await trend_repo.get_grouped_metric_heatmap(asset_id=asset_id)
    assert len(runs) == 3


@pytest.mark.integration
async def test_grouped_heatmap_excludes_pending_runs(db_session: AsyncSession) -> None:
    """Pending EvaluationRun rows do not appear in the heatmap."""
    asset_id = await _create_asset(db_session, 'grouped-hm-pending-asset')
    run_repo = EvaluationRunRepository(db_session)
    trend_repo = TrendRepository(db_session)

    await run_repo.create(
        asset_id=asset_id,
        eval_name='daily',
        period_start=_BASE,
        period_end=_BASE + timedelta(hours=1),
    )

    runs = await trend_repo.get_grouped_metric_heatmap(asset_id=asset_id)
    assert len(runs) == 0


@pytest.mark.integration
async def test_grouped_heatmap_eval_name_filter(db_session: AsyncSession) -> None:
    """eval_name filter restricts which EvaluationRuns are returned."""
    asset_id = await _create_asset(db_session, 'grouped-hm-filter-asset')
    run_repo = EvaluationRunRepository(db_session)
    trend_repo = TrendRepository(db_session)

    for name in ('daily', 'weekly'):
        run = await run_repo.create(
            asset_id=asset_id,
            eval_name=name,
            period_start=_BASE,
            period_end=_BASE + timedelta(hours=1),
        )
        await run_repo.mark_completed(
            run.id, result='pass', achieved_points=10, total_points=10
        )

    runs = await trend_repo.get_grouped_metric_heatmap(
        asset_id=asset_id, eval_name=['daily']
    )
    assert len(runs) == 1
    assert runs[0].eval_name == 'daily'
