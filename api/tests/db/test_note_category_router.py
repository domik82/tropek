"""Integration tests for /note-categories router."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.session import get_session
from tropek.main import app

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    async def _override_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as c:
        yield c
    app.dependency_overrides.clear()


async def test_list_returns_seeded(client: AsyncClient) -> None:
    res = await client.get('/note-categories')
    assert res.status_code == 200
    names = {row['name'] for row in res.json()}
    assert {'info', 'failure', 'investigation', 're-evaluation'} <= names


async def test_create_category(client: AsyncClient) -> None:
    res = await client.post(
        '/note-categories',
        json={'name': 'release', 'label': 'Release', 'color': 'green', 'show_on_graph': True},
    )
    assert res.status_code == 201
    body = res.json()
    assert body['name'] == 'release'
    assert body['is_system'] is False


async def test_create_rejects_bad_color(client: AsyncClient) -> None:
    res = await client.post(
        '/note-categories',
        json={'name': 'neon', 'label': 'Neon', 'color': 'fuschia', 'show_on_graph': True},
    )
    assert res.status_code == 422


async def test_create_rejects_long_label(client: AsyncClient) -> None:
    res = await client.post(
        '/note-categories',
        json={
            'name': 'long',
            'label': 'ThisLabelIsWayTooLong',
            'color': 'sky',
            'show_on_graph': True,
        },
    )
    assert res.status_code == 422


async def test_update_system_label_ok(client: AsyncClient) -> None:
    list_res = await client.get('/note-categories')
    re_eval = next(r for r in list_res.json() if r['name'] == 're-evaluation')
    res = await client.patch(f'/note-categories/{re_eval["id"]}', json={'label': 'Re-Eval'})
    assert res.status_code == 200


async def test_update_system_name_rejected(client: AsyncClient) -> None:
    list_res = await client.get('/note-categories')
    re_eval = next(r for r in list_res.json() if r['name'] == 're-evaluation')
    res = await client.patch(f'/note-categories/{re_eval["id"]}', json={'name': 'renamed'})
    assert res.status_code == 409


async def test_delete_system_rejected(client: AsyncClient) -> None:
    list_res = await client.get('/note-categories')
    re_eval = next(r for r in list_res.json() if r['name'] == 're-evaluation')
    res = await client.delete(f'/note-categories/{re_eval["id"]}')
    assert res.status_code == 409


async def test_delete_non_system_returns_reassigned_count(client: AsyncClient) -> None:
    create = await client.post(
        '/note-categories',
        json={'name': 'ephemeral', 'label': 'Eph', 'color': 'purple', 'show_on_graph': True},
    )
    cat_id = create.json()['id']

    res = await client.delete(f'/note-categories/{cat_id}')
    assert res.status_code == 204
    assert res.headers.get('X-Reassigned-Annotations') == '0'
