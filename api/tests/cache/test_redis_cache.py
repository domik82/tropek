"""Unit tests for Redis cache utility (uses fakeredis)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from tropek.cache.redis_cache import RedisCache


@pytest.fixture
def mock_redis():
    """Provide a mock Redis client."""
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock()
    r.delete = AsyncMock()
    return r


async def test_cache_miss_calls_loader(mock_redis) -> None:
    cache = RedisCache(mock_redis)
    loader = AsyncMock(return_value='{"name": "test-slo", "version": 1}')

    result = await cache.get_or_load('slo:test:v1', loader)

    assert result == '{"name": "test-slo", "version": 1}'
    loader.assert_called_once()
    mock_redis.set.assert_called_once_with('slo:test:v1', '{"name": "test-slo", "version": 1}')


async def test_cache_hit_skips_loader(mock_redis) -> None:
    mock_redis.get = AsyncMock(return_value=b'{"cached": true}')
    cache = RedisCache(mock_redis)
    loader = AsyncMock()

    result = await cache.get_or_load('key', loader)

    assert result == '{"cached": true}'
    loader.assert_not_called()


async def test_cache_with_ttl(mock_redis) -> None:
    cache = RedisCache(mock_redis)
    loader = AsyncMock(return_value='{"data": 1}')

    await cache.get_or_load('key', loader, ttl_seconds=300)

    mock_redis.set.assert_called_once_with('key', '{"data": 1}', ex=300)


async def test_invalidate_key(mock_redis) -> None:
    cache = RedisCache(mock_redis)
    await cache.invalidate('slo:test:latest')
    mock_redis.delete.assert_called_once_with('slo:test:latest')


async def test_cache_miss_loader_returns_none(mock_redis) -> None:
    """If loader returns None, don't cache it."""
    cache = RedisCache(mock_redis)
    loader = AsyncMock(return_value=None)

    result = await cache.get_or_load('key', loader)

    assert result is None
    mock_redis.set.assert_not_called()
