import asyncio
from typing import Any

import httpx
import pytest
import respx
from httpx import Response
from tropek_prometheus.core.prometheus_client import PrometheusClient, PrometheusQueryError


def _matrix(values: list[list[Any]]) -> dict[str, Any]:
    return {'status': 'success', 'data': {'resultType': 'matrix', 'result': [{'metric': {}, 'values': values}]}}


def _scalar(value: str) -> dict[str, Any]:
    return {'status': 'success', 'data': {'resultType': 'scalar', 'result': [1705312800, value]}}


@pytest.fixture
def client():
    return PrometheusClient(base_url='http://prom:9090', timeout=5.0, retry_backoff_seconds=0)


@respx.mock
@pytest.mark.asyncio
async def test_instant_query_returns_scalar(client: PrometheusClient):
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
    value = await client.instant_query('some_query', time='2026-01-15T10:00:00Z')
    assert value == 0.245


@respx.mock
@pytest.mark.asyncio
async def test_instant_query_zero_results_raises(client: PrometheusClient):
    respx.get('http://prom:9090/api/v1/query').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {'resultType': 'vector', 'result': []},
            },
        )
    )
    with pytest.raises(PrometheusQueryError, match='0 results'):
        await client.instant_query('some_query', time='2026-01-15T10:00:00Z')


@respx.mock
@pytest.mark.asyncio
async def test_instant_query_multiple_results_raises(client: PrometheusClient):
    respx.get('http://prom:9090/api/v1/query').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {
                    'resultType': 'vector',
                    'result': [
                        {'metric': {'a': '1'}, 'value': [1705312800, '1.0']},
                        {'metric': {'a': '2'}, 'value': [1705312800, '2.0']},
                    ],
                },
            },
        )
    )
    with pytest.raises(PrometheusQueryError, match='2 results'):
        await client.instant_query('some_query', time='2026-01-15T10:00:00Z')


@respx.mock
@pytest.mark.asyncio
async def test_instant_query_nan_raises(client: PrometheusClient):
    respx.get('http://prom:9090/api/v1/query').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {
                    'resultType': 'vector',
                    'result': [{'metric': {}, 'value': [1705312800, 'NaN']}],
                },
            },
        )
    )
    with pytest.raises(PrometheusQueryError, match='NaN'):
        await client.instant_query('some_query', time='2026-01-15T10:00:00Z')


@respx.mock
@pytest.mark.asyncio
async def test_instant_query_scalar_result_type(client: PrometheusClient):
    respx.get('http://prom:9090/api/v1/query').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {'resultType': 'scalar', 'result': [1705312800, '42.5']},
            },
        )
    )
    value = await client.instant_query('some_query', time='2026-01-15T10:00:00Z')
    assert value == 42.5


@respx.mock
@pytest.mark.asyncio
async def test_instant_query_http_error(client: PrometheusClient):
    respx.get('http://prom:9090/api/v1/query').mock(return_value=Response(500, text='Internal Server Error'))
    with pytest.raises(PrometheusQueryError, match='500'):
        await client.instant_query('some_query', time='2026-01-15T10:00:00Z')


@respx.mock
@pytest.mark.asyncio
@pytest.mark.parametrize(
    'transport_error',
    [
        httpx.ReadTimeout('slow'),
        httpx.ConnectError('refused'),
        httpx.ReadError('connection reset'),
        httpx.RemoteProtocolError('server disconnected without sending a response'),
    ],
    ids=['read-timeout', 'connect-error', 'read-error', 'remote-protocol-error'],
)
async def test_range_query_retries_a_transport_error_then_succeeds(
    client: PrometheusClient, transport_error: httpx.TransportError
):
    route = respx.get('http://prom:9090/api/v1/query_range').mock(
        side_effect=[transport_error, Response(200, json=_matrix([[1, '1.0']]))]
    )
    assert await client.range_query('up', start='s', end='e', step='1m') == [1.0]
    assert route.call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_503_then_success_waits_the_retry_after_value(client: PrometheusClient, monkeypatch: pytest.MonkeyPatch):
    delays: list[float] = []

    async def record_sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr(asyncio, 'sleep', record_sleep)
    route = respx.get('http://prom:9090/api/v1/query').mock(
        side_effect=[Response(503, headers={'Retry-After': '7'}), Response(200, json=_scalar('2'))]
    )
    assert await client.instant_query('up', time='t') == 2.0
    assert route.call_count == 2
    assert delays == [7.0]


@respx.mock
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('status_code', 'expected_calls', 'expected_transient'),
    [
        (429, 3, True),
        (500, 3, True),
        (502, 3, True),
        (503, 3, True),
        (504, 3, True),
        (400, 1, False),
        (422, 1, False),
    ],
)
async def test_status_decides_whether_the_request_is_retried(
    client: PrometheusClient, status_code: int, expected_calls: int, expected_transient: bool
):
    route = respx.get('http://prom:9090/api/v1/query').mock(
        return_value=Response(status_code, json={'status': 'error', 'errorType': 'bad_data', 'error': 'parse error'})
    )
    with pytest.raises(PrometheusQueryError) as error_info:
        await client.instant_query('up', time='t')
    assert error_info.value.transient is expected_transient
    assert route.call_count == expected_calls
    if expected_transient:
        assert 'after 3 attempts' in str(error_info.value)


@pytest.mark.asyncio
async def test_global_semaphore_bounds_in_flight():
    client = PrometheusClient('http://prom:9090', timeout=5, max_in_flight=2, retry_attempts=1)
    peak = 0

    async def slow(request: httpx.Request) -> Response:
        nonlocal peak
        peak = max(peak, client.in_flight)
        await asyncio.sleep(0.01)
        return Response(200, json=_scalar('1'))

    with respx.mock:
        respx.get('http://prom:9090/api/v1/query').mock(side_effect=slow)
        await asyncio.gather(*(client.instant_query('up', time='t') for _ in range(6)))
    assert peak == 2
