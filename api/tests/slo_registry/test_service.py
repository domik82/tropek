# api/tests/test_slo_test_endpoint.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from tropek.db.models import SLIDefinition
from tropek.db.session import get_session
from tropek.main import app

VALID_OBJECTIVES = [{'sli': 'response_time_p99', 'pass_threshold': ['<600'], 'weight': 1}]


def _client_with_lookup_result(lookup_result):
    """Build a TestClient whose every repository lookup resolves to ``lookup_result``."""
    mock_session = AsyncMock()
    # All repository lookups use result.scalar_one_or_none()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=lookup_result)
    mock_session.execute = AsyncMock(return_value=execute_result)

    async def _mock_session():
        yield mock_session

    app.dependency_overrides[get_session] = _mock_session
    return TestClient(app)


@pytest.fixture
def client():
    """TestClient with mocked DB session for unit tests — every lookup returns not-found."""
    yield _client_with_lookup_result(None)
    app.dependency_overrides.clear()


@pytest.fixture
def aggregated_sli_client():
    """TestClient whose SLI lookup resolves to an aggregated-mode definition."""
    sli_def = SLIDefinition(
        name='agg-latency-sli',
        mode='aggregated',
        indicators={'cpu': 'rate(cpu[$interval])'},
        interval='5m',
        methods=['mean'],
    )
    yield _client_with_lookup_result(sli_def)
    app.dependency_overrides.clear()


def test_slo_test_rejects_empty_objectives(client):
    resp = client.post(
        '/slo-definitions/test',
        json={
            'objectives': [],
            'sli_name': 'my-sli',
            'data_source_name': 'prometheus',
            'asset_name': 'vm-01',
            'period_start': '2026-03-01T00:00:00Z',
            'period_end': '2026-03-01T01:00:00Z',
        },
    )
    assert resp.status_code == 422
    # Schema-level MinLen(1) constraint rejects empty objectives list
    assert any('objectives' in str(entry.get('loc', '')).lower() for entry in resp.json()['detail'])


def test_slo_test_rejects_missing_required_fields(client):
    resp = client.post(
        '/slo-definitions/test',
        json={'objectives': VALID_OBJECTIVES},
    )
    assert resp.status_code == 422


def test_slo_test_accepts_valid_request_shape(client):
    """Valid shape should not get 422 for request validation.

    It will likely get 404 for missing SLI/asset/datasource since there's no DB,
    but the request shape itself should be accepted.
    """
    resp = client.post(
        '/slo-definitions/test',
        json={
            'objectives': VALID_OBJECTIVES,
            'sli_name': 'nonexistent-sli',
            'data_source_name': 'nonexistent-ds',
            'asset_name': 'nonexistent-asset',
            'period_start': '2026-03-01T00:00:00Z',
            'period_end': '2026-03-01T01:00:00Z',
        },
    )
    # Should be 404 (entity not found) not 422 (bad request shape)
    assert resp.status_code in (404, 502)


def test_slo_test_rejects_aggregated_mode_sli(aggregated_sli_client):
    """A dry run of an aggregated SLI must fail rather than report every metric missing.

    The endpoint posts plain ``{name: query}`` pairs, which adapters read as raw mode, so
    values come back keyed ``cpu`` while the objectives are named ``cpu.mean``.
    """
    resp = aggregated_sli_client.post(
        '/slo-definitions/test',
        json={
            'objectives': [{'sli': 'cpu.mean', 'pass_threshold': ['<600'], 'weight': 1}],
            'sli_name': 'agg-latency-sli',
            'data_source_name': 'prometheus',
            'asset_name': 'vm-01',
            'period_start': '2026-03-01T00:00:00Z',
            'period_end': '2026-03-01T01:00:00Z',
        },
    )
    assert resp.status_code == 422
    assert 'raw mode only' in str(resp.json()['detail'])
