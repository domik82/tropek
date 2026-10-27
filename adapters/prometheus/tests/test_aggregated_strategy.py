"""Tests for AggregatedQueryStrategy."""

from datetime import datetime
from urllib.parse import parse_qs, unquote, urlparse

import httpx
import pytest
import respx
from httpx import Response
from tropek_prometheus.core.prometheus_client import PrometheusClient
from tropek_prometheus.core.strategies.aggregated import AggregatedQueryStrategy, _parse_duration_seconds
from tropek_prometheus.core.strategies.models import AggregatedMetadata, ErrorKind, IndicatorOutcome


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


def _series_matrix_response(series: list[list[list]]) -> Response:
    """Build a Prometheus matrix response holding one entry per series."""
    return Response(
        200,
        json={
            'status': 'success',
            'data': {
                'resultType': 'matrix',
                'result': [
                    {'metric': {'instance': f'host-{idx}'}, 'values': values} for idx, values in enumerate(series)
                ],
            },
        },
    )


def _simulated_prometheus(series_count: int = 1):
    """Respond like a real ``query_range``: evaluate at every step from ``start`` to ``end``, inclusive.

    Mirrors Prometheus' own ``for ts := start; ts <= end; ts += step`` iteration so that sample
    counts asserted in tests are the counts a live server would actually return.

    :param int series_count: Number of series the query fans out to.
    :returns: A respx side-effect callable.
    """

    def _respond(request: httpx.Request) -> Response:
        params = parse_qs(urlparse(str(request.url)).query)
        start = datetime.fromisoformat(unquote(params['start'][0])).timestamp()
        end = datetime.fromisoformat(unquote(params['end'][0])).timestamp()
        step = _parse_duration_seconds(params['step'][0])
        stamps: list[float] = []
        timestamp = start
        while timestamp <= end:
            stamps.append(timestamp)
            timestamp += step
        return _series_matrix_response([[[ts, '1.0'] for ts in stamps] for _ in range(series_count)])

    return _respond


@pytest.fixture
def strategy() -> AggregatedQueryStrategy:
    client = PrometheusClient(base_url='http://prom:9090', timeout=5.0, retry_attempts=1, retry_backoff_seconds=0)
    return AggregatedQueryStrategy(client, chunk_size='4h', parallel_chunks=3)


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_basic_mean_and_max(strategy: AggregatedQueryStrategy) -> None:
    """Short eval window (< chunk_size) -> single query_range call."""
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=_matrix_response(
            [
                [1705312800, '1.0'],
                [1705312860, '2.0'],
                [1705312920, '3.0'],
                [1705312980, '4.0'],
                [1705313040, '5.0'],
            ]
        )
    )
    result = await strategy.execute(
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
    assert result.indicators['cpu.mean'].value == pytest.approx(3.0)
    assert result.indicators['cpu.max'].value == pytest.approx(5.0)
    assert [name for name, outcome in result.indicators.items() if outcome.error] == []
    assert result.metadata is not None
    assert result.metadata.mode == 'aggregated'
    assert result.metadata.actual_samples == 5


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_interval_substitution(
    strategy: AggregatedQueryStrategy,
) -> None:
    """$interval in query_template is replaced with the spec's interval value."""
    route = respx.get('http://prom:9090/api/v1/query_range').mock(return_value=_matrix_response([[1705312800, '1.0']]))
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
    route = respx.get('http://prom:9090/api/v1/query_range').mock(return_value=_matrix_response([[1705312800, '1.0']]))
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
    route = respx.get('http://prom:9090/api/v1/query_range').mock(return_value=_matrix_response([[1705312800, '1.0']]))
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
    result = await strategy.execute(
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
    assert result.indicators['cpu.mean'].value is None
    assert 'unresolved' in (result.indicators['cpu.mean'].error or '').lower()


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
    result = await strategy.execute(
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
    assert {name: outcome.value for name, outcome in result.indicators.items()} == {'cpu.mean': None, 'cpu.p99': None}
    assert result.indicators['cpu.mean'].error == 'no valid data points'


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_metadata_sample_counts(
    strategy: AggregatedQueryStrategy,
) -> None:
    """Metadata includes expected and actual sample counts."""
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=_matrix_response(
            [
                [1705312800, '1.0'],
                [1705312860, '2.0'],
                [1705312920, '3.0'],
            ]
        )
    )
    result = await strategy.execute(
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
    assert result.metadata is not None
    assert result.metadata.expected_samples == 6
    assert result.metadata.actual_samples == 3
    assert result.metadata.missing_pct == pytest.approx(50.0)
    assert result.metadata.chunks_failed == 0


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_full_coverage_reports_zero_missing(
    strategy: AggregatedQueryStrategy,
) -> None:
    """query_range includes both endpoints, so a fully covered window is 0% missing, never negative."""
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=_matrix_response([[1705312800 + 60 * i, '1.0'] for i in range(6)])
    )
    result = await strategy.execute(
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
    assert result.metadata is not None
    assert result.metadata.expected_samples == 6
    assert result.metadata.actual_samples == 6
    assert result.metadata.missing_pct == pytest.approx(0.0)


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_prometheus_error_captured(
    strategy: AggregatedQueryStrategy,
) -> None:
    respx.get('http://prom:9090/api/v1/query_range').mock(return_value=Response(500, text='internal server error'))
    result = await strategy.execute(
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
    assert result.indicators['cpu.mean'].value is None
    assert result.indicators['cpu.mean'].error is not None


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_chunking_8h_window() -> None:
    """8h eval with 4h chunk_size -> 2 query_range calls."""
    client = PrometheusClient(base_url='http://prom:9090', timeout=5.0, retry_attempts=1, retry_backoff_seconds=0)
    strat = AggregatedQueryStrategy(client, chunk_size='4h', parallel_chunks=3)

    route = respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=_matrix_response(
            [
                [1705312800, '1.0'],
                [1705312860, '2.0'],
            ]
        )
    )

    result = await strat.execute(
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
    assert result.indicators['cpu.mean'].value == pytest.approx(1.5)
    assert result.metadata is not None
    assert result.metadata.chunks_failed == 0


_WINDOW_END = {'1h': '2026-01-01T01:00:00+00:00', '12h': '2026-01-01T12:00:00+00:00'}


@respx.mock
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('window', 'chunk_outcomes', 'expected_kind'),
    [
        ('1h', [503], 'transient'),
        ('1h', [400], 'data'),
        ('12h', [None, None, 503], 'transient'),
        ('12h', [None, 400, None], 'data'),
        ('12h', [400, None, 503], 'data'),  # one permanent failure wins: a retry can never fix it
    ],
)
async def test_failed_chunks_fail_every_method_with_the_right_kind(
    strategy: AggregatedQueryStrategy,
    window: str,
    chunk_outcomes: list[int | None],
    expected_kind: ErrorKind,
) -> None:
    """Each chunk answers with its outcome (an HTTP status, or ``None`` for success), in chunk order."""
    call_count = 0

    def responder(request: httpx.Request) -> Response:
        nonlocal call_count
        outcome = chunk_outcomes[call_count]
        call_count += 1
        return _matrix_response([[1705312800, '1.0']]) if outcome is None else Response(outcome)

    respx.get('http://prom:9090/api/v1/query_range').mock(side_effect=responder)
    result = await strategy.execute(
        sli_name='cpu',
        query_spec={'query_template': 'up', 'interval': '1m', 'methods': ['mean', 'p95']},
        variables={},
        start='2026-01-01T00:00:00+00:00',
        end=_WINDOW_END[window],
    )
    failed_count = sum(1 for outcome in chunk_outcomes if outcome is not None)
    assert {name: outcome.value for name, outcome in result.indicators.items()} == {'cpu.mean': None, 'cpu.p95': None}
    assert (result.indicators['cpu.mean'].error or '').startswith('incomplete data:')
    assert result.indicators['cpu.p95'].error == result.indicators['cpu.mean'].error
    assert {name: outcome.error_kind for name, outcome in result.indicators.items()} == {
        'cpu.mean': expected_kind,
        'cpu.p95': expected_kind,
    }
    assert result.metadata is not None
    assert result.metadata.chunks_failed == failed_count
    assert result.metadata.chunks_total == len(chunk_outcomes)


@respx.mock
@pytest.mark.asyncio
async def test_empty_complete_result_stays_a_data_error(strategy: AggregatedQueryStrategy) -> None:
    """A fetch that completed but matched no series is the source's answer, not a retryable failure."""
    respx.get('http://prom:9090/api/v1/query_range').mock(return_value=_matrix_response([]))
    result = await strategy.execute(
        sli_name='cpu',
        query_spec={'query_template': 'up', 'interval': '1m', 'methods': ['mean']},
        variables={},
        start='2026-01-01T00:00:00+00:00',
        end='2026-01-01T01:00:00+00:00',
    )
    assert result.indicators == {
        'cpu.mean': IndicatorOutcome(value=None, error='no valid data points', error_kind='data'),
    }


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_all_chunks_fail() -> None:
    """All chunks fail -> all methods return None with error."""
    client = PrometheusClient(base_url='http://prom:9090', timeout=5.0, retry_attempts=1, retry_backoff_seconds=0)
    strat = AggregatedQueryStrategy(client, chunk_size='4h', parallel_chunks=3)

    respx.get('http://prom:9090/api/v1/query_range').mock(return_value=Response(500, text='error'))

    result = await strat.execute(
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
    assert result.indicators['cpu.mean'].value is None
    assert result.indicators['cpu.p99'].value is None
    assert (result.indicators['cpu.mean'].error or '').startswith('incomplete data: 2 of 2 chunks failed')
    assert result.indicators['cpu.mean'].error_kind == 'transient'
    assert result.indicators['cpu.p99'].error_kind == 'transient'
    assert result.metadata == AggregatedMetadata(
        mode='aggregated',
        expected_samples=481,
        actual_samples=0,
        missing_pct=100.0,
        chunks_failed=2,
        chunks_total=2,
    )


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_short_window_no_chunking() -> None:
    """Window shorter than chunk_size -> exactly 1 query_range call."""
    client = PrometheusClient(base_url='http://prom:9090', timeout=5.0, retry_attempts=1, retry_backoff_seconds=0)
    strat = AggregatedQueryStrategy(client, chunk_size='4h', parallel_chunks=3)

    route = respx.get('http://prom:9090/api/v1/query_range').mock(return_value=_matrix_response([[1705312800, '5.0']]))

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


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_multi_series_full_coverage_reports_zero_missing(
    strategy: AggregatedQueryStrategy,
) -> None:
    """A query that fans out to several series is fully covered, not several hundred percent over."""
    respx.get('http://prom:9090/api/v1/query_range').mock(side_effect=_simulated_prometheus(series_count=3))
    result = await strategy.execute(
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
    assert result.metadata is not None
    assert result.metadata.expected_samples == 18
    assert result.metadata.actual_samples == 18
    assert result.metadata.missing_pct == pytest.approx(0.0)


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_multi_series_partial_coverage(strategy: AggregatedQueryStrategy) -> None:
    """One series missing half its points is 25% missing across two series, not 0%."""
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=_series_matrix_response(
            [
                [[1705312800 + 60 * i, '1.0'] for i in range(6)],
                [[1705312800 + 60 * i, '1.0'] for i in range(3)],
            ]
        )
    )
    result = await strategy.execute(
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
    assert result.metadata is not None
    assert result.metadata.expected_samples == 12
    assert result.metadata.actual_samples == 9
    assert result.metadata.missing_pct == pytest.approx(25.0)


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_empty_matrix_reports_fully_missing(strategy: AggregatedQueryStrategy) -> None:
    """A query matching no series reports 100% missing against one series' worth of points."""
    respx.get('http://prom:9090/api/v1/query_range').mock(side_effect=_simulated_prometheus(series_count=0))
    result = await strategy.execute(
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
    assert result.metadata is not None
    assert result.metadata.expected_samples == 6
    assert result.metadata.actual_samples == 0
    assert result.metadata.missing_pct == pytest.approx(100.0)


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_chunked_window_does_not_double_count_boundaries(
    strategy: AggregatedQueryStrategy,
) -> None:
    """Adjacent chunks must not both return the instant they share, which would over-count samples."""
    respx.get('http://prom:9090/api/v1/query_range').mock(side_effect=_simulated_prometheus())
    result = await strategy.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '1m',
            'methods': ['mean'],
        },
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T18:00:00Z',
    )
    assert result.metadata is not None
    assert result.metadata.expected_samples == 481
    assert result.metadata.actual_samples == 481
    assert result.metadata.missing_pct == pytest.approx(0.0)


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_chunked_window_covers_a_final_boundary_instant(
    strategy: AggregatedQueryStrategy,
) -> None:
    """Stepping past a chunk boundary can land exactly on the window end; that instant still counts.

    A 4h1m window with a 4h chunk leaves one lone timestamp after the first chunk. Advancing the
    loop past it instead of covering it loses a real sample and reports the window as incomplete.
    """
    respx.get('http://prom:9090/api/v1/query_range').mock(side_effect=_simulated_prometheus())
    result = await strategy.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '1m',
            'methods': ['mean'],
        },
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T14:01:00Z',
    )
    assert result.metadata is not None
    assert result.metadata.expected_samples == 242
    assert result.metadata.actual_samples == 242
    assert result.metadata.missing_pct == pytest.approx(0.0)


def test_parse_duration_rejects_zero() -> None:
    """A zero step is meaningless: it divides by zero and makes the chunk loop never advance."""
    with pytest.raises(ValueError, match='must be greater than zero'):
        _parse_duration_seconds('0s')


def test_parse_duration_rejects_zero_hours() -> None:
    """Zero is rejected whatever unit spells it."""
    with pytest.raises(ValueError, match='must be greater than zero'):
        _parse_duration_seconds('0h')


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_rejects_inverted_window(strategy: AggregatedQueryStrategy) -> None:
    """An end before its start is an error, not a window to report coverage for.

    Prometheus refuses an inverted range outright, and the adapter's own expectation goes negative
    and clamps to 1 — so the failure used to surface as a sample-coverage figure instead of an error.
    """
    route = respx.get('http://prom:9090/api/v1/query_range').mock(side_effect=_simulated_prometheus())
    result = await strategy.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '1m',
            'methods': ['mean'],
        },
        variables={},
        start='2026-01-15T10:05:00Z',
        end='2026-01-15T10:00:00Z',
    )
    assert result.indicators['cpu.mean'].value is None
    assert result.indicators['cpu.mean'].error is not None
    assert result.metadata is None
    assert route.call_count == 0


@respx.mock
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('chunk_response', 'expected_chunks_failed'),
    [(_matrix_response([[1705312800, '1.0']]), 0), (Response(400), 1)],
    ids=['success', 'failure'],
)
async def test_metadata_has_every_field_on_both_branches(
    strategy: AggregatedQueryStrategy, chunk_response: Response, expected_chunks_failed: int
) -> None:
    """The success and the failure branch both report the full metadata, chunk counts included.

    Both branches build the same metadata model, so no key can drift between them.
    """
    respx.get('http://prom:9090/api/v1/query_range').mock(return_value=chunk_response)
    result = await strategy.execute(
        sli_name='cpu',
        query_spec={'query_template': 'up', 'interval': '1m', 'methods': ['mean']},
        variables={},
        start='2026-01-01T00:00:00+00:00',
        end='2026-01-01T01:00:00+00:00',
    )
    assert result.metadata is not None
    assert result.metadata.chunks_total == 1
    assert result.metadata.chunks_failed == expected_chunks_failed
