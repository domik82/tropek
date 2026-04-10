"""Round-trip tests: write indicator rows -> read via presenter -> assert field equality.

These lock down the exact transformation from normalized DB storage to API response.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.db.models import (
    Asset,
    AssetType,
    SLIDefinition,
    SLODefinition,
    SLOObjective,
)
from app.modules.quality_gate.indicator_repository import IndicatorRepository
from app.modules.quality_gate.params import EvalCreateParams
from app.modules.quality_gate.presenter import build_detail, build_summary
from app.modules.quality_gate.repository import EvaluationRepository
from sqlalchemy.ext.asyncio import AsyncSession

_START = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
_END = datetime(2026, 3, 15, 10, 30, 0, tzinfo=UTC)


async def _create_asset(session: AsyncSession) -> uuid.UUID:
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(Asset(id=asset_id, name=f'asset-{asset_id.hex[:8]}', type_name=type_name))
    await session.flush()
    return asset_id


async def _seed_slo_objectives(session: AsyncSession) -> dict[str, SLOObjective]:
    """Create SLO with four objectives, return {sli_name: SLOObjective}."""
    sli = SLIDefinition(
        id=uuid.uuid4(),
        name='round-trip-sli',
        version=1,
        adapter_type='prometheus',
        indicators={},
        tags={},
    )
    session.add(sli)

    slo_id = uuid.uuid4()
    slo = SLODefinition(
        id=slo_id,
        name='test-slo',
        version=1,
        display_name='Test SLO',
        comparison={},
        total_score_pass_threshold=90.0,
        total_score_warning_threshold=75.0,
        tags={},
        variables={},
    )
    session.add(slo)

    objectives = [
        SLOObjective(
            id=uuid.uuid4(),
            slo_definition_id=slo_id,
            sli='response_time_p95',
            display_name='Response Time P95',
            weight=1,
            key_sli=True,
            sort_order=0,
            pass_threshold=['<600'],
            warning_threshold=[],
            tab_group='latency',
        ),
        SLOObjective(
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
        ),
        SLOObjective(
            id=uuid.uuid4(),
            slo_definition_id=slo_id,
            sli='cpu_usage',
            display_name='CPU Usage',
            weight=1,
            key_sli=False,
            sort_order=2,
            pass_threshold=['<80'],
            warning_threshold=[],
            tab_group=None,
        ),
        SLOObjective(
            id=uuid.uuid4(),
            slo_definition_id=slo_id,
            sli='build_duration',
            display_name='Build Duration',
            weight=0,
            key_sli=False,
            sort_order=3,
            pass_threshold=[],
            warning_threshold=[],
            tab_group=None,
        ),
    ]
    session.add_all(objectives)
    await session.flush()
    return {obj.sli: obj for obj in objectives}


@pytest.mark.integration
async def test_detail_round_trip_all_fields(db_session: AsyncSession) -> None:
    """Write indicator rows with all field types, read back via presenter, assert equality."""
    asset_id = await _create_asset(db_session)
    objs = await _seed_slo_objectives(db_session)
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='round-trip-test',
            period_start=_START,
            period_end=_END,
            ingestion_mode='push',
            asset_snapshot={'name': 'vm-test-01', 'tags': {}},
            variables={},
            asset_id=asset_id,
            slo_name='test-slo',
        )
    )
    await repo.mark_completed(ev.id, result='fail', score=25.0, slo_name='test-slo')

    # Seed normalized indicator rows
    indicator_repo = IndicatorRepository(db_session)
    await indicator_repo.bulk_insert(
        ev.id,
        [
            {
                'evaluation_id': ev.id,
                'slo_objective_id': objs['response_time_p95'].id,
                'value': 580.0,
                'compared_value': 500.0,
                'change_absolute': 80.0,
                'change_relative_pct': 16.0,
                'status': 'pass',
                'score': 1.0,
            },
            {
                'evaluation_id': ev.id,
                'slo_objective_id': objs['error_rate'].id,
                'value': 5.2,
                'compared_value': 1.0,
                'change_absolute': 4.2,
                'change_relative_pct': 420.0,
                'status': 'fail',
                'score': 0.0,
            },
            {
                'evaluation_id': ev.id,
                'slo_objective_id': objs['cpu_usage'].id,
                'value': None,
                'compared_value': None,
                'change_absolute': None,
                'change_relative_pct': None,
                'status': 'fail',
                'score': 0.0,
            },
            {
                'evaluation_id': ev.id,
                'slo_objective_id': objs['build_duration'].id,
                'value': 120.0,
                'compared_value': None,
                'change_absolute': None,
                'change_relative_pct': None,
                'status': 'info',
                'score': 0.0,
            },
        ],
    )

    fetched = await repo.get_by_id(ev.id)
    detail = build_detail(fetched)

    assert len(detail.indicator_results) == 4

    # Assert pass indicator
    ir_pass = next(ir for ir in detail.indicator_results if ir.metric == 'response_time_p95')
    assert ir_pass.value == 580.0
    assert ir_pass.compared_value == 500.0
    assert ir_pass.status == 'pass'
    assert ir_pass.key_sli is True
    assert ir_pass.tab_group == 'latency'
    assert ir_pass.pass_targets == [{'criteria': '<600', 'target_value': 600, 'violated': False}]

    # Assert fail indicator
    ir_fail = next(ir for ir in detail.indicator_results if ir.metric == 'error_rate')
    assert ir_fail.status == 'fail'
    assert ir_fail.weight == 2
    assert ir_fail.warning_targets is not None
    assert len(ir_fail.warning_targets) == 1

    # Assert null-value indicator
    ir_null = next(ir for ir in detail.indicator_results if ir.metric == 'cpu_usage')
    assert ir_null.value is None
    assert ir_null.compared_value is None
    assert ir_null.change_absolute is None

    # Assert info indicator
    ir_info = next(ir for ir in detail.indicator_results if ir.metric == 'build_duration')
    assert ir_info.status == 'info'
    assert ir_info.score == 0.0
    assert ir_info.pass_targets is None


@pytest.mark.integration
async def test_summary_top_failures(db_session: AsyncSession) -> None:
    """Summary extracts only failing indicators into top_failures."""
    asset_id = await _create_asset(db_session)
    objs = await _seed_slo_objectives(db_session)
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='failures-test',
            period_start=_START,
            period_end=_END,
            ingestion_mode='push',
            asset_snapshot={'name': 'vm-test-01', 'tags': {}},
            variables={},
            asset_id=asset_id,
            slo_name='test-slo',
        )
    )
    await repo.mark_completed(ev.id, result='fail', score=25.0, slo_name='test-slo')

    indicator_repo = IndicatorRepository(db_session)
    await indicator_repo.bulk_insert(
        ev.id,
        [
            {
                'evaluation_id': ev.id,
                'slo_objective_id': objs['response_time_p95'].id,
                'value': 580.0,
                'compared_value': 500.0,
                'change_absolute': 80.0,
                'change_relative_pct': 16.0,
                'status': 'pass',
                'score': 1.0,
            },
            {
                'evaluation_id': ev.id,
                'slo_objective_id': objs['error_rate'].id,
                'value': 5.2,
                'compared_value': 1.0,
                'change_absolute': 4.2,
                'change_relative_pct': 420.0,
                'status': 'fail',
                'score': 0.0,
            },
        ],
    )

    fetched = await repo.get_by_id(ev.id)
    summary = build_summary(fetched, annotation_count=0, latest_ann=None)

    assert len(summary.top_failures) == 1
    assert summary.top_failures[0].metric == 'error_rate'
    assert summary.top_failures[0].threshold == '<2'


@pytest.mark.integration
async def test_empty_indicator_results(db_session: AsyncSession) -> None:
    """Evaluation with no indicators produces empty lists."""
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='empty-test',
            period_start=_START,
            period_end=_END,
            ingestion_mode='push',
            asset_snapshot={'name': 'vm-test-01', 'tags': {}},
            variables={},
            asset_id=asset_id,
            slo_name='test-slo',
        )
    )
    await repo.mark_completed(ev.id, result='pass', score=100.0, slo_name='test-slo')

    fetched = await repo.get_by_id(ev.id)
    detail = build_detail(fetched)
    summary = build_summary(fetched, annotation_count=0, latest_ann=None)

    assert detail.indicator_results == []
    assert summary.top_failures == []
