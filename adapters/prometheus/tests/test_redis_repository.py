import json

import fakeredis.aioredis
import pytest

from app.redis.repository import JobRepository


@pytest.fixture
async def repo():
    redis = fakeredis.aioredis.FakeRedis()
    return JobRepository(redis, prefix="test:")


@pytest.mark.asyncio
async def test_create_job(repo: JobRepository):
    job_id = await repo.create_job(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout=120,
    )
    assert job_id is not None
    status = await repo.get_status(job_id)
    assert status["status"] == "queued"
    assert status["total_queries"] == 1


@pytest.mark.asyncio
async def test_mark_running(repo: JobRepository):
    job_id = await repo.create_job(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout=120,
    )
    await repo.mark_running(job_id)
    status = await repo.get_status(job_id)
    assert status["status"] == "running"


@pytest.mark.asyncio
async def test_write_result(repo: JobRepository):
    job_id = await repo.create_job(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout=120,
    )
    await repo.write_result(job_id, "cpu", value=4.3, success=True, message="")
    results = await repo.get_results(job_id)
    assert results["cpu"]["value"] == 4.3
    assert results["cpu"]["success"] is True


@pytest.mark.asyncio
async def test_mark_completed_sets_ttl(repo: JobRepository):
    job_id = await repo.create_job(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout=120,
    )
    await repo.mark_completed(job_id, retention_seconds=60)
    status = await repo.get_status(job_id)
    assert status["status"] == "completed"


@pytest.mark.asyncio
async def test_cancel_queued_job(repo: JobRepository):
    job_id = await repo.create_job(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout=120,
    )
    cancelled = await repo.cancel(job_id)
    assert cancelled is True
    status = await repo.get_status(job_id)
    assert status["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_completed_job_returns_false(repo: JobRepository):
    job_id = await repo.create_job(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout=120,
    )
    await repo.mark_completed(job_id, retention_seconds=60)
    cancelled = await repo.cancel(job_id)
    assert cancelled is False


@pytest.mark.asyncio
async def test_enqueue_and_dequeue(repo: JobRepository):
    job_id = await repo.create_job(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout=120,
    )
    await repo.enqueue(job_id)
    dequeued = await repo.dequeue()
    assert dequeued == job_id


@pytest.mark.asyncio
async def test_dequeue_empty_returns_none(repo: JobRepository):
    dequeued = await repo.dequeue()
    assert dequeued is None


@pytest.mark.asyncio
async def test_queue_depth(repo: JobRepository):
    for _ in range(3):
        jid = await repo.create_job(queries={"x": {"mode": "raw", "query": "x"}}, variables={}, timeout=120)
        await repo.enqueue(jid)
    assert await repo.queue_depth() == 3
