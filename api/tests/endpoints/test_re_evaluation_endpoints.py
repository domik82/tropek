"""Endpoint tests for re-evaluation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.db.models import Asset, AssetType, SLOObjective
from app.modules.quality_gate.indicator_repository import IndicatorRepository
from app.modules.quality_gate.params import EvalCreateParams
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.slo_registry.params import SLOCreateParams, SLOObjectiveParams
from app.modules.slo_registry.repository import SLORepository
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_START = datetime(2026, 3, 10, 10, 0, 0, tzinfo=UTC)


async def _setup_re_eval(
    session: AsyncSession,
) -> tuple[str, uuid.UUID]:
    """Create asset, SLO v1, and a failing evaluation — returns (asset_name, eval_id)."""
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    asset_name = f're-eval-{asset_id.hex[:8]}'
    session.add(Asset(id=asset_id, name=asset_name, type_name=type_name))
    await session.flush()

    slo_repo = SLORepository(session)
    # SLO v1: pass if cpu < 90
    await slo_repo.create(
        SLOCreateParams(
            name='re-eval-ep-slo',
            objectives=[SLOObjectiveParams(sli='cpu', pass_threshold=['<90'], weight=1)],
        )
    )

    repo = EvaluationRepository(session)
    ev = await repo.create_pending(
        EvalCreateParams(
            evaluation_name='daily',
            period_start=_START,
            period_end=_START + timedelta(minutes=30),
            ingestion_mode='push',
            asset_snapshot={'name': asset_name},
            variables={},
            asset_id=asset_id,
            slo_name='re-eval-ep-slo',
        )
    )
    await repo.mark_completed(
        ev.id,
        result='fail',
        score=0.0,
        slo_name='re-eval-ep-slo',
    )

    # Seed normalized indicator rows (cpu=95 -> fail under v1 threshold <90)
    obj_q = select(SLOObjective).where(SLOObjective.sli == 'cpu')
    obj_row = await session.execute(obj_q)
    obj = obj_row.scalar_one()
    indicator_repo = IndicatorRepository(session)
    await indicator_repo.bulk_insert(
        ev.id,
        [
            {
                'evaluation_id': ev.id,
                'slo_objective_id': obj.id,
                'value': 95.0,
                'compared_value': None,
                'change_absolute': None,
                'change_relative_pct': None,
                'status': 'fail',
                'score': 0.0,
            },
        ],
    )

    # SLO v2: relaxed threshold — pass if cpu < 100
    await slo_repo.create(
        SLOCreateParams(
            name='re-eval-ep-slo',
            objectives=[SLOObjectiveParams(sli='cpu', pass_threshold=['<100'], weight=1)],
        )
    )

    return asset_name, ev.id


@pytest.mark.integration
async def test_re_evaluate_sets_original_result(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """First re-evaluation must set original_result and original_score."""
    asset_name, eval_id = await _setup_re_eval(db_session)

    resp = await async_client.post(
        '/evaluations/re-evaluate',
        json={
            'asset_name': asset_name,
            'slo_name': 're-eval-ep-slo',
            'from_date': '2026-03-09T00:00:00Z',
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body['affected_evaluations'] == 1
    assert body['results'][0]['old_result'] == 'fail'
    assert body['results'][0]['new_result'] == 'pass'

    # Verify original preserved in detail
    detail = await async_client.get(f'/evaluations/{eval_id}')
    assert detail.json()['original_score'] == 0.0


@pytest.mark.integration
async def test_re_evaluate_preserves_original_on_second_reeval(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Second re-evaluation must NOT overwrite original_result."""
    asset_name, eval_id = await _setup_re_eval(db_session)

    # First re-eval
    await async_client.post(
        '/evaluations/re-evaluate',
        json={
            'asset_name': asset_name,
            'slo_name': 're-eval-ep-slo',
            'from_date': '2026-03-09T00:00:00Z',
        },
    )

    # Create SLO v3 (same threshold, just to trigger a second re-eval)
    slo_repo = SLORepository(db_session)
    await slo_repo.create(
        SLOCreateParams(
            name='re-eval-ep-slo',
            objectives=[SLOObjectiveParams(sli='cpu', pass_threshold=['<100'], weight=1)],
        )
    )

    # Second re-eval
    resp = await async_client.post(
        '/evaluations/re-evaluate',
        json={
            'asset_name': asset_name,
            'slo_name': 're-eval-ep-slo',
            'from_date': '2026-03-09T00:00:00Z',
        },
    )
    assert resp.status_code == 200

    # Verify original_score is still from the very first evaluation (0.0), not from the first re-eval
    detail = await async_client.get(f'/evaluations/{eval_id}')
    assert detail.json()['original_score'] == 0.0
