"""Tests for datasource endpoints."""

import httpx
import respx
from tropek_client.models import DataSourceCreate, DataSourceRead, PagedResponse

from .conftest import BASE_URL, TIMESTAMP, UUID1, load_fixture

DATASOURCE_JSON = {
    'id': UUID1,
    'name': 'prometheus',
    'adapter_type': 'prometheus',
    'adapter_url': 'http://prom:9090',
    'tags': {},
    'created_at': TIMESTAMP,
    'updated_at': TIMESTAMP,
}


class TestDataSources:
    @respx.mock
    def test_list(self, client):
        respx.get(f'{BASE_URL}/datasources').mock(
            return_value=httpx.Response(200, json={'items': [DATASOURCE_JSON], 'total': 1})
        )
        result = client.datasources.list()
        assert isinstance(result, PagedResponse)
        assert isinstance(result.items[0], DataSourceRead)
        assert result.items[0].adapter_type == 'prometheus'

    @respx.mock
    def test_create(self, client):
        route = respx.post(f'{BASE_URL}/datasources').mock(return_value=httpx.Response(201, json=DATASOURCE_JSON))
        result = client.datasources.create(
            DataSourceCreate(
                name='prometheus',
                adapter_type='prometheus',
                adapter_url='http://prom:9090',
            )
        )
        assert isinstance(result, DataSourceRead)
        assert b'"name":"prometheus"' in route.calls[0].request.content


class TestDataSourceFixtures:
    @respx.mock
    def test_get(self, client):
        data = load_fixture('datasource_get')
        respx.get(f'{BASE_URL}/datasources/mock-dc-b').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.datasources.get('mock-dc-b')
        assert isinstance(result, DataSourceRead)
        assert result.name == 'mock-dc-b'
        assert result.adapter_type
