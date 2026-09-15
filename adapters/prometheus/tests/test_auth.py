"""Tests for bearer-token authentication on the adapter's query endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from tropek_prometheus.main import create_app

_TOKEN = 'a-shared-secret'
_QUERY_BODY = {
    'queries': {'cpu': {'mode': 'raw', 'query': 'up'}},
    'start': '2026-01-15T10:00:00Z',
    'end': '2026-01-15T10:05:00Z',
}


async def _client(monkeypatch: pytest.MonkeyPatch, token: str | None):
    """Build an ASGI client for an adapter configured with (or without) an auth token."""
    if token is None:
        monkeypatch.delenv('ADAPTER_AUTH_TOKEN', raising=False)
    else:
        monkeypatch.setenv('ADAPTER_AUTH_TOKEN', token)
    app = create_app(use_fakeredis=True)
    return app


@pytest.fixture
async def secured_client(monkeypatch: pytest.MonkeyPatch):
    app = await _client(monkeypatch, _TOKEN)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            yield client


@pytest.fixture
async def open_client(monkeypatch: pytest.MonkeyPatch):
    app = await _client(monkeypatch, None)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            yield client


@pytest.mark.asyncio
async def test_sync_query_rejected_without_a_token(secured_client: AsyncClient) -> None:
    """The endpoint runs arbitrary queries against live data, so it must not answer anonymously."""
    resp = await secured_client.post('/query', json=_QUERY_BODY)
    assert resp.status_code == 401
    assert resp.headers.get('WWW-Authenticate') == 'Bearer'


@pytest.mark.asyncio
async def test_sync_query_rejected_with_the_wrong_token(secured_client: AsyncClient) -> None:
    resp = await secured_client.post(
        '/query',
        json=_QUERY_BODY,
        headers={'Authorization': 'Bearer not-the-secret'},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sync_query_accepted_with_the_configured_token(secured_client: AsyncClient) -> None:
    resp = await secured_client.post(
        '/query',
        json=_QUERY_BODY,
        headers={'Authorization': f'Bearer {_TOKEN}'},
    )
    assert resp.status_code != 401


@pytest.mark.asyncio
async def test_job_api_is_protected_too(secured_client: AsyncClient) -> None:
    """Guarding only /query would leave the job API as an equivalent way to run queries."""
    submit = await secured_client.post('/api/v1/query-jobs', json=_QUERY_BODY)
    assert submit.status_code == 401

    status = await secured_client.get('/api/v1/query-jobs/any-id')
    assert status.status_code == 401

    cancel = await secured_client.delete('/api/v1/query-jobs/any-id')
    assert cancel.status_code == 401


@pytest.mark.asyncio
async def test_health_stays_open_when_a_token_is_configured(secured_client: AsyncClient) -> None:
    """Container healthchecks and the API's reachability probe carry no credentials."""
    resp = await secured_client.get('/health/live')
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_unconfigured_adapter_still_answers_anonymously(open_client: AsyncClient) -> None:
    """Without a configured token the adapter stays permissive, so existing deployments keep working.

    The startup log warns that the query endpoints are unauthenticated.
    """
    resp = await open_client.post('/query', json=_QUERY_BODY)
    assert resp.status_code != 401
