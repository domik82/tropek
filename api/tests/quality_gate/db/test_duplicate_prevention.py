"""Integration tests for duplicate evaluation prevention.

Requires TEST_DATABASE_URL and a running TimescaleDB instance.
Run: uv run pytest api/tests/db/test_duplicate_prevention.py -m integration -v
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.db.models import Asset, AssetType
from app.modules.quality_gate.repositories.evaluation import EvaluationRepository
from app.modules.quality_gate.shared.exceptions import DuplicateEvaluationError
from app.modules.quality_gate.shared.params import EvalCreateParams
from sqlalchemy.ext.asyncio import AsyncSession

_START = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
_END = datetime(2026, 3, 15, 10, 30, 0, tzinfo=UTC)


async def _create_asset(session: AsyncSession) -> uuid.UUID:
    """Insert an AssetType and Asset, returning the asset ID."""
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(Asset(id=asset_id, name=f'asset-{asset_id.hex[:8]}', type_name=type_name))
    await session.flush()
    return asset_id


@pytest.mark.integration
async def test_find_duplicate_returns_none_when_no_match(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    result = await repo.find_duplicate(
        asset_id=asset_id,
        slo_name='latency-slo',
        evaluation_name='nightly',
        period_start=_START,
        period_end=_END,
    )
    assert result is None


@pytest.mark.integration
async def test_find_duplicate_returns_existing_completed(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='nightly',
            period_start=_START,
            period_end=_END,
            ingestion_mode='pull',
            asset_snapshot={'name': 'test'},
            variables={},
            asset_id=asset_id,
            slo_name='latency-slo',
        )
    )
    await repo.mark_running(ev.id)
    await repo.mark_completed(
        eval_id=ev.id,
        result='pass',
        score=95.0,
    )
    dup = await repo.find_duplicate(
        asset_id=asset_id,
        slo_name='latency-slo',
        evaluation_name='nightly',
        period_start=_START,
        period_end=_END,
    )
    assert dup is not None
    assert dup.id == ev.id
    assert dup.status == 'completed'


@pytest.mark.integration
async def test_find_duplicate_ignores_failed(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='nightly',
            period_start=_START,
            period_end=_END,
            ingestion_mode='pull',
            asset_snapshot={'name': 'test'},
            variables={},
            asset_id=asset_id,
            slo_name='latency-slo',
        )
    )
    await repo.mark_failed(ev.id, job_stats={'error': 'boom'})
    dup = await repo.find_duplicate(
        asset_id=asset_id,
        slo_name='latency-slo',
        evaluation_name='nightly',
        period_start=_START,
        period_end=_END,
    )
    assert dup is None


@pytest.mark.integration
async def test_find_duplicate_returns_pending(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='nightly',
            period_start=_START,
            period_end=_END,
            ingestion_mode='pull',
            asset_snapshot={'name': 'test'},
            variables={},
            asset_id=asset_id,
            slo_name='latency-slo',
        )
    )
    dup = await repo.find_duplicate(
        asset_id=asset_id,
        slo_name='latency-slo',
        evaluation_name='nightly',
        period_start=_START,
        period_end=_END,
    )
    assert dup is not None
    assert dup.status == 'pending'


@pytest.mark.integration
async def test_find_duplicate_different_name_no_conflict(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='nightly-hourly',
            period_start=_START,
            period_end=_END,
            ingestion_mode='pull',
            asset_snapshot={'name': 'test'},
            variables={},
            asset_id=asset_id,
            slo_name='latency-slo',
        )
    )
    dup = await repo.find_duplicate(
        asset_id=asset_id,
        slo_name='latency-slo',
        evaluation_name='nightly-daily',
        period_start=_START,
        period_end=_END,
    )
    assert dup is None


@pytest.mark.integration
async def test_create_pending_raises_on_constraint_violation(db_session: AsyncSession) -> None:
    """Simulate a race condition where two creates pass the app-level check."""
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='nightly',
            period_start=_START,
            period_end=_END,
            ingestion_mode='pull',
            asset_snapshot={'name': 'test'},
            variables={},
            asset_id=asset_id,
            slo_name='latency-slo',
        )
    )
    with pytest.raises(DuplicateEvaluationError):
        await repo.create_pending(
            EvalCreateParams(
                evaluation_id=uuid.uuid4(),
                evaluation_name='nightly',
                period_start=_START,
                period_end=_END,
                ingestion_mode='pull',
                asset_snapshot={'name': 'test'},
                variables={},
                asset_id=asset_id,
                slo_name='latency-slo',
            )
        )
