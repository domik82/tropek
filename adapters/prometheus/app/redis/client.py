"""Redis connection pool lifecycle."""

import redis.asyncio as redis


async def create_redis_pool(url: str) -> redis.Redis:
    return redis.from_url(url, decode_responses=True)
