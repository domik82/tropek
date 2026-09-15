"""Unit tests for HttpAdapterClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from tropek.modules.quality_gate.workflows.execution.adapter_client import HttpAdapterClient


@pytest.mark.asyncio
async def test_uses_injected_client() -> None:
    """When an external httpx.AsyncClient is provided, query() uses it directly."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = {
        'values': {'cpu_usage': 42.5},
        'errors': {},
        'metadata': {},
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_response

    client = HttpAdapterClient(timeout=10, http_client=mock_client)
    values, errors, metadata = await client.query(
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
