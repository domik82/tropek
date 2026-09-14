"""The SLO dry-run calls adapters directly, so it must authenticate like the evaluation path."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from tropek.modules.slo_registry.service import SLOTestService


def _adapter_response() -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.json.return_value = {'values': {'cpu': 1.0}, 'errors': {}}
    response.raise_for_status = MagicMock()
    return response


async def _call_dry_run(token: str | None) -> dict[str, str]:
    """Run the dry-run adapter call against a mocked httpx client and return the headers sent."""
    service = SLOTestService(session=MagicMock())
    datasource = SimpleNamespace(adapter_url='http://adapter:8081', name='prometheus-dev', token=token)
    body = SimpleNamespace(
        period_start=datetime(2026, 1, 1, tzinfo=UTC),
        period_end=datetime(2026, 1, 1, 1, tzinfo=UTC),
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = _adapter_response()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch('tropek.modules.slo_registry.service.httpx.AsyncClient', return_value=mock_client):
        await service._query_adapter(body, datasource, {'cpu': 'up'})

    return mock_client.post.call_args.kwargs['headers']


@pytest.mark.asyncio
async def test_dry_run_presents_the_datasource_token() -> None:
    """Without this the dry-run endpoint breaks with 401 against an authenticated adapter."""
    headers = await _call_dry_run('a-shared-secret')
    assert headers['Authorization'] == 'Bearer a-shared-secret'


@pytest.mark.asyncio
async def test_dry_run_sends_no_authorization_without_a_token() -> None:
    headers = await _call_dry_run(None)
    assert 'Authorization' not in headers
