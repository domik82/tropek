"""Tests for the job coordinator."""

import asyncio

import fakeredis.aioredis
import pytest

from app.config import Settings
from app.core.coordinator import Coordinator
from app.core.strategies.raw import RawQueryStrategy
from app.redis.repository import JobRepository


class FakePrometheusClient:
    """Returns canned values for testing coordinator logic."""

    async def instant_query(self, query: str, *, time: str) -> float:
        return 42.0


@pytest.fixture
async def coordinator():
    redis = fakeredis.aioredis.FakeRedis()
    repo = JobRepository(redis, prefix="test:")
    settings = Settings(max_concurrent_queries=2, max_concurrent_jobs=1)
    client = FakePrometheusClient()
    strategy = RawQueryStrategy(client)
    return Coordinator(repo, settings, strategies={"raw": strategy})


@pytest.mark.asyncio
async def test_coordinator_processes_single_job(coordinator: Coordinator):
    repo = coordinator._repo
    job_id = await repo.create_job(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout=120,
    )
    await repo.enqueue(job_id)

    await coordinator.process_one()

    status = await repo.get_status(job_id)
    assert status["status"] == "completed"
    results = await repo.get_results(job_id)
    assert results["cpu"]["value"] == 42.0
    assert results["cpu"]["success"] is True


@pytest.mark.asyncio
async def test_coordinator_handles_multiple_queries(coordinator: Coordinator):
    repo = coordinator._repo
    queries = {f"metric_{i}": {"mode": "raw", "query": f"q{i}"} for i in range(5)}
    job_id = await repo.create_job(queries=queries, variables={}, timeout=120)
    await repo.enqueue(job_id)

    await coordinator.process_one()

    status = await repo.get_status(job_id)
    assert status["status"] == "completed"
    results = await repo.get_results(job_id)
    assert len(results) == 5


@pytest.mark.asyncio
async def test_coordinator_skips_cancelled_job(coordinator: Coordinator):
    repo = coordinator._repo
    job_id = await repo.create_job(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout=120,
    )
    await repo.enqueue(job_id)
    await repo.cancel(job_id)

    await coordinator.process_one()

    status = await repo.get_status(job_id)
    assert status["status"] == "cancelled"
