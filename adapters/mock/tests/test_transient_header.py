"""The mock adapter's header-driven transient failure scenario."""

import asyncio
from typing import Any

import httpx
from tropek_mock.main import app

_BODY = {
    'queries': {'m': {'mode': 'raw', 'query': 'm'}},
    'start': '2026-01-01T00:00:00Z',
    'end': '2026-01-02T00:00:00Z',
}


async def _post_query(headers: dict[str, str]) -> dict[str, Any]:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post('/query', json=_BODY, headers=headers)
    response.raise_for_status()
    return response.json()


def test_transient_header_marks_named_metrics_transient() -> None:
    flagged = asyncio.run(_post_query({'X-Mock-Transient': 'm'}))
    assert flagged['values']['m'] is None
    assert 'm' in flagged['errors']
    assert flagged['error_kinds']['m'] == 'transient'

    assert asyncio.run(_post_query({}))['error_kinds'] == {}
