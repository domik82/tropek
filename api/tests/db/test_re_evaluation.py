"""Integration tests for re-evaluation repository methods."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.db.models import Asset, AssetType
from app.modules.quality_gate.repository import EvaluationRepository
from sqlalchemy.ext.asyncio import AsyncSession

_START = datetime(2026, 3, 10, 10, 0, 0, tzinfo=UTC)
_END = datetime(2026, 3, 10, 10, 30, 0, tzinfo=UTC)


async def _create_asset(session: AsyncSession) -> uuid.UUID:
    type_name = f"vm-{uuid.uuid4().hex[:8]}"
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(Asset(id=asset_id, name=f"re-eval-{asset_id.hex[:8]}", type_name=type_name))
    await session.flush()
    return asset_id


async def _create_completed_eval(
    repo: EvaluationRepository,
    asset_id: uuid.UUID,
    period_start: datetime,
    result: str = "pass",
    score: float = 90.0,
    indicator_results: list[Any] | None = None,
    sli_version: int | None = None,
) -> uuid.UUID:
    ev = await repo.create_pending(
        evaluation_name="daily",
        period_start=period_start,
        period_end=period_start + timedelta(minutes=30),
        ingestion_mode="push",
        asset_snapshot={"name": "test"},
        metadata={},
        asset_id=asset_id,
        slo_name="http-slo",
        sli_version=sli_version,
    )
    await repo.mark_completed(
        ev.id,
        result=result,
        score=score,
        indicator_results=indicator_results or [],
        slo_name="http-slo",
    )
    return ev.id


@pytest.mark.integration
async def test_load_evaluations_for_reeval_from_date(db_session: AsyncSession) -> None:
    """load_evaluations_for_reeval returns evals in chronological order from a start date."""
    repo = EvaluationRepository(db_session)
    asset_id = await _create_asset(db_session)

    for day in range(10, 15):
        await _create_completed_eval(repo, asset_id, datetime(2026, 3, day, tzinfo=UTC))

    evals = await repo.load_evaluations_for_reeval(
        asset_id=asset_id,
        slo_name="http-slo",
        from_date=datetime(2026, 3, 12, tzinfo=UTC),
    )
    assert len(evals) == 3
    assert evals[0].period_start < evals[1].period_start < evals[2].period_start


@pytest.mark.integration
async def test_load_evaluations_for_reeval_excludes_invalidated(
    db_session: AsyncSession,
) -> None:
    repo = EvaluationRepository(db_session)
    asset_id = await _create_asset(db_session)

    eid1 = await _create_completed_eval(repo, asset_id, datetime(2026, 3, 10, tzinfo=UTC))
    await _create_completed_eval(repo, asset_id, datetime(2026, 3, 11, tzinfo=UTC))
    await repo.invalidate(eid1, note="bad")

    evals = await repo.load_evaluations_for_reeval(
        asset_id=asset_id,
        slo_name="http-slo",
        from_date=datetime(2026, 3, 9, tzinfo=UTC),
    )
    assert len(evals) == 1


@pytest.mark.integration
async def test_update_reeval_result_preserves_original(db_session: AsyncSession) -> None:
    """First re-eval sets original_result in job_stats; second re-eval does not overwrite."""
    repo = EvaluationRepository(db_session)
    asset_id = await _create_asset(db_session)

    eid = await _create_completed_eval(
        repo,
        asset_id,
        datetime(2026, 3, 10, tzinfo=UTC),
        result="fail",
        score=45.0,
        indicator_results=[{"metric": "cpu", "status": "fail"}],
    )

    # First re-eval
    await repo.update_reeval_result(
        eval_id=eid,
        new_result="pass",
        new_score=92.0,
        new_indicator_results=[{"metric": "cpu", "status": "pass"}],
        old_result="fail",
        old_score=45.0,
        slo_version=2,
    )
    ev = await repo.get_by_id(eid)
    assert ev is not None
    assert ev.result == "pass"
    assert ev.score == 92.0
    assert ev.job_stats["original_result"] == "fail"
    assert ev.job_stats["original_score"] == 45.0
    assert ev.job_stats["re_evaluated_at"] is not None

    # Second re-eval should NOT overwrite original
    await repo.update_reeval_result(
        eval_id=eid,
        new_result="warning",
        new_score=78.0,
        new_indicator_results=[{"metric": "cpu", "status": "warning"}],
        old_result="pass",
        old_score=92.0,
        slo_version=3,
    )
    ev2 = await repo.get_by_id(eid)
    assert ev2 is not None
    assert ev2.result == "warning"
    assert ev2.job_stats["original_result"] == "fail"
    assert ev2.job_stats["original_score"] == 45.0
