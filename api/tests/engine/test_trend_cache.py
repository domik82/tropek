import uuid
from datetime import UTC, datetime
from typing import Any

from tropek.modules.quality_gate.schemas.trend import TrendColumnFragment, TrendFragmentPoint
from tropek.modules.quality_gate.workflows.presentation.trend_cache import (
    TrendColumnCache,
    trend_column_cache_key,
)


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}
        self.fail = False

    async def mget(self, keys: list[str]) -> list[bytes | None]:
        if self.fail:
            raise RuntimeError('redis down')
        return [self.store.get(key) for key in keys]

    def pipeline(self) -> 'FakePipeline':
        return FakePipeline(self)

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self.store.pop(key, None)


class FakePipeline:
    def __init__(self, redis: FakeRedis) -> None:
        self.redis = redis
        self.ops: list[tuple[str, bytes | str]] = []

    def set(self, key: str, value: bytes | str, ex: int | None = None) -> None:
        self.ops.append((key, value))

    async def execute(self) -> None:
        for key, value in self.ops:
            self.redis.store[key] = value.encode() if isinstance(value, str) else value


def _fragment(slo_evaluation_id: uuid.UUID) -> TrendColumnFragment:
    return TrendColumnFragment(
        slo_evaluation_id=slo_evaluation_id,
        slo_name='s',
        period_start=datetime(2026, 1, 1, tzinfo=UTC),
        period_end=None,
        evaluation_name='e',
        points=[TrendFragmentPoint(metric='m', value=1.0, score=10.0, result='pass', baseline=None, targets=None)],
    )


async def test_set_then_get_round_trips() -> None:
    redis: Any = FakeRedis()
    cache = TrendColumnCache(redis, ttl_seconds=60)
    slo_evaluation_id = uuid.uuid4()
    await cache.set_many([_fragment(slo_evaluation_id)])
    hits = await cache.get_many([slo_evaluation_id])
    assert str(slo_evaluation_id) in hits
    assert hits[str(slo_evaluation_id)].points[0].metric == 'm'


async def test_get_many_returns_empty_on_redis_failure() -> None:
    redis: Any = FakeRedis()
    redis.fail = True
    cache = TrendColumnCache(redis, ttl_seconds=60)
    assert await cache.get_many([uuid.uuid4()]) == {}


async def test_key_uses_versioned_prefix() -> None:
    slo_evaluation_id = uuid.uuid4()
    assert trend_column_cache_key(slo_evaluation_id) == f'trend:col:v1:{slo_evaluation_id}'
