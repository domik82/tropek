"""Integration tests for BaselineRepository evaluation_name filtering."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import Asset, AssetType, SLOEvaluation
from tropek.modules.quality_gate.repositories.baseline import BaselineRepository
from tropek.modules.quality_gate.repositories.evaluation import EvaluationRepository
from tropek.modules.quality_gate.shared.params import EvalCreateParams

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture()
async def seed_asset(db_session: AsyncSession) -> Asset:
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    db_session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await db_session.flush()
    asset = Asset(id=uuid.uuid4(), name=f'baseline-test-{uuid.uuid4().hex[:8]}', type_name=type_name)
    db_session.add(asset)
    await db_session.flush()
    return asset


async def test_get_evaluation_baselines_filters_by_evaluation_name(
    db_session: AsyncSession,
    seed_asset: Asset,
):
    """Baselines should only include evaluations with the matching evaluation_name."""
    slo_name = f'slo-{uuid.uuid4().hex[:8]}'
    repo = BaselineRepository(db_session)
    eval_repo = EvaluationRepository(db_session)

    for i, eval_name in enumerate(['load-test', 'load-test', 'prod-validation']):
        await eval_repo.create_pending(EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name=eval_name,
            period_start=datetime(2026, 3, 15, i * 4, tzinfo=UTC),
            period_end=datetime(2026, 3, 15, i * 4 + 1, tzinfo=UTC),
            ingestion_mode='pull',
            asset_snapshot={},
            asset_id=seed_asset.id,
            slo_name=slo_name,
        ))

    for evaluation in (await db_session.execute(
        select(SLOEvaluation).where(SLOEvaluation.slo_name == slo_name)
    )).scalars():
        evaluation.status = 'completed'
        evaluation.result = 'pass'
    await db_session.flush()

    baselines = await repo.get_evaluation_baselines(
        asset_id=seed_asset.id,
        slo_name=slo_name,
        period_start_before=datetime(2026, 3, 16, tzinfo=UTC),
        include_result_with_score='all',
        limit=10,
        evaluation_name='load-test',
    )

    assert len(baselines) == 2
    assert all(b.evaluation_name == 'load-test' for b in baselines)
