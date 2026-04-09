"""Integration tests for finalize_sweeper_job."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
from app.config import get_settings
from app.db.models import Asset, AssetType, EvaluationRun, SLOEvaluation
from app.queue import finalize_sweeper_job
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture()
async def sweeper_session_factory(db_session: AsyncSession):
    """Return a context-manager factory that reuses the test DB session.

    Patched into app.queue.get_session_factory so finalize_sweeper_job sees the
    same connection (and therefore the same flushed data) as the test's db_session.

    The sweeper calls session.commit() on each session it opens — under the test
    savepoint strategy (join_transaction_mode='create_savepoint') this releases the
    inner savepoint and immediately creates a new one, so the outer rolled-back
    transaction is not disturbed.
    """

    @asynccontextmanager
    async def _ctx():
        yield db_session

    return _ctx


@pytest_asyncio.fixture()
async def asset(db_session):
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    db_session.add(AssetType(name=type_name, is_default=False))
    await db_session.flush()
    a = Asset(name=f'test-asset-{uuid.uuid4().hex[:8]}', type_name=type_name)
    db_session.add(a)
    await db_session.flush()
    return a


def _make_ctx() -> dict[str, Any]:
    return {'job_id': 'sweeper-test-1'}


async def _create_stuck_run(db_session, asset, day: int = 15) -> uuid.UUID:
    """Create a parent run with all children completed but parent still pending."""
    start = datetime(2026, 1, day, tzinfo=UTC)
    end = datetime(2026, 1, day + 1, tzinfo=UTC)

    run = EvaluationRun(
        asset_id=asset.id,
        eval_name='daily',
        period_start=start,
        period_end=end,
        status='pending',
    )
    db_session.add(run)
    await db_session.flush()

    db_session.add(
        SLOEvaluation(
            evaluation_id=run.id,
            evaluation_name='daily',
            asset_id=asset.id,
            asset_snapshot={},
            period_start=start,
            period_end=end,
            slo_name='slo-1',
            ingestion_mode='pull',
            status='completed',
            result='pass',
            achieved_points=10,
            total_points=10,
        )
    )
    await db_session.flush()
    return run.id


@pytest.mark.integration
async def test_sweeper_tick_no_stuck_runs_is_noop(db_session, sweeper_session_factory, monkeypatch):
    """Empty DB: sweeper tick runs cleanly, no exceptions."""
    monkeypatch.setattr('app.queue.get_session_factory', lambda: sweeper_session_factory)
    await finalize_sweeper_job(_make_ctx())


@pytest.mark.integration
async def test_sweeper_rescues_single_stuck_run(db_session, asset, sweeper_session_factory, monkeypatch):
    """One stuck run gets finalized by the sweeper."""
    monkeypatch.setattr('app.queue.get_session_factory', lambda: sweeper_session_factory)
    run_id = await _create_stuck_run(db_session, asset)

    await finalize_sweeper_job(_make_ctx())

    refreshed = await db_session.get(EvaluationRun, run_id)
    await db_session.refresh(refreshed)
    assert refreshed.status == 'completed'
    assert refreshed.result == 'pass'
    assert refreshed.achieved_points == 10
    assert refreshed.total_points == 10


@pytest.mark.integration
async def test_sweeper_respects_batch_limit(db_session, asset, sweeper_session_factory, monkeypatch):
    """More stuck runs than batch_limit: sweeper rescues only batch_limit of them."""
    settings = get_settings()
    monkeypatch.setattr('app.queue.get_session_factory', lambda: sweeper_session_factory)
    monkeypatch.setattr(settings.queue, 'finalize_sweeper_batch_limit', 1)

    id_old = await _create_stuck_run(db_session, asset, day=10)
    id_new = await _create_stuck_run(db_session, asset, day=20)

    await finalize_sweeper_job(_make_ctx())

    old = await db_session.get(EvaluationRun, id_old)
    new = await db_session.get(EvaluationRun, id_new)
    await db_session.refresh(old)
    await db_session.refresh(new)

    assert old.status == 'completed'
    assert new.status == 'pending'

    await finalize_sweeper_job(_make_ctx())
    await db_session.refresh(new)
    assert new.status == 'completed'


@pytest.mark.integration
async def test_sweeper_idempotent_on_already_finalized(db_session, asset, sweeper_session_factory, monkeypatch):
    """Calling sweeper twice on the same stuck run leaves state consistent."""
    monkeypatch.setattr('app.queue.get_session_factory', lambda: sweeper_session_factory)
    run_id = await _create_stuck_run(db_session, asset)

    await finalize_sweeper_job(_make_ctx())
    await finalize_sweeper_job(_make_ctx())

    refreshed = await db_session.get(EvaluationRun, run_id)
    await db_session.refresh(refreshed)
    assert refreshed.status == 'completed'
    assert refreshed.result == 'pass'
