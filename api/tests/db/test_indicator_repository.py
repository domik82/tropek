"""Integration tests for IndicatorRepository."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.db.models import (
    Asset,
    AssetType,
    Evaluation,
    IndicatorResultRow,
    SLIDefinition,
    SLODefinition,
    SLOObjective,
)
from app.modules.quality_gate.indicator_repository import IndicatorRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_START = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
_END = datetime(2026, 3, 15, 10, 30, 0, tzinfo=UTC)


async def _seed_slo_with_objectives(session: AsyncSession) -> tuple[str, int, list[SLOObjective]]:
    """Create an SLO definition with two objectives. Return (slo_name, version, objectives)."""
    sli = SLIDefinition(
        id=uuid.uuid4(),
        name='test-sli',
        version=1,
        adapter_type='prometheus',
        indicators={
            'response_time': {'query': 'histogram_quantile(0.95, ...)'},
            'error_rate': {'query': 'rate(...)'},
        },
        tags={},
    )
    session.add(sli)

    slo_id = uuid.uuid4()
    slo = SLODefinition(
        id=slo_id,
        name='test-slo',
        version=1,
        display_name='Test SLO',
        comparison={'compare_with': 'single_result', 'number_of_comparison_results': 3},
        total_score_pass_threshold=90.0,
        total_score_warning_threshold=75.0,
        tags={},
        variables={},
    )
    session.add(slo)

    obj1 = SLOObjective(
        id=uuid.uuid4(),
        slo_definition_id=slo_id,
        sli='response_time',
        display_name='Response Time P95',
        weight=1,
        key_sli=True,
        sort_order=0,
        pass_threshold=['<600'],
        warning_threshold=['<800'],
        tab_group='latency',
    )
    obj2 = SLOObjective(
        id=uuid.uuid4(),
        slo_definition_id=slo_id,
        sli='error_rate',
        display_name='Error Rate',
        weight=2,
        key_sli=False,
        sort_order=1,
        pass_threshold=['<2'],
        warning_threshold=['<5'],
        tab_group=None,
    )
    session.add_all([obj1, obj2])
    await session.flush()
    return 'test-slo', 1, [obj1, obj2]


async def _create_asset(session: AsyncSession) -> uuid.UUID:
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(
        Asset(
            id=asset_id,
            name=f'asset-{asset_id.hex[:8]}',
            type_name=type_name,
            tags={},
            variables={},
        )
    )
    await session.flush()
    return asset_id


async def _create_eval(session: AsyncSession, asset_id: uuid.UUID) -> uuid.UUID:
    eval_id = uuid.uuid4()
    session.add(
        Evaluation(
            id=eval_id,
            evaluation_name='test',
            asset_id=asset_id,
            period_start=_START,
            period_end=_END,
            slo_name='test-slo',
            slo_version=1,
            ingestion_mode='push',
            status='completed',
            result='pass',
            score=90.0,
        )
    )
    await session.flush()
    return eval_id


@pytest.mark.integration
async def test_bulk_insert_and_read_back(db_session: AsyncSession) -> None:
    """Write indicator rows, read them back, verify fields match."""
    _slo_name, _slo_version, objectives = await _seed_slo_with_objectives(db_session)
    asset_id = await _create_asset(db_session)
    eval_id = await _create_eval(db_session, asset_id)

    repo = IndicatorRepository(db_session)

    rows_to_insert = [
        {
            'evaluation_id': eval_id,
            'slo_objective_id': objectives[0].id,
            'value': 580.0,
            'compared_value': 500.0,
            'change_absolute': 80.0,
            'change_relative_pct': 16.0,
            'status': 'pass',
            'score': 1.0,
        },
        {
            'evaluation_id': eval_id,
            'slo_objective_id': objectives[1].id,
            'value': 5.2,
            'compared_value': 1.0,
            'change_absolute': 4.2,
            'change_relative_pct': 420.0,
            'status': 'fail',
            'score': 0.0,
        },
    ]
    await repo.bulk_insert(eval_id, rows_to_insert)

    result = await db_session.execute(select(IndicatorResultRow).where(IndicatorResultRow.evaluation_id == eval_id))
    rows = list(result.scalars().all())
    assert len(rows) == 2

    pass_row = next(r for r in rows if r.status == 'pass')
    assert pass_row.value == 580.0
    assert pass_row.compared_value == 500.0
    assert pass_row.slo_objective_id == objectives[0].id

    fail_row = next(r for r in rows if r.status == 'fail')
    assert fail_row.value == 5.2
    assert fail_row.score == 0.0


@pytest.mark.integration
async def test_delete_and_reinsert(db_session: AsyncSession) -> None:
    """Re-evaluation pattern: delete old rows, insert new set."""
    _slo_name, _slo_version, objectives = await _seed_slo_with_objectives(db_session)
    asset_id = await _create_asset(db_session)
    eval_id = await _create_eval(db_session, asset_id)

    repo = IndicatorRepository(db_session)

    # Initial insert
    await repo.bulk_insert(
        eval_id,
        [
            {
                'evaluation_id': eval_id,
                'slo_objective_id': objectives[0].id,
                'value': 580.0,
                'compared_value': None,
                'change_absolute': None,
                'change_relative_pct': None,
                'status': 'pass',
                'score': 1.0,
            }
        ],
    )

    # Delete + reinsert (re-evaluation)
    await repo.delete_for_evaluation(eval_id)
    await repo.bulk_insert(
        eval_id,
        [
            {
                'evaluation_id': eval_id,
                'slo_objective_id': objectives[0].id,
                'value': 620.0,
                'compared_value': None,
                'change_absolute': None,
                'change_relative_pct': None,
                'status': 'fail',
                'score': 0.0,
            }
        ],
    )

    result = await db_session.execute(select(IndicatorResultRow).where(IndicatorResultRow.evaluation_id == eval_id))
    rows = list(result.scalars().all())
    assert len(rows) == 1
    assert rows[0].value == 620.0
    assert rows[0].status == 'fail'
