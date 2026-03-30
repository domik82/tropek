"""Integration tests for SLO binding CRUD via HTTP API.

Requires TEST_DATABASE_URL and a running TimescaleDB instance.
Run: uv run pytest api/tests/db/test_slo_bindings.py -m integration -v
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from app.db.session import get_session
from app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture()
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """Yield an httpx AsyncClient bound to the FastAPI app with test DB session."""

    async def _override_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.integration
async def test_create_and_list_asset_slo_binding(async_client: AsyncClient) -> None:
    """Creating an SLO binding for an asset stores and lists correctly."""
    await async_client.post('/asset-types', json={'name': 'vm-bind-test'})
    await async_client.post('/assets', json={'name': 'bind-test-asset', 'type_name': 'vm-bind-test'})
    await async_client.post(
        '/sli-definitions',
        json={
            'name': 'bind-sli',
            'adapter_type': 'prometheus',
            'indicators': {'cpu': 'rate(cpu[5m])'},
        },
    )
    await async_client.post(
        '/slo-definitions',
        json={
            'name': 'bind-slo',
            'sli_name': 'bind-sli',
            'sli_version': 1,
            'objectives': [{'sli': 'cpu', 'pass_threshold': ['<80']}],
        },
    )
    await async_client.post(
        '/datasources',
        json={
            'name': 'bind-ds',
            'adapter_type': 'prometheus',
            'adapter_url': 'http://localhost:9090',
        },
    )

    resp = await async_client.post(
        '/assets/bind-test-asset/slo-bindings',
        json={'slo_name': 'bind-slo', 'data_source_name': 'bind-ds'},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data['target_type'] == 'asset'
    assert data['slo_name'] == 'bind-slo'
    assert data['data_source_name'] == 'bind-ds'

    list_resp = await async_client.get('/assets/bind-test-asset/slo-bindings')
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


@pytest.mark.integration
async def test_delete_asset_slo_binding(async_client: AsyncClient) -> None:
    """Deleting an SLO binding removes it."""
    await async_client.post('/asset-types', json={'name': 'vm-del-test'})
    await async_client.post('/assets', json={'name': 'del-test-asset', 'type_name': 'vm-del-test'})
    await async_client.post(
        '/sli-definitions',
        json={
            'name': 'del-sli',
            'adapter_type': 'prometheus',
            'indicators': {'cpu': 'rate(cpu[5m])'},
        },
    )
    await async_client.post(
        '/slo-definitions',
        json={
            'name': 'del-slo',
            'sli_name': 'del-sli',
            'sli_version': 1,
            'objectives': [{'sli': 'cpu', 'pass_threshold': ['<80']}],
        },
    )
    await async_client.post(
        '/datasources',
        json={
            'name': 'del-ds',
            'adapter_type': 'prometheus',
            'adapter_url': 'http://localhost:9090',
        },
    )

    await async_client.post(
        '/assets/del-test-asset/slo-bindings',
        json={'slo_name': 'del-slo', 'data_source_name': 'del-ds'},
    )
    del_resp = await async_client.delete('/assets/del-test-asset/slo-bindings/del-slo')
    assert del_resp.status_code == 204

    list_resp = await async_client.get('/assets/del-test-asset/slo-bindings')
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 0


@pytest.mark.integration
async def test_create_group_slo_binding(async_client: AsyncClient) -> None:
    """Creating an SLO binding for an asset group works."""
    await async_client.post(
        '/sli-definitions',
        json={
            'name': 'grp-bind-sli',
            'adapter_type': 'prometheus',
            'indicators': {'cpu': 'rate(cpu[5m])'},
        },
    )
    await async_client.post(
        '/slo-definitions',
        json={
            'name': 'grp-bind-slo',
            'sli_name': 'grp-bind-sli',
            'sli_version': 1,
            'objectives': [{'sli': 'cpu', 'pass_threshold': ['<80']}],
        },
    )
    await async_client.post(
        '/datasources',
        json={
            'name': 'grp-bind-ds',
            'adapter_type': 'prometheus',
            'adapter_url': 'http://localhost:9090',
        },
    )
    await async_client.post('/asset-groups', json={'name': 'bind-test-group'})

    resp = await async_client.post(
        '/asset-groups/bind-test-group/slo-bindings',
        json={'slo_name': 'grp-bind-slo', 'data_source_name': 'grp-bind-ds'},
    )
    assert resp.status_code == 201
    assert resp.json()['target_type'] == 'asset_group'

    list_resp = await async_client.get('/asset-groups/bind-test-group/slo-bindings')
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1
