"""Job state CRUD on Redis keys."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis


def _decode(value: Any) -> Any:
    """Decode bytes to str if needed (handles fakeredis without decode_responses)."""
    if isinstance(value, bytes):
        return value.decode()
    return value


def _decode_mapping(mapping: dict[Any, Any]) -> dict[str, Any]:
    """Decode all keys and values in a mapping from bytes to str if needed."""
    return {_decode(k): _decode(v) for k, v in mapping.items()}


class JobRepository:
    """Manages job state in Redis using hash + list keys."""

    def __init__(self, redis_client: Redis[Any], prefix: str = "prom-sli:") -> None:
        self._r = redis_client
        self._p = prefix

    def _key(self, *parts: str) -> str:
        return self._p + ":".join(parts)

    async def create_job(
        self,
        queries: dict[str, dict[str, Any]],
        variables: dict[str, str],
        timeout: int,
        start: str = "",
        end: str = "",
    ) -> str:
        """Create a new job in Redis and return the generated job ID."""
        job_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        await self._r.hset(
            self._key("job", job_id),
            mapping={
                "status": "queued",
                "created_at": now,
                "total_queries": str(len(queries)),
                "completed_count": "0",
                "failed_count": "0",
                "timeout": str(timeout),
                "variables": json.dumps(variables),
                "start": start,
                "end": end,
            },
        )
        await self._r.set(
            self._key("job", job_id, "queries"),
            json.dumps(queries),
        )
        return job_id

    async def get_status(self, job_id: str) -> dict[str, Any] | None:
        """Return the status hash for a job, or None if the job does not exist."""
        raw = await self._r.hgetall(self._key("job", job_id))
        if not raw:
            return None
        data = _decode_mapping(raw)
        return {
            "job_id": job_id,
            "status": data["status"],
            "created_at": data["created_at"],
            "total_queries": int(data["total_queries"]),
            "completed_count": int(data["completed_count"]),
            "failed_count": int(data["failed_count"]),
            "completed_at": data.get("completed_at"),
            "duration_ms": int(data["duration_ms"]) if "duration_ms" in data else None,
        }

    async def get_queries(self, job_id: str) -> dict[str, dict[str, Any]]:
        """Return the query specs stored for a job."""
        raw = await self._r.get(self._key("job", job_id, "queries"))
        return json.loads(_decode(raw)) if raw else {}

    async def get_variables(self, job_id: str) -> dict[str, str]:
        """Return the template variables stored for a job."""
        raw = await self._r.hget(self._key("job", job_id), "variables")
        return json.loads(_decode(raw)) if raw else {}

    async def get_start_end(self, job_id: str) -> tuple[str, str]:
        """Return the (start, end) ISO timestamps stored for a job."""
        data = await self._r.hmget(self._key("job", job_id), "start", "end")
        s, e = _decode(data[0]), _decode(data[1])
        return s or "", e or ""

    async def mark_running(self, job_id: str) -> None:
        """Transition a job to the running state and record the start timestamp."""
        now = datetime.now(UTC).isoformat()
        await self._r.hset(
            self._key("job", job_id),
            mapping={"status": "running", "started_at": now},
        )

    async def write_result(
        self,
        job_id: str,
        indicator: str,
        *,
        value: float | None,
        success: bool,
        message: str,
        query_executed: str = "",
    ) -> None:
        """Persist a single indicator result and increment the success or failure counter."""
        result = json.dumps({
            "value": value,
            "success": success,
            "message": message,
            "query_executed": query_executed,
        })
        await self._r.hset(self._key("job", job_id, "results"), indicator, result)
        if success:
            await self._r.hincrby(self._key("job", job_id), "completed_count", 1)
        else:
            await self._r.hincrby(self._key("job", job_id), "failed_count", 1)

    async def get_results(self, job_id: str) -> dict[str, dict[str, Any]]:
        """Return all indicator results stored for a job."""
        raw = await self._r.hgetall(self._key("job", job_id, "results"))
        return {_decode(k): json.loads(_decode(v)) for k, v in raw.items()}

    async def mark_completed(self, job_id: str, retention_seconds: int) -> None:
        """Transition a job to completed, compute duration, and set TTL on all keys."""
        now = datetime.now(UTC).isoformat()
        job_key = self._key("job", job_id)
        created = _decode(await self._r.hget(job_key, "created_at"))
        duration_ms = 0
        if created:
            start = datetime.fromisoformat(created)
            duration_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)
        await self._r.hset(
            job_key,
            mapping={
                "status": "completed",
                "completed_at": now,
                "duration_ms": str(duration_ms),
            },
        )
        await self._r.expire(job_key, retention_seconds)
        await self._r.expire(self._key("job", job_id, "results"), retention_seconds)
        await self._r.expire(self._key("job", job_id, "queries"), retention_seconds)

    async def mark_timed_out(self, job_id: str, retention_seconds: int) -> None:
        """Transition a job to timed_out status and set TTL on the job key."""
        now = datetime.now(UTC).isoformat()
        await self._r.hset(
            self._key("job", job_id),
            mapping={"status": "timed_out", "completed_at": now},
        )
        await self._r.expire(self._key("job", job_id), retention_seconds)

    async def cancel(self, job_id: str) -> bool:
        """Cancel a job; returns False if the job is already in a terminal state."""
        status = _decode(await self._r.hget(self._key("job", job_id), "status"))
        if status in ("completed", "timed_out", "cancelled"):
            return False
        await self._r.hset(self._key("job", job_id), "status", "cancelled")
        return True

    async def enqueue(self, job_id: str) -> None:
        """Append a job ID to the tail of the pending queue."""
        await self._r.rpush(self._key("queue", "pending"), job_id)

    async def dequeue(self) -> str | None:
        """Pop and return the next job ID from the head of the pending queue."""
        result = await self._r.lpop(self._key("queue", "pending"))
        return _decode(result) if result is not None else None

    async def queue_depth(self) -> int:
        """Return the number of jobs currently waiting in the pending queue."""
        return await self._r.llen(self._key("queue", "pending"))
