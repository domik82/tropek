"""Generic read-through Redis cache utility."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


class RedisCache:
    """Read-through cache with optional TTL and manual invalidation."""

    def __init__(self, redis: Any) -> None:
        self._redis = redis

    @property
    def client(self) -> Any:
        """The underlying ``redis.asyncio`` client.

        Exposed so cache-fragment helpers (heatmap/trend column caches) and the
        worker warm path can share the single client this ``RedisCache`` owns,
        without reaching through the private attribute.
        """
        return self._redis

    async def get_or_load(
        self,
        key: str,
        loader: Callable[[], Awaitable[str | None]],
        ttl_seconds: int | None = None,
    ) -> str | None:
        """Return cached value or call loader, cache result, and return it."""
        cached = await self._redis.get(key)
        if cached is not None:
            return cached.decode() if isinstance(cached, bytes) else cached

        value = await loader()
        if value is None:
            return None

        if ttl_seconds is not None:
            await self._redis.set(key, value, ex=ttl_seconds)
        else:
            await self._redis.set(key, value)
        return value

    async def invalidate(self, key: str) -> None:
        """Remove a cached entry."""
        await self._redis.delete(key)
