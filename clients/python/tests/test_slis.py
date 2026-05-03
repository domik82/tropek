"""Tests for SLI definition endpoints."""

import httpx
import respx
from tropek_client.models import PagedResponse, SLIDefinitionCreate, SLIDefinitionRead

from .conftest import BASE_URL, TIMESTAMP, UUID1, UUID2, load_fixture

SLI_JSON = {
    'id': UUID1,
    'name': 'response-time',
    'adapter_type': 'prometheus',
    'version': 1,
    'comparable_from_version': 1,
    'indicators': {'response_time_p95': 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))'},
    'tags': {},
    'mode': 'raw',
    'active': True,
    'created_at': TIMESTAMP,
}


class TestSLIs:
    @respx.mock
    def test_list(self, client):
        respx.get(f'{BASE_URL}/sli-definitions').mock(
            return_value=httpx.Response(200, json={'items': [SLI_JSON], 'total': 1})
        )
        result = client.slis.list()
        assert isinstance(result, PagedResponse)
        assert isinstance(result.items[0], SLIDefinitionRead)
        assert result.items[0].name == 'response-time'

    @respx.mock
    def test_create(self, client):
        route = respx.post(f'{BASE_URL}/sli-definitions').mock(return_value=httpx.Response(201, json=SLI_JSON))
        result = client.slis.create(SLIDefinitionCreate(name='response-time', adapter_type='prometheus'))
        assert isinstance(result, SLIDefinitionRead)
        assert b'"name":"response-time"' in route.calls[0].request.content

    @respx.mock
    def test_new_version(self, client):
        current_sli = {
            **SLI_JSON,
            'display_name': 'Response Time P95',
            'notes': 'original notes',
            'author': 'alice',
        }
        created_sli = {**current_sli, 'version': 2, 'id': UUID2}

        respx.get(f'{BASE_URL}/sli-definitions/response-time').mock(return_value=httpx.Response(200, json=current_sli))
        route = respx.post(f'{BASE_URL}/sli-definitions').mock(return_value=httpx.Response(201, json=created_sli))

        result = client.slis.new_version(
            'response-time',
            indicators={'p99': 'new_query(rate(http_duration[5m]))'},
        )
        assert result.version == 2
        body = route.calls[0].request.content
        assert b'"p99"' in body
        assert b'"new_query' in body
        assert b'"response-time"' in body


class TestSLIFixtures:
    @respx.mock
    def test_get(self, client):
        data = load_fixture('sli_get')
        respx.get(f'{BASE_URL}/sli-definitions/http-service-sli').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.slis.get('http-service-sli')
        assert isinstance(result, SLIDefinitionRead)
        assert result.name == 'http-service-sli'

    @respx.mock
    def test_versions(self, client):
        data = load_fixture('sli_versions')
        respx.get(f'{BASE_URL}/sli-definitions/http-service-sli/versions').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.slis.versions('http-service-sli')
        assert isinstance(result, list)
        assert all(isinstance(item, SLIDefinitionRead) for item in result)
