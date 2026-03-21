"""Integration tests for trend query (joins Evaluation + SLIValue)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.db.models import Asset, AssetType
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.quality_gate.sli_repository import SLIValueRepository
from app.modules.quality_gate.trend_repository import TrendRepository
from sqlalchemy.ext.asyncio import AsyncSession

_BASE = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)

_INDICATORS = [
    {
        "metric": "response_time",
        "display_name": "Response Time",
        "value": 250.0,
        "compared_value": 200.0,
        "change_absolute": 50.0,
        "change_relative_pct": 25.0,
        "status": "pass",
        "score": 1.0,
        "weight": 1,
        "key_sli": False,
        "pass_targets": [{"criteria": "<600", "target_value": 600, "violated": False}],
        "warning_targets": None,
    },
]


async def _create_asset(session: AsyncSession, name: str) -> uuid.UUID:
    type_name = f"vm-{uuid.uuid4().hex[:8]}"
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(Asset(id=asset_id, name=name, type_name=type_name))
    await session.flush()
    return asset_id


@pytest.mark.integration
async def test_trend_returns_points_with_baseline(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session, "trend-asset")
    repo = EvaluationRepository(db_session)
    sli_repo = SLIValueRepository(db_session)
    trend_repo = TrendRepository(db_session)

    ev = await repo.create_pending(
        evaluation_name="trend-test",
        period_start=_BASE,
        period_end=_BASE + timedelta(minutes=30),
        ingestion_mode="push",
        asset_snapshot={"name": "trend-asset", "tags": {}},
        metadata={},
        asset_id=asset_id,
        slo_name="test-slo",
    )
    await repo.mark_completed(
        ev.id, result="pass", score=90.0, indicator_results=_INDICATORS, slo_name="test-slo"
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
    assert points[0]["baseline"] == 200.0  # from indicator_results compared_value


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
        metadata={},
        asset_id=asset_id,
        slo_name="test-slo",
    )
    await repo.mark_completed(
        ev.id, result="pass", score=90.0, indicator_results=_INDICATORS, slo_name="test-slo"
    )
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
