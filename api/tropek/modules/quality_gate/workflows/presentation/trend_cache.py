"""Per-SLO-evaluation Redis cache for the batched trend endpoint.

Each SLO's contribution to one EvaluationRun is cached as one
TrendColumnFragment serialized as JSON under ``trend:col:v{SCHEMA}:{slo_evaluation_id}``
with a 7-day TTL safety net. Invalidation is precise: a re-evaluation deletes
exactly that SLO-evaluation's fragment. Schema-bumping self-heals via the
version prefix — old entries become orphans and fall out on TTL.

The cache is opportunistic: a Redis failure NEVER blocks a read (falls back
to DB) or a write (falls back to the next reader paying the rebuild cost).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from tropek.modules.quality_gate.schemas.trend import TREND_FRAGMENT_SCHEMA_VERSION, TrendColumnFragment

logger = logging.getLogger(__name__)

SCHEMA_VERSION = TREND_FRAGMENT_SCHEMA_VERSION
_KEY_PREFIX = f'trend:col:v{SCHEMA_VERSION}'
_DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days


def trend_column_cache_key(slo_evaluation_id: str | uuid.UUID) -> str:
    """Build the Redis key for a single trend fragment."""
    return f'{_KEY_PREFIX}:{slo_evaluation_id}'


class TrendColumnCache:
    """Thin wrapper over redis.asyncio for TrendColumnFragment persistence.

    Knows how to serialize/deserialize TrendColumnFragment and batches gets
    and sets via MGET and a Redis pipeline.
    """

    def __init__(self, redis: Any, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    async def get_many(self, slo_evaluation_ids: Iterable[str | uuid.UUID]) -> dict[str, TrendColumnFragment]:
        """Return ``{slo_evaluation_id (string form): fragment}`` for every cache hit.

        Misses and corrupt payloads are silently omitted from the result —
        the caller falls through to the DB build path for them.
        """
        id_list = [str(slo_evaluation_id) for slo_evaluation_id in slo_evaluation_ids]
        if not id_list:
            return {}
        keys = [trend_column_cache_key(slo_evaluation_id) for slo_evaluation_id in id_list]
        try:
            raw_values = await self._redis.mget(keys)
        except Exception as error:  # noqa: BLE001 - cache must never block reads
            logger.warning('trend column cache mget failed: %s', error)
            return {}
        hits: dict[str, TrendColumnFragment] = {}
        for slo_evaluation_id, raw in zip(id_list, raw_values, strict=True):
            if raw is None:
                continue
            try:
                fragment = TrendColumnFragment.model_validate_json(raw)
            except ValidationError as error:
                logger.warning(
                    'trend column cache dropped corrupt payload for slo_evaluation_id=%s: %s',
                    slo_evaluation_id,
                    error,
                )
                continue
            hits[slo_evaluation_id] = fragment
        return hits

    async def set_many(self, fragments: Iterable[TrendColumnFragment]) -> None:
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
                key = trend_column_cache_key(fragment.slo_evaluation_id)
                payload = fragment.model_dump_json()
                pipeline.set(key, payload, ex=self._ttl_seconds)
            await pipeline.execute()
        except Exception as error:  # noqa: BLE001 - cache must never block writes
            logger.warning('trend column cache set_many failed: %s', error)

    async def delete(self, slo_evaluation_id: str | uuid.UUID) -> None:
        """Delete a single trend fragment. Failures logged and dropped."""
        try:
            await self._redis.delete(trend_column_cache_key(slo_evaluation_id))
        except Exception as error:  # noqa: BLE001 - cache must never block invalidation
            logger.warning('trend column cache delete failed for slo_evaluation_id=%s: %s', slo_evaluation_id, error)

    async def delete_many(self, slo_evaluation_ids: Iterable[str | uuid.UUID]) -> None:
        """Delete multiple trend fragments in a single Redis call."""
        keys = [trend_column_cache_key(slo_evaluation_id) for slo_evaluation_id in slo_evaluation_ids]
        if not keys:
            return
        try:
            await self._redis.delete(*keys)
        except Exception as error:  # noqa: BLE001 - cache must never block invalidation
            logger.warning('trend column cache delete_many failed: %s', error)
