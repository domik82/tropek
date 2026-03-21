"""Integration tests for baseline query — verifies which evaluations are eligible as baselines."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.db.models import Asset, AssetType
from app.modules.quality_gate.baseline_repository import BaselineRepository
from app.modules.quality_gate.repository import EvaluationRepository
from sqlalchemy.ext.asyncio import AsyncSession

_BASE = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)


async def _create_asset(session: AsyncSession, name: str) -> uuid.UUID:
    type_name = f"vm-{uuid.uuid4().hex[:8]}"
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
    result: str = "pass",
    score: float = 90.0,
    offset_hours: int = 0,
) -> uuid.UUID:
    start = _BASE + timedelta(hours=offset_hours)
    ev = await repo.create_pending(
        evaluation_name="baseline-test",
        period_start=start,
        period_end=start + timedelta(minutes=30),
        ingestion_mode="push",
        asset_snapshot={"name": "baseline-asset", "tags": {}},
        metadata={},
        asset_id=asset_id,
        slo_name="test-slo",
    )
    await repo.mark_completed(
        ev.id, result=result, score=score, indicator_results=[], slo_name="test-slo"
    )
    return ev.id


@pytest.mark.integration
async def test_baselines_exclude_invalidated(db_session: AsyncSession) -> None:
    """Invalidated evaluations must not appear in baseline results."""
    asset_id = await _create_asset(db_session, "bl-inv")
    repo = EvaluationRepository(db_session)
    bl_repo = BaselineRepository(db_session)

    ev1 = await _create_eval(db_session, repo, asset_id, result="pass", offset_hours=0)
    ev2 = await _create_eval(db_session, repo, asset_id, result="pass", offset_hours=1)
    await repo.invalidate(ev1, note="bad data")

    baselines = await bl_repo.get_evaluation_baselines(
        asset_id=asset_id,
        slo_name="test-slo",
        period_start_before=_BASE + timedelta(hours=3),
        include_result_with_score="all",
        limit=10,
    )
    baseline_ids = [b.id for b in baselines]
    assert ev1 not in baseline_ids
    assert ev2 in baseline_ids


@pytest.mark.integration
async def test_baselines_return_pass_only(db_session: AsyncSession) -> None:
    """When include_result_with_score='pass', only passing evals returned."""
    asset_id = await _create_asset(db_session, "bl-pass")
    repo = EvaluationRepository(db_session)
    bl_repo = BaselineRepository(db_session)

    await _create_eval(db_session, repo, asset_id, result="pass", offset_hours=0)
    await _create_eval(db_session, repo, asset_id, result="fail", offset_hours=1)
    await _create_eval(db_session, repo, asset_id, result="warning", offset_hours=2)

    baselines = await bl_repo.get_evaluation_baselines(
        asset_id=asset_id,
        slo_name="test-slo",
        period_start_before=_BASE + timedelta(hours=4),
        include_result_with_score="pass",
        limit=10,
    )
    assert all(b.result == "pass" for b in baselines)
    assert len(baselines) == 1
