"""Tests for SLO definition endpoints."""

import httpx
import respx
from tropek_client.models import (
    PagedResponse,
    SLOAssignmentRead,
    SLODefinitionCreate,
    SLODefinitionRead,
    SLOGroupRead,
    SLOValidateRequest,
    SLOValidationResult,
)

from .conftest import BASE_URL, TIMESTAMP, UUID1, UUID2, load_fixture

SLO_JSON = {
    'id': UUID1,
    'name': 'my-slo',
    'version': 1,
    'comparable_from_version': 1,
    'active': True,
    'objectives': [],
    'total_score_pass_threshold': 90.0,
    'total_score_warning_threshold': 75.0,
    'comparison': {},
    'tags': {},
    'variables': {},
    'kind': 'standard',
    'created_at': TIMESTAMP,
}


class TestSLOs:
    @respx.mock
    def test_list(self, client):
        respx.get(f'{BASE_URL}/slo-definitions').mock(
            return_value=httpx.Response(200, json={'items': [SLO_JSON], 'total': 1})
        )
        result = client.slos.list()
        assert isinstance(result, PagedResponse)
        assert isinstance(result.items[0], SLODefinitionRead)
        assert result.items[0].name == 'my-slo'

    @respx.mock
    def test_create(self, client):
        route = respx.post(f'{BASE_URL}/slo-definitions').mock(return_value=httpx.Response(201, json=SLO_JSON))
        result = client.slos.create(SLODefinitionCreate(name='my-slo', objectives=[]))
        assert isinstance(result, SLODefinitionRead)
        assert b'"name":"my-slo"' in route.calls[0].request.content

    @respx.mock
    def test_validate(self, client):
        respx.post(f'{BASE_URL}/slo-definitions/validate').mock(
            return_value=httpx.Response(200, json={'valid': True, 'errors': []})
        )
        result = client.slos.validate(SLOValidateRequest(objectives=[]))
        assert isinstance(result, SLOValidationResult)
        assert result.valid is True

    @respx.mock
    def test_new_version(self, client):
        current_slo = {
            **SLO_JSON,
            'display_name': 'My SLO',
            'notes': 'original',
            'author': 'alice',
            'objectives': [
                {
                    'sli': 'response_time_p95',
                    'display_name': 'P95 Latency',
                    'pass_threshold': ['<600'],
                    'warning_threshold': ['<800'],
                    'weight': 1,
                    'key_sli': False,
                    'sort_order': 0,
                },
            ],
        }
        created_slo = {**current_slo, 'version': 2, 'id': UUID2}

        respx.get(f'{BASE_URL}/slo-definitions/my-slo').mock(return_value=httpx.Response(200, json=current_slo))
        route = respx.post(f'{BASE_URL}/slo-definitions').mock(return_value=httpx.Response(201, json=created_slo))

        result = client.slos.new_version(
            'my-slo',
            total_score_pass_threshold=95.0,
        )
        assert result.version == 2
        body = route.calls[0].request.content
        assert b'"total_score_pass_threshold":95.0' in body
        assert b'"my-slo"' in body
        assert b'sort_order' not in body


class TestSLOFixtures:
    @respx.mock
    def test_get(self, client):
        data = load_fixture('slo_get')
        respx.get(f'{BASE_URL}/slo-definitions/http-availability-slo').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.slos.get('http-availability-slo')
        assert isinstance(result, SLODefinitionRead)
        assert result.name == 'http-availability-slo'
        assert result.objectives

    @respx.mock
    def test_versions(self, client):
        data = load_fixture('slo_versions')
        respx.get(f'{BASE_URL}/slo-definitions/http-availability-slo/versions').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.slos.versions('http-availability-slo')
        assert isinstance(result, list)
        assert all(isinstance(item, SLODefinitionRead) for item in result)


class TestSLOAssignmentFixtures:
    @respx.mock
    def test_list_for_asset(self, client):
        data = load_fixture('slo_assignment_list_for_asset')
        respx.get(f'{BASE_URL}/assets/checkout-api/slo-assignments').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.slo_assignments.list_for_asset('checkout-api')
        assert isinstance(result, list)
        assert all(isinstance(item, SLOAssignmentRead) for item in result)


class TestSLOGroupFixtures:
    @respx.mock
    def test_get(self, client):
        data = load_fixture('slo_group_get')
        respx.get(f'{BASE_URL}/slo-groups/app-x-plugins').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.slo_groups.get('app-x-plugins')
        assert isinstance(result, SLOGroupRead)
        assert result.name == 'app-x-plugins'

    @respx.mock
    def test_list(self, client):
        data = load_fixture('slo_group_list')
        respx.get(f'{BASE_URL}/slo-groups').mock(return_value=httpx.Response(200, json=data))
        result = client.slo_groups.list()
        assert isinstance(result, PagedResponse)
        assert len(result.items) > 0
