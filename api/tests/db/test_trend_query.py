"""Integration tests for trend query (joins Evaluation + SLIValue + IndicatorResultRow)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.db.models import Asset, AssetType, SLIDefinition, SLODefinition, SLOObjective
from app.modules.quality_gate.indicator_repository import IndicatorRepository
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.quality_gate.sli_repository import SLIValueRepository
from app.modules.quality_gate.trend_repository import TrendRepository
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


async def _seed_slo_objective(session: AsyncSession, sli: str = "response_time") -> SLOObjective:
    """Create a minimal SLO definition with one objective and return it."""
    sli_def = SLIDefinition(
        id=uuid.uuid4(),
        name="trend-sli",
        version=1,
        adapter_type="prometheus",
        indicators={},
        tags={},
    )
    session.add(sli_def)

    slo_id = uuid.uuid4()
    slo = SLODefinition(
        id=slo_id,
        name="test-slo",
        version=1,
        display_name="Test SLO",
        comparison={},
        total_score_pass_pct=90.0,
        total_score_warning_pct=75.0,
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
        pass_criteria=["<600"],
        warning_criteria=[],
    )
    session.add(obj)
    await session.flush()
    return obj


@pytest.mark.integration
async def test_trend_returns_points_with_baseline(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session, "trend-asset")
    obj = await _seed_slo_objective(db_session)
    repo = EvaluationRepository(db_session)
    sli_repo = SLIValueRepository(db_session)
    trend_repo = TrendRepository(db_session)

    ev = await repo.create_pending(
        evaluation_name="trend-test",
        period_start=_BASE,
        period_end=_BASE + timedelta(minutes=30),
        ingestion_mode="push",
        asset_snapshot={"name": "trend-asset", "tags": {}},
        variables={},
        asset_id=asset_id,
        slo_name="test-slo",
    )
    await repo.mark_completed(ev.id, result="pass", score=90.0, slo_name="test-slo")

    # Seed indicator row with compared_value for baseline
    indicator_repo = IndicatorRepository(db_session)
    await indicator_repo.bulk_insert(
        ev.id,
        [
            {
                "evaluation_id": ev.id,
                "slo_objective_id": obj.id,
                "value": 250.0,
                "compared_value": 200.0,
                "change_absolute": 50.0,
                "change_relative_pct": 25.0,
                "status": "pass",
                "score": 1.0,
            },
        ],
    )

    # Seed SLI value for the join
    await sli_repo.write_sli_values(
        [
            {
                "eval_id": ev.id,
                "eval_start": _BASE,
                "metric_name": "response_time",
                "aggregation": "avg",
                "value": 250.0,
                "asset_name": "trend-asset",
                "evaluation_name": "trend-test",
                "os_tag": None,
            }
        ]
    )

    points = await trend_repo.get_trend_by_domain(
        asset_id=asset_id, slo_name="test-slo", metric_name="response_time", limit=50
    )
    assert len(points) == 1
    assert points[0]["value"] == 250.0
    assert points[0]["baseline"] == 200.0  # from IndicatorResultRow.compared_value


@pytest.mark.integration
async def test_trend_excludes_invalidated(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session, "trend-inv-asset")
    repo = EvaluationRepository(db_session)
    sli_repo = SLIValueRepository(db_session)
    trend_repo = TrendRepository(db_session)

    ev = await repo.create_pending(
        evaluation_name="trend-inv",
        period_start=_BASE,
        period_end=_BASE + timedelta(minutes=30),
        ingestion_mode="push",
        asset_snapshot={"name": "trend-inv-asset", "tags": {}},
        variables={},
        asset_id=asset_id,
        slo_name="test-slo",
    )
    await repo.mark_completed(ev.id, result="pass", score=90.0, slo_name="test-slo")
    await sli_repo.write_sli_values(
        [
            {
                "eval_id": ev.id,
                "eval_start": _BASE,
                "metric_name": "response_time",
                "aggregation": "avg",
                "value": 250.0,
                "asset_name": "trend-inv-asset",
                "evaluation_name": "trend-inv",
                "os_tag": None,
            }
        ]
    )

    await repo.invalidate(ev.id, note="bad")

    points = await trend_repo.get_trend_by_domain(
        asset_id=asset_id, slo_name="test-slo", metric_name="response_time", limit=50
    )
    assert len(points) == 0
