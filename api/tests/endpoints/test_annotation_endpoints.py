"""Endpoint tests for annotation CRUD operations."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import _create_asset, _create_completed_eval


@pytest.mark.integration
async def test_create_annotation(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    resp = await async_client.post(
        f'/evaluations/{eval_id}/annotations',
        json={'content': 'Looks like a network blip', 'author': 'alice', 'category': 'observation'},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body['content'] == 'Looks like a network blip'
    assert body['author'] == 'alice'
    assert body['category'] == 'observation'
    assert body['hidden_at'] is None


@pytest.mark.integration
async def test_annotation_appears_in_eval_detail(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    await async_client.post(
        f'/evaluations/{eval_id}/annotations',
        json={'content': 'Note one', 'author': 'alice'},
    )
    await async_client.post(
        f'/evaluations/{eval_id}/annotations',
        json={'content': 'Note two', 'author': 'bob'},
    )

    resp = await async_client.get(f'/evaluations/{eval_id}')
    assert resp.status_code == 200
    detail = resp.json()
    assert detail['annotation_count'] == 2
    contents = [a['content'] for a in detail['annotations']]
    assert 'Note one' in contents
    assert 'Note two' in contents


@pytest.mark.integration
async def test_list_annotations(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    await async_client.post(
        f'/evaluations/{eval_id}/annotations',
        json={'content': 'Visible note', 'author': 'alice'},
    )

    resp = await async_client.get(f'/evaluations/{eval_id}/annotations')
    assert resp.status_code == 200
    annotations = resp.json()
    assert len(annotations) == 1
    assert annotations[0]['content'] == 'Visible note'


@pytest.mark.integration
async def test_update_annotation(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    create_resp = await async_client.post(
        f'/evaluations/{eval_id}/annotations',
        json={'content': 'Original', 'author': 'alice'},
    )
    ann_id = create_resp.json()['id']

    resp = await async_client.patch(
        f'/evaluations/{eval_id}/annotations/{ann_id}',
        json={'content': 'Updated content'},
    )
    assert resp.status_code == 200
    assert resp.json()['content'] == 'Updated content'


@pytest.mark.integration
async def test_hide_annotation_excludes_from_detail(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    create_resp = await async_client.post(
        f'/evaluations/{eval_id}/annotations',
        json={'content': 'Will be hidden', 'author': 'alice'},
    )
    ann_id = create_resp.json()['id']

    hide_resp = await async_client.post(
        f'/evaluations/{eval_id}/annotations/{ann_id}/hide',
        json={'reason': 'Duplicate', 'author': 'bob'},
    )
    assert hide_resp.status_code == 200
    assert hide_resp.json()['hidden_at'] is not None

    detail_resp = await async_client.get(f'/evaluations/{eval_id}')
    detail = detail_resp.json()
    assert detail['annotation_count'] == 0
    assert len(detail['annotations']) == 0


@pytest.mark.integration
async def test_create_annotation_on_missing_eval(async_client: AsyncClient) -> None:
    fake_id = uuid.uuid4()
    resp = await async_client.post(
        f'/evaluations/{fake_id}/annotations',
        json={'content': 'Orphan note', 'author': 'alice'},
    )
    assert resp.status_code == 404
