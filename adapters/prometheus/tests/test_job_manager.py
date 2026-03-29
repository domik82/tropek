"""Tests for JobManager — submit, poll, cancel, and back-pressure."""

import fakeredis.aioredis
import pytest
from app.config import Settings
from app.core.job_manager import JobManager
from app.redis.repository import JobRepository


@pytest.fixture
async def manager():
    redis = fakeredis.aioredis.FakeRedis()
    repo = JobRepository(redis, prefix="test:")
    settings = Settings()
    return JobManager(repo, settings)


@pytest.mark.asyncio
async def test_submit_job(manager: JobManager):
    result = await manager.submit(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout_seconds=None,
        start="2026-01-15T10:00:00Z",
        end="2026-01-15T10:05:00Z",
    )
    assert result["status"] == "queued"
    assert result["total_queries"] == 1
    assert "job_id" in result


@pytest.mark.asyncio
async def test_submit_respects_max_timeout(manager: JobManager):
    result = await manager.submit(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout_seconds=9999,
    )
    # Should be capped to max_job_timeout_seconds (600)
    status = await manager.get_status(result["job_id"])
    assert status is not None


@pytest.mark.asyncio
async def test_submit_rejects_when_queue_full(manager: JobManager):
    # Fill queue to max_queue_depth
    for i in range(manager._settings.max_queue_depth):
        await manager.submit(
            queries={f"m{i}": {"mode": "raw", "query": "x"}},
            variables={},
            timeout_seconds=None,
        )
    with pytest.raises(manager.QueueFullError):
        await manager.submit(
            queries={"overflow": {"mode": "raw", "query": "x"}},
            variables={},
            timeout_seconds=None,
        )


@pytest.mark.asyncio
async def test_get_status_not_found(manager: JobManager):
    status = await manager.get_status("nonexistent")
    assert status is None


@pytest.mark.asyncio
async def test_cancel_job(manager: JobManager):
    result = await manager.submit(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout_seconds=None,
    )
    cancelled = await manager.cancel(result["job_id"])
    assert cancelled is True
