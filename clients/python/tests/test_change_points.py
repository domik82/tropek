"""Tests for the change_points client resource."""

import httpx
import respx
from tropek_client.models import (
    BulkTriageRequest,
    ChangePointConfigInput,
    ChangePointConfigRead,
    ChangePointRead,
    TriageRequest,
)

from .conftest import BASE_URL, TIMESTAMP, UUID1, UUID2

CHANGE_POINT_JSON = {
    'id': UUID1,
    'asset_id': UUID2,
    'slo_name': 'perf-slo',
    'metric_name': 'response_time_p95',
    'period_start': TIMESTAMP,
    'period_end': None,
    'detector': 'e_divisive',
    'direction': 'regression',
    'change_relative_pct': 15.0,
    'change_absolute': 30.0,
    'pvalue': 0.001,
    'pre_segment_mean': 200.0,
    'post_segment_mean': 230.0,
    'post_segment_std': 12.5,
    'status': 'unprocessed',
    'triage_author': None,
    'triage_note': None,
    'triage_at': None,
    'linked_ticket': None,
    'found_by_evaluation_id': None,
    'created_at': TIMESTAMP,
    'updated_at': TIMESTAMP,
}

CONFIG_JSON = {
    'slo_objective_id': UUID1,
    'enabled': True,
    'higher_is_better': False,
    'window_size': 30,
    'max_pvalue': 0.001,
    'min_magnitude': 0.0,
    'min_sample_size': 10,
}


class TestChangePointsList:
    @respx.mock
    def test_list_returns_change_points(self, client):
        respx.get(f'{BASE_URL}/change-points').mock(return_value=httpx.Response(200, json=[CHANGE_POINT_JSON]))
        result = client.change_points.list()
        assert len(result) == 1
        assert isinstance(result[0], ChangePointRead)
        assert result[0].metric_name == 'response_time_p95'

    @respx.mock
    def test_list_sends_metric_name_filter(self, client):
        """The metric filter must go out as `metric_name` — the name the API declares."""
        route = respx.get(f'{BASE_URL}/change-points').mock(return_value=httpx.Response(200, json=[]))
        client.change_points.list(metric_name='errors_zero_origin_appear')
        sent_params = route.calls[0].request.url.params
        assert sent_params.get('metric_name') == 'errors_zero_origin_appear'
        assert 'metric' not in sent_params

    @respx.mock
    def test_list_sends_all_filters(self, client):
        route = respx.get(f'{BASE_URL}/change-points').mock(return_value=httpx.Response(200, json=[]))
        client.change_points.list(
            status='acknowledged',
            direction='improvement',
            asset_id=UUID2,
            slo_name='perf-slo',
            metric_name='response_time_p95',
            from_ts='2026-01-01T00:00:00Z',
            to_ts='2026-12-31T00:00:00Z',
            limit=10,
            offset=5,
        )
        sent_params = route.calls[0].request.url.params
        assert sent_params.get('status') == 'acknowledged'
        assert sent_params.get('direction') == 'improvement'
        assert sent_params.get('asset_id') == UUID2
        assert sent_params.get('slo_name') == 'perf-slo'
        assert sent_params.get('metric_name') == 'response_time_p95'
        assert sent_params.get('from_ts') == '2026-01-01T00:00:00Z'
        assert sent_params.get('to_ts') == '2026-12-31T00:00:00Z'
        assert sent_params.get('limit') == '10'
        assert sent_params.get('offset') == '5'

    @respx.mock
    def test_list_omits_unset_filters(self, client):
        route = respx.get(f'{BASE_URL}/change-points').mock(return_value=httpx.Response(200, json=[]))
        client.change_points.list(status='unprocessed')
        sent_params = route.calls[0].request.url.params
        assert sent_params.get('status') == 'unprocessed'
        assert 'metric_name' not in sent_params
        assert 'limit' not in sent_params


class TestChangePointsItem:
    @respx.mock
    def test_get(self, client):
        respx.get(f'{BASE_URL}/change-points/{UUID1}').mock(return_value=httpx.Response(200, json=CHANGE_POINT_JSON))
        result = client.change_points.get(UUID1)
        assert isinstance(result, ChangePointRead)
        assert str(result.id) == UUID1

    @respx.mock
    def test_triage(self, client):
        route = respx.patch(f'{BASE_URL}/change-points/{UUID1}').mock(
            return_value=httpx.Response(200, json={**CHANGE_POINT_JSON, 'status': 'acknowledged'})
        )
        result = client.change_points.triage(UUID1, TriageRequest(status='acknowledged', triage_author='alice'))
        assert isinstance(result, ChangePointRead)
        assert result.status == 'acknowledged'
        assert b'"status":"acknowledged"' in route.calls[0].request.content

    @respx.mock
    def test_bulk_triage(self, client):
        route = respx.patch(f'{BASE_URL}/change-points/bulk-triage').mock(
            return_value=httpx.Response(200, json={'updated': 2})
        )
        result = client.change_points.bulk_triage(BulkTriageRequest(ids=[UUID1, UUID2], status='hidden'))
        assert result == {'updated': 2}
        assert b'"status":"hidden"' in route.calls[0].request.content


class TestChangePointsConfig:
    @respx.mock
    def test_get_config(self, client):
        respx.get(f'{BASE_URL}/change-points/config/{UUID1}').mock(return_value=httpx.Response(200, json=CONFIG_JSON))
        result = client.change_points.get_config(UUID1)
        assert isinstance(result, ChangePointConfigRead)
        assert result.window_size == 30

    @respx.mock
    def test_set_config(self, client):
        route = respx.put(f'{BASE_URL}/change-points/config/{UUID1}').mock(
            return_value=httpx.Response(200, json={**CONFIG_JSON, 'window_size': 60})
        )
        result = client.change_points.set_config(UUID1, ChangePointConfigInput(window_size=60))
        assert result.window_size == 60
        assert b'"window_size":60' in route.calls[0].request.content

    @respx.mock
    def test_delete_config(self, client):
        route = respx.delete(f'{BASE_URL}/change-points/config/{UUID1}').mock(return_value=httpx.Response(204))
        client.change_points.delete_config(UUID1)
        assert route.called


class TestTriageAlias:
    @respx.mock
    def test_evaluations_triage_delegates_to_change_points(self, client):
        """The deprecated client.evaluations.triage alias still hits the change-points route."""
        route = respx.patch(f'{BASE_URL}/change-points/{UUID1}').mock(
            return_value=httpx.Response(200, json={**CHANGE_POINT_JSON, 'status': 'hidden'})
        )
        result = client.evaluations.triage(UUID1, TriageRequest(status='hidden'))
        assert isinstance(result, ChangePointRead)
        assert result.status == 'hidden'
        assert route.called
