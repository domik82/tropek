"""Tests for TropekClient — one test per method covering URL, deserialization, and request body."""

import httpx
import pytest
import respx
from tropek_client import TropekClient
from tropek_client.exceptions import TropekNotFoundError
from tropek_client.models import (
    AddMemberRequest,
    AnnotationCategoryCreate,
    AnnotationCreate,
    AnnotationRead,
    AssetCreate,
    AssetGroupCreate,
    AssetGroupRead,
    AssetRead,
    AssetTypeCreate,
    AssetTypeRead,
    ConfigurationRead,
    DataSourceCreate,
    DataSourceRead,
    EvaluateBatchRequest,
    EvaluateBatchResponse,
    EvaluateSingleRequest,
    EvaluateSingleResponse,
    EvaluationDetail,
    EvaluationSummary,
    GroupedMetricHeatmapResponse,
    MetaSnapshotCreate,
    MetaSnapshotCreated,
    PagedResponse,
    SLIDefinitionCreate,
    SLIDefinitionRead,
    SLODefinitionCreate,
    SLODefinitionRead,
    SLOValidateRequest,
    SLOValidationResult,
    TimelineResponse,
    TrendPoint,
)

BASE_URL = 'http://test-api:8080'

_UUID = '00000000-0000-0000-0000-000000000001'
_UUID2 = '00000000-0000-0000-0000-000000000002'
_TS = '2026-03-01T00:00:00Z'

_ASSET_JSON = {
    'id': _UUID,
    'name': 'vm-01',
    'display_name': 'VM 01',
    'type_name': 'vm',
    'tags': {},
    'variables': {},
    'created_at': _TS,
    'updated_at': _TS,
}

_ASSET_TYPE_JSON = {
    'id': _UUID,
    'name': 'vm',
    'is_default': True,
    'asset_count': 5,
}

_ASSET_GROUP_JSON = {
    'id': _UUID,
    'name': 'prod-group',
    'display_name': None,
    'description': None,
    'members': [],
    'subgroups': [],
    'created_at': _TS,
    'updated_at': _TS,
}

_DATASOURCE_JSON = {
    'id': _UUID,
    'name': 'prometheus',
    'adapter_type': 'prometheus',
    'adapter_url': 'http://prom:9090',
    'tags': {},
    'created_at': _TS,
    'updated_at': _TS,
}

_SLI_JSON = {
    'id': _UUID,
    'name': 'response-time',
    'adapter_type': 'prometheus',
    'version': 1,
    'comparable_from_version': 1,
    'indicators': {'response_time_p95': 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))'},
    'tags': {},
    'mode': 'raw',
    'active': True,
    'created_at': _TS,
}

_SLO_JSON = {
    'id': _UUID,
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
    'created_at': _TS,
}

_EVALUATION_SUMMARY_JSON = {
    'id': _UUID,
    'evaluation_id': _UUID2,
    'evaluation_name': 'nightly',
    'status': 'succeeded',
    'result': 'pass',
    'score': 95.0,
    'period_start': '2026-03-01T00:00:00Z',
    'period_end': '2026-03-01T01:00:00Z',
    'slo_name': 'my-slo',
    'slo_version': 1,
    'sli_name': 'response-time',
    'sli_version': 1,
    'data_source_name': 'prometheus',
    'ingestion_mode': 'live',
    'adapter_used': 'prometheus',
    'invalidated': False,
    'asset_snapshot': {'name': 'vm-01'},
    'variables': {},
    'created_at': _TS,
}

_ANNOTATION_CATEGORY_JSON = {
    'id': _UUID,
    'name': 'deployment',
    'label': 'Deployment',
    'color': 'green',
    'show_on_graph': True,
    'is_system': False,
    'created_at': _TS,
}

_ANNOTATION_JSON = {
    'id': _UUID,
    'content': 'Deployed v1.2',
    'author': 'alice',
    'category_id': _UUID,
    'category': _ANNOTATION_CATEGORY_JSON,
    'tags': {},
    'created_at': _TS,
}


@pytest.fixture
def client():
    return TropekClient(base_url=BASE_URL)


class TestAssetTypes:
    @respx.mock
    def test_list(self, client):
        respx.get(f'{BASE_URL}/asset-types').mock(
            return_value=httpx.Response(200, json={'items': [_ASSET_TYPE_JSON], 'total': 1})
        )
        result = client.asset_types.list()
        assert isinstance(result, PagedResponse)
        assert result.total == 1
        assert isinstance(result.items[0], AssetTypeRead)
        assert result.items[0].name == 'vm'

    @respx.mock
    def test_create(self, client):
        route = respx.post(f'{BASE_URL}/asset-types').mock(return_value=httpx.Response(201, json=_ASSET_TYPE_JSON))
        result = client.asset_types.create(AssetTypeCreate(name='vm'))
        assert isinstance(result, AssetTypeRead)
        assert result.name == 'vm'
        assert b'"name":"vm"' in route.calls[0].request.content


class TestAssets:
    @respx.mock
    def test_list(self, client):
        respx.get(f'{BASE_URL}/assets').mock(
            return_value=httpx.Response(200, json={'items': [_ASSET_JSON], 'total': 1})
        )
        result = client.assets.list()
        assert isinstance(result, PagedResponse)
        assert result.total == 1
        assert isinstance(result.items[0], AssetRead)
        assert result.items[0].name == 'vm-01'

    @respx.mock
    def test_create(self, client):
        route = respx.post(f'{BASE_URL}/assets').mock(return_value=httpx.Response(201, json=_ASSET_JSON))
        result = client.assets.create(AssetCreate(name='vm-01', type_name='vm'))
        assert isinstance(result, AssetRead)
        assert result.name == 'vm-01'
        assert b'"name":"vm-01"' in route.calls[0].request.content
        assert b'"type_name":"vm"' in route.calls[0].request.content

    @respx.mock
    def test_get(self, client):
        respx.get(f'{BASE_URL}/assets/vm-01').mock(return_value=httpx.Response(200, json=_ASSET_JSON))
        result = client.assets.get('vm-01')
        assert isinstance(result, AssetRead)
        assert result.name == 'vm-01'

    @respx.mock
    def test_delete(self, client):
        route = respx.delete(f'{BASE_URL}/assets/vm-01').mock(return_value=httpx.Response(204))
        client.assets.delete('vm-01')
        assert route.called


class TestAssetGroups:
    @respx.mock
    def test_list(self, client):
        respx.get(f'{BASE_URL}/asset-groups').mock(
            return_value=httpx.Response(200, json={'items': [_ASSET_GROUP_JSON], 'total': 1})
        )
        result = client.asset_groups.list()
        assert isinstance(result, PagedResponse)
        assert result.total == 1
        assert isinstance(result.items[0], AssetGroupRead)

    @respx.mock
    def test_create(self, client):
        route = respx.post(f'{BASE_URL}/asset-groups').mock(return_value=httpx.Response(201, json=_ASSET_GROUP_JSON))
        result = client.asset_groups.create(AssetGroupCreate(name='prod-group'))
        assert isinstance(result, AssetGroupRead)
        assert b'"name":"prod-group"' in route.calls[0].request.content

    @respx.mock
    def test_add_member(self, client):
        route = respx.post(f'{BASE_URL}/asset-groups/prod-group/members').mock(
            return_value=httpx.Response(200, json=_ASSET_GROUP_JSON)
        )
        result = client.asset_groups.add_member(
            'prod-group',
            AddMemberRequest(asset_id=_UUID),
        )
        assert isinstance(result, AssetGroupRead)
        assert route.called


class TestDataSources:
    @respx.mock
    def test_list(self, client):
        respx.get(f'{BASE_URL}/datasources').mock(
            return_value=httpx.Response(200, json={'items': [_DATASOURCE_JSON], 'total': 1})
        )
        result = client.datasources.list()
        assert isinstance(result, PagedResponse)
        assert isinstance(result.items[0], DataSourceRead)
        assert result.items[0].adapter_type == 'prometheus'

    @respx.mock
    def test_create(self, client):
        route = respx.post(f'{BASE_URL}/datasources').mock(return_value=httpx.Response(201, json=_DATASOURCE_JSON))
        result = client.datasources.create(
            DataSourceCreate(
                name='prometheus',
                adapter_type='prometheus',
                adapter_url='http://prom:9090',
            )
        )
        assert isinstance(result, DataSourceRead)
        assert b'"name":"prometheus"' in route.calls[0].request.content


class TestSLIs:
    @respx.mock
    def test_list(self, client):
        respx.get(f'{BASE_URL}/sli-definitions').mock(
            return_value=httpx.Response(200, json={'items': [_SLI_JSON], 'total': 1})
        )
        result = client.slis.list()
        assert isinstance(result, PagedResponse)
        assert isinstance(result.items[0], SLIDefinitionRead)
        assert result.items[0].name == 'response-time'

    @respx.mock
    def test_create(self, client):
        route = respx.post(f'{BASE_URL}/sli-definitions').mock(return_value=httpx.Response(201, json=_SLI_JSON))
        result = client.slis.create(SLIDefinitionCreate(name='response-time', adapter_type='prometheus'))
        assert isinstance(result, SLIDefinitionRead)
        assert b'"name":"response-time"' in route.calls[0].request.content


class TestSLOs:
    @respx.mock
    def test_list(self, client):
        respx.get(f'{BASE_URL}/slo-definitions').mock(
            return_value=httpx.Response(200, json={'items': [_SLO_JSON], 'total': 1})
        )
        result = client.slos.list()
        assert isinstance(result, PagedResponse)
        assert isinstance(result.items[0], SLODefinitionRead)
        assert result.items[0].name == 'my-slo'

    @respx.mock
    def test_create(self, client):
        route = respx.post(f'{BASE_URL}/slo-definitions').mock(return_value=httpx.Response(201, json=_SLO_JSON))
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


class TestEvaluations:
    @respx.mock
    def test_list(self, client):
        respx.get(f'{BASE_URL}/evaluations').mock(
            return_value=httpx.Response(200, json={'items': [_EVALUATION_SUMMARY_JSON], 'total': 1})
        )
        result = client.evaluations.list()
        assert isinstance(result, PagedResponse)
        assert isinstance(result.items[0], EvaluationSummary)
        assert result.items[0].evaluation_name == 'nightly'

    @respx.mock
    def test_get(self, client):
        eval_detail = {
            **_EVALUATION_SUMMARY_JSON,
            'invalidation_note': None,
            'annotations': [],
            'indicator_results': [],
        }
        respx.get(f'{BASE_URL}/evaluation/{_UUID}').mock(return_value=httpx.Response(200, json=eval_detail))
        result = client.evaluations.get(_UUID)
        assert isinstance(result, EvaluationDetail)
        assert str(result.id) == _UUID

    @respx.mock
    def test_trigger(self, client):
        route = respx.post(f'{BASE_URL}/evaluations').mock(
            return_value=httpx.Response(
                202,
                json={'evaluation_id': _UUID, 'slo_evaluation_ids': [_UUID2]},
            )
        )
        result = client.evaluations.trigger(
            EvaluateSingleRequest(
                asset_name='vm-01',
                eval_name='nightly',
                period_start='2026-03-01T00:00:00Z',
                period_end='2026-03-01T01:00:00Z',
            )
        )
        assert isinstance(result, EvaluateSingleResponse)
        assert b'"asset_name":"vm-01"' in route.calls[0].request.content

    @respx.mock
    def test_trigger_batch(self, client):
        route = respx.post(f'{BASE_URL}/evaluations/batch').mock(
            return_value=httpx.Response(
                202,
                json={'evaluation_ids': [_UUID], 'slo_evaluation_ids': [_UUID2]},
            )
        )
        result = client.evaluations.trigger_batch(
            EvaluateBatchRequest(
                mode='multi_asset',
                eval_name='nightly',
                asset_names=['vm-01', 'vm-02'],
                period_start='2026-03-01T00:00:00Z',
                period_end='2026-03-01T01:00:00Z',
            )
        )
        assert isinstance(result, EvaluateBatchResponse)
        assert b'"eval_name":"nightly"' in route.calls[0].request.content


class TestAnnotations:
    @respx.mock
    def test_list(self, client):
        respx.get(f'{BASE_URL}/evaluation/{_UUID}/annotations').mock(
            return_value=httpx.Response(200, json=[_ANNOTATION_JSON])
        )
        result = client.annotations.list(_UUID)
        assert len(result) == 1
        assert isinstance(result[0], AnnotationRead)
        assert result[0].content == 'Deployed v1.2'

    @respx.mock
    def test_create(self, client):
        route = respx.post(f'{BASE_URL}/evaluation/{_UUID}/annotations').mock(
            return_value=httpx.Response(201, json=_ANNOTATION_JSON)
        )
        result = client.annotations.create(
            _UUID,
            AnnotationCreate(content='Deployed v1.2', category_id=_UUID),
        )
        assert isinstance(result, AnnotationRead)
        assert b'"content":"Deployed v1.2"' in route.calls[0].request.content


class TestAnnotationCategories:
    @respx.mock
    def test_list(self, client):
        respx.get(f'{BASE_URL}/note-categories').mock(
            return_value=httpx.Response(200, json=[_ANNOTATION_CATEGORY_JSON])
        )
        result = client.annotation_categories.list()
        assert len(result) == 1
        assert result[0].name == 'deployment'

    @respx.mock
    def test_create(self, client):
        route = respx.post(f'{BASE_URL}/note-categories').mock(
            return_value=httpx.Response(201, json=_ANNOTATION_CATEGORY_JSON)
        )
        result = client.annotation_categories.create(
            AnnotationCategoryCreate(name='deployment', label='Deployment', color='green')
        )
        assert result.name == 'deployment'
        assert b'"name":"deployment"' in route.calls[0].request.content

    @respx.mock
    def test_delete(self, client):
        respx.delete(f'{BASE_URL}/note-categories/{_UUID}').mock(return_value=httpx.Response(204))
        client.annotation_categories.delete(_UUID)


class TestTrend:
    @respx.mock
    def test_by_eval(self, client):
        trend_point = {
            'timestamp': _TS,
            'value': 150.5,
            'score': 1.0,
            'eval_id': _UUID,
            'result': 'pass',
        }
        respx.get(f'{BASE_URL}/evaluation/{_UUID}/trend').mock(return_value=httpx.Response(200, json=[trend_point]))
        result = client.trend.by_eval(_UUID, metric='response_time', from_='2026-03-01T00:00:00Z')
        assert len(result) == 1
        assert isinstance(result[0], TrendPoint)
        assert result[0].value == 150.5


class TestHeatmap:
    @respx.mock
    def test_grouped(self, client):
        heatmap_response = {
            'asset_name': 'vm-01',
            'columns': [],
            'groups': [],
            'composite': [],
        }
        respx.get(f'{BASE_URL}/assets/vm-01/heatmap').mock(return_value=httpx.Response(200, json=heatmap_response))
        result = client.heatmap.grouped('vm-01')
        assert isinstance(result, GroupedMetricHeatmapResponse)
        assert result.asset_name == 'vm-01'
        assert result.groups == []


class TestTimeline:
    @respx.mock
    def test_get(self, client):
        timeline_response = {'groups': [], 'items': []}
        respx.get(f'{BASE_URL}/assets/vm-01/timeline').mock(return_value=httpx.Response(200, json=timeline_response))
        result = client.timeline.get('vm-01', from_='2026-03-01T00:00:00Z', to='2026-03-01T01:00:00Z')
        assert isinstance(result, TimelineResponse)
        assert result.groups == []
        assert result.items == []


class TestConfiguration:
    @respx.mock
    def test_list(self, client):
        config_json = {
            'name': 'max_comparison_results',
            'value': '5',
            'value_type': 'int',
            'description': 'Max results',
        }
        respx.get(f'{BASE_URL}/config').mock(return_value=httpx.Response(200, json=[config_json]))
        result = client.configuration.list()
        assert len(result) == 1
        assert isinstance(result[0], ConfigurationRead)
        assert result[0].name == 'max_comparison_results'

    @respx.mock
    def test_get(self, client):
        config_json = {
            'name': 'max_comparison_results',
            'value': '5',
            'value_type': 'int',
            'description': 'Max results',
        }
        respx.get(f'{BASE_URL}/config/max_comparison_results').mock(return_value=httpx.Response(200, json=config_json))
        result = client.configuration.get('max_comparison_results')
        assert isinstance(result, ConfigurationRead)
        assert result.value == '5'

    @respx.mock
    def test_update(self, client):
        config_json = {
            'name': 'change_point.window_size',
            'value': '50',
            'value_type': 'int',
            'description': 'sliding window length',
        }
        route = respx.put(f'{BASE_URL}/configuration/change_point.window_size').mock(
            return_value=httpx.Response(200, json=config_json)
        )
        result = client.configuration.update('change_point.window_size', '50')
        assert isinstance(result, ConfigurationRead)
        assert result.value == '50'
        assert b'"value":"50"' in route.calls[0].request.content


class TestMeta:
    @respx.mock
    def test_create_snapshot(self, client):
        route = respx.post(f'{BASE_URL}/assets/vm-01/meta/snapshots').mock(
            return_value=httpx.Response(201, json={'snapshot_id': _UUID})
        )
        result = client.meta.create_snapshot(
            'vm-01', MetaSnapshotCreate(source='ci', observed_at='2026-01-01T00:00:00Z')
        )
        assert isinstance(result, MetaSnapshotCreated)
        assert route.called


class TestHealth:
    @respx.mock
    def test_health(self, client):
        respx.get(f'{BASE_URL}/health').mock(return_value=httpx.Response(200, json={'status': 'ok'}))
        result = client.health()
        assert result == {'status': 'ok'}


class TestNotFound:
    @respx.mock
    def test_get_missing_asset_raises_not_found(self, client):
        respx.get(f'{BASE_URL}/assets/missing').mock(
            return_value=httpx.Response(404, json={'detail': "asset 'missing' not found"})
        )
        with pytest.raises(TropekNotFoundError) as exc_info:
            client.assets.get('missing')
        assert exc_info.value.entity == 'asset'
        assert exc_info.value.name == 'missing'
