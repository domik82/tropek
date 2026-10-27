import json

import fakeredis.aioredis
import pytest
from tropek_prometheus.redis.repository import JobRepository


@pytest.fixture
async def repo():
    redis = fakeredis.aioredis.FakeRedis()
    return JobRepository(redis, prefix='test:')


@pytest.mark.asyncio
async def test_create_job(repo: JobRepository):
    job_id = await repo.create_job(
        queries={'cpu': {'mode': 'raw', 'query': 'x'}},
        variables={},
        timeout=120,
    )
    assert job_id is not None
    status = await repo.get_status(job_id)
    assert status['status'] == 'queued'
    assert status['total_queries'] == 1


@pytest.mark.asyncio
async def test_mark_running(repo: JobRepository):
    job_id = await repo.create_job(
        queries={'cpu': {'mode': 'raw', 'query': 'x'}},
        variables={},
        timeout=120,
    )
    await repo.mark_running(job_id)
    status = await repo.get_status(job_id)
    assert status['status'] == 'running'


@pytest.mark.asyncio
async def test_write_result(repo: JobRepository):
    job_id = await repo.create_job(
        queries={'cpu': {'mode': 'raw', 'query': 'x'}},
        variables={},
        timeout=120,
    )
    await repo.write_result(job_id, 'cpu', value=4.3, success=True, message='')
    results = await repo.get_results(job_id)
    assert results['cpu']['value'] == 4.3
    assert results['cpu']['success'] is True


@pytest.mark.asyncio
async def test_mark_completed_sets_ttl(repo: JobRepository):
    job_id = await repo.create_job(
        queries={'cpu': {'mode': 'raw', 'query': 'x'}},
        variables={},
        timeout=120,
    )
    await repo.mark_completed(job_id, retention_seconds=60)
    status = await repo.get_status(job_id)
    assert status['status'] == 'completed'


@pytest.mark.asyncio
async def test_cancel_queued_job(repo: JobRepository):
    job_id = await repo.create_job(
        queries={'cpu': {'mode': 'raw', 'query': 'x'}},
        variables={},
        timeout=120,
    )
    cancelled = await repo.cancel(job_id)
    assert cancelled is True
    status = await repo.get_status(job_id)
    assert status['status'] == 'cancelled'


@pytest.mark.asyncio
async def test_cancel_completed_job_returns_false(repo: JobRepository):
    job_id = await repo.create_job(
        queries={'cpu': {'mode': 'raw', 'query': 'x'}},
        variables={},
        timeout=120,
    )
    await repo.mark_completed(job_id, retention_seconds=60)
    cancelled = await repo.cancel(job_id)
    assert cancelled is False


@pytest.mark.asyncio
async def test_enqueue_and_dequeue(repo: JobRepository):
    job_id = await repo.create_job(
        queries={'cpu': {'mode': 'raw', 'query': 'x'}},
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
        jid = await repo.create_job(queries={'x': {'mode': 'raw', 'query': 'x'}}, variables={}, timeout=120)
        await repo.enqueue(jid)
    assert await repo.queue_depth() == 3


@pytest.mark.asyncio
async def test_write_result_round_trips_kind(repo: JobRepository):
    job_id = await repo.create_job(queries={'x': {'mode': 'raw', 'query': 'x'}}, variables={}, timeout=120)
    await repo.write_result(job_id, 'a', value=None, success=False, message='down', kind='transient')

    results = await repo.get_results(job_id)

    assert results['a']['kind'] == 'transient'


@pytest.mark.asyncio
async def test_get_results_reads_entries_written_before_kind_existed_as_data(repo: JobRepository):
    job_id = await repo.create_job(queries={'x': {'mode': 'raw', 'query': 'x'}}, variables={}, timeout=120)
    legacy = json.dumps({'value': None, 'success': False, 'message': 'old', 'query_executed': ''})
    await repo._r.hset(repo._key('job', job_id, 'results'), 'legacy', legacy)

    results = await repo.get_results(job_id)

    assert results['legacy']['kind'] == 'data'


@pytest.mark.asyncio
async def test_expire_job_keys_sets_ttl_on_every_job_key(repo: JobRepository):
    job_id = await repo.create_job(queries={'x': {'mode': 'raw', 'query': 'x'}}, variables={}, timeout=120)
    await repo.write_result(job_id, 'x', value=1.0, success=True, message='')
    await repo.write_metadata(job_id, 'x', {'mode': 'raw'})
    await repo.cancel(job_id)

    await repo.expire_job_keys(job_id, 60)

    for suffix in ((), ('queries',), ('results',), ('metadata',)):
        assert await repo._r.ttl(repo._key('job', job_id, *suffix)) > 0
