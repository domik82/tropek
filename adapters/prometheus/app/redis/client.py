"""Redis connection pool lifecycle."""

from __future__ import annotations

from typing import Any

import redis.asyncio as redis


async def create_redis_pool(url: str) -> redis.Redis[Any]:
    """Create and return an async Redis connection pool from the given URL."""
    return redis.from_url(url, decode_responses=True)
