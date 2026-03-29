"""Tests for AggregatedQueryStrategy."""

from urllib.parse import parse_qs, unquote, urlparse

import pytest
import respx
from app.core.prometheus_client import PrometheusClient
from app.core.strategies.aggregated import AggregatedQueryStrategy
from httpx import Response


def _matrix_response(values: list[list]) -> Response:
    """Build a Prometheus matrix response from [[ts, val], ...] pairs."""
    return Response(
        200,
        json={
            'status': 'success',
            'data': {
                'resultType': 'matrix',
                'result': [{'metric': {}, 'values': values}],
            },
        },
    )


@pytest.fixture
def strategy() -> AggregatedQueryStrategy:
    client = PrometheusClient(base_url='http://prom:9090', timeout=5.0)
    return AggregatedQueryStrategy(client, chunk_size='4h', parallel_chunks=3)


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_basic_mean_and_max(strategy: AggregatedQueryStrategy) -> None:
    """Short eval window (< chunk_size) -> single query_range call."""
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=_matrix_response([
            [1705312800, '1.0'],
            [1705312860, '2.0'],
            [1705312920, '3.0'],
            [1705312980, '4.0'],
            [1705313040, '5.0'],
        ])
    )
    values, errors, metadata = await strategy.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '1m',
            'methods': ['mean', 'max'],
        },
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    assert values['cpu.mean'] == pytest.approx(3.0)
    assert values['cpu.max'] == pytest.approx(5.0)
    assert errors == {}
    assert metadata is not None
    assert metadata['mode'] == 'aggregated'
    assert metadata['actual_samples'] == 5


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_interval_substitution(
    strategy: AggregatedQueryStrategy,
) -> None:
    """$interval in query_template is replaced with the spec's interval value."""
    route = respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=_matrix_response([[1705312800, '1.0']])
    )
    await strategy.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '5m',
            'methods': ['mean'],
        },
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    url = unquote(str(route.calls[0].request.url))
    assert 'rate(cpu[5m])' in url


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_step_matches_interval(
    strategy: AggregatedQueryStrategy,
) -> None:
    """query_range step parameter must equal the spec's interval."""
    route = respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=_matrix_response([[1705312800, '1.0']])
    )
    await strategy.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '5m',
            'methods': ['mean'],
        },
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    params = parse_qs(urlparse(str(route.calls[0].request.url)).query)
    assert params['step'] == ['5m']


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_variable_substitution(
    strategy: AggregatedQueryStrategy,
) -> None:
    """User variables are substituted alongside $interval."""
    route = respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=_matrix_response([[1705312800, '1.0']])
    )
    await strategy.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu{job="$SERVICE"}[$interval])',
            'interval': '1m',
            'methods': ['mean'],
        },
        variables={'SERVICE': 'api'},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    url = unquote(str(route.calls[0].request.url))
    assert 'job="api"' in url


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_unresolved_variable_error(
    strategy: AggregatedQueryStrategy,
) -> None:
    values, errors, metadata = await strategy.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu{host=$HOST}[$interval])',
            'interval': '1m',
            'methods': ['mean'],
        },
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    assert values['cpu.mean'] is None
    assert 'unresolved' in errors['cpu.mean'].lower()


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_empty_result_returns_none(
    strategy: AggregatedQueryStrategy,
) -> None:
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {'resultType': 'matrix', 'result': []},
            },
        )
    )
    values, errors, metadata = await strategy.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '1m',
            'methods': ['mean', 'p99'],
        },
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    assert values == {'cpu.mean': None, 'cpu.p99': None}
    assert 'no valid data points' in errors['cpu.mean']


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_metadata_sample_counts(
    strategy: AggregatedQueryStrategy,
) -> None:
    """Metadata includes expected and actual sample counts."""
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=_matrix_response([
            [1705312800, '1.0'],
            [1705312860, '2.0'],
            [1705312920, '3.0'],
        ])
    )
    _values, _errors, metadata = await strategy.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '1m',
            'methods': ['mean'],
        },
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    assert metadata is not None
    assert metadata['expected_samples'] == 5
    assert metadata['actual_samples'] == 3
    assert metadata['missing_pct'] == pytest.approx(40.0)
    assert metadata['chunks_failed'] == 0


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_prometheus_error_captured(
    strategy: AggregatedQueryStrategy,
) -> None:
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=Response(500, text='internal server error')
    )
    values, errors, metadata = await strategy.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '1m',
            'methods': ['mean'],
        },
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    assert values['cpu.mean'] is None
    assert 'cpu.mean' in errors


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_chunking_8h_window() -> None:
    """8h eval with 4h chunk_size -> 2 query_range calls."""
    client = PrometheusClient(base_url='http://prom:9090', timeout=5.0)
    strat = AggregatedQueryStrategy(client, chunk_size='4h', parallel_chunks=3)

    route = respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=_matrix_response([
            [1705312800, '1.0'],
            [1705312860, '2.0'],
        ])
    )

    values, errors, metadata = await strat.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '1m',
            'methods': ['mean'],
        },
        variables={},
        start='2026-01-15T00:00:00+00:00',
        end='2026-01-15T08:00:00+00:00',
    )
    # 2 chunks x 2 values each = 4 total values -> mean = 1.5
    assert len(route.calls) == 2
    assert values['cpu.mean'] == pytest.approx(1.5)
    assert metadata is not None
    assert metadata['chunks_failed'] == 0


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_chunk_failure_isolated() -> None:
    """If one chunk fails, remaining chunks still produce valid stats."""
    client = PrometheusClient(base_url='http://prom:9090', timeout=5.0)
    strat = AggregatedQueryStrategy(client, chunk_size='4h', parallel_chunks=3)

    call_count = 0

    def side_effect(request, route):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return Response(500, text='chunk error')
        return _matrix_response([[1705312800, '10.0'], [1705312860, '20.0']])

    respx.get('http://prom:9090/api/v1/query_range').mock(side_effect=side_effect)

    values, errors, metadata = await strat.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '1m',
            'methods': ['mean'],
        },
        variables={},
        start='2026-01-15T00:00:00+00:00',
        end='2026-01-15T08:00:00+00:00',
    )
    assert values['cpu.mean'] == pytest.approx(15.0)
    assert metadata is not None
    assert metadata['chunks_failed'] == 1


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_all_chunks_fail() -> None:
    """All chunks fail -> all methods return None with error."""
    client = PrometheusClient(base_url='http://prom:9090', timeout=5.0)
    strat = AggregatedQueryStrategy(client, chunk_size='4h', parallel_chunks=3)

    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=Response(500, text='error')
    )

    values, errors, metadata = await strat.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '1m',
            'methods': ['mean', 'p99'],
        },
        variables={},
        start='2026-01-15T00:00:00+00:00',
        end='2026-01-15T08:00:00+00:00',
    )
    assert values['cpu.mean'] is None
    assert values['cpu.p99'] is None
    assert 'no valid data points' in errors['cpu.mean']
    assert metadata is not None
    assert metadata['chunks_failed'] == 2


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_short_window_no_chunking() -> None:
    """Window shorter than chunk_size -> exactly 1 query_range call."""
    client = PrometheusClient(base_url='http://prom:9090', timeout=5.0)
    strat = AggregatedQueryStrategy(client, chunk_size='4h', parallel_chunks=3)

    route = respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=_matrix_response([[1705312800, '5.0']])
    )

    await strat.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '1m',
            'methods': ['mean'],
        },
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:30:00Z',
    )
    assert len(route.calls) == 1
