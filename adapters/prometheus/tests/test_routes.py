"""Route integration tests using fakeredis."""

import pytest
from app.main import create_app
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client():
    app = create_app(use_fakeredis=True)
    # Trigger lifespan so app.state is populated before requests
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            yield c


@pytest.mark.asyncio
async def test_health_live(client: AsyncClient):
    resp = await client.get('/health/live')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'ok'


@pytest.mark.asyncio
async def test_submit_job(client: AsyncClient):
    resp = await client.post(
        '/api/v1/query-jobs',
        json={
            'queries': {'cpu': {'mode': 'raw', 'query': 'up'}},
            'start': '2026-01-15T10:00:00Z',
            'end': '2026-01-15T10:05:00Z',
        },
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body['status'] == 'queued'
    assert 'job_id' in body
    assert body['total_queries'] == 1


@pytest.mark.asyncio
async def test_get_job_status(client: AsyncClient):
    submit = await client.post(
        '/api/v1/query-jobs',
        json={
            'queries': {'cpu': {'mode': 'raw', 'query': 'up'}},
            'start': '2026-01-15T10:00:00Z',
            'end': '2026-01-15T10:05:00Z',
        },
    )
    job_id = submit.json()['job_id']
    resp = await client.get(f'/api/v1/query-jobs/{job_id}')
    assert resp.status_code == 200
    assert resp.json()['status'] in ('queued', 'running', 'completed')


@pytest.mark.asyncio
async def test_get_nonexistent_job(client: AsyncClient):
    resp = await client.get('/api/v1/query-jobs/nonexistent')
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_job(client: AsyncClient):
    submit = await client.post(
        '/api/v1/query-jobs',
        json={
            'queries': {'cpu': {'mode': 'raw', 'query': 'up'}},
            'start': '2026-01-15T10:00:00Z',
            'end': '2026-01-15T10:05:00Z',
        },
    )
    job_id = submit.json()['job_id']
    resp = await client.delete(f'/api/v1/query-jobs/{job_id}')
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_queue_full_returns_503(client: AsyncClient):
    # Submit max_queue_depth + 1 jobs
    for i in range(101):
        resp = await client.post(
            '/api/v1/query-jobs',
            json={
                'queries': {f'm{i}': {'mode': 'raw', 'query': 'up'}},
                'start': '2026-01-15T10:00:00Z',
                'end': '2026-01-15T10:05:00Z',
            },
        )
        if resp.status_code == 503:
            assert 'Retry-After' in resp.headers
            return
    pytest.fail('Expected 503 but queue never filled')
