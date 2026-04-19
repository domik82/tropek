"""Endpoint tests for annotation CRUD operations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import EvaluationRun, SLOEvaluation

from .conftest import _create_asset, _create_completed_eval


@pytest.mark.integration
async def test_create_annotation(
    async_client: AsyncClient,
    db_session: AsyncSession,
    category_ids: dict[str, uuid.UUID],
) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    resp = await async_client.post(
        f'/evaluation/{eval_id}/annotations',
        json={
            'content': 'Looks like a network blip',
            'author': 'alice',
            'category_id': str(category_ids['investigation']),
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body['content'] == 'Looks like a network blip'
    assert body['author'] == 'alice'
    assert body['category']['name'] == 'investigation'
    assert body['hidden_at'] is None


@pytest.mark.integration
async def test_annotation_appears_in_eval_detail(
    async_client: AsyncClient,
    db_session: AsyncSession,
    category_ids: dict[str, uuid.UUID],
) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)
    info_id = str(category_ids['info'])

    await async_client.post(
        f'/evaluation/{eval_id}/annotations',
        json={'content': 'Note one', 'author': 'alice', 'category_id': info_id},
    )
    await async_client.post(
        f'/evaluation/{eval_id}/annotations',
        json={'content': 'Note two', 'author': 'bob', 'category_id': info_id},
    )

    resp = await async_client.get(f'/evaluation/{eval_id}')
    assert resp.status_code == 200
    detail = resp.json()
    assert detail['annotation_count'] == 2
    contents = [a['content'] for a in detail['annotations']]
    assert 'Note one' in contents
    assert 'Note two' in contents


@pytest.mark.integration
async def test_list_evaluations_serializes_latest_annotation_category(
    async_client: AsyncClient,
    db_session: AsyncSession,
    category_ids: dict[str, uuid.UUID],
) -> None:
    """Regression guard: GET /evaluations must serialize latest_annotation.category
    without triggering a lazy-load (MissingGreenlet) in the presenter."""
    asset_name = f'reg-asset-{uuid.uuid4().hex[:8]}'
    asset_id = await _create_asset(db_session, name=asset_name)
    eval_id = await _create_completed_eval(db_session, asset_id)

    await async_client.post(
        f'/evaluation/{eval_id}/annotations',
        json={
            'content': 'regression probe',
            'author': 'ops',
            'category_id': str(category_ids['info']),
        },
    )

    resp = await async_client.get(f'/evaluations?asset_name={asset_name}')
    assert resp.status_code == 200
    body = resp.json()
    assert body['total'] >= 1
    latest = body['items'][0]['latest_annotation']
    assert latest is not None
    assert latest['content'] == 'regression probe'
    assert latest['category']['name'] == 'info'


@pytest.mark.integration
async def test_list_annotations(
    async_client: AsyncClient,
    db_session: AsyncSession,
    category_ids: dict[str, uuid.UUID],
) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    await async_client.post(
        f'/evaluation/{eval_id}/annotations',
        json={
            'content': 'Visible note',
            'author': 'alice',
            'category_id': str(category_ids['info']),
        },
    )

    resp = await async_client.get(f'/evaluation/{eval_id}/annotations')
    assert resp.status_code == 200
    annotations = resp.json()
    assert len(annotations) == 1
    assert annotations[0]['content'] == 'Visible note'


@pytest.mark.integration
async def test_update_annotation(
    async_client: AsyncClient,
    db_session: AsyncSession,
    category_ids: dict[str, uuid.UUID],
) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    create_resp = await async_client.post(
        f'/evaluation/{eval_id}/annotations',
        json={
            'content': 'Original',
            'author': 'alice',
            'category_id': str(category_ids['info']),
        },
    )
    ann_id = create_resp.json()['id']

    resp = await async_client.patch(
        f'/evaluation/{eval_id}/annotations/{ann_id}',
        json={'content': 'Updated content'},
    )
    assert resp.status_code == 200
    assert resp.json()['content'] == 'Updated content'


@pytest.mark.integration
async def test_hide_annotation_excludes_from_detail(
    async_client: AsyncClient,
    db_session: AsyncSession,
    category_ids: dict[str, uuid.UUID],
) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    create_resp = await async_client.post(
        f'/evaluation/{eval_id}/annotations',
        json={
            'content': 'Will be hidden',
            'author': 'alice',
            'category_id': str(category_ids['info']),
        },
    )
    ann_id = create_resp.json()['id']

    hide_resp = await async_client.post(
        f'/evaluation/{eval_id}/annotations/{ann_id}/hide',
        json={'reason': 'Duplicate', 'author': 'bob'},
    )
    assert hide_resp.status_code == 200
    assert hide_resp.json()['hidden_at'] is not None

    detail_resp = await async_client.get(f'/evaluation/{eval_id}')
    detail = detail_resp.json()
    assert detail['annotation_count'] == 0
    assert len(detail['annotations']) == 0


@pytest.mark.integration
async def test_create_annotation_on_missing_eval(
    async_client: AsyncClient,
    category_ids: dict[str, uuid.UUID],
) -> None:
    fake_id = uuid.uuid4()
    resp = await async_client.post(
        f'/evaluation/{fake_id}/annotations',
        json={
            'content': 'Orphan note',
            'author': 'alice',
            'category_id': str(category_ids['info']),
        },
    )
    assert resp.status_code == 404


async def _create_evaluation_run(
    db_session: AsyncSession,
    asset_id: uuid.UUID,
) -> uuid.UUID:
    period_start = datetime(2026, 4, 10, 12, 0, 0, tzinfo=UTC)
    run = EvaluationRun(
        id=uuid.uuid4(),
        asset_id=asset_id,
        eval_name='daily',
        period_start=period_start,
        period_end=period_start + timedelta(hours=1),
        status='completed',
        result='pass',
        achieved_points=10,
        total_points=10,
    )
    db_session.add(run)
    await db_session.flush()
    return run.id


@pytest.mark.integration
async def test_create_run_annotation(
    async_client: AsyncClient,
    db_session: AsyncSession,
    category_ids: dict[str, uuid.UUID],
) -> None:
    asset_id = await _create_asset(db_session)
    run_id = await _create_evaluation_run(db_session, asset_id)

    resp = await async_client.post(
        f'/evaluation-run/{run_id}/annotations',
        json={
            'content': 'Column-level note from UI',
            'author': 'daisy',
            'category_id': str(category_ids['info']),
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body['content'] == 'Column-level note from UI'
    assert body['author'] == 'daisy'
    assert body['evaluation_run_id'] == str(run_id)
    assert body['slo_evaluation_id'] is None


@pytest.mark.integration
async def test_run_annotation_visible_in_column_endpoint(
    async_client: AsyncClient,
    db_session: AsyncSession,
    category_ids: dict[str, uuid.UUID],
) -> None:
    asset_id = await _create_asset(db_session)
    run_id = await _create_evaluation_run(db_session, asset_id)

    create_resp = await async_client.post(
        f'/evaluation-run/{run_id}/annotations',
        json={
            'content': 'Visible column note',
            'author': 'daisy',
            'category_id': str(category_ids['info']),
        },
    )
    ann_id = create_resp.json()['id']

    list_resp = await async_client.get(
        '/evaluations/column-annotations',
        params={'evaluation_id': str(run_id)},
    )
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert len(data) == 1
    assert data[0]['id'] == ann_id
    assert data[0]['evaluation_run_id'] == str(run_id)


@pytest.mark.integration
async def test_trend_annotations_keyed_by_slo_evaluation_id(
    async_client: AsyncClient,
    db_session: AsyncSession,
    category_ids: dict[str, uuid.UUID],
) -> None:
    """Regression guard: trend points are keyed by slo_evaluation_id on the UI
    side, so the trend-annotations map must be keyed the same way. Run-level
    annotations must fan out to every slo_evaluation_id whose parent run they
    belong to."""
    asset_name = f'trend-asset-{uuid.uuid4().hex[:8]}'
    asset_id = await _create_asset(db_session, name=asset_name)
    slo_eval_id = await _create_completed_eval(db_session, asset_id, slo_name='svc/latency')

    slo_eval = await db_session.get(SLOEvaluation, slo_eval_id)
    assert slo_eval is not None
    run_id = slo_eval.evaluation_id

    run_resp = await async_client.post(
        f'/evaluation-run/{run_id}/annotations',
        json={
            'content': 'run-level note',
            'author': 'ops',
            'category_id': str(category_ids['info']),
        },
    )
    assert run_resp.status_code == 201

    slo_resp = await async_client.post(
        f'/evaluation/{slo_eval_id}/annotations',
        json={
            'content': 'slo-level note',
            'author': 'ops',
            'category_id': str(category_ids['info']),
        },
    )
    assert slo_resp.status_code == 201

    resp = await async_client.get(
        '/evaluations/trend-annotations',
        params={'asset': asset_name, 'slo': 'svc/latency'},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert str(slo_eval_id) in body, (
        f'expected slo_evaluation_id as key, got keys: {list(body.keys())}'
    )
    assert str(run_id) not in body
    contents = sorted(ann['content'] for ann in body[str(slo_eval_id)])
    assert contents == ['run-level note', 'slo-level note']


@pytest.mark.integration
async def test_create_run_annotation_on_missing_run(
    async_client: AsyncClient,
    category_ids: dict[str, uuid.UUID],
) -> None:
    fake_id = uuid.uuid4()
    resp = await async_client.post(
        f'/evaluations/run/{fake_id}/annotations',
        json={
            'content': 'Orphan run note',
            'author': 'daisy',
            'category_id': str(category_ids['info']),
        },
    )
    assert resp.status_code == 404
