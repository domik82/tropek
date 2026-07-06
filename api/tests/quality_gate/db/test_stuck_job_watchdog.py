"""Integration tests for the stuck-evaluation watchdog and the
stale-running-predecessor guard in has_pending_predecessor."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.config import get_settings
from tropek.db.models import Asset, AssetType, EvaluationRun, SLOEvaluation
from tropek.modules.quality_gate.repositories.evaluation import EvaluationRepository
from tropek.queue import watchdog_stuck_evaluations_job


@pytest_asyncio.fixture()
async def watchdog_session_factory(db_session: AsyncSession):
    """Context-manager factory reusing the test session, patched into tropek.queue."""

    @asynccontextmanager
    async def _ctx():
        yield db_session

    return _ctx


@pytest_asyncio.fixture()
async def asset(db_session):
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    db_session.add(AssetType(name=type_name, is_default=False))
    await db_session.flush()
    new_asset = Asset(name=f'test-asset-{uuid.uuid4().hex[:8]}', type_name=type_name)
    db_session.add(new_asset)
    await db_session.flush()
    return new_asset


def _watchdog_ctx(pool: AsyncMock) -> dict[str, Any]:
    return {'redis': pool}


async def _create_eval(
    db_session,
    asset,
    *,
    day: int,
    status: str,
    started_minutes_ago: int | None,
    stuck_job_retries: int = 0,
) -> uuid.UUID:
    """Create a parent run + one SLOEvaluation for that day, in the given state."""
    start = datetime(2026, 1, day, tzinfo=UTC)
    end = datetime(2026, 1, day + 1, tzinfo=UTC)
    run = EvaluationRun(asset_id=asset.id, eval_name='daily', period_start=start, period_end=end, status='pending')
    db_session.add(run)
    await db_session.flush()

    started_at = None if started_minutes_ago is None else datetime.now(tz=UTC) - timedelta(minutes=started_minutes_ago)
    slo_eval = SLOEvaluation(
        evaluation_id=run.id,
        evaluation_name='daily',
        asset_id=asset.id,
        asset_snapshot={},
        period_start=start,
        period_end=end,
        slo_name='slo-1',
        ingestion_mode='pull',
        status=status,
        started_at=started_at,
        job_stats={'stuck_job_retries': stuck_job_retries} if stuck_job_retries else {},
    )
    db_session.add(slo_eval)
    await db_session.flush()
    return slo_eval.id


@pytest.mark.integration
async def test_has_pending_predecessor_counts_fresh_running(db_session, asset):
    """A recently-started running predecessor still blocks (counts as pending)."""
    await _create_eval(db_session, asset, day=10, status='running', started_minutes_ago=1)
    repo = EvaluationRepository(db_session)
    cutoff = datetime.now(tz=UTC) - timedelta(seconds=get_settings().reliability.stuck_job_threshold_seconds)

    blocked = await repo.has_pending_predecessor(
        asset_id=asset.id,
        slo_name='slo-1',
        period_start=datetime(2026, 1, 15, tzinfo=UTC),
        stale_running_cutoff=cutoff,
    )
    assert blocked is True


@pytest.mark.integration
async def test_has_pending_predecessor_ignores_stale_running(db_session, asset):
    """A running predecessor older than the cutoff is treated as dead, not pending."""
    await _create_eval(db_session, asset, day=10, status='running', started_minutes_ago=120)
    repo = EvaluationRepository(db_session)
    cutoff = datetime.now(tz=UTC) - timedelta(seconds=get_settings().reliability.stuck_job_threshold_seconds)

    blocked = await repo.has_pending_predecessor(
        asset_id=asset.id,
        slo_name='slo-1',
        period_start=datetime(2026, 1, 15, tzinfo=UTC),
        stale_running_cutoff=cutoff,
    )
    assert blocked is False


@pytest.mark.integration
async def test_watchdog_requeues_stuck_eval(db_session, asset, watchdog_session_factory, monkeypatch):
    """A stuck running eval below the cap is reset to pending and re-enqueued."""
    monkeypatch.setattr('tropek.queue.get_session_factory', lambda: watchdog_session_factory)
    eval_id = await _create_eval(db_session, asset, day=15, status='running', started_minutes_ago=120)
    pool = AsyncMock()

    await watchdog_stuck_evaluations_job(_watchdog_ctx(pool))

    refreshed = await db_session.get(SLOEvaluation, eval_id)
    await db_session.refresh(refreshed)
    assert refreshed.status == 'pending'
    assert refreshed.job_stats.get('stuck_job_retries') == 1
    pool.enqueue_job.assert_awaited_once_with('run_evaluation_job', str(eval_id))


@pytest.mark.integration
async def test_watchdog_marks_failed_at_cap(db_session, asset, watchdog_session_factory, monkeypatch):
    """A stuck eval that has already hit max_stuck_job_retries is failed, not requeued."""
    monkeypatch.setattr('tropek.queue.get_session_factory', lambda: watchdog_session_factory)
    max_attempts = get_settings().reliability.max_stuck_job_retries
    eval_id = await _create_eval(
        db_session,
        asset,
        day=16,
        status='running',
        started_minutes_ago=120,
        stuck_job_retries=max_attempts,
    )
    pool = AsyncMock()

    await watchdog_stuck_evaluations_job(_watchdog_ctx(pool))

    refreshed = await db_session.get(SLOEvaluation, eval_id)
    await db_session.refresh(refreshed)
    assert refreshed.status == 'failed'
    pool.enqueue_job.assert_not_awaited()


@pytest.mark.integration
async def test_mark_running_preserves_stuck_job_retries(db_session, asset):
    """mark_running must keep the watchdog's retry counter (regression).

    requeue_stuck records ``stuck_job_retries`` in job_stats; when the requeued
    job runs, mark_running previously overwrote job_stats wholesale, resetting the
    counter to 0 so the next stuck detection read 0 again — a hard-crashing job
    would requeue forever and never hit the cap. mark_running must merge, not
    replace, so the counter survives across the requeue → rerun → re-stuck cycle.
    """
    eval_id = await _create_eval(
        db_session,
        asset,
        day=20,
        status='pending',
        started_minutes_ago=None,
        stuck_job_retries=2,
    )
    repo = EvaluationRepository(db_session)

    await repo.mark_running(eval_id, worker_id='worker-1')
    await db_session.flush()

    refreshed = await db_session.get(SLOEvaluation, eval_id)
    await db_session.refresh(refreshed)
    assert refreshed.status == 'running'
    assert refreshed.job_stats.get('stuck_job_retries') == 2
    assert refreshed.job_stats.get('worker_id') == 'worker-1'


@pytest.mark.integration
async def test_watchdog_accumulates_retries_across_reruns(
    db_session,
    asset,
    watchdog_session_factory,
    monkeypatch,
):
    """End-to-end: requeue → mark_running (rerun) → re-stuck bumps the counter to 2.

    Drives the real path the injected-counter test cannot: the counter must
    accumulate so a job that keeps crashing eventually reaches the cap.
    """
    monkeypatch.setattr('tropek.queue.get_session_factory', lambda: watchdog_session_factory)
    eval_id = await _create_eval(db_session, asset, day=21, status='running', started_minutes_ago=120)
    pool = AsyncMock()

    # First watchdog tick: requeue with stuck_job_retries=1.
    await watchdog_stuck_evaluations_job(_watchdog_ctx(pool))
    requeued = await db_session.get(SLOEvaluation, eval_id)
    await db_session.refresh(requeued)
    assert requeued.job_stats.get('stuck_job_retries') == 1

    # The requeued job runs (mark_running) then gets stuck again.
    repo = EvaluationRepository(db_session)
    await repo.mark_running(eval_id, worker_id='worker-2')
    await db_session.execute(
        update(SLOEvaluation)
        .where(SLOEvaluation.id == eval_id)
        .values(started_at=datetime.now(tz=UTC) - timedelta(minutes=120)),
    )
    await db_session.flush()

    # Second watchdog tick: the counter must climb to 2, not reset to 1.
    await watchdog_stuck_evaluations_job(_watchdog_ctx(pool))
    re_requeued = await db_session.get(SLOEvaluation, eval_id)
    await db_session.refresh(re_requeued)
    assert re_requeued.job_stats.get('stuck_job_retries') == 2


@pytest.mark.integration
async def test_watchdog_noop_when_nothing_stuck(db_session, asset, watchdog_session_factory, monkeypatch):
    """A fresh running eval (not past the threshold) is left untouched."""
    monkeypatch.setattr('tropek.queue.get_session_factory', lambda: watchdog_session_factory)
    eval_id = await _create_eval(db_session, asset, day=17, status='running', started_minutes_ago=1)
    pool = AsyncMock()

    await watchdog_stuck_evaluations_job(_watchdog_ctx(pool))

    refreshed = await db_session.get(SLOEvaluation, eval_id)
    await db_session.refresh(refreshed)
    assert refreshed.status == 'running'
    pool.enqueue_job.assert_not_awaited()
