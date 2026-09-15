"""Tests for the job coordinator."""

import fakeredis.aioredis
import pytest
from tropek_prometheus.config import Settings
from tropek_prometheus.core.coordinator import Coordinator
from tropek_prometheus.core.strategies.raw import RawQueryStrategy
from tropek_prometheus.redis.repository import JobRepository


class FakePrometheusClient:
    """Returns canned values for testing coordinator logic."""

    async def instant_query(self, query: str, *, time: str) -> float:
        return 42.0


class ExplodingStrategy:
    """Raises for one named SLI and succeeds for the rest.

    Stands in for any SLI whose spec only fails once the adapter runs it — a malformed interval,
    for instance, which no schema rejected on the way in.
    """

    def __init__(self, failing_sli: str) -> None:
        self._failing_sli = failing_sli

    async def execute(
        self,
        *,
        sli_name: str,
        query_spec: dict,
        variables: dict,
        start: str,
        end: str,
    ) -> tuple[dict, dict, dict | None]:
        if sli_name == self._failing_sli:
            raise ValueError(f'invalid duration format: {query_spec.get("interval")}')
        return {f'{sli_name}.mean': 7.0}, {}, None


@pytest.fixture
async def coordinator():
    redis = fakeredis.aioredis.FakeRedis()
    repo = JobRepository(redis, prefix='test:')
    settings = Settings(max_concurrent_queries=2, max_concurrent_jobs=1)
    client = FakePrometheusClient()
    strategy = RawQueryStrategy(client)
    return Coordinator(repo, settings, strategies={'raw': strategy})


@pytest.mark.asyncio
async def test_coordinator_processes_single_job(coordinator: Coordinator):
    repo = coordinator._repo
    job_id = await repo.create_job(
        queries={'cpu': {'mode': 'raw', 'query': 'x'}},
        variables={},
        timeout=120,
    )
    await repo.enqueue(job_id)

    await coordinator.process_one()

    status = await repo.get_status(job_id)
    assert status['status'] == 'completed'
    results = await repo.get_results(job_id)
    assert results['cpu']['value'] == 42.0
    assert results['cpu']['success'] is True


@pytest.mark.asyncio
async def test_coordinator_handles_multiple_queries(coordinator: Coordinator):
    repo = coordinator._repo
    queries = {f'metric_{i}': {'mode': 'raw', 'query': f'q{i}'} for i in range(5)}
    job_id = await repo.create_job(queries=queries, variables={}, timeout=120)
    await repo.enqueue(job_id)

    await coordinator.process_one()

    status = await repo.get_status(job_id)
    assert status['status'] == 'completed'
    results = await repo.get_results(job_id)
    assert len(results) == 5


@pytest.mark.asyncio
async def test_coordinator_skips_cancelled_job(coordinator: Coordinator):
    repo = coordinator._repo
    job_id = await repo.create_job(
        queries={'cpu': {'mode': 'raw', 'query': 'x'}},
        variables={},
        timeout=120,
    )
    await repo.enqueue(job_id)
    await repo.cancel(job_id)

    await coordinator.process_one()

    status = await repo.get_status(job_id)
    assert status['status'] == 'cancelled'


@pytest.fixture
async def exploding_coordinator():
    redis = fakeredis.aioredis.FakeRedis()
    repo = JobRepository(redis, prefix='test:')
    settings = Settings(max_concurrent_queries=2, max_concurrent_jobs=1)
    return Coordinator(repo, settings, strategies={'aggregated': ExplodingStrategy('bad')})


@pytest.mark.asyncio
async def test_coordinator_completes_job_when_one_sli_raises(exploding_coordinator: Coordinator):
    """One SLI blowing up must not strand the job in `running` forever."""
    repo = exploding_coordinator._repo
    job_id = await repo.create_job(
        queries={
            'bad': {'mode': 'aggregated', 'interval': '1m30s', 'methods': ['mean']},
            'good': {'mode': 'aggregated', 'interval': '1m', 'methods': ['mean']},
        },
        variables={},
        timeout=120,
    )
    await repo.enqueue(job_id)

    await exploding_coordinator.process_one()

    status = await repo.get_status(job_id)
    assert status['status'] == 'completed'


@pytest.mark.asyncio
async def test_coordinator_keeps_sibling_results_when_one_sli_raises(
    exploding_coordinator: Coordinator,
):
    """A failing SLI must not discard the results of the SLIs that succeeded alongside it."""
    repo = exploding_coordinator._repo
    job_id = await repo.create_job(
        queries={
            'bad': {'mode': 'aggregated', 'interval': '1m30s', 'methods': ['mean']},
            'good': {'mode': 'aggregated', 'interval': '1m', 'methods': ['mean']},
        },
        variables={},
        timeout=120,
    )
    await repo.enqueue(job_id)

    await exploding_coordinator.process_one()

    results = await repo.get_results(job_id)
    assert results['good.mean']['value'] == 7.0
    assert results['good.mean']['success'] is True


@pytest.mark.asyncio
async def test_coordinator_records_the_failure_for_the_offending_sli(
    exploding_coordinator: Coordinator,
):
    """The SLI that failed is reported as failed, with the reason, rather than silently absent."""
    repo = exploding_coordinator._repo
    job_id = await repo.create_job(
        queries={'bad': {'mode': 'aggregated', 'interval': '1m30s', 'methods': ['mean']}},
        variables={},
        timeout=120,
    )
    await repo.enqueue(job_id)

    await exploding_coordinator.process_one()

    results = await repo.get_results(job_id)
    assert results['bad']['success'] is False
    assert '1m30s' in results['bad']['message']
