"""Integration tests for API schema consistency fixes."""

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
    async with AsyncClient(transport=transport, base_url='http://test') as test_client:
        yield test_client
    app.dependency_overrides.clear()


async def test_datasource_update_name(client: AsyncClient) -> None:
    """DataSource can be renamed via PATCH."""
    create_response = await client.post(
        '/datasources',
        json={'name': 'ds-original', 'adapter_type': 'prometheus', 'adapter_url': 'http://prom:9090'},
    )
    assert create_response.status_code == 201

    rename_response = await client.patch('/datasources/ds-original', json={'name': 'ds-renamed'})
    assert rename_response.status_code == 200
    assert rename_response.json()['name'] == 'ds-renamed'

    get_response = await client.get('/datasources/ds-renamed')
    assert get_response.status_code == 200


async def test_datasource_update_adapter_type(client: AsyncClient) -> None:
    """DataSource adapter_type can be changed via PATCH."""
    await client.post(
        '/datasources',
        json={'name': 'ds-adapter-test', 'adapter_type': 'prometheus', 'adapter_url': 'http://prom:9090'},
    )
    response = await client.patch('/datasources/ds-adapter-test', json={'adapter_type': 'datadog'})
    assert response.status_code == 200
    assert response.json()['adapter_type'] == 'datadog'


async def test_datasource_rename_conflict(client: AsyncClient) -> None:
    """Renaming a DataSource to an existing name returns 409."""
    await client.post(
        '/datasources',
        json={'name': 'ds-a', 'adapter_type': 'prometheus', 'adapter_url': 'http://a:9090'},
    )
    await client.post(
        '/datasources',
        json={'name': 'ds-b', 'adapter_type': 'prometheus', 'adapter_url': 'http://b:9090'},
    )
    response = await client.patch('/datasources/ds-b', json={'name': 'ds-a'})
    assert response.status_code == 409


async def test_asset_create_with_heatmap_config(client: AsyncClient) -> None:
    """Asset can be created with heatmap_config."""
    await client.post('/asset-types', json={'name': 'vm'})
    config = {'columns': 30, 'cell_size': 'medium'}
    response = await client.post(
        '/assets',
        json={'name': 'heatmap-asset', 'type_name': 'vm', 'heatmap_config': config},
    )
    assert response.status_code == 201
    assert response.json()['heatmap_config'] == config


async def test_asset_type_update_is_default(client: AsyncClient) -> None:
    """AssetType is_default can be set via PATCH."""
    await client.post('/asset-types', json={'name': 'custom-type'})
    response = await client.patch('/asset-types/custom-type', json={'is_default': True})
    assert response.status_code == 200
    assert response.json()['is_default'] is True
