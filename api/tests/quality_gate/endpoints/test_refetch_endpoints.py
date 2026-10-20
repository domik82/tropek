"""Endpoint tests for refetching stored SLO evaluations from the source."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import AnnotationCategory, Asset, AssetType, EvaluationAnnotation, EvaluationRun, SLOEvaluation
from tropek.main import app
from tropek.modules.change_points.repository import ChangePointInsertParams, ChangePointRepository
from tropek.modules.quality_gate.repositories.evaluation import EvaluationRepository
from tropek.modules.quality_gate.repositories.evaluation_run import EvaluationRunRepository
from tropek.modules.quality_gate.repositories.indicator import IndicatorRepository
from tropek.modules.quality_gate.shared.params import EvalCreateParams
from tropek.queue import get_arq_pool

from .conftest import _ensure_slo_objective, _seed_indicator_row

_DAY_ONE = datetime(2026, 10, 15, tzinfo=UTC)
_DAY_TWO = _DAY_ONE + timedelta(days=1)
_SLO_A = 'refetch-ep-slo-a'
_SLO_B = 'refetch-ep-slo-b'


@pytest_asyncio.fixture()
async def arq_pool(async_client: AsyncClient) -> AsyncMock:
    """Replace the arq pool with a mock that records ``enqueue_job`` calls (cleared with the client)."""
    pool = AsyncMock()
    app.dependency_overrides[get_arq_pool] = lambda: pool
    return pool


async def _seed_asset(session: AsyncSession) -> tuple[uuid.UUID, str]:
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    asset_name = f'refetch-ep-{asset_id.hex[:8]}'
    session.add(Asset(id=asset_id, name=asset_name, type_name=type_name))
    await session.flush()
    return asset_id, asset_name


async def _seed_run(session: AsyncSession, asset_id: uuid.UUID, period_start: datetime = _DAY_ONE) -> EvaluationRun:
    run_repo = EvaluationRunRepository(session)
    run = await run_repo.create(
        asset_id=asset_id, eval_name='daily', period_start=period_start, period_end=period_start + timedelta(hours=1)
    )
    await run_repo.mark_completed(run.id, result='pass', achieved_points=1, total_points=1)
    return run


async def _seed_slo_evaluation(
    session: AsyncSession,
    run: EvaluationRun,
    *,
    slo_name: str,
    status: str = 'completed',
    with_indicator_row: bool = False,
) -> SLOEvaluation:
    repo = EvaluationRepository(session)
    slo_eval = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=run.id,
            evaluation_name=run.eval_name,
            period_start=run.period_start,
            period_end=run.period_end,
            ingestion_mode='pull',
            asset_snapshot={'name': 'refetch-asset'},
            asset_id=run.asset_id,
            slo_name=slo_name,
        )
    )
    if status == 'completed':
        await repo.mark_completed(slo_eval.id, result='pass', score=100.0, achieved_points=1, total_points=1)
    elif status == 'failed':
        await repo.mark_failed(slo_eval.id, {'error': 'adapter query failed'})
    elif status == 'running':
        await repo.mark_running(slo_eval.id)
    if with_indicator_row:
        await _seed_indicator_row(session, slo_eval.id, await _ensure_slo_objective(session, slo_name=slo_name))
    return slo_eval


async def _seed_change_point(
    session: AsyncSession, asset_id: uuid.UUID, slo_name: str, period_start: datetime
) -> uuid.UUID:
    change_point = await ChangePointRepository(session).insert_change_point(
        ChangePointInsertParams(
            indicator_result_id=None,
            evaluation_run_id=None,
            asset_id=asset_id,
            slo_name=slo_name,
            metric_name='response_time',
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


async def _run_notes(session: AsyncSession, run_id: uuid.UUID) -> list[tuple[str, str | None, str]]:
    result = await session.execute(
        select(EvaluationAnnotation.content, EvaluationAnnotation.author, AnnotationCategory.name)
        .join(AnnotationCategory, AnnotationCategory.id == EvaluationAnnotation.category_id)
        .where(EvaluationAnnotation.evaluation_run_id == run_id)
    )
    return [(row.content, row.author, row.name) for row in result.all()]


def _period_body(asset_name: str, **overrides: object) -> dict[str, object]:
    return {
        'asset_name': asset_name,
        'from': _DAY_ONE.isoformat(),
        'to': (_DAY_ONE + timedelta(hours=23)).isoformat(),
        **overrides,
    }


@pytest.mark.integration
async def test_refetch_by_period_resets_rows_and_enqueues(
    async_client: AsyncClient, db_session: AsyncSession, arq_pool: AsyncMock
) -> None:
    asset_id, asset_name = await _seed_asset(db_session)
    run = await _seed_run(db_session, asset_id)
    first = await _seed_slo_evaluation(db_session, run, slo_name=_SLO_A, with_indicator_row=True)
    second = await _seed_slo_evaluation(db_session, run, slo_name=_SLO_B, with_indicator_row=True)
    next_day = await _seed_slo_evaluation(db_session, await _seed_run(db_session, asset_id, _DAY_TWO), slo_name=_SLO_A)
    change_point_inside = await _seed_change_point(db_session, asset_id, _SLO_A, _DAY_ONE)
    change_point_next_day = await _seed_change_point(db_session, asset_id, _SLO_A, _DAY_TWO)

    response = await async_client.post(
        '/evaluations/refetch',
        json=_period_body(asset_name, reason='adapter outage', requested_by='operator'),
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        'matched': 2,
        'refetched': 2,
        'skipped': [],
        'run_ids': [str(run.id)],
        'dry_run': False,
    }
    for slo_eval in (first, second):
        await db_session.refresh(slo_eval)
        assert (slo_eval.status, slo_eval.result, slo_eval.score) == ('pending', None, None)
        assert slo_eval.job_stats['refetch']['previous_status'] == 'completed'
        assert slo_eval.job_stats['refetch']['previous_result'] == 'pass'
        assert slo_eval.job_stats['refetch']['requested_by'] == 'operator'
        assert await IndicatorRepository(db_session).get_for_evaluation(slo_eval.id) == []
    await db_session.refresh(next_day)
    assert next_day.status == 'completed'
    change_point_repo = ChangePointRepository(db_session)
    assert await change_point_repo.get_by_id(change_point_inside) is None
    assert await change_point_repo.get_by_id(change_point_next_day) is not None
    await db_session.refresh(run)
    assert (run.status, run.result) == ('pending', None)
    assert await _run_notes(db_session, run.id) == [
        ('refetched from source: 2 SLO evaluation(s) — adapter outage', 'operator', 'refetch')
    ]
    enqueued = sorted(call.args for call in arq_pool.enqueue_job.await_args_list)
    assert enqueued == sorted([('run_evaluation_job', str(first.id)), ('run_evaluation_job', str(second.id))])


@pytest.mark.integration
async def test_refetch_dry_run_changes_nothing(
    async_client: AsyncClient, db_session: AsyncSession, arq_pool: AsyncMock
) -> None:
    asset_id, asset_name = await _seed_asset(db_session)
    run = await _seed_run(db_session, asset_id)
    slo_eval = await _seed_slo_evaluation(db_session, run, slo_name=_SLO_A)

    response = await async_client.post('/evaluations/refetch', json=_period_body(asset_name, dry_run=True))

    assert response.status_code == 200, response.text
    assert (response.json()['refetched'], response.json()['dry_run']) == (1, True)
    await db_session.refresh(slo_eval)
    assert slo_eval.status == 'completed'
    arq_pool.enqueue_job.assert_not_awaited()


@pytest.mark.integration
async def test_refetch_run_endpoint(async_client: AsyncClient, db_session: AsyncSession, arq_pool: AsyncMock) -> None:
    asset_id, _ = await _seed_asset(db_session)
    run = await _seed_run(db_session, asset_id)
    completed = await _seed_slo_evaluation(db_session, run, slo_name=_SLO_A)
    failed = await _seed_slo_evaluation(db_session, run, slo_name=_SLO_B, status='failed')

    response = await async_client.post(
        f'/evaluation-run/{run.id}/refetch', json={'only_failed': True, 'reason': 'retry the outage day'}
    )

    assert response.status_code == 200, response.text
    assert (response.json()['matched'], response.json()['refetched']) == (1, 1)
    await db_session.refresh(failed)
    await db_session.refresh(completed)
    assert failed.status == 'pending'
    assert failed.job_stats['refetch']['previous_status'] == 'failed'
    assert completed.status == 'completed'
    arq_pool.enqueue_job.assert_awaited_once_with('run_evaluation_job', str(failed.id))

    missing = await async_client.post(f'/evaluation-run/{uuid.uuid4()}/refetch', json={})
    assert missing.status_code == 404


@pytest.mark.integration
async def test_refetch_with_running_row_is_atomic_409(
    async_client: AsyncClient, db_session: AsyncSession, arq_pool: AsyncMock
) -> None:
    asset_id, asset_name = await _seed_asset(db_session)
    run = await _seed_run(db_session, asset_id)
    completed = await _seed_slo_evaluation(db_session, run, slo_name=_SLO_A, with_indicator_row=True)
    running = await _seed_slo_evaluation(db_session, run, slo_name=_SLO_B, status='running')
    change_point_id = await _seed_change_point(db_session, asset_id, _SLO_A, _DAY_ONE)

    response = await async_client.post('/evaluations/refetch', json=_period_body(asset_name))

    assert response.status_code == 409
    assert str(running.id) in response.json()['detail']
    assert 'in progress' in response.json()['detail']
    await db_session.refresh(completed)
    assert (completed.status, completed.result, completed.score) == ('completed', 'pass', 100.0)
    assert len(await IndicatorRepository(db_session).get_for_evaluation(completed.id)) == 1
    assert await ChangePointRepository(db_session).get_by_id(change_point_id) is not None
    await db_session.refresh(run)
    assert run.status == 'completed'
    assert await _run_notes(db_session, run.id) == []
    arq_pool.enqueue_job.assert_not_awaited()


@pytest.mark.integration
@pytest.mark.parametrize(
    ('period_from', 'period_to'),
    [
        (_DAY_TWO, _DAY_ONE),
        (_DAY_ONE - timedelta(days=401), _DAY_ONE),
        # A naive bound cannot be compared with an aware one; it is refused instead of answering 500.
        (_DAY_ONE.replace(tzinfo=None), _DAY_TWO),
    ],
    ids=['to-before-from', 'wider-than-400-days', 'naive-from'],
)
async def test_refetch_range_validation_422(
    async_client: AsyncClient,
    db_session: AsyncSession,
    arq_pool: AsyncMock,
    period_from: datetime,
    period_to: datetime,
) -> None:
    _, asset_name = await _seed_asset(db_session)

    response = await async_client.post(
        '/evaluations/refetch',
        json={'asset_name': asset_name, 'from': period_from.isoformat(), 'to': period_to.isoformat()},
    )

    assert response.status_code == 422
    arq_pool.enqueue_job.assert_not_awaited()


@pytest.mark.integration
async def test_detail_of_a_fetch_that_failed_with_minimal_metadata_is_200(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """A metric whose aggregated fetch failed with a data error may store only the chunk counts."""
    asset_id, _ = await _seed_asset(db_session)
    slo_eval = await _seed_slo_evaluation(db_session, await _seed_run(db_session, asset_id), slo_name=_SLO_A)
    minimal = {'mode': 'aggregated', 'chunks_failed': 1, 'chunks_total': 6}
    await EvaluationRepository(db_session).mark_completed(
        slo_eval.id, result='error', score=0.0, job_stats={'sli_metadata': {'cpu': minimal}}
    )
    await db_session.flush()

    response = await async_client.get(f'/evaluation/{slo_eval.id}')

    assert response.status_code == 200, response.text
    cpu = response.json()['sli_metadata']['cpu']
    assert (cpu['chunks_failed'], cpu['expected_samples'], cpu['missing_pct']) == (1, None, None)


@pytest.mark.integration
async def test_refetch_unknown_asset_404(async_client: AsyncClient, arq_pool: AsyncMock) -> None:
    response = await async_client.post('/evaluations/refetch', json=_period_body('no-such-asset'))

    assert response.status_code == 404


@pytest.mark.integration
async def test_refetch_keeps_pin_and_invalidation(
    async_client: AsyncClient, db_session: AsyncSession, arq_pool: AsyncMock, info_category_id: uuid.UUID
) -> None:
    asset_id, asset_name = await _seed_asset(db_session)
    slo_eval = await _seed_slo_evaluation(db_session, await _seed_run(db_session, asset_id), slo_name=_SLO_A)
    repo = EvaluationRepository(db_session)
    await repo.invalidate(slo_eval.id, note='bad data')
    await repo.pin_baseline(slo_eval.id, reason='golden', author='tester')
    db_session.add(
        EvaluationAnnotation(
            slo_evaluation_id=slo_eval.id, content='keep me', author='tester', category_id=info_category_id
        )
    )
    await db_session.flush()
    await db_session.refresh(slo_eval)
    pinned_at = slo_eval.baseline_pinned_at

    response = await async_client.post('/evaluations/refetch', json=_period_body(asset_name))

    assert response.status_code == 200, response.text
    await db_session.refresh(slo_eval)
    assert slo_eval.status == 'pending'
    assert (slo_eval.invalidated, slo_eval.invalidation_note) == (True, 'bad data')
    assert pinned_at is not None
    assert (slo_eval.baseline_pinned_at, slo_eval.baseline_unpinned_at) == (pinned_at, None)
    notes = await db_session.execute(
        select(EvaluationAnnotation.content).where(EvaluationAnnotation.slo_evaluation_id == slo_eval.id)
    )
    assert list(notes.scalars().all()) == ['keep me']
