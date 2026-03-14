"""Integration tests for EvaluationRepository.

Requires TEST_DATABASE_URL and a running TimescaleDB instance.
Run: uv run pytest api/tests/db/test_evaluation_repository.py -m integration -v
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.modules.quality_gate.repository import EvaluationRepository
from sqlalchemy.ext.asyncio import AsyncSession

_START = datetime(2026, 3, 12, 10, 0, 0, tzinfo=UTC)
_END = datetime(2026, 3, 12, 10, 30, 0, tzinfo=UTC)


def _make_snapshot(os: str = "windows-11", arch: str = "x64") -> dict:
    return {"name": "vm-test-01", "tags": {"os": os, "arch": arch}}


@pytest.mark.integration
async def test_create_pending_returns_evaluation(db_session: AsyncSession) -> None:
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        name="compile-test",
        period_start=_START,
        period_end=_END,
        ingestion_mode="push",
        asset_snapshot=_make_snapshot(),
        metadata={},
    )
    assert ev.status == "pending"
    assert ev.result is None
    assert ev.id is not None


@pytest.mark.integration
async def test_get_returns_evaluation(db_session: AsyncSession) -> None:
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        name="get-test",
        period_start=_START,
        period_end=_END,
        ingestion_mode="push",
        asset_snapshot=_make_snapshot(),
        metadata={},
    )
    fetched = await repo.get_by_id(ev.id)
    assert fetched is not None
    assert fetched.id == ev.id


@pytest.mark.integration
async def test_mark_completed_updates_fields(db_session: AsyncSession) -> None:
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        name="complete-test",
        period_start=_START,
        period_end=_END,
        ingestion_mode="push",
        asset_snapshot=_make_snapshot(),
        metadata={},
    )
    await repo.mark_completed(
        ev.id,
        result="pass",
        score=95.0,
        slo_yaml="spec_version: '1.0'\n",
        indicator_results=[{"metric": "cpu", "status": "pass"}],
    )
    fetched = await repo.get_by_id(ev.id)
    assert fetched is not None
    assert fetched.status == "completed"
    assert fetched.result == "pass"
    assert fetched.score == 95.0


@pytest.mark.integration
async def test_mark_running_sets_status(db_session: AsyncSession) -> None:
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        name="running-test",
        period_start=_START,
        period_end=_END,
        ingestion_mode="pull",
        asset_snapshot=_make_snapshot(),
        metadata={},
    )
    await repo.mark_running(ev.id)
    fetched = await repo.get_by_id(ev.id)
    assert fetched is not None
    assert fetched.status == "running"


@pytest.mark.integration
async def test_list_evaluations_filters_by_name(db_session: AsyncSession) -> None:
    repo = EvaluationRepository(db_session)
    for name in ("alpha", "alpha", "beta"):
        await repo.create_pending(
            name=name,
            start_time=_START,
            end_time=_END,
            ingestion_mode="push",
            asset_snapshot=_make_snapshot(),
            metadata={},
        )
    results = await repo.list_evaluations(name="alpha")
    assert len(results) == 2
    assert all(e.name == "alpha" for e in results)


@pytest.mark.integration
async def test_get_baselines_filters_by_os_tag(db_session: AsyncSession) -> None:
    repo = EvaluationRepository(db_session)
    for os in ("windows-11", "windows-11", "ubuntu-22"):
        ev = await repo.create_pending(
            name="scope-test",
            start_time=_START,
            end_time=_END,
            ingestion_mode="push",
            asset_snapshot=_make_snapshot(os=os),
            metadata={},
        )
        await repo.mark_completed(
            ev.id,
            result="pass",
            score=90.0,
            slo_yaml="",
            indicator_results=[],
        )
    baselines = await repo.get_baselines(
        name="scope-test",
        scope_tags=["os"],
        asset_snapshot=_make_snapshot(os="windows-11"),
        include_result_with_score="pass",
        limit=10,
    )
    assert len(baselines) == 2
    for b in baselines:
        assert b.asset_snapshot["tags"]["os"] == "windows-11"


@pytest.mark.integration
async def test_add_and_list_annotations(db_session: AsyncSession) -> None:
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        name="ann-test",
        period_start=_START,
        period_end=_END,
        ingestion_mode="push",
        asset_snapshot=_make_snapshot(),
        metadata={},
    )
    await repo.add_annotation(ev.id, content="Defender update applied", author="ops")
    fetched = await repo.get_by_id(ev.id)
    assert fetched is not None
    assert len(fetched.annotations) == 1
    assert fetched.annotations[0].content == "Defender update applied"


@pytest.mark.integration
async def test_write_and_read_sli_values(db_session: AsyncSession) -> None:
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        name="sli-test",
        period_start=_START,
        period_end=_END,
        ingestion_mode="push",
        asset_snapshot=_make_snapshot(),
        metadata={},
    )
    rows = [
        {
            "eval_id": ev.id,
            "eval_start": _START,
            "metric_name": "cpu_usage",
            "aggregation": "avg",
            "value": 72.3,
            "asset_name": "vm-test-01",
            "test_name": "sli-test",
            "os_tag": "windows-11",
        }
    ]
    await repo.write_sli_values(rows)
    stored = await repo.get_sli_values_for_eval(ev.id)
    assert len(stored) == 1
    assert stored[0].metric_name == "cpu_usage"
    assert stored[0].value == pytest.approx(72.3)
