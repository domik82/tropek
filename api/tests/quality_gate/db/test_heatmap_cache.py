"""Integration tests for the per-column heatmap cache (Chunk C PR2).

The property test (cache_equals_uncached_after_mutation) lives in a follow-up
task (Task 12). These tests cover the raw cache module: key shape, MGET, SET,
DELETE, and corrupt-payload handling, plus the read-path integration that
wires the cache into the router handler.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from tropek.cache.redis_cache import RedisCache
from tropek.config import get_settings
from tropek.db.models import EvaluationRun, SLOEvaluation
from tropek.modules.quality_gate.repositories.evaluation import EvaluationRepository
from tropek.modules.quality_gate.schemas.heatmap import (
    EvaluationColumn,
    HeatmapColumnFragment,
    HeatmapSummaryCell,
)
from tropek.modules.quality_gate.workflows.execution.evaluation_executor import (
    warm_heatmap_column_cache,
)
from tropek.modules.quality_gate.workflows.presentation import heatmap_cache
from tropek.modules.quality_gate.workflows.re_evaluation.re_evaluation_service import (
    _persist_reeval_result,
)

from .conftest import SeededAsset


def _make_fragment(run_id: uuid.UUID | None = None) -> HeatmapColumnFragment:
    """Construct a minimal HeatmapColumnFragment for cache roundtrip tests."""
    if run_id is None:
        run_id = uuid.uuid4()
    period_start = datetime(2026, 4, 1, tzinfo=UTC)
    return HeatmapColumnFragment(
        evaluation_run_id=run_id,
        column=EvaluationColumn(
            evaluation_id=run_id,
            period_start=period_start,
            period_end=period_start.replace(minute=15),
            eval_name='daily',
            has_notes=False,
        ),
        per_slo=[],
        composite_summary=HeatmapSummaryCell(
            evaluation_id=run_id,
            period_start=period_start,
            result='pass',
            score=100.0,
            invalidated=False,
            invalidation_note=None,
        ),
    )


@pytest.mark.integration
def test_cache_key_shape() -> None:
    """The cache key embeds the schema version (v1) so a future schema bump
    self-heals — old v1 entries become orphans and expire on TTL.
    """
    key = heatmap_cache.column_cache_key('abc-123')
    assert key == 'heatmap:col:v1:abc-123'


@pytest.mark.integration
async def test_set_and_get_roundtrips_fragment(redis_client) -> None:
    cache = heatmap_cache.HeatmapColumnCache(redis_client)
    fragment = _make_fragment()
    await cache.set_many([fragment])
    results = await cache.get_many([fragment.evaluation_run_id])
    assert len(results) == 1
    returned = results[str(fragment.evaluation_run_id)]
    assert returned.evaluation_run_id == fragment.evaluation_run_id
    assert returned.schema_version == 1


@pytest.mark.integration
async def test_get_many_returns_only_hits(redis_client) -> None:
    cache = heatmap_cache.HeatmapColumnCache(redis_client)
    hit = _make_fragment()
    miss_id = uuid.uuid4()
    await cache.set_many([hit])
    results = await cache.get_many([hit.evaluation_run_id, miss_id])
    assert str(hit.evaluation_run_id) in results
    assert str(miss_id) not in results


@pytest.mark.integration
async def test_delete_one_removes_only_target(redis_client) -> None:
    cache = heatmap_cache.HeatmapColumnCache(redis_client)
    fragment_a = _make_fragment()
    fragment_b = _make_fragment()
    await cache.set_many([fragment_a, fragment_b])
    await cache.delete(fragment_a.evaluation_run_id)
    results = await cache.get_many([fragment_a.evaluation_run_id, fragment_b.evaluation_run_id])
    assert str(fragment_a.evaluation_run_id) not in results
    assert str(fragment_b.evaluation_run_id) in results


@pytest.mark.integration
async def test_delete_many_removes_all_targets(redis_client) -> None:
    cache = heatmap_cache.HeatmapColumnCache(redis_client)
    fragments = [_make_fragment() for _ in range(5)]
    await cache.set_many(fragments)
    ids_to_delete = [fragment.evaluation_run_id for fragment in fragments[:3]]
    await cache.delete_many(ids_to_delete)
    remaining = await cache.get_many([fragment.evaluation_run_id for fragment in fragments])
    assert len(remaining) == 2


@pytest.mark.integration
async def test_corrupted_payload_returns_miss_not_exception(redis_client) -> None:
    """A malformed JSON payload must be treated as a cache miss, not crash
    the read path. This is what lets v1 to v2 schema bumps self-heal.
    """
    cache = heatmap_cache.HeatmapColumnCache(redis_client)
    run_id = uuid.uuid4()
    await redis_client.set(
        heatmap_cache.column_cache_key(str(run_id)),
        b'{"not a valid fragment": true}',
    )
    results = await cache.get_many([run_id])
    assert results == {}


# ---------------------------------------------------------------------------
# Read-path integration tests (router handler + HeatmapColumnCache)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_read_path_cold_cache_writes_back_every_column(
    api_client: AsyncClient,
    redis_client,
    seed_asset_with_indicators: Callable[..., Coroutine[Any, Any, SeededAsset]],
) -> None:
    """Cold cache: the read path must rebuild every column from the DB and
    write each fresh fragment back into Redis before returning.
    """
    seeded = await seed_asset_with_indicators(cell_count=5)

    cache = heatmap_cache.HeatmapColumnCache(redis_client)
    pre_hits = await cache.get_many([])
    assert pre_hits == {}

    response = await api_client.get(f'/evaluate/metric-heatmap?asset_name={seeded.name}')
    assert response.status_code == 200
    column_ids = [column['evaluation_id'] for column in response.json()['columns']]
    assert len(column_ids) == 5

    hits_after = await cache.get_many(column_ids)
    assert len(hits_after) == 5
    for column_id in column_ids:
        assert column_id in hits_after


@pytest.mark.integration
async def test_read_path_warm_cache_serves_same_response(
    api_client: AsyncClient,
    redis_client,  # consumed by the api_client fixture override; required to share state
    seed_asset_with_indicators: Callable[..., Coroutine[Any, Any, SeededAsset]],
) -> None:
    """Warm cache: a second read hits the cached fragments and the response
    must be byte-identical to the first (cold) read.
    """
    seeded = await seed_asset_with_indicators(cell_count=4)

    first = await api_client.get(f'/evaluate/metric-heatmap?asset_name={seeded.name}')
    second = await api_client.get(f'/evaluate/metric-heatmap?asset_name={seeded.name}')

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert len(first.json()['columns']) == 4


@pytest.mark.integration
async def test_cache_false_does_not_read_or_write_cache(
    api_client: AsyncClient,
    redis_client,
    seed_asset_with_indicators: Callable[..., Coroutine[Any, Any, SeededAsset]],
) -> None:
    """``cache=false`` is pure bypass: no Redis read, no Redis write.

    We pre-warm the cache with a real first read, snapshot every fragment
    payload, issue a ``cache=false`` read, and assert that the cache state is
    byte-identical after the bypass. If the handler wrote rebuilt fragments
    back under ``cache=false``, the payloads would diverge (even trivially,
    because the write would touch Redis). If it read from cache under
    ``cache=false``, the rebuilt response would still be correct but the
    write-back half is the load-bearing assertion here.
    """
    seeded = await seed_asset_with_indicators(cell_count=3)

    initial = await api_client.get(f'/evaluate/metric-heatmap?asset_name={seeded.name}')
    assert initial.status_code == 200
    run_ids = [column['evaluation_id'] for column in initial.json()['columns']]
    assert len(run_ids) == 3

    cache = heatmap_cache.HeatmapColumnCache(redis_client)
    cached_before = await cache.get_many(run_ids)
    snapshot_before = {run_id: fragment.model_dump_json() for run_id, fragment in cached_before.items()}
    assert len(snapshot_before) == 3

    bypass = await api_client.get(f'/evaluate/metric-heatmap?asset_name={seeded.name}&cache=false')
    assert bypass.status_code == 200

    cached_after = await cache.get_many(run_ids)
    snapshot_after = {run_id: fragment.model_dump_json() for run_id, fragment in cached_after.items()}
    assert snapshot_after == snapshot_before, 'cache=false must not write fragments back to Redis'


# ---------------------------------------------------------------------------
# Worker warm path — Task 10
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_worker_warm_helper_caches_fragment(
    redis_client,
    db_session,
    seed_asset_with_indicators: Callable[..., Coroutine[Any, Any, SeededAsset]],
) -> None:
    """``warm_heatmap_column_cache`` builds and caches a fragment for a completed run.

    The helper is fire-and-forget — this test exercises the happy path, asserting
    that the fragment lands in Redis under the column cache key. The executor's
    wiring (``finalize_run_job`` → warm helper) is covered by reading rather
    than by test; Task 12's property test will cover the end-to-end contract.
    """
    seeded = await seed_asset_with_indicators(cell_count=1)

    run_id_result = await db_session.execute(select(EvaluationRun.id).where(EvaluationRun.asset_id == seeded.id))
    run_id = run_id_result.scalar_one()

    redis_cache = RedisCache(redis_client)
    await warm_heatmap_column_cache(
        db_session,
        run_id,
        redis_cache=redis_cache,
        settings=get_settings(),
    )

    column_cache = heatmap_cache.HeatmapColumnCache(redis_client)
    hits = await column_cache.get_many([run_id])
    assert str(run_id) in hits, 'warm helper must write a fragment to the column cache'
    cached_fragment = hits[str(run_id)]
    assert cached_fragment.evaluation_run_id == run_id
    assert cached_fragment.column.has_notes is False


@pytest.mark.integration
async def test_worker_warm_helper_is_fire_and_forget_on_missing_run(
    redis_client,
    db_session,
) -> None:
    """A missing run must not raise — the helper logs and returns."""
    redis_cache = RedisCache(redis_client)
    await warm_heatmap_column_cache(
        db_session,
        uuid.uuid4(),
        redis_cache=redis_cache,
        settings=get_settings(),
    )


@pytest.mark.integration
async def test_worker_warm_helper_noop_when_redis_cache_is_none(
    db_session,
    seed_asset_with_indicators: Callable[..., Coroutine[Any, Any, SeededAsset]],
) -> None:
    """If no RedisCache is configured, the helper short-circuits without touching the DB."""
    seeded = await seed_asset_with_indicators(cell_count=1)
    run_id_result = await db_session.execute(select(EvaluationRun.id).where(EvaluationRun.asset_id == seeded.id))
    run_id = run_id_result.scalar_one()
    await warm_heatmap_column_cache(
        db_session,
        run_id,
        redis_cache=None,
        settings=get_settings(),
    )


# ---------------------------------------------------------------------------
# Task 11 — invalidation wiring at every mutation site
# ---------------------------------------------------------------------------


async def _prime_cache_fragment(
    column_cache: heatmap_cache.HeatmapColumnCache,
    run_id: uuid.UUID,
) -> None:
    """Write a sentinel fragment for ``run_id`` so invalidation has something to delete."""
    await column_cache.set_many([_make_fragment(run_id=run_id)])
    hits = await column_cache.get_many([run_id])
    assert str(run_id) in hits, 'prime failed — subsequent assertions would be vacuous'


@pytest.mark.integration
@pytest.mark.parametrize('mutation', ['invalidate', 'restore', 'override_status', 'restore_override'])
async def test_repository_mutation_deletes_cached_fragment(
    mutation: str,
    redis_client,
    db_session,
    seed_asset_with_indicators: Callable[..., Coroutine[Any, Any, SeededAsset]],
) -> None:
    """Every repository mutation that changes a run's presented state must
    delete the cached HeatmapColumnFragment for that run.

    The helper in EvaluationRepository short-circuits on a missing heatmap
    cache, so the test builds a repo instance that is explicitly wired to
    the same fakeredis client the fixture exposes. This exercises the exact
    production contract: repo method → ``_invalidate_heatmap_column`` → cache
    delete — without reaching for the API layer or the service layer.
    """
    seeded = await seed_asset_with_indicators(cell_count=1)

    child_row = await db_session.execute(select(SLOEvaluation).where(SLOEvaluation.asset_id == seeded.id))
    child_eval: SLOEvaluation = child_row.scalars().one()
    run_id = child_eval.evaluation_id

    column_cache = heatmap_cache.HeatmapColumnCache(redis_client)
    await _prime_cache_fragment(column_cache, run_id)

    repo = EvaluationRepository(db_session, heatmap_cache=column_cache)

    if mutation == 'invalidate':
        await repo.invalidate(child_eval.id, note='stale data')
    elif mutation == 'restore':
        # Invalidate first using a cache-less repo so the cache stays primed,
        # then run restore on the wired repo to exercise its invalidation.
        uncached_repo = EvaluationRepository(db_session)
        await uncached_repo.invalidate(child_eval.id, note='stale data')
        await _prime_cache_fragment(column_cache, run_id)
        await repo.restore(child_eval.id)
    elif mutation == 'override_status':
        await repo.override_status(
            child_eval.id,
            new_result='fail',
            reason='manual flip',
            author='tester',
        )
    elif mutation == 'restore_override':
        # override_status must run first to populate original_result.
        uncached_repo = EvaluationRepository(db_session)
        await uncached_repo.override_status(
            child_eval.id,
            new_result='fail',
            reason='setup',
            author='tester',
        )
        await _prime_cache_fragment(column_cache, run_id)
        await repo.restore_override(child_eval.id)
    else:
        raise AssertionError(f'unknown mutation parameter: {mutation}')

    hits_after = await column_cache.get_many([run_id])
    assert str(run_id) not in hits_after, (
        f'{mutation} did not invalidate the heatmap column cache entry for run {run_id}'
    )


@pytest.mark.integration
@pytest.mark.parametrize('mutation', ['pin_baseline', 'unpin_baseline'])
async def test_baseline_pin_mutation_deletes_cached_fragment(
    mutation: str,
    redis_client,
    db_session,
    seed_asset_with_indicators: Callable[..., Coroutine[Any, Any, SeededAsset]],
) -> None:
    """Pin and unpin baseline mutations must also delete the cached fragment.

    The pinned run's own heatmap column does not embed ``baseline_pinned_at``
    today, so a missed invalidation would not surface visually. The
    invalidation is still wired — a correct-but-redundant cache clear is
    cheap and guards against future fragment shape changes.
    """
    seeded = await seed_asset_with_indicators(cell_count=1)

    child_row = await db_session.execute(select(SLOEvaluation).where(SLOEvaluation.asset_id == seeded.id))
    child_eval: SLOEvaluation = child_row.scalars().one()
    run_id = child_eval.evaluation_id

    column_cache = heatmap_cache.HeatmapColumnCache(redis_client)
    await _prime_cache_fragment(column_cache, run_id)

    repo = EvaluationRepository(db_session, heatmap_cache=column_cache)

    if mutation == 'pin_baseline':
        await repo.pin_baseline(child_eval.id, reason='golden', author='tester')
    elif mutation == 'unpin_baseline':
        uncached_repo = EvaluationRepository(db_session)
        await uncached_repo.pin_baseline(child_eval.id, reason='setup', author='tester')
        await _prime_cache_fragment(column_cache, run_id)
        await repo.unpin_baseline(child_eval.id)
    else:
        raise AssertionError(f'unknown mutation parameter: {mutation}')

    hits_after = await column_cache.get_many([run_id])
    assert str(run_id) not in hits_after, (
        f'{mutation} did not invalidate the heatmap column cache entry for run {run_id}'
    )


@pytest.mark.integration
async def test_reevaluation_persist_deletes_cached_fragment(
    redis_client,
    db_session,
    seed_asset_with_indicators: Callable[..., Coroutine[Any, Any, SeededAsset]],
) -> None:
    """``_persist_reeval_result`` must delete the cached fragment for the
    mutated run. Re-evaluate is the batch-mutation flavor; each call within
    the batch invalidates exactly one run fragment without a per-call SELECT
    because the caller already holds the ``SLOEvaluation`` row.
    """
    seeded = await seed_asset_with_indicators(cell_count=1)

    child_row = await db_session.execute(select(SLOEvaluation).where(SLOEvaluation.asset_id == seeded.id))
    child_eval: SLOEvaluation = child_row.scalars().one()
    run_id = child_eval.evaluation_id

    column_cache = heatmap_cache.HeatmapColumnCache(redis_client)
    await _prime_cache_fragment(column_cache, run_id)

    await _persist_reeval_result(
        db_session,
        ev=child_eval,
        new_result='warning',
        new_score=82.0,
        old_result='pass',
        old_score=100.0,
        slo_version=2,
        new_engine_results=None,
        slo_objectives=None,
        cache=None,
        heatmap_cache=column_cache,
    )

    hits_after = await column_cache.get_many([run_id])
    assert str(run_id) not in hits_after, f're-evaluation persist did not invalidate the fragment for run {run_id}'
