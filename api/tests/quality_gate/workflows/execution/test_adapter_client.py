"""Unit tests for HttpAdapterClient."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from tropek.modules.quality_gate.workflows.execution.adapter_client import (
    AdapterFetchError,
    AdapterRetryPolicy,
    HttpAdapterClient,
    _compute_backoff,
)


@pytest.mark.asyncio
async def test_uses_injected_client() -> None:
    """When an external httpx.AsyncClient is provided, query() uses it directly."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = {
        'values': {'cpu_usage': 42.5},
        'errors': {},
        'metadata': {},
    }
    mock_response.is_success = True
    mock_response.status_code = 200

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_response

    client = HttpAdapterClient(timeout=10, http_client=mock_client)
    values, errors, metadata, error_kinds = await client.query(
        adapter_url='http://adapter:8081',
        datasource_name='prometheus-dev',
        queries={'cpu_usage': {'query': 'avg(cpu)'}},
        variables={},
        start='2026-01-01T00:00:00Z',
        end='2026-01-01T01:00:00Z',
    )

    mock_client.post.assert_called_once()
    assert values == {'cpu_usage': 42.5}
    assert errors == {}
    assert metadata == {}
    assert error_kinds == {}


async def test_creates_own_client_when_none_injected() -> None:
    """When no http_client is given, _http_client is None and timeout is stored."""
    client = HttpAdapterClient(timeout=10)

    assert client._http_client is None
    assert client._timeout == 10


def _ok_response() -> MagicMock:
    """A minimal successful adapter response."""
    response = MagicMock(spec=httpx.Response)
    response.json.return_value = {'values': {}, 'errors': {}, 'metadata': {}}
    response.raise_for_status = MagicMock()
    return response


@pytest.mark.asyncio
async def test_datasource_token_is_sent_as_a_bearer_header() -> None:
    """The adapter's query endpoints authenticate the caller, so the token must reach the wire.

    The datasource stores it precisely so the API can present it; keeping it in the database means
    the adapter answers anyone who can reach its port.
    """
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = _ok_response()

    client = HttpAdapterClient(timeout=10, http_client=mock_client)
    await client.query(
        adapter_url='http://adapter:8081',
        datasource_name='prometheus-dev',
        queries={'cpu_usage': {'query': 'avg(cpu)'}},
        variables={},
        start='2026-01-01T00:00:00Z',
        end='2026-01-01T01:00:00Z',
        token='a-shared-secret',
    )

    headers = mock_client.post.call_args.kwargs['headers']
    assert headers['Authorization'] == 'Bearer a-shared-secret'
    assert headers['X-Datasource-Name'] == 'prometheus-dev'


@pytest.mark.asyncio
async def test_no_authorization_header_when_the_datasource_has_no_token() -> None:
    """Datasources without a token keep talking to permissive adapters unchanged."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = _ok_response()

    client = HttpAdapterClient(timeout=10, http_client=mock_client)
    await client.query(
        adapter_url='http://adapter:8081',
        datasource_name='prometheus-dev',
        queries={'cpu_usage': {'query': 'avg(cpu)'}},
        variables={},
        start='2026-01-01T00:00:00Z',
        end='2026-01-01T01:00:00Z',
        token=None,
    )

    headers = mock_client.post.call_args.kwargs['headers']
    assert 'Authorization' not in headers


_QUERY_ARGS: dict[str, Any] = {
    'adapter_url': 'http://a',
    'datasource_name': 'd',
    'queries': {},
    'variables': {},
    'start': 's',
    'end': 'e',
}
_OK_BODY = {'values': {'m': 1.0}, 'errors': {}, 'metadata': {}}
_NO_WAIT = AdapterRetryPolicy(max_attempts=3, backoff_seconds=0, jitter=0)


def _client_for(handler: Callable[[httpx.Request], httpx.Response], **kwargs: Any) -> HttpAdapterClient:
    """Build a client whose http layer is a real AsyncClient over a MockTransport."""
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    kwargs.setdefault('policy', _NO_WAIT)
    return HttpAdapterClient(timeout=1, http_client=http_client, **kwargs)


@pytest.mark.asyncio
async def test_read_timeout_goes_straight_to_the_job_retry() -> None:
    """A timed-out attempt already used a whole adapter timeout; a second one would overrun the job."""
    calls = {'n': 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls['n'] += 1
        raise httpx.ReadTimeout('slow', request=request)

    with pytest.raises(AdapterFetchError) as exc_info:
        await _client_for(handler).query(**_QUERY_ARGS)

    assert calls['n'] == 1
    assert exc_info.value.attempts == 1
    assert exc_info.value.retryable is True
    assert 'ReadTimeout' in exc_info.value.cause


@pytest.mark.asyncio
async def test_504_budget_exhausted_goes_straight_to_the_job_retry() -> None:
    calls = {'n': 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls['n'] += 1
        return httpx.Response(
            504,
            headers={'Retry-After': '0'},
            json={'detail': 'job did not complete within budget', 'job_id': 'j1'},
        )

    with pytest.raises(AdapterFetchError) as exc_info:
        await _client_for(handler).query(**_QUERY_ARGS)

    assert calls['n'] == 1
    assert exc_info.value.attempts == 1
    assert exc_info.value.last_status == 504
    assert exc_info.value.retryable is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'first_answer',
    [
        httpx.Response(429, headers={'Retry-After': '0'}),
        httpx.Response(504),
        httpx.Response(503, headers={'Retry-After': 'Wed, 21 Oct 2026 07:28:00 GMT'}),
        httpx.ReadError('dropped'),
        httpx.RemoteProtocolError('dropped'),
        httpx.WriteError('dropped'),
    ],
    ids=['429', 'plain-504', '503-retry-after-http-date', 'read-error', 'remote-protocol-error', 'write-error'],
)
async def test_quick_failure_then_success_is_retried_over_http(
    first_answer: httpx.Response | httpx.TransportError,
) -> None:
    calls = {'n': 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls['n'] += 1
        if calls['n'] == 1:
            if isinstance(first_answer, httpx.TransportError):
                raise first_answer
            return first_answer
        return httpx.Response(200, json=_OK_BODY)

    values, _errors, _metadata, _kinds = await _client_for(handler).query(**_QUERY_ARGS)

    assert values == {'m': 1.0}
    assert calls['n'] == 2


@pytest.mark.asyncio
async def test_deadline_refuses_an_attempt_without_an_http_call() -> None:
    """With less time left before the job deadline than one attempt needs, no request is started."""
    calls = {'n': 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls['n'] += 1
        return httpx.Response(200, json=_OK_BODY)

    with pytest.raises(AdapterFetchError) as exc_info:
        await _client_for(handler, deadline_seconds=0.5).query(**_QUERY_ARGS)

    assert calls['n'] == 0
    assert exc_info.value.attempts == 0
    assert exc_info.value.retryable is True
    assert 'deadline' in exc_info.value.cause


@pytest.mark.asyncio
async def test_deadline_stops_retrying_a_quick_failure() -> None:
    """A retry is not started when the job deadline no longer leaves room for a whole attempt."""
    calls = {'n': 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls['n'] += 1
        return httpx.Response(503, headers={'Retry-After': '1'})

    with pytest.raises(AdapterFetchError) as exc_info:
        await _client_for(handler, deadline_seconds=1.5).query(**_QUERY_ARGS)

    assert calls['n'] == 1
    assert exc_info.value.attempts == 1
    assert exc_info.value.last_status == 503
    assert exc_info.value.retryable is True
    assert 'adapter returned 503' in exc_info.value.cause


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'response',
    [
        httpx.Response(200, content=b'<html>gateway</html>'),
        httpx.Response(200, json={'values': {'m': 'not a number'}}),
        httpx.Response(200, json=['not', 'an', 'object']),
        httpx.Response(200, json={'errors': {'cpu_usage': 'boom'}, 'error_kinds': {'cpu_usage': 'foo'}}),
    ],
    ids=['not-json', 'bad-values', 'not-an-object', 'unknown-error-kind'],
)
async def test_malformed_2xx_is_a_non_retryable_fetch_error(response: httpx.Response) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return response

    with pytest.raises(AdapterFetchError) as exc_info:
        await _client_for(handler).query(**_QUERY_ARGS)

    assert exc_info.value.retryable is False
    assert exc_info.value.last_status == 200
    assert exc_info.value.attempts == 1
    assert 'malformed' in exc_info.value.cause


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('first_failure', 'expected_last_status'),
    [(502, 502), (httpx.ConnectError, None)],
    ids=['502', 'connect-error'],
)
async def test_exhausted_attempts_raise_adapter_fetch_error(
    first_failure: int | type[httpx.ConnectError], expected_last_status: int | None
) -> None:
    calls = {'n': 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls['n'] += 1
        if isinstance(first_failure, int):
            return httpx.Response(first_failure)
        raise first_failure('refused', request=request)

    with pytest.raises(AdapterFetchError) as exc_info:
        await _client_for(handler).query(**_QUERY_ARGS)

    assert exc_info.value.attempts == 3
    assert exc_info.value.last_status == expected_last_status
    assert calls['n'] == 3
    assert 'attempts' not in exc_info.value.cause, 'the count lives in http_attempts, not in the cause text'
    attempt_record = exc_info.value.as_attempt(1)
    assert attempt_record.http_attempts == 3
    assert datetime.fromisoformat(attempt_record.at).tzinfo is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(('status', 'retryable'), [(400, False), (404, False), (422, False), (500, True)])
async def test_non_retryable_status_is_not_retried_over_http(status: int, retryable: bool) -> None:
    """A 4xx (other than 429) is the caller's fault, so the job is not retried either; a 500 may be."""
    calls = {'n': 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls['n'] += 1
        return httpx.Response(status)

    with pytest.raises(AdapterFetchError) as exc_info:
        await _client_for(handler).query(**_QUERY_ARGS)

    assert exc_info.value.attempts == 1
    assert exc_info.value.last_status == status
    assert exc_info.value.retryable is retryable
    assert calls['n'] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('budget_seconds', [300, None])
async def test_budget_is_sent_as_timeout_seconds_only_when_set(budget_seconds: int | None) -> None:
    captured: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=_OK_BODY)

    await _client_for(handler, budget_seconds=budget_seconds).query(**_QUERY_ARGS)

    assert captured[0].get('timeout_seconds') == budget_seconds
    assert ('timeout_seconds' in captured[0]) is (budget_seconds is not None)


@pytest.mark.asyncio
async def test_error_kinds_are_parsed() -> None:
    body = {'values': {'m': None}, 'errors': {'m': 'boom'}, 'metadata': {}, 'error_kinds': {'m': 'transient'}}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    _values, errors, _metadata, kinds = await _client_for(handler).query(**_QUERY_ARGS)

    assert errors == {'m': 'boom'}
    assert kinds == {'m': 'transient'}


def test_backoff_caps_a_huge_retry_after() -> None:
    assert _compute_backoff(1, base_seconds=2, retry_after='3600', jitter=0) == 60


@pytest.mark.parametrize('retry_after', ['nan', 'inf', '-inf'])
def test_backoff_ignores_non_finite_retry_after(retry_after: str) -> None:
    assert _compute_backoff(2, base_seconds=2, retry_after=retry_after, jitter=0) == 4
