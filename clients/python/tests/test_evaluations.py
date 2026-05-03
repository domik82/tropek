"""Tests for evaluation, annotation, annotation category, and trend endpoints."""

import httpx
import respx
from tropek_client.models import (
    AnnotationCategoryCreate,
    AnnotationCategoryRead,
    AnnotationCreate,
    AnnotationRead,
    EvaluateBatchRequest,
    EvaluateBatchResponse,
    EvaluateSingleRequest,
    EvaluateSingleResponse,
    EvaluationDetail,
    EvaluationNameEntry,
    EvaluationSummary,
    PagedResponse,
    TrendPoint,
)

from .conftest import BASE_URL, TIMESTAMP, UUID1, UUID2, load_fixture

ANNOTATION_CATEGORY_JSON = {
    'id': UUID1,
    'name': 'deployment',
    'label': 'Deployment',
    'color': 'green',
    'show_on_graph': True,
    'is_system': False,
    'created_at': TIMESTAMP,
}

ANNOTATION_JSON = {
    'id': UUID1,
    'content': 'Deployed v1.2',
    'author': 'alice',
    'category_id': UUID1,
    'category': ANNOTATION_CATEGORY_JSON,
    'tags': {},
    'created_at': TIMESTAMP,
}

EVALUATION_SUMMARY_JSON = {
    'id': UUID1,
    'evaluation_id': UUID2,
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
    'created_at': TIMESTAMP,
}


class TestEvaluations:
    @respx.mock
    def test_list(self, client):
        respx.get(f'{BASE_URL}/evaluations').mock(
            return_value=httpx.Response(200, json={'items': [EVALUATION_SUMMARY_JSON], 'total': 1})
        )
        result = client.evaluations.list()
        assert isinstance(result, PagedResponse)
        assert isinstance(result.items[0], EvaluationSummary)
        assert result.items[0].evaluation_name == 'nightly'

    @respx.mock
    def test_get(self, client):
        eval_detail = {
            **EVALUATION_SUMMARY_JSON,
            'invalidation_note': None,
            'annotations': [],
            'indicator_results': [],
        }
        respx.get(f'{BASE_URL}/evaluation/{UUID1}').mock(return_value=httpx.Response(200, json=eval_detail))
        result = client.evaluations.get(UUID1)
        assert isinstance(result, EvaluationDetail)
        assert str(result.id) == UUID1

    @respx.mock
    def test_trigger(self, client):
        route = respx.post(f'{BASE_URL}/evaluations').mock(
            return_value=httpx.Response(
                202,
                json={'evaluation_id': UUID1, 'slo_evaluation_ids': [UUID2]},
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
                json={'evaluation_ids': [UUID1], 'slo_evaluation_ids': [UUID2]},
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
        respx.get(f'{BASE_URL}/evaluation/{UUID1}/annotations').mock(
            return_value=httpx.Response(200, json=[ANNOTATION_JSON])
        )
        result = client.annotations.list(UUID1)
        assert len(result) == 1
        assert isinstance(result[0], AnnotationRead)
        assert result[0].content == 'Deployed v1.2'

    @respx.mock
    def test_create(self, client):
        route = respx.post(f'{BASE_URL}/evaluation/{UUID1}/annotations').mock(
            return_value=httpx.Response(201, json=ANNOTATION_JSON)
        )
        result = client.annotations.create(
            UUID1,
            AnnotationCreate(content='Deployed v1.2', category_id=UUID1),
        )
        assert isinstance(result, AnnotationRead)
        assert b'"content":"Deployed v1.2"' in route.calls[0].request.content


class TestAnnotationCategories:
    @respx.mock
    def test_list(self, client):
        respx.get(f'{BASE_URL}/note-categories').mock(return_value=httpx.Response(200, json=[ANNOTATION_CATEGORY_JSON]))
        result = client.annotation_categories.list()
        assert len(result) == 1
        assert result[0].name == 'deployment'

    @respx.mock
    def test_create(self, client):
        route = respx.post(f'{BASE_URL}/note-categories').mock(
            return_value=httpx.Response(201, json=ANNOTATION_CATEGORY_JSON)
        )
        result = client.annotation_categories.create(
            AnnotationCategoryCreate(name='deployment', label='Deployment', color='green')
        )
        assert result.name == 'deployment'
        assert b'"name":"deployment"' in route.calls[0].request.content

    @respx.mock
    def test_delete(self, client):
        respx.delete(f'{BASE_URL}/note-categories/{UUID1}').mock(return_value=httpx.Response(204))
        client.annotation_categories.delete(UUID1)


class TestTrend:
    @respx.mock
    def test_by_eval(self, client):
        trend_point = {
            'timestamp': TIMESTAMP,
            'value': 150.5,
            'score': 1.0,
            'eval_id': UUID1,
            'result': 'pass',
        }
        respx.get(f'{BASE_URL}/evaluation/{UUID1}/trend').mock(return_value=httpx.Response(200, json=[trend_point]))
        result = client.trend.by_eval(UUID1, metric='response_time', from_='2026-03-01T00:00:00Z')
        assert len(result) == 1
        assert isinstance(result[0], TrendPoint)
        assert result[0].value == 150.5


class TestEvaluationFixtures:
    @respx.mock
    def test_list(self, client):
        data = load_fixture('evaluation_list')
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
        data = load_fixture('evaluation_detail_pass')
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
        data = load_fixture('evaluation_detail_fail')
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
        data = load_fixture('evaluation_detail_override')
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
        data = load_fixture('evaluation_detail_baseline')
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
        data = load_fixture('evaluation_detail_invalidated')
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
        data = load_fixture('evaluation_names')
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
        data = load_fixture('annotation_list')
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
        data = load_fixture('note_category_list')
        respx.get(f'{BASE_URL}/note-categories').mock(return_value=httpx.Response(200, json=data))
        result = client.annotation_categories.list()
        assert isinstance(result, list)
        assert all(isinstance(item, AnnotationCategoryRead) for item in result)
