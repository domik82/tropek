"""Integration tests for metric heatmap query."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.db.models import Asset, AssetType
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
async def test_heatmap_returns_completed_evals(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session, 'heatmap-asset')
    eval_repo = EvaluationRepository(db_session)
    trend_repo = TrendRepository(db_session)

    for i in range(3):
        start = _BASE + timedelta(hours=i)
        ev = await eval_repo.create_pending(
            EvalCreateParams(
                evaluation_id=uuid.uuid4(),
                evaluation_name='hm-test',
                period_start=start,
                period_end=start + timedelta(minutes=30),
                ingestion_mode='push',
                asset_snapshot={'name': 'heatmap-asset', 'tags': {}},
                variables={},
                asset_id=asset_id,
                slo_name='test-slo',
            )
        )
        await eval_repo.mark_completed(ev.id, result='pass', score=90.0, slo_name='test-slo')

    evals = await trend_repo.get_metric_heatmap(asset_id=asset_id)
    assert len(evals) == 3


@pytest.mark.integration
async def test_heatmap_includes_invalidated_completed(db_session: AsyncSession) -> None:
    """The repository query returns invalidated evals (router handles display)."""
    asset_id = await _create_asset(db_session, 'hm-inv-asset')
    eval_repo = EvaluationRepository(db_session)
    trend_repo = TrendRepository(db_session)

    ev = await eval_repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='hm-inv',
            period_start=_BASE,
            period_end=_BASE + timedelta(minutes=30),
            ingestion_mode='push',
            asset_snapshot={'name': 'hm-inv-asset', 'tags': {}},
            variables={},
            asset_id=asset_id,
            slo_name='test-slo',
        )
    )
    await eval_repo.mark_completed(ev.id, result='pass', score=90.0, slo_name='test-slo')
    await eval_repo.invalidate(ev.id, note='bad data')

    evals = await trend_repo.get_metric_heatmap(asset_id=asset_id)
    # Repository returns it — router transforms result to "invalidated"
    assert len(evals) == 1
