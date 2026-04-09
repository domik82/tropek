"""Integration tests for re-evaluation repository methods."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.db.models import Asset, AssetType, SLOObjective
from app.modules.quality_gate.baseline_repository import BaselineRepository
from app.modules.quality_gate.indicator_repository import IndicatorRepository
from app.modules.quality_gate.params import EvalCreateParams, ReEvalUpdateParams
from app.modules.quality_gate.re_evaluator import re_evaluate
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.quality_gate.schemas.re_evaluation import ReEvaluateRequest
from app.modules.slo_registry.params import SLOCreateParams, SLOObjectiveParams
from app.modules.slo_registry.repository import SLORepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_START = datetime(2026, 3, 10, 10, 0, 0, tzinfo=UTC)
_END = datetime(2026, 3, 10, 10, 30, 0, tzinfo=UTC)


async def _create_asset(session: AsyncSession) -> uuid.UUID:
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(Asset(id=asset_id, name=f're-eval-{asset_id.hex[:8]}', type_name=type_name))
    await session.flush()
    return asset_id


async def _create_completed_eval(
    repo: EvaluationRepository,
    asset_id: uuid.UUID,
    period_start: datetime,
    result: str = 'pass',
    score: float = 90.0,
    sli_version: int | None = None,
    slo_name: str = 'http-slo',
) -> uuid.UUID:
    ev = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='daily',
            period_start=period_start,
            period_end=period_start + timedelta(minutes=30),
            ingestion_mode='push',
            asset_snapshot={'name': 'test'},
            variables={},
            asset_id=asset_id,
            slo_name=slo_name,
            sli_version=sli_version,
        )
    )
    await repo.mark_completed(
        ev.id,
        result=result,
        score=score,
        slo_name=slo_name,
    )
    return ev.id


async def _seed_indicator_rows(
    session: AsyncSession,
    eval_id: uuid.UUID,
    slo_name: str,
    metrics: dict[str, float | None],
    status: str = 'fail',
) -> None:
    """Create IndicatorResultRow records for each metric, looking up SLO objectives by sli name."""
    obj_q = select(SLOObjective).where(
        SLOObjective.sli.in_(list(metrics.keys())),
    )
    obj_rows = await session.execute(obj_q)
    obj_by_sli = {obj.sli: obj for obj in obj_rows.scalars().all()}

    indicator_repo = IndicatorRepository(session)
    ir_rows = []
    for metric_name, value in metrics.items():
        obj = obj_by_sli.get(metric_name)
        if obj is None:
            continue
        ir_rows.append(
            {
                'evaluation_id': eval_id,
                'slo_objective_id': obj.id,
                'value': value,
                'compared_value': None,
                'change_absolute': None,
                'change_relative_pct': None,
                'status': status,
                'score': 0.0,
            }
        )
    if ir_rows:
        await indicator_repo.bulk_insert(eval_id, ir_rows)


@pytest.mark.integration
async def test_load_evaluations_for_reeval_from_date(db_session: AsyncSession) -> None:
    """load_evaluations_for_reeval returns evals in chronological order from a start date."""
    repo = EvaluationRepository(db_session)
    baseline_repo = BaselineRepository(db_session)
    asset_id = await _create_asset(db_session)

    for day in range(10, 15):
        await _create_completed_eval(repo, asset_id, datetime(2026, 3, day, tzinfo=UTC))

    evals = await baseline_repo.load_evaluations_for_reeval(
        asset_id=asset_id,
        slo_name='http-slo',
        from_date=datetime(2026, 3, 12, tzinfo=UTC),
    )
    assert len(evals) == 3
    assert evals[0].period_start < evals[1].period_start < evals[2].period_start


@pytest.mark.integration
async def test_load_evaluations_for_reeval_excludes_invalidated(
    db_session: AsyncSession,
) -> None:
    repo = EvaluationRepository(db_session)
    baseline_repo = BaselineRepository(db_session)
    asset_id = await _create_asset(db_session)

    eid1 = await _create_completed_eval(repo, asset_id, datetime(2026, 3, 10, tzinfo=UTC))
    await _create_completed_eval(repo, asset_id, datetime(2026, 3, 11, tzinfo=UTC))
    await repo.invalidate(eid1, note='bad')

    evals = await baseline_repo.load_evaluations_for_reeval(
        asset_id=asset_id,
        slo_name='http-slo',
        from_date=datetime(2026, 3, 9, tzinfo=UTC),
    )
    assert len(evals) == 1


@pytest.mark.integration
async def test_update_reeval_result_preserves_original(db_session: AsyncSession) -> None:
    """First re-eval sets original_result in job_stats; second re-eval does not overwrite."""
    repo = EvaluationRepository(db_session)
    baseline_repo = BaselineRepository(db_session)
    asset_id = await _create_asset(db_session)

    eid = await _create_completed_eval(
        repo,
        asset_id,
        datetime(2026, 3, 10, tzinfo=UTC),
        result='fail',
        score=45.0,
    )

    # First re-eval
    await baseline_repo.update_reeval_result(
        ReEvalUpdateParams(
            eval_id=eid,
            new_result='pass',
            new_score=92.0,
            old_result='fail',
            old_score=45.0,
            slo_version=2,
        )
    )
    ev = await repo.get_by_id(eid)
    assert ev is not None
    assert ev.result == 'pass'
    assert ev.score == 92.0
    assert ev.job_stats['original_result'] == 'fail'
    assert ev.job_stats['original_score'] == 45.0
    assert ev.job_stats['re_evaluated_at'] is not None

    # Second re-eval should NOT overwrite original
    await baseline_repo.update_reeval_result(
        ReEvalUpdateParams(
            eval_id=eid,
            new_result='warning',
            new_score=78.0,
            old_result='pass',
            old_score=92.0,
            slo_version=3,
        )
    )
    ev2 = await repo.get_by_id(eid)
    assert ev2 is not None
    assert ev2.result == 'warning'
    assert ev2.job_stats['original_result'] == 'fail'
    assert ev2.job_stats['original_score'] == 45.0


@pytest.mark.integration
async def test_re_evaluate_updates_results_and_adds_annotation(
    db_session: AsyncSession,
) -> None:
    """Full re-evaluation flow: create evals, re-eval with new SLO, verify results."""
    repo = EvaluationRepository(db_session)
    slo_repo = SLORepository(db_session)
    asset_id = await _create_asset(db_session)

    # Create SLO v1: pass if cpu < 90
    await slo_repo.create(
        SLOCreateParams(
            name='re-eval-slo',
            objectives=[SLOObjectiveParams(sli='cpu', pass_threshold=['<90'], weight=1)],
        )
    )

    # Create eval that fails under v1 (cpu=95)
    eid = await _create_completed_eval(
        repo,
        asset_id,
        datetime(2026, 3, 10, tzinfo=UTC),
        result='fail',
        score=0.0,
        slo_name='re-eval-slo',
    )

    # Seed normalized indicator rows (cpu=95)
    await _seed_indicator_rows(db_session, eid, 're-eval-slo', {'cpu': 95.0}, status='fail')

    # Create SLO v2: pass if cpu < 100 (relaxed threshold)
    await slo_repo.create(
        SLOCreateParams(
            name='re-eval-slo',
            objectives=[SLOObjectiveParams(sli='cpu', pass_threshold=['<100'], weight=1)],
        )
    )

    # Get asset name for the request
    asset_row = await db_session.get(Asset, asset_id)
    assert asset_row is not None

    # Re-evaluate with latest SLO
    response = await re_evaluate(
        ReEvaluateRequest(
            asset_name=asset_row.name,
            slo_name='re-eval-slo',
            from_date=datetime(2026, 3, 9, tzinfo=UTC),
        ),
        db_session,
    )

    assert response.affected_evaluations == 1
    assert response.slo_version_used == 2
    assert response.results[0].old_result == 'fail'
    assert response.results[0].new_result == 'pass'

    # Verify the DB was updated
    ev = await repo.get_by_id(eid)
    assert ev is not None
    assert ev.result == 'pass'
    assert ev.job_stats['original_result'] == 'fail'

    # Verify annotation was added
    assert len(ev.annotations) == 1
    assert 're-evaluated' in ev.annotations[0].content


@pytest.mark.integration
async def test_re_evaluate_dry_run_does_not_write(db_session: AsyncSession) -> None:
    """Dry run returns diffs without modifying the database."""
    repo = EvaluationRepository(db_session)
    slo_repo = SLORepository(db_session)
    asset_id = await _create_asset(db_session)

    await slo_repo.create(
        SLOCreateParams(
            name='dry-run-slo',
            objectives=[SLOObjectiveParams(sli='cpu', pass_threshold=['<100'], weight=1)],
        )
    )

    eid = await _create_completed_eval(
        repo,
        asset_id,
        datetime(2026, 3, 10, tzinfo=UTC),
        result='fail',
        score=0.0,
        slo_name='dry-run-slo',
    )

    # Seed normalized indicator rows (cpu=50)
    await _seed_indicator_rows(db_session, eid, 'dry-run-slo', {'cpu': 50.0}, status='fail')

    asset_row = await db_session.get(Asset, asset_id)
    assert asset_row is not None

    response = await re_evaluate(
        ReEvaluateRequest(
            asset_name=asset_row.name,
            slo_name='dry-run-slo',
            from_date=datetime(2026, 3, 9, tzinfo=UTC),
            dry_run=True,
        ),
        db_session,
    )

    assert response.affected_evaluations == 1
    assert response.results[0].new_result == 'pass'

    # DB should NOT be updated
    ev = await repo.get_by_id(eid)
    assert ev is not None
    assert ev.result == 'fail'
    assert len(ev.annotations) == 0


@pytest.mark.integration
async def test_re_evaluate_cascading_baselines(db_session: AsyncSession) -> None:
    """Each re-evaluated eval becomes available as a baseline for the next."""
    repo = EvaluationRepository(db_session)
    slo_repo = SLORepository(db_session)
    asset_id = await _create_asset(db_session)

    # SLO with relative criteria: value must be <= +10% of baseline
    await slo_repo.create(
        SLOCreateParams(
            name='cascade-slo',
            objectives=[SLOObjectiveParams(sli='rt', pass_threshold=['<=+10%'], weight=1)],
            comparison={'include_result_with_score': 'all', 'number_of_comparison_results': 1},
        )
    )

    # Create 3 evals with response times: 100, 105, 110
    # Without cascading, all would have no baseline. With cascading, each uses the previous.
    for day, val in [(10, 100.0), (11, 105.0), (12, 110.0)]:
        eid = await _create_completed_eval(
            repo,
            asset_id,
            datetime(2026, 3, day, tzinfo=UTC),
            result='fail',
            score=0.0,
            slo_name='cascade-slo',
        )
        await _seed_indicator_rows(db_session, eid, 'cascade-slo', {'rt': val}, status='fail')

    asset_row = await db_session.get(Asset, asset_id)
    assert asset_row is not None

    response = await re_evaluate(
        ReEvaluateRequest(
            asset_name=asset_row.name,
            slo_name='cascade-slo',
            from_date=datetime(2026, 3, 9, tzinfo=UTC),
        ),
        db_session,
    )

    assert response.affected_evaluations == 3
    # First eval: no baseline -> relative criteria pass (no history to compare against)
    # Second eval: baseline=100, value=105 -> +5% -> pass
    # Third eval: baseline=105, value=110 -> +4.8% -> pass
    assert all(r.new_result == 'pass' for r in response.results)
