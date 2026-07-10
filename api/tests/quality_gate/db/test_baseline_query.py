"""Integration tests for baseline query — verifies which evaluations are eligible as baselines."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import Asset, AssetType
from tropek.modules.quality_gate.repositories.baseline import BaselineRepository
from tropek.modules.quality_gate.repositories.evaluation import EvaluationRepository
from tropek.modules.quality_gate.shared.params import EvalCreateParams

_BASE = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)


async def _create_asset(session: AsyncSession, name: str) -> uuid.UUID:
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(Asset(id=asset_id, name=name, type_name=type_name))
    await session.flush()
    return asset_id


async def _create_eval(
    session: AsyncSession,
    repo: EvaluationRepository,
    asset_id: uuid.UUID,
    *,
    result: str = 'pass',
    score: float = 90.0,
    offset_hours: int = 0,
) -> uuid.UUID:
    start = _BASE + timedelta(hours=offset_hours)
    ev = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='baseline-test',
            period_start=start,
            period_end=start + timedelta(minutes=30),
            ingestion_mode='push',
            asset_snapshot={'name': 'baseline-asset', 'tags': {}},
            variables={},
            asset_id=asset_id,
            slo_name='test-slo',
        )
    )
    await repo.mark_completed(ev.id, result=result, score=score, slo_name='test-slo')
    return ev.id


@pytest.mark.integration
async def test_baselines_exclude_invalidated(db_session: AsyncSession) -> None:
    """Invalidated evaluations must not appear in baseline results."""
    asset_id = await _create_asset(db_session, 'bl-inv')
    repo = EvaluationRepository(db_session)
    bl_repo = BaselineRepository(db_session)

    ev1 = await _create_eval(db_session, repo, asset_id, result='pass', offset_hours=0)
    ev2 = await _create_eval(db_session, repo, asset_id, result='pass', offset_hours=1)
    await repo.invalidate(ev1, note='bad data')

    baselines = await bl_repo.get_evaluation_baselines(
        asset_id=asset_id,
        slo_name='test-slo',
        period_start_before=_BASE + timedelta(hours=3),
        include_result_with_score='all',
        limit=10,
    )
    baseline_ids = [b.id for b in baselines]
    assert ev1 not in baseline_ids
    assert ev2 in baseline_ids


@pytest.mark.integration
async def test_baselines_return_pass_only(db_session: AsyncSession) -> None:
    """When include_result_with_score='pass', only passing evals returned."""
    asset_id = await _create_asset(db_session, 'bl-pass')
    repo = EvaluationRepository(db_session)
    bl_repo = BaselineRepository(db_session)

    await _create_eval(db_session, repo, asset_id, result='pass', offset_hours=0)
    await _create_eval(db_session, repo, asset_id, result='fail', offset_hours=1)
    await _create_eval(db_session, repo, asset_id, result='warning', offset_hours=2)

    baselines = await bl_repo.get_evaluation_baselines(
        asset_id=asset_id,
        slo_name='test-slo',
        period_start_before=_BASE + timedelta(hours=4),
        include_result_with_score='pass',
        limit=10,
    )
    assert all(b.result == 'pass' for b in baselines)
    assert len(baselines) == 1


async def test_get_evaluation_baselines_is_single_round_trip() -> None:
    """Pin filtering is folded into the main query — one execute, not a separate pin SELECT."""
    session = AsyncMock()
    query_result = MagicMock()
    query_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=query_result)

    repo = BaselineRepository(session)
    await repo.get_evaluation_baselines(
        asset_id=uuid.uuid4(),
        slo_name='test-slo',
        period_start_before=_BASE,
        include_result_with_score='all',
        limit=10,
    )
    assert session.execute.await_count == 1


@pytest.mark.integration
async def test_baselines_respect_active_pin(db_session: AsyncSession) -> None:
    """An active baseline pin restricts baselines to evaluations at/after the pin."""
    asset_id = await _create_asset(db_session, 'bl-pin')
    repo = EvaluationRepository(db_session)
    bl_repo = BaselineRepository(db_session)

    ev0 = await _create_eval(db_session, repo, asset_id, result='pass', offset_hours=0)
    ev1 = await _create_eval(db_session, repo, asset_id, result='pass', offset_hours=1)  # pin here
    ev2 = await _create_eval(db_session, repo, asset_id, result='pass', offset_hours=2)
    await repo.pin_baseline(ev1, reason='baseline floor', author='test')

    baselines = await bl_repo.get_evaluation_baselines(
        asset_id=asset_id,
        slo_name='test-slo',
        period_start_before=_BASE + timedelta(hours=5),
        include_result_with_score='all',
        limit=10,
    )
    ids = [b.id for b in baselines]
    assert ev0 not in ids  # before the pin — excluded
    assert ev1 in ids  # at the pin — included
    assert ev2 in ids  # after the pin — included
