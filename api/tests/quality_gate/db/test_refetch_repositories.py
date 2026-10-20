"""Integration tests for the refetch repository methods."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import (
    Asset,
    AssetType,
    EvaluationAnnotation,
    SLIValue,
    SLOEvaluation,
    SLOObjective,
)
from tropek.modules.change_points.repository import ChangePointInsertParams, ChangePointRepository
from tropek.modules.quality_gate.repositories.evaluation import EvaluationRepository
from tropek.modules.quality_gate.repositories.evaluation_run import EvaluationRunRepository
from tropek.modules.quality_gate.repositories.indicator import IndicatorRepository
from tropek.modules.quality_gate.shared.params import EvalCreateParams, RefetchScope
from tropek.modules.slo_registry.params import SLOCreateParams, SLOObjectiveParams
from tropek.modules.slo_registry.repository import SLORepository

_DAY_ONE = datetime(2026, 3, 10, 0, 0, 0, tzinfo=UTC)
_DAY_TWO = datetime(2026, 3, 11, 0, 0, 0, tzinfo=UTC)
_SLO_A = 'refetch-slo-a'
_SLO_B = 'refetch-slo-b'


async def _seed_asset(session: AsyncSession) -> uuid.UUID:
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(Asset(id=asset_id, name=f'refetch-{asset_id.hex[:8]}', type_name=type_name))
    await session.flush()
    return asset_id


async def _seed_slo_evaluation(
    session: AsyncSession,
    *,
    asset_id: uuid.UUID,
    slo_name: str,
    period_start: datetime,
    evaluation_name: str = 'daily',
    status: str = 'completed',
) -> SLOEvaluation:
    run = await EvaluationRunRepository(session).create(
        asset_id=asset_id,
        eval_name=evaluation_name,
        period_start=period_start,
        period_end=period_start + timedelta(hours=1),
    )
    repo = EvaluationRepository(session)
    slo_eval = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=run.id,
            evaluation_name=evaluation_name,
            period_start=period_start,
            period_end=period_start + timedelta(hours=1),
            ingestion_mode='pull',
            asset_snapshot={'name': 'refetch-asset'},
            asset_id=asset_id,
            slo_name=slo_name,
        )
    )
    if status == 'completed':
        await repo.mark_completed(slo_eval.id, result='pass', score=100.0, achieved_points=1, total_points=1)
    elif status == 'failed':
        await repo.mark_failed(slo_eval.id, {'error': 'adapter query failed'})
    return slo_eval


async def _seed_children(session: AsyncSession, slo_eval: SLOEvaluation) -> None:
    """Give a SLO evaluation an indicator row, an SLI value and a note."""
    slo_definition = await SLORepository(session).create(
        SLOCreateParams(
            name=f'{slo_eval.slo_name}-{uuid.uuid4().hex[:6]}',
            objectives=[SLOObjectiveParams(sli='cpu', pass_threshold=['<90'], weight=1)],
        )
    )
    objective = (
        await session.execute(select(SLOObjective).where(SLOObjective.slo_definition_id == slo_definition.id))
    ).scalar_one()
    await IndicatorRepository(session).bulk_insert(
        slo_eval.id,
        [{'slo_objective_id': objective.id, 'value': 50.0, 'status': 'pass', 'score': 100.0}],
    )
    session.add(
        SLIValue(
            slo_evaluation_id=slo_eval.id,
            eval_start=slo_eval.period_start,
            metric_name='cpu',
            aggregation='mean',
            value=50.0,
        )
    )
    await session.flush()


async def _count(session: AsyncSession, model: Any, column: Any, value: uuid.UUID) -> int:
    return (await session.execute(select(func.count()).select_from(model).where(column == value))).scalar_one()


@pytest.mark.integration
async def test_list_for_refetch_filters_by_range_name_slo_and_failed(db_session: AsyncSession) -> None:
    asset_id = await _seed_asset(db_session)
    other_asset_id = await _seed_asset(db_session)
    day_one_a = await _seed_slo_evaluation(db_session, asset_id=asset_id, slo_name=_SLO_A, period_start=_DAY_ONE)
    day_one_b = await _seed_slo_evaluation(
        db_session, asset_id=asset_id, slo_name=_SLO_B, period_start=_DAY_ONE, status='failed'
    )
    day_two_a = await _seed_slo_evaluation(db_session, asset_id=asset_id, slo_name=_SLO_A, period_start=_DAY_TWO)
    weekly_a = await _seed_slo_evaluation(
        db_session, asset_id=asset_id, slo_name=_SLO_A, period_start=_DAY_ONE, evaluation_name='weekly'
    )
    await _seed_slo_evaluation(db_session, asset_id=other_asset_id, slo_name=_SLO_A, period_start=_DAY_ONE)
    repo = EvaluationRepository(db_session)
    base = {'asset_id': asset_id, 'period_from': _DAY_ONE, 'period_to': _DAY_TWO}

    everything = await repo.list_for_refetch(RefetchScope(**base))
    assert {row.id for row in everything} == {day_one_a.id, day_one_b.id, day_two_a.id, weekly_a.id}
    assert [row.period_start for row in everything] == sorted(row.period_start for row in everything)

    first_day_only = await repo.list_for_refetch(RefetchScope(**{**base, 'period_to': _DAY_ONE}))
    assert {row.id for row in first_day_only} == {day_one_a.id, day_one_b.id, weekly_a.id}

    by_name = await repo.list_for_refetch(RefetchScope(**base, evaluation_name='weekly'))
    assert [row.id for row in by_name] == [weekly_a.id]

    by_slo = await repo.list_for_refetch(RefetchScope(**base, slo_names=[_SLO_B]))
    assert [row.id for row in by_slo] == [day_one_b.id]

    only_failed = await repo.list_for_refetch(RefetchScope(**base, only_failed=True))
    assert [row.id for row in only_failed] == [day_one_b.id]


@pytest.mark.integration
async def test_reset_for_refetch_clears_results_and_children_but_keeps_annotations_and_invalidation(
    db_session: AsyncSession, info_category_id: uuid.UUID
) -> None:
    asset_id = await _seed_asset(db_session)
    slo_eval = await _seed_slo_evaluation(db_session, asset_id=asset_id, slo_name=_SLO_A, period_start=_DAY_ONE)
    untouched = await _seed_slo_evaluation(db_session, asset_id=asset_id, slo_name=_SLO_B, period_start=_DAY_ONE)
    await _seed_children(db_session, slo_eval)
    await _seed_children(db_session, untouched)
    pinned_at = datetime(2026, 3, 12, 8, 0, 0, tzinfo=UTC)
    db_session.add(
        EvaluationAnnotation(
            slo_evaluation_id=slo_eval.id, content='keep me', author='tester', category_id=info_category_id
        )
    )
    await db_session.flush()
    await EvaluationRepository(db_session).override_status(
        slo_eval.id, new_result='fail', reason='manual', author='tester'
    )
    await EvaluationRepository(db_session).invalidate(slo_eval.id, note='bad data')
    await EvaluationRepository(db_session).pin_baseline(slo_eval.id, reason='golden', author='tester')
    slo_eval.started_at = pinned_at
    await db_session.flush()
    await db_session.refresh(slo_eval)
    pinned_before = slo_eval.baseline_pinned_at
    job_stats = {'refetch': {'reason': 'outage', 'previous_status': 'completed'}}

    repo = EvaluationRepository(db_session)
    await repo.reset_for_refetch([slo_eval.id], job_stats_by_id={slo_eval.id: job_stats})
    await db_session.refresh(slo_eval)

    assert slo_eval.status == 'pending'
    assert slo_eval.result is None
    assert slo_eval.score is None
    assert slo_eval.achieved_points is None
    assert slo_eval.total_points is None
    assert slo_eval.started_at is None
    assert slo_eval.original_result is None
    assert slo_eval.override_reason is None
    assert slo_eval.override_author is None
    assert slo_eval.job_stats == job_stats
    assert await _count(db_session, SLIValue, SLIValue.slo_evaluation_id, slo_eval.id) == 0
    assert len(await IndicatorRepository(db_session).get_for_evaluation(slo_eval.id)) == 0
    assert await _count(db_session, EvaluationAnnotation, EvaluationAnnotation.slo_evaluation_id, slo_eval.id) == 1
    assert slo_eval.invalidated is True
    assert slo_eval.invalidation_note == 'bad data'
    assert slo_eval.baseline_pinned_at == pinned_before
    assert pinned_before is not None

    # A row that was not listed keeps everything.
    await db_session.refresh(untouched)
    assert untouched.status == 'completed'
    assert await _count(db_session, SLIValue, SLIValue.slo_evaluation_id, untouched.id) == 1
    assert len(await IndicatorRepository(db_session).get_for_evaluation(untouched.id)) == 1


@pytest.mark.integration
async def test_delete_for_slo_range_only_touches_the_slo_and_period(db_session: AsyncSession) -> None:
    asset_id = await _seed_asset(db_session)
    other_asset_id = await _seed_asset(db_session)
    repo = ChangePointRepository(db_session)

    async def insert(*, target_asset: uuid.UUID, slo_name: str, period_start: datetime) -> uuid.UUID:
        change_point = await repo.insert_change_point(
            ChangePointInsertParams(
                indicator_result_id=None,
                evaluation_run_id=None,
                asset_id=target_asset,
                slo_name=slo_name,
                metric_name='cpu',
                period_start=period_start,
                detector='e_divisive',
                direction='regression',
                change_relative_pct=10.0,
                change_absolute=5.0,
                pvalue=0.001,
                pre_segment_mean=50.0,
                post_segment_mean=55.0,
                post_segment_std=1.0,
            )
        )
        return change_point.id

    inside = await insert(target_asset=asset_id, slo_name=_SLO_A, period_start=_DAY_ONE)
    inside_edge = await insert(target_asset=asset_id, slo_name=_SLO_A, period_start=_DAY_TWO)
    outside_period = await insert(target_asset=asset_id, slo_name=_SLO_A, period_start=_DAY_TWO + timedelta(days=1))
    other_slo = await insert(target_asset=asset_id, slo_name=_SLO_B, period_start=_DAY_ONE)
    other_asset = await insert(target_asset=other_asset_id, slo_name=_SLO_A, period_start=_DAY_ONE)

    deleted = await repo.delete_for_slo_range(
        asset_id=asset_id, slo_name=_SLO_A, period_from=_DAY_ONE, period_to=_DAY_TWO
    )

    assert deleted == 2
    assert await repo.get_by_id(inside) is None
    assert await repo.get_by_id(inside_edge) is None
    for survivor in (outside_period, other_slo, other_asset):
        assert await repo.get_by_id(survivor) is not None


@pytest.mark.integration
async def test_mark_pending_sets_run_status(db_session: AsyncSession) -> None:
    asset_id = await _seed_asset(db_session)
    run_repo = EvaluationRunRepository(db_session)
    run = await run_repo.create(
        asset_id=asset_id, eval_name='daily', period_start=_DAY_ONE, period_end=_DAY_ONE + timedelta(hours=1)
    )
    await run_repo.mark_completed(run.id, result='pass', achieved_points=1, total_points=1)

    await run_repo.mark_pending(run.id)
    await db_session.refresh(run)

    assert run.status == 'pending'
    assert run.result is None
    assert run.achieved_points is None
    assert run.total_points is None


@pytest.mark.integration
async def test_list_for_refetch_skips_failed_row_superseded_by_a_retry(db_session: AsyncSession) -> None:
    asset_id = await _seed_asset(db_session)
    failed = await _seed_slo_evaluation(
        db_session, asset_id=asset_id, slo_name=_SLO_A, period_start=_DAY_ONE, status='failed'
    )
    completed = await _seed_slo_evaluation(db_session, asset_id=asset_id, slo_name=_SLO_A, period_start=_DAY_ONE)
    lone_failed = await _seed_slo_evaluation(
        db_session, asset_id=asset_id, slo_name=_SLO_B, period_start=_DAY_ONE, status='failed'
    )
    repo = EvaluationRepository(db_session)
    base = {'asset_id': asset_id, 'period_from': _DAY_ONE, 'period_to': _DAY_ONE}

    everything = await repo.list_for_refetch(RefetchScope(**base))
    only_failed = await repo.list_for_refetch(RefetchScope(**base, only_failed=True))

    assert failed.id not in {row.id for row in everything}
    assert {row.id for row in everything} == {completed.id, lone_failed.id}
    assert [row.id for row in only_failed] == [lone_failed.id]
    job_stats: dict[uuid.UUID, dict[str, Any]] = {row.id: {'refetch': {}} for row in everything}
    await repo.reset_for_refetch([row.id for row in everything], job_stats_by_id=job_stats)


_REFETCH_STATS = {'refetch': {'reason': 'outage', 'previous_status': 'completed', 'previous_result': 'pass'}}
_ATTEMPT = {'attempt': 1, 'cause': 'adapter returned 504: budget exhausted', 'status': 504, 'elapsed_s': 305.0}


@pytest.mark.integration
async def test_refetched_row_run_to_completed_keeps_the_refetch_block(db_session: AsyncSession) -> None:
    """The job's terminal write merges: the refetch audit block, attempts and worker id survive; ``error`` goes."""
    asset_id = await _seed_asset(db_session)
    slo_eval = await _seed_slo_evaluation(db_session, asset_id=asset_id, slo_name=_SLO_A, period_start=_DAY_ONE)
    repo = EvaluationRepository(db_session)
    await repo.reset_for_refetch([slo_eval.id], job_stats_by_id={slo_eval.id: _REFETCH_STATS})

    await repo.mark_running(slo_eval.id, worker_id='worker-1')
    await repo.mark_pending_retry(slo_eval.id, attempt_record=_ATTEMPT)
    await repo.mark_running(slo_eval.id, worker_id='worker-1')
    await repo.mark_completed(slo_eval.id, result='pass', score=100.0, job_stats={'fetch_errors': {}})
    await db_session.refresh(slo_eval)

    assert slo_eval.status == 'completed'
    assert slo_eval.job_stats['refetch'] == _REFETCH_STATS['refetch']
    assert slo_eval.job_stats['fetch_attempts'] == [_ATTEMPT]
    assert slo_eval.job_stats['worker_id'] == 'worker-1'
    assert slo_eval.job_stats['fetch_errors'] == {}
    assert 'error' not in slo_eval.job_stats


@pytest.mark.integration
async def test_completed_and_partial_writes_drop_a_stale_error(db_session: AsyncSession) -> None:
    asset_id = await _seed_asset(db_session)
    slo_eval = await _seed_slo_evaluation(
        db_session, asset_id=asset_id, slo_name=_SLO_A, period_start=_DAY_ONE, status='failed'
    )
    repo = EvaluationRepository(db_session)

    await repo.mark_partial(slo_eval.id, {'indicators_attempted': 2})
    await db_session.refresh(slo_eval)
    assert slo_eval.job_stats == {'indicators_attempted': 2}

    await repo.mark_failed(slo_eval.id, {'error': 'adapter query failed'})
    await repo.mark_completed(slo_eval.id, result='pass', score=100.0, job_stats={'fetch_errors': {}})
    await db_session.refresh(slo_eval)
    assert slo_eval.job_stats == {'indicators_attempted': 2, 'fetch_errors': {}}


@pytest.mark.integration
async def test_refetched_row_run_to_failed_keeps_refetch_and_fetch_attempts(db_session: AsyncSession) -> None:
    asset_id = await _seed_asset(db_session)
    slo_eval = await _seed_slo_evaluation(db_session, asset_id=asset_id, slo_name=_SLO_A, period_start=_DAY_ONE)
    repo = EvaluationRepository(db_session)
    await repo.reset_for_refetch([slo_eval.id], job_stats_by_id={slo_eval.id: _REFETCH_STATS})
    await repo.mark_running(slo_eval.id, worker_id='worker-1')
    final_attempt = {**_ATTEMPT, 'attempt': 2}

    await repo.mark_failed(
        slo_eval.id,
        {'error': 'adapter query failed after 2 attempts: boom', 'fetch_attempts': [_ATTEMPT, final_attempt]},
    )
    await db_session.refresh(slo_eval)

    assert slo_eval.status == 'failed'
    assert slo_eval.job_stats['refetch'] == _REFETCH_STATS['refetch']
    assert slo_eval.job_stats['fetch_attempts'] == [_ATTEMPT, final_attempt]
    assert slo_eval.job_stats['error'] == 'adapter query failed after 2 attempts: boom'


@pytest.mark.integration
async def test_reset_for_refetch_skips_a_row_already_reopened(db_session: AsyncSession) -> None:
    """A second, concurrent refetch finds the row ``pending`` and neither resets nor counts it."""
    asset_id = await _seed_asset(db_session)
    slo_eval = await _seed_slo_evaluation(db_session, asset_id=asset_id, slo_name=_SLO_A, period_start=_DAY_ONE)
    repo = EvaluationRepository(db_session)

    first = await repo.reset_for_refetch([slo_eval.id], job_stats_by_id={slo_eval.id: _REFETCH_STATS})
    second = await repo.reset_for_refetch([slo_eval.id], job_stats_by_id={slo_eval.id: {'refetch': {}}})
    await db_session.refresh(slo_eval)

    assert (first, second) == (1, 0)
    assert slo_eval.job_stats == _REFETCH_STATS
