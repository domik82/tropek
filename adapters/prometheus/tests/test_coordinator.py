"""Tests for the job coordinator."""

import asyncio

import fakeredis.aioredis
import pytest
from tropek_prometheus.config import Settings
from tropek_prometheus.core.coordinator import Coordinator
from tropek_prometheus.core.prometheus_client import PrometheusQueryError
from tropek_prometheus.core.strategies.models import IndicatorOutcome, StrategyResult
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
    ) -> StrategyResult:
        if sli_name == self._failing_sli:
            raise ValueError(f'invalid duration format: {query_spec.get("interval")}')
        return StrategyResult(indicators={f'{sli_name}.mean': IndicatorOutcome(value=7.0)})


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


class HangingStrategy:
    """Never returns within the test's job timeout."""

    async def execute(self, **_: object) -> StrategyResult:
        await asyncio.sleep(10)
        return StrategyResult(indicators={})


class SlowForOneStrategy:
    """Answers at once for every SLI except the named one, which hangs."""

    def __init__(self, slow_sli: str) -> None:
        self._slow_sli = slow_sli

    async def execute(self, *, sli_name: str, **_: object) -> StrategyResult:
        if sli_name == self._slow_sli:
            await asyncio.sleep(10)
        return StrategyResult(indicators={sli_name: IndicatorOutcome(value=1.0)})


class TransientFailureStrategy:
    """Reports a retryable failure for its SLI."""

    async def execute(self, *, sli_name: str, **_: object) -> StrategyResult:
        return StrategyResult(
            indicators={sli_name: IndicatorOutcome(value=None, error='overloaded', error_kind='transient')}
        )


def _timeout_coordinator(strategy: object) -> Coordinator:
    repo = JobRepository(fakeredis.aioredis.FakeRedis(), prefix='test:')
    settings = Settings(max_concurrent_queries=2, max_concurrent_jobs=1, default_job_timeout_seconds=1)
    return Coordinator(repo, settings, strategies={'raw': strategy, 'aggregated': strategy})


@pytest.mark.asyncio
async def test_job_timeout_marks_timed_out_and_writes_transient_results():
    coordinator = _timeout_coordinator(HangingStrategy())
    repo = coordinator._repo
    job_id = await repo.create_job({'m': {'mode': 'raw', 'query': 'up'}}, {}, 1, 's', 'e')
    await repo.enqueue(job_id)

    await coordinator.process_one()

    status = await repo.get_status(job_id)
    assert status['status'] == 'timed_out'
    results = await repo.get_results(job_id)
    assert results['m']['success'] is False
    assert results['m']['kind'] == 'transient'
    assert 'job timed out after 1s' in results['m']['message']
    assert coordinator.running_jobs == 0


@pytest.mark.asyncio
async def test_job_timeout_keeps_finished_results_and_fails_only_unfinished_ones():
    coordinator = _timeout_coordinator(SlowForOneStrategy('slow'))
    repo = coordinator._repo
    queries = {'fast': {'mode': 'raw', 'query': 'up'}, 'slow': {'mode': 'raw', 'query': 'up'}}
    job_id = await repo.create_job(queries, {}, 1, 's', 'e')
    await repo.enqueue(job_id)

    await coordinator.process_one()

    results = await repo.get_results(job_id)
    assert results['fast']['success'] is True
    assert results['slow']['success'] is False
    assert results['slow']['kind'] == 'transient'


@pytest.mark.asyncio
async def test_job_timeout_fails_every_method_of_an_unfinished_aggregated_query():
    coordinator = _timeout_coordinator(HangingStrategy())
    repo = coordinator._repo
    queries = {'a': {'mode': 'aggregated', 'query_template': 'up', 'interval': '1m', 'methods': ['mean', 'max']}}
    job_id = await repo.create_job(queries, {}, 1, 's', 'e')
    await repo.enqueue(job_id)

    await coordinator.process_one()

    results = await repo.get_results(job_id)
    assert set(results) == {'a.mean', 'a.max'}
    assert all(result['kind'] == 'transient' for result in results.values())


@pytest.mark.asyncio
async def test_job_timeout_does_not_overwrite_a_cancelled_job():
    coordinator = _timeout_coordinator(HangingStrategy())
    repo = coordinator._repo
    job_id = await repo.create_job({'m': {'mode': 'raw', 'query': 'up'}}, {}, 1, 's', 'e')
    await repo.enqueue(job_id)
    processing = asyncio.create_task(coordinator.process_one())
    await asyncio.sleep(0.2)
    await repo.cancel(job_id)

    await processing

    assert (await repo.get_status(job_id))['status'] == 'cancelled'


@pytest.mark.asyncio
async def test_strategy_kinds_are_persisted_with_each_result():
    coordinator = _timeout_coordinator(TransientFailureStrategy())
    repo = coordinator._repo
    job_id = await repo.create_job({'m': {'mode': 'raw', 'query': 'up'}}, {}, 120, 's', 'e')
    await repo.enqueue(job_id)

    await coordinator.process_one()

    results = await repo.get_results(job_id)
    assert results['m']['success'] is False
    assert results['m']['kind'] == 'transient'


class RaisingStrategy:
    def __init__(self, error: Exception) -> None:
        self._error = error

    async def execute(self, **_: object) -> StrategyResult:
        raise self._error


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('error', 'expected_kind'),
    [
        (PrometheusQueryError('down', transient=True), 'transient'),
        (PrometheusQueryError('bad', transient=False), 'data'),
        (ValueError('boom'), 'data'),
    ],
)
async def test_exception_is_transient_only_for_a_transient_prometheus_error(error: Exception, expected_kind: str):
    coordinator = _timeout_coordinator(RaisingStrategy(error))
    repo = coordinator._repo
    job_id = await repo.create_job({'m': {'mode': 'raw', 'query': 'up'}}, {}, 120, 's', 'e')
    await repo.enqueue(job_id)

    await coordinator.process_one()

    assert (await repo.get_results(job_id))['m']['kind'] == expected_kind


class PeakRecordingStrategy:
    """Takes a while per query and records the most jobs the coordinator ran at once."""

    def __init__(self) -> None:
        self.coordinator: Coordinator | None = None
        self.peak_running_jobs = 0

    async def execute(self, *, sli_name: str, **_: object) -> StrategyResult:
        assert self.coordinator is not None
        self.peak_running_jobs = max(self.peak_running_jobs, self.coordinator.running_jobs)
        await asyncio.sleep(0.2)
        return StrategyResult(indicators={sli_name: IndicatorOutcome(value=1.0)})


@pytest.mark.asyncio
@pytest.mark.parametrize(('job_count', 'max_concurrent_jobs'), [(5, 2)])
async def test_run_processes_up_to_max_concurrent_jobs_at_once(job_count: int, max_concurrent_jobs: int):
    strategy = PeakRecordingStrategy()
    repo = JobRepository(fakeredis.aioredis.FakeRedis(), prefix='test:')
    settings = Settings(max_concurrent_queries=10, max_concurrent_jobs=max_concurrent_jobs)
    coordinator = Coordinator(repo, settings, strategies={'raw': strategy})
    strategy.coordinator = coordinator
    job_ids = []
    for _ in range(job_count):
        job_id = await repo.create_job({'m': {'mode': 'raw', 'query': 'up'}}, {}, 120, 's', 'e')
        await repo.enqueue(job_id)
        job_ids.append(job_id)

    loop_task = asyncio.create_task(coordinator.run())

    async def all_completed() -> None:
        while True:
            statuses = [(await repo.get_status(job_id))['status'] for job_id in job_ids]
            if all(status == 'completed' for status in statuses):
                return
            await asyncio.sleep(0.05)

    try:
        await asyncio.wait_for(all_completed(), timeout=5)
    finally:
        loop_task.cancel()
        await asyncio.gather(loop_task, return_exceptions=True)
        await coordinator.stop()

    assert strategy.peak_running_jobs == min(job_count, max_concurrent_jobs)
    assert coordinator.running_jobs == 0


@pytest.mark.asyncio
async def test_stop_cancels_jobs_still_running():
    coordinator = _timeout_coordinator(HangingStrategy())
    repo = coordinator._repo
    job_id = await repo.create_job({'m': {'mode': 'raw', 'query': 'up'}}, {}, 120, 's', 'e')
    await repo.enqueue(job_id)
    loop_task = asyncio.create_task(coordinator.run())
    while coordinator.running_jobs == 0:
        await asyncio.sleep(0.01)

    loop_task.cancel()
    await asyncio.gather(loop_task, return_exceptions=True)
    await asyncio.wait_for(coordinator.stop(), timeout=1)

    assert coordinator.running_jobs == 0


@pytest.mark.asyncio
async def test_coordinator_applies_retention_ttl_when_skipping_a_cancelled_job(coordinator: Coordinator):
    repo = coordinator._repo
    job_id = await repo.create_job(queries={'cpu': {'mode': 'raw', 'query': 'x'}}, variables={}, timeout=120)
    await repo.enqueue(job_id)
    await repo.cancel(job_id)

    await coordinator.process_one()

    assert await repo._r.ttl(repo._key('job', job_id)) > 0
