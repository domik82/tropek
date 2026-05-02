"""Fixture-based client tests using captured API responses.

These tests use real API responses saved as JSON fixtures (by capture_responses.py)
to verify the client correctly deserializes every response shape the API produces.

To refresh fixtures:
    1. Start the dev environment: just dev
    2. Run capture: uv run --directory clients/python python ../../dev_setup/stages/capture_responses.py
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from tropek_client import TropekClient
from tropek_client.models import (
    AnnotationCategoryRead,
    AnnotationRead,
    AssetGroupRead,
    AssetGroupTreeResponse,
    AssetRead,
    AssetTypeRead,
    ConfigurationRead,
    DataSourceRead,
    EvaluationDetail,
    EvaluationNameEntry,
    EvaluationSummary,
    GroupedMetricHeatmapResponse,
    PagedResponse,
    SLIDefinitionRead,
    SLOAssignmentRead,
    SLODefinitionRead,
    SLOGroupRead,
    TagKeyCount,
    TimelineResponse,
)

BASE_URL = 'http://fixture-test:8080'
FIXTURES_DIR = Path(__file__).parent / 'fixtures'


def _load(name: str) -> dict | list:
    path = FIXTURES_DIR / f'{name}.json'
    if not path.exists():
        pytest.skip(f'fixture {name}.json not found — run capture_responses.py first')
    return json.loads(path.read_text())


@pytest.fixture
def client():
    with TropekClient(BASE_URL) as tropek_client:
        yield tropek_client


class TestAssetTypeFixtures:
    @respx.mock
    def test_list(self, client):
        data = _load('asset_type_list')
        respx.get(f'{BASE_URL}/asset-types').mock(return_value=httpx.Response(200, json=data))
        result = client.asset_types.list()
        assert isinstance(result, PagedResponse)
        assert len(result.items) > 0
        assert all(isinstance(item, AssetTypeRead) for item in result.items)
        first = result.items[0]
        assert first.name
        assert first.id


class TestAssetFixtures:
    @respx.mock
    def test_get(self, client):
        data = _load('asset_get')
        respx.get(f'{BASE_URL}/assets/checkout-api').mock(return_value=httpx.Response(200, json=data))
        result = client.assets.get('checkout-api')
        assert isinstance(result, AssetRead)
        assert result.name == 'checkout-api'
        assert result.id
        assert result.type_name

    @respx.mock
    def test_list(self, client):
        data = _load('asset_list')
        respx.get(f'{BASE_URL}/assets').mock(return_value=httpx.Response(200, json=data))
        result = client.assets.list()
        assert isinstance(result, PagedResponse)
        assert len(result.items) > 0
        assert all(isinstance(item, AssetRead) for item in result.items)

    @respx.mock
    def test_tag_keys(self, client):
        data = _load('asset_tag_keys')
        respx.get(f'{BASE_URL}/assets/tag-keys').mock(return_value=httpx.Response(200, json=data))
        result = client.assets.tag_keys()
        assert isinstance(result, list)
        if result:
            assert all(isinstance(item, TagKeyCount) for item in result)


class TestAssetGroupFixtures:
    @respx.mock
    def test_get(self, client):
        data = _load('asset_group_get')
        respx.get(f'{BASE_URL}/asset-groups/core-services').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.asset_groups.get('core-services')
        assert isinstance(result, AssetGroupRead)
        assert result.name == 'core-services'
        assert result.members is not None

    @respx.mock
    def test_tree(self, client):
        data = _load('asset_group_tree')
        respx.get(f'{BASE_URL}/asset-groups/tree').mock(return_value=httpx.Response(200, json=data))
        result = client.asset_groups.tree()
        assert isinstance(result, AssetGroupTreeResponse)


class TestDataSourceFixtures:
    @respx.mock
    def test_get(self, client):
        data = _load('datasource_get')
        respx.get(f'{BASE_URL}/datasources/mock-dc-b').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.datasources.get('mock-dc-b')
        assert isinstance(result, DataSourceRead)
        assert result.name == 'mock-dc-b'
        assert result.adapter_type


class TestSLIFixtures:
    @respx.mock
    def test_get(self, client):
        data = _load('sli_get')
        respx.get(f'{BASE_URL}/sli-definitions/http-service-sli').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.slis.get('http-service-sli')
        assert isinstance(result, SLIDefinitionRead)
        assert result.name == 'http-service-sli'

    @respx.mock
    def test_versions(self, client):
        data = _load('sli_versions')
        respx.get(f'{BASE_URL}/sli-definitions/http-service-sli/versions').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.slis.versions('http-service-sli')
        assert isinstance(result, list)
        assert all(isinstance(item, SLIDefinitionRead) for item in result)


class TestSLOFixtures:
    @respx.mock
    def test_get(self, client):
        data = _load('slo_get')
        respx.get(f'{BASE_URL}/slo-definitions/http-availability-slo').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.slos.get('http-availability-slo')
        assert isinstance(result, SLODefinitionRead)
        assert result.name == 'http-availability-slo'
        assert result.objectives

    @respx.mock
    def test_versions(self, client):
        data = _load('slo_versions')
        respx.get(f'{BASE_URL}/slo-definitions/http-availability-slo/versions').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.slos.versions('http-availability-slo')
        assert isinstance(result, list)
        assert all(isinstance(item, SLODefinitionRead) for item in result)


class TestSLOAssignmentFixtures:
    @respx.mock
    def test_list_for_asset(self, client):
        data = _load('slo_assignment_list_for_asset')
        respx.get(f'{BASE_URL}/assets/checkout-api/slo-assignments').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.slo_assignments.list_for_asset('checkout-api')
        assert isinstance(result, list)
        assert all(isinstance(item, SLOAssignmentRead) for item in result)


class TestSLOGroupFixtures:
    @respx.mock
    def test_get(self, client):
        data = _load('slo_group_get')
        respx.get(f'{BASE_URL}/slo-groups/app-x-plugins').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.slo_groups.get('app-x-plugins')
        assert isinstance(result, SLOGroupRead)
        assert result.name == 'app-x-plugins'

    @respx.mock
    def test_list(self, client):
        data = _load('slo_group_list')
        respx.get(f'{BASE_URL}/slo-groups').mock(return_value=httpx.Response(200, json=data))
        result = client.slo_groups.list()
        assert isinstance(result, PagedResponse)
        assert len(result.items) > 0


class TestEvaluationFixtures:
    @respx.mock
    def test_list(self, client):
        data = _load('evaluation_list')
        respx.get(f'{BASE_URL}/evaluations').mock(return_value=httpx.Response(200, json=data))
        result = client.evaluations.list(asset_name='checkout-api')
        assert isinstance(result, PagedResponse)
        assert len(result.items) > 0
        assert all(isinstance(item, EvaluationSummary) for item in result.items)
        first = result.items[0]
        assert first.id
        assert first.evaluation_name
        assert first.status

    @respx.mock
    def test_detail_pass(self, client):
        data = _load('evaluation_detail_pass')
        eval_id = data['id']
        respx.get(f'{BASE_URL}/evaluation/{eval_id}').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.evaluations.get(eval_id)
        assert isinstance(result, EvaluationDetail)
        assert result.result == 'pass'
        assert result.indicator_results is not None
        assert len(result.indicator_results) > 0
        assert not result.invalidated

    @respx.mock
    def test_detail_fail(self, client):
        data = _load('evaluation_detail_fail')
        eval_id = data['id']
        respx.get(f'{BASE_URL}/evaluation/{eval_id}').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.evaluations.get(eval_id)
        assert isinstance(result, EvaluationDetail)
        assert result.result == 'fail'
        assert result.indicator_results is not None

    @respx.mock
    def test_detail_override(self, client):
        data = _load('evaluation_detail_override')
        eval_id = data['id']
        respx.get(f'{BASE_URL}/evaluation/{eval_id}').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.evaluations.get(eval_id)
        assert isinstance(result, EvaluationDetail)
        assert result.override_reason is not None
        assert result.override_author is not None
        assert result.original_result is not None

    @respx.mock
    def test_detail_baseline(self, client):
        data = _load('evaluation_detail_baseline')
        eval_id = data['id']
        respx.get(f'{BASE_URL}/evaluation/{eval_id}').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.evaluations.get(eval_id)
        assert isinstance(result, EvaluationDetail)
        assert result.baseline_pinned_at is not None
        assert result.baseline_pin_reason is not None

    @respx.mock
    def test_detail_invalidated(self, client):
        data = _load('evaluation_detail_invalidated')
        eval_id = data['id']
        respx.get(f'{BASE_URL}/evaluation/{eval_id}').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.evaluations.get(eval_id)
        assert isinstance(result, EvaluationDetail)
        assert result.invalidated is True
        assert result.invalidation_note is not None

    @respx.mock
    def test_names(self, client):
        data = _load('evaluation_names')
        respx.get(f'{BASE_URL}/evaluations/names').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.evaluations.names(asset_name='checkout-api')
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(item, EvaluationNameEntry) for item in result)
        assert result[0].name
        assert result[0].count > 0


class TestAnnotationFixtures:
    @respx.mock
    def test_list(self, client):
        data = _load('annotation_list')
        eval_id = 'fixture-eval-id'
        respx.get(f'{BASE_URL}/evaluation/{eval_id}/annotations').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.annotations.list(eval_id)
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(item, AnnotationRead) for item in result)
        first = result[0]
        assert first.content
        assert first.id


class TestAnnotationCategoryFixtures:
    @respx.mock
    def test_list(self, client):
        data = _load('note_category_list')
        respx.get(f'{BASE_URL}/note-categories').mock(return_value=httpx.Response(200, json=data))
        result = client.annotation_categories.list()
        assert isinstance(result, list)
        assert all(isinstance(item, AnnotationCategoryRead) for item in result)


class TestHeatmapFixtures:
    @respx.mock
    def test_grouped(self, client):
        data = _load('heatmap_grouped')
        respx.get(f'{BASE_URL}/evaluations/heatmap', params={'asset_name': 'checkout-api'}).mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.heatmap.grouped('checkout-api')
        assert isinstance(result, GroupedMetricHeatmapResponse)
        assert result.asset_name == 'checkout-api'


class TestTimelineFixtures:
    @respx.mock
    def test_get(self, client):
        data = _load('timeline_get')
        asset_id = 'fixture-asset-id'
        respx.get(
            f'{BASE_URL}/assets/{asset_id}/meta/timeline',
            params={'from': '2026-02-01T00:00:00Z', 'to': '2026-04-01T00:00:00Z'},
        ).mock(return_value=httpx.Response(200, json=data))
        result = client.timeline.get(
            asset_id,
            from_='2026-02-01T00:00:00Z',
            to='2026-04-01T00:00:00Z',
        )
        assert isinstance(result, TimelineResponse)


class TestConfigurationFixtures:
    @respx.mock
    def test_list(self, client):
        data = _load('configuration_list')
        respx.get(f'{BASE_URL}/configuration').mock(return_value=httpx.Response(200, json=data))
        result = client.configuration.list()
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(item, ConfigurationRead) for item in result)

    @respx.mock
    def test_get(self, client):
        data = _load('configuration_get')
        name = data['name']
        respx.get(f'{BASE_URL}/configuration/{name}').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.configuration.get(name)
        assert isinstance(result, ConfigurationRead)
        assert result.name == name
