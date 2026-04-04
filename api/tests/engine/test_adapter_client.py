"""Unit tests for HttpAdapterClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from app.modules.quality_gate.adapter_client import HttpAdapterClient


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
