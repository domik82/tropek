"""Route integration tests using fakeredis."""

import asyncio
import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tropek_prometheus.api import routes
from tropek_prometheus.config import Settings
from tropek_prometheus.core.prometheus_client import PrometheusQueryError
from tropek_prometheus.main import create_app
from tropek_prometheus.redis.repository import JobRepository


@pytest.fixture
async def app():
    application = create_app(use_fakeredis=True)
    # Trigger lifespan so app.state is populated before requests
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as c:
        yield c


@pytest.fixture
def idle_coordinator(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stop the coordinator from dequeuing, so submitted jobs stay queued."""

    async def _dequeue_nothing() -> None:
        return None

    monkeypatch.setattr(app.state.coordinator, '_next_job', _dequeue_nothing)


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
async def test_queue_full_returns_503(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """A submission against a full queue is refused with 503 and a Retry-After hint.

    The depth is reported as full rather than reached by submitting: the coordinator drains the
    queue concurrently, so racing it to ``max_queue_depth`` is timing-dependent and fails whenever
    the drain wins. The real depth accounting is covered by
    ``test_job_manager.py::test_submit_rejects_when_queue_full``, which uses a manager with no
    coordinator attached.
    """
    full_depth = Settings().max_queue_depth

    async def _report_full(self: JobRepository) -> int:
        return full_depth

    monkeypatch.setattr(JobRepository, 'queue_depth', _report_full)

    resp = await client.post(
        '/api/v1/query-jobs',
        json={
            'queries': {'cpu': {'mode': 'raw', 'query': 'up'}},
            'start': '2026-01-15T10:00:00Z',
            'end': '2026-01-15T10:05:00Z',
        },
    )

    assert resp.status_code == 503
    assert 'Retry-After' in resp.headers


class _RaisingTransientStrategy:
    async def execute(self, **_: object) -> tuple[dict, dict, dict | None, dict]:
        raise PrometheusQueryError('down', transient=True)


def _sync_body(**extra: object) -> dict:
    return {'queries': {'m': {'mode': 'raw', 'query': 'up'}}, 'start': 's', 'end': 'e', **extra}


@pytest.mark.asyncio
async def test_sync_query_returns_error_kinds(client: AsyncClient, app: FastAPI, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setitem(app.state.coordinator._strategies, 'raw', _RaisingTransientStrategy())

    resp = await client.post('/query', json=_sync_body())

    assert resp.status_code == 200
    assert resp.json()['errors']['m']
    assert resp.json()['error_kinds'] == {'m': 'transient'}


@pytest.mark.asyncio
async def test_sync_query_budget_exhausted_is_504_with_retry_after(
    client: AsyncClient, idle_coordinator: None, monkeypatch: pytest.MonkeyPatch
):
    """A job the coordinator never picks up (queued behind others) exhausts the caller's budget.

    The job's own timeout is shorter than the budget, so only a job that is not being processed can
    outlast it; the idle coordinator models that.
    """
    # A caller budget of 1 s plus the 5 s grace would take 6 s; shrink the grace so the test stays fast.
    monkeypatch.setattr(routes, 'BUDGET_GRACE_SECONDS', 0)

    resp = await client.post('/query', json=_sync_body(timeout_seconds=1))

    assert resp.status_code == 504
    assert resp.headers['Retry-After'] == '5'
    body = resp.json()
    assert body['detail'] == 'job did not complete within budget'
    status = await client.get(f'/api/v1/query-jobs/{body["job_id"]}')
    assert status.json()['status'] in ('cancelled', 'timed_out')


@pytest.mark.asyncio
async def test_sync_query_uses_the_capped_timeout_as_budget(
    client: AsyncClient, app: FastAPI, idle_coordinator: None, monkeypatch: pytest.MonkeyPatch
):
    """The 504 arrives only after the manager's capped timeout plus the grace, not the caller's 10_000."""
    manager = app.state.job_manager
    original_submit = manager.submit

    async def _submit_capped(**kwargs: object) -> dict:
        return {**await original_submit(**kwargs), 'timeout_seconds': 600}

    monkeypatch.setattr(manager, 'submit', _submit_capped)
    start = time.monotonic()
    # The first reading sets the deadline; later ones jump just short of, then past, the full budget.
    readings = iter([start, start + 600 + routes.BUDGET_GRACE_SECONDS, start + 600 + routes.BUDGET_GRACE_SECONDS + 1])
    # Only the route's clock is replaced: the event loop reads the real time.monotonic.
    clock_reads: list[float] = []

    def _read_clock() -> float:
        clock_reads.append(next(readings))
        return clock_reads[-1]

    monkeypatch.setattr(routes, 'time', SimpleNamespace(monotonic=_read_clock))

    resp = await client.post('/query', json=_sync_body(timeout_seconds=10_000))

    assert resp.status_code == 504
    # Reading 2 sits exactly on the deadline (600 + grace) and must not yet time out; a route without the grace
    # would give up on reading 2.
    assert len(clock_reads) == 3
    assert resp.json()['detail'] == 'job did not complete within budget'


def test_to_query_response_maps_success_and_failure_kinds():
    job_status = {
        'metadata': {'strategy': 'raw'},
        'results': [
            {'indicator': 'ok', 'success': True, 'value': 1.5, 'kind': 'data'},
            {'indicator': 'down', 'success': False, 'message': 'prometheus down', 'kind': 'transient'},
        ],
    }

    assert routes._to_query_response(job_status) == {
        'values': {'ok': 1.5, 'down': None},
        'errors': {'down': 'prometheus down'},
        'metadata': {'strategy': 'raw'},
        'error_kinds': {'down': 'transient'},
    }


@pytest.mark.asyncio
async def test_readiness_reports_counters(client: AsyncClient):
    resp = await client.get('/health/ready')

    assert {'queue_depth', 'running_jobs', 'prometheus_in_flight'} <= resp.json().keys()


@pytest.mark.asyncio
async def test_sync_query_queue_full_is_503_with_retry_after(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    full_depth = Settings().max_queue_depth

    async def _report_full(self: JobRepository) -> int:
        return full_depth

    monkeypatch.setattr(JobRepository, 'queue_depth', _report_full)

    resp = await client.post('/query', json=_sync_body())

    assert resp.status_code == 503
    assert resp.headers['Retry-After'] == '5'


@pytest.mark.asyncio
async def test_sync_query_stops_waiting_when_the_job_is_cancelled(
    client: AsyncClient, app: FastAPI, idle_coordinator: None, monkeypatch: pytest.MonkeyPatch
):
    """A job cancelled under the caller (``DELETE /api/v1/query-jobs/{id}``) answers at once, retryably."""
    manager = app.state.job_manager
    original_submit = manager.submit

    async def _submit_then_cancel(**kwargs: object) -> dict:
        result = await original_submit(**kwargs)
        await manager.cancel(result['job_id'])
        return result

    monkeypatch.setattr(manager, 'submit', _submit_then_cancel)

    resp = await asyncio.wait_for(client.post('/query', json=_sync_body(timeout_seconds=30)), timeout=5)

    assert resp.status_code == 503
    assert resp.headers['Retry-After'] == '5'
    assert resp.json()['detail'] == 'job was cancelled'
