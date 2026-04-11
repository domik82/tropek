"""Tests for PrometheusClient.range_query()."""

import math
from urllib.parse import parse_qs, urlparse

import pytest
import respx
from httpx import Response
from tropek_prometheus.core.prometheus_client import PrometheusClient, PrometheusQueryError


@pytest.fixture
def client() -> PrometheusClient:
    return PrometheusClient(base_url='http://prom:9090', timeout=5.0)


@respx.mock
@pytest.mark.asyncio
async def test_range_query_returns_matrix_values(client: PrometheusClient) -> None:
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {
                    'resultType': 'matrix',
                    'result': [
                        {
                            'metric': {'instance': 'localhost:9090'},
                            'values': [
                                [1705312800, '1.5'],
                                [1705312860, '2.5'],
                                [1705312920, '3.5'],
                            ],
                        }
                    ],
                },
            },
        )
    )
    values = await client.range_query(
        'rate(cpu[1m])',
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:03:00Z',
        step='1m',
    )
    assert values == [1.5, 2.5, 3.5]


@respx.mock
@pytest.mark.asyncio
async def test_range_query_flattens_multiple_series(client: PrometheusClient) -> None:
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {
                    'resultType': 'matrix',
                    'result': [
                        {
                            'metric': {'instance': 'a'},
                            'values': [[1705312800, '1.0'], [1705312860, '2.0']],
                        },
                        {
                            'metric': {'instance': 'b'},
                            'values': [[1705312800, '3.0'], [1705312860, '4.0']],
                        },
                    ],
                },
            },
        )
    )
    values = await client.range_query('rate(cpu[1m])', start='s', end='e', step='1m')
    assert values == [1.0, 2.0, 3.0, 4.0]


@respx.mock
@pytest.mark.asyncio
async def test_range_query_empty_matrix(client: PrometheusClient) -> None:
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {'resultType': 'matrix', 'result': []},
            },
        )
    )
    values = await client.range_query('nonexistent', start='s', end='e', step='1m')
    assert values == []


@respx.mock
@pytest.mark.asyncio
async def test_range_query_nan_preserved_as_nan(client: PrometheusClient) -> None:
    """NaN values from Prometheus are kept — stats module handles filtering."""
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {
                    'resultType': 'matrix',
                    'result': [
                        {
                            'metric': {},
                            'values': [[1705312800, '1.0'], [1705312860, 'NaN']],
                        }
                    ],
                },
            },
        )
    )
    values = await client.range_query('q', start='s', end='e', step='1m')
    assert values[0] == 1.0
    assert math.isnan(values[1])


@respx.mock
@pytest.mark.asyncio
async def test_range_query_unexpected_result_type(client: PrometheusClient) -> None:
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {'resultType': 'vector', 'result': []},
            },
        )
    )
    with pytest.raises(PrometheusQueryError, match='expected matrix'):
        await client.range_query('q', start='s', end='e', step='1m')


@respx.mock
@pytest.mark.asyncio
async def test_range_query_sends_correct_params(client: PrometheusClient) -> None:
    route = respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {'resultType': 'matrix', 'result': []},
            },
        )
    )
    await client.range_query('up', start='2026-01-15T10:00:00Z', end='2026-01-15T11:00:00Z', step='5m')
    url = str(route.calls[0].request.url)
    params = parse_qs(urlparse(url).query)
    assert params['query'] == ['up']
    assert params['start'] == ['2026-01-15T10:00:00Z']
    assert params['end'] == ['2026-01-15T11:00:00Z']
    assert params['step'] == ['5m']
