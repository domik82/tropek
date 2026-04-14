"""Integration tests for the per-column heatmap cache (Chunk C PR2).

The property test (cache_equals_uncached_after_mutation) lives in a follow-up
task (Task 12). These tests cover the raw cache module: key shape, MGET, SET,
DELETE, and corrupt-payload handling.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from tropek.modules.quality_gate.schemas.heatmap import (
    EvaluationColumn,
    HeatmapColumnFragment,
    HeatmapSummaryCell,
)
from tropek.modules.quality_gate.workflows.presentation import heatmap_cache


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
