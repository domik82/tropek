"""Tests for RawQueryStrategy."""

from unittest.mock import AsyncMock
from urllib.parse import unquote

import pytest
import respx
from httpx import Response
from tropek_prometheus.core.prometheus_client import PrometheusClient, PrometheusQueryError
from tropek_prometheus.core.strategies.models import IndicatorOutcome, StrategyResult
from tropek_prometheus.core.strategies.raw import RawQueryStrategy


@pytest.fixture
def strategy() -> RawQueryStrategy:
    client = PrometheusClient(base_url='http://prom:9090', timeout=5.0, retry_attempts=1, retry_backoff_seconds=0)
    return RawQueryStrategy(client)


@respx.mock
@pytest.mark.asyncio
async def test_raw_strategy_returns_single_value(strategy: RawQueryStrategy) -> None:
    respx.get('http://prom:9090/api/v1/query').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {
                    'resultType': 'vector',
                    'result': [{'metric': {}, 'value': [1705312800, '0.245']}],
                },
            },
        )
    )
    result = await strategy.execute(
        sli_name='response_time_p99',
        query_spec={'mode': 'raw', 'query': 'histogram_quantile(0.99, ...)'},
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    assert result == StrategyResult(indicators={'response_time_p99': IndicatorOutcome(value=0.245)})


@respx.mock
@pytest.mark.asyncio
async def test_raw_strategy_substitutes_variables(strategy: RawQueryStrategy) -> None:
    route = respx.get('http://prom:9090/api/v1/query').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {
                    'resultType': 'vector',
                    'result': [{'metric': {}, 'value': [1705312800, '1.0']}],
                },
            },
        )
    )
    await strategy.execute(
        sli_name='cpu',
        query_spec={'mode': 'raw', 'query': 'rate(cpu{job="$SERVICE"}[5m])'},
        variables={'SERVICE': 'api'},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    assert 'job="api"' in unquote(str(route.calls[0].request.url))


@respx.mock
@pytest.mark.asyncio
async def test_raw_strategy_captures_error(strategy: RawQueryStrategy) -> None:
    respx.get('http://prom:9090/api/v1/query').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {'resultType': 'vector', 'result': []},
            },
        )
    )
    result = await strategy.execute(
        sli_name='missing_metric',
        query_spec={'mode': 'raw', 'query': 'nonexistent_metric'},
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    outcome = result.indicators['missing_metric']
    assert outcome.value is None
    assert '0 results' in (outcome.error or '')
    assert outcome.error_kind == 'data'


@pytest.mark.asyncio
@pytest.mark.parametrize(('transient', 'expected_kind'), [(True, 'transient'), (False, 'data')])
async def test_raw_query_error_kind_follows_the_error_transience(transient: bool, expected_kind: str) -> None:
    """A query error is retryable exactly when the client marked it transient."""
    client = AsyncMock()
    client.instant_query.side_effect = PrometheusQueryError('x', transient=transient)
    result = await RawQueryStrategy(client).execute(
        sli_name='cpu',
        query_spec={'mode': 'raw', 'query': 'up'},
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    assert set(result.indicators) == {'cpu'}
    assert result.indicators['cpu'].error_kind == expected_kind
