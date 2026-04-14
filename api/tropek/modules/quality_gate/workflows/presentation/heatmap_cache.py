"""Per-column Redis cache for the grouped heatmap endpoint.

Each EvaluationRun's contribution to the grouped heatmap is cached as one
HeatmapColumnFragment serialized as JSON under ``heatmap:col:v{SCHEMA}:{run_id}``
with a 7-day TTL safety net. Invalidation is precise: every mutation that
changes a completed run deletes exactly that run's fragment. Schema-bumping
self-heals via the version prefix — old entries become orphans and fall out
on TTL.

The cache is opportunistic: a Redis failure NEVER blocks a read (falls back
to DB) or a write (falls back to the next reader paying the rebuild cost).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from tropek.modules.quality_gate.schemas.heatmap import HeatmapColumnFragment

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
_KEY_PREFIX = f'heatmap:col:v{SCHEMA_VERSION}'
_DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days


def column_cache_key(run_id: str | uuid.UUID) -> str:
    """Build the Redis key for a single column fragment."""
    return f'{_KEY_PREFIX}:{run_id}'


class HeatmapColumnCache:
    """Thin wrapper over redis.asyncio for HeatmapColumnFragment persistence.

    Knows how to serialize/deserialize HeatmapColumnFragment and batches gets
    and sets via MGET and a Redis pipeline.
    """

    def __init__(self, redis: Any, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    async def get_many(self, run_ids: Iterable[str | uuid.UUID]) -> dict[str, HeatmapColumnFragment]:
        """Return ``{run_id (string form): fragment}`` for every cache hit.

        Misses and corrupt payloads are silently omitted from the result —
        the caller falls through to the DB build path for them.
        """
        id_list = [str(run_id) for run_id in run_ids]
        if not id_list:
            return {}
        keys = [column_cache_key(run_id) for run_id in id_list]
        try:
            raw_values = await self._redis.mget(keys)
        except Exception as exc:  # noqa: BLE001 - cache must never block reads
            logger.warning('heatmap column cache mget failed: %s', exc)
            return {}
        hits: dict[str, HeatmapColumnFragment] = {}
        for run_id, raw in zip(id_list, raw_values, strict=True):
            if raw is None:
                continue
            try:
                fragment = HeatmapColumnFragment.model_validate_json(raw)
            except ValidationError as exc:
                logger.warning(
                    'heatmap column cache dropped corrupt payload for run_id=%s: %s',
                    run_id,
                    exc,
                )
                continue
            hits[run_id] = fragment
        return hits

    async def set_many(self, fragments: Iterable[HeatmapColumnFragment]) -> None:
        """Write fragments to Redis via a pipeline.

        Failures are logged and dropped — the DB is the source of truth, the
        cache is opportunistic.
        """
        fragments_list = list(fragments)
        if not fragments_list:
            return
        try:
            pipeline = self._redis.pipeline()
            for fragment in fragments_list:
                key = column_cache_key(fragment.evaluation_run_id)
                payload = fragment.model_dump_json()
                pipeline.set(key, payload, ex=self._ttl_seconds)
            await pipeline.execute()
        except Exception as exc:  # noqa: BLE001 - cache must never block writes
            logger.warning('heatmap column cache set_many failed: %s', exc)

    async def delete(self, run_id: str | uuid.UUID) -> None:
        """Delete a single column fragment. Failures logged and dropped."""
        try:
            await self._redis.delete(column_cache_key(run_id))
        except Exception as exc:  # noqa: BLE001 - cache must never block invalidation
            logger.warning('heatmap column cache delete failed for run_id=%s: %s', run_id, exc)

    async def delete_many(self, run_ids: Iterable[str | uuid.UUID]) -> None:
        """Delete multiple column fragments in a single Redis call."""
        keys = [column_cache_key(run_id) for run_id in run_ids]
        if not keys:
            return
        try:
            await self._redis.delete(*keys)
        except Exception as exc:  # noqa: BLE001 - cache must never block invalidation
            logger.warning('heatmap column cache delete_many failed: %s', exc)
