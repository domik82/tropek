# Quality Platform Phase 1 — Chunk 4: Job Queue, Reliability, and Watchdog

> **For agentic workers:** Use superpowers:executing-plans to implement this chunk.
> **Depends on:** Chunks 1, 2, 3

**Goal:** arq job queue for evaluation jobs, retry logic with tenacity, job status lifecycle, soft/hard rerun endpoint, watchdog for stuck jobs.

---

## Chunk 4: Queue and Reliability

### Task 4.1: arq Worker Settings

**Files:**
- Create: `quality-gate-api/app/worker.py`
- Create: `quality-gate-api/app/cache/redis.py`
- Create: `quality-gate-api/app/cache/__init__.py`

- [ ] Create Redis client `app/cache/redis.py`

```python
# app/cache/redis.py
from __future__ import annotations

import hashlib
import json
from typing import Any

import redis.asyncio as aioredis

from app.config import get_settings

_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        settings = get_settings()
        _client = aioredis.from_url(
            settings.cache.url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _client


def get_queue_redis() -> aioredis.Redis:
    """Separate Redis connection for the job queue (different db index)."""
    settings = get_settings()
    pw = settings.cache.password.get_secret_value()
    auth = f":{pw}@" if pw else ""
    url = f"redis://{auth}{settings.cache.host}:{settings.cache.port}/{settings.queue.db_index}"
    return aioredis.from_url(url, encoding="utf-8", decode_responses=True)


async def cache_get(key: str) -> Any | None:
    client = get_redis()
    raw = await client.get(key)
    return json.loads(raw) if raw else None


async def cache_set(key: str, value: Any, ttl: int) -> None:
    client = get_redis()
    await client.setex(key, ttl, json.dumps(value))


async def cache_delete_pattern(pattern: str) -> None:
    client = get_redis()
    keys = await client.keys(pattern)
    if keys:
        await client.delete(*keys)


def make_cache_key(*parts: str) -> str:
    return ":".join(parts)


def hash_filter(**kwargs: Any) -> str:
    payload = json.dumps(kwargs, sort_keys=True)
    return hashlib.md5(payload.encode()).hexdigest()
```

- [ ] Create `app/worker.py`

```python
# app/worker.py
from __future__ import annotations

import asyncio
import socket
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from arq import ArqRedis
from arq.connections import RedisSettings

from app.config import get_settings

logger = structlog.get_logger()
_WORKER_ID = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"


async def run_evaluation_job(
    ctx: dict[str, Any],
    eval_id: str,
) -> dict[str, Any]:
    """
    arq job function: orchestrate a single evaluation.

    Marks the evaluation as 'running', calls the adapter (pull mode)
    or processes inline metrics (push/file), runs the evaluation engine,
    writes results. On any exception: marks as 'failed'.
    """
    from app.db.session import get_session
    from app.modules.quality_gate.repository import EvaluationRepository

    settings = get_settings()
    eval_uuid = uuid.UUID(eval_id)

    async with get_session() as session:
        repo = EvaluationRepository(session)
        await repo.mark_running(eval_uuid, _WORKER_ID)

    log = logger.bind(eval_id=eval_id, worker=_WORKER_ID)
    log.info("Evaluation job started")

    try:
        result = await _execute_evaluation(eval_uuid, settings)
        log.info("Evaluation job completed", result=result["result"])
        return result
    except Exception as exc:
        log.error("Evaluation job failed", error=str(exc))
        async with get_session() as session:
            repo = EvaluationRepository(session)
            retry_count = ctx.get("job_try", 1)
            await repo.mark_failed(eval_uuid, error=str(exc), retry_count=retry_count)
        raise  # let arq handle retry


async def _execute_evaluation(
    eval_uuid: uuid.UUID,
    settings: Any,
) -> dict[str, Any]:
    from app.db.session import get_session
    from app.modules.quality_gate.repository import EvaluationRepository
    from app.modules.quality_gate.engine.evaluator import evaluate
    from app.adapters.client import AdapterClient
    from app.cache.redis import cache_delete_pattern

    async with get_session() as session:
        repo = EvaluationRepository(session)
        ev = await repo.get(eval_uuid)
        if ev is None:
            raise ValueError(f"Evaluation {eval_uuid} not found")

    # Get metrics: either from stored inline payload or via adapter
    job_stats = ev.job_stats or {}
    ingestion_mode = ev.ingestion_mode

    if ingestion_mode == "push":
        metrics: dict[str, float | None] = job_stats.get("metrics", {})
    elif ingestion_mode == "file":
        metrics = job_stats.get("metrics", {})
    else:  # pull
        adapter_url = job_stats.get("adapter_url", settings.adapters.prometheus.url)
        sli_yaml = job_stats.get("sli_yaml", "")
        variables = job_stats.get("variables", {})
        indicators = job_stats.get("indicators", [])

        client = AdapterClient(
            base_url=adapter_url,
            timeout=settings.reliability.adapter_timeout_seconds,
            retry_attempts=settings.reliability.adapter_retry_attempts,
            retry_backoff=settings.reliability.adapter_retry_backoff_seconds,
        )
        adapter_result = await client.query(
            indicators=indicators,
            start=ev.start_time.isoformat(),
            end=ev.end_time.isoformat(),
            variables=variables,
            sli_yaml=sli_yaml,
        )
        metrics = adapter_result.metrics

    # Fetch baselines for relative criteria
    slo_yaml_text = job_stats.get("resolved_slo_yaml", "")
    from app.modules.quality_gate.engine.slo_parser import parse_slo
    slo = parse_slo(slo_yaml_text)

    baselines: dict[str, float | None] = {}
    compared_ids: list[str] = []
    if slo.comparison.compare_with != "none":
        async with get_session() as session:
            repo = EvaluationRepository(session)
            prev_evals = await repo.get_baselines(
                name=ev.name,
                scope_tags=slo.comparison.scope_tags,
                asset_snapshot=ev.asset_snapshot,
                include_result_with_score=slo.comparison.include_result_with_score,
                limit=slo.comparison.number_of_comparison_results,
            )
        if prev_evals:
            compared_ids = [str(e.id) for e in prev_evals]
            # Aggregate baseline values per metric
            for obj in slo.objectives:
                values = []
                for prev in prev_evals:
                    for ir in (prev.indicator_results or []):
                        if ir.get("metric") == obj.sli and ir.get("value") is not None:
                            values.append(float(ir["value"]))
                if values:
                    agg = slo.comparison.aggregate_function
                    if agg == "avg":
                        baselines[obj.sli] = sum(values) / len(values)
                    elif agg in ("p90", "p95", "p99"):
                        pct = int(agg[1:]) / 100
                        sorted_vals = sorted(values)
                        idx = int(len(sorted_vals) * pct)
                        baselines[obj.sli] = sorted_vals[min(idx, len(sorted_vals) - 1)]

    # Run pure evaluation engine
    result = evaluate(slo_yaml_text, metrics, baselines, compared_evaluation_ids=compared_ids)

    # Write sli_values rows
    sli_rows = [
        {
            "eval_id": eval_uuid,
            "eval_start": ev.start_time,
            "metric_name": ir["metric"],
            "aggregation": "raw",
            "value": ir["value"] or 0.0,
            "asset_name": ev.asset_snapshot.get("name"),
            "test_name": ev.name,
            "os_tag": ev.asset_snapshot.get("tags", {}).get("os"),
        }
        for ir in result.indicator_results
        if ir.get("value") is not None
    ]

    async with get_session() as session:
        repo = EvaluationRepository(session)
        await repo.write_sli_values(sli_rows)
        await repo.mark_completed(
            eval_uuid,
            result=result.result,
            score=result.score,
            slo_yaml=slo_yaml_text,
            indicator_results=result.indicator_results,
            compared_evaluation_ids=compared_ids,
        )

    # Invalidate caches
    await cache_delete_pattern(f"evals:list:*")
    await cache_delete_pattern(f"trend:{ev.name}:*")
    await cache_delete_pattern(f"eval:{eval_uuid}")

    return {"result": result.result, "score": result.score}


async def run_watchdog(ctx: dict[str, Any]) -> None:
    """Periodic task: find stuck running jobs and reschedule them."""
    from app.db.session import get_session
    from app.modules.quality_gate.repository import EvaluationRepository

    settings = get_settings()
    log = logger.bind(task="watchdog")

    async with get_session() as session:
        repo = EvaluationRepository(session)
        stuck = await repo.find_stuck(settings.reliability.stuck_job_threshold_seconds)

    for ev in stuck:
        log.warning("Found stuck evaluation, rescheduling", eval_id=str(ev.id))
        arq_redis: ArqRedis = ctx["redis"]
        await arq_redis.enqueue_job("run_evaluation_job", str(ev.id))

    log.info("Watchdog complete", stuck_count=len(stuck))


class WorkerSettings:
    functions = [run_evaluation_job]
    cron_jobs = []  # watchdog added below
    on_startup = None
    on_shutdown = None
    max_jobs = 20
    job_timeout = 120

    @classmethod
    def _get_redis_settings(cls) -> RedisSettings:
        settings = get_settings()
        pw = settings.cache.password.get_secret_value()
        return RedisSettings(
            host=settings.cache.host,
            port=settings.cache.port,
            database=settings.queue.db_index,
            password=pw or None,
        )

    redis_settings = property(lambda self: WorkerSettings._get_redis_settings())
    retry_jobs = True
    max_tries = 3


# Add watchdog as cron every 60s
from arq import cron
WorkerSettings.cron_jobs = [
    cron(run_watchdog, second={0})  # runs at :00 of every minute
]
```

- [ ] Commit

```bash
git add app/worker.py app/cache/
git commit -m "feat: arq worker with evaluation job, watchdog cron, retry on failure"
```

---

### Task 4.2: Adapter HTTP Client with Retry

**Files:**
- Create: `quality-gate-api/app/adapters/__init__.py`
- Create: `quality-gate-api/app/adapters/client.py`
- Create: `quality-gate-api/tests/test_adapter_client.py`

- [ ] Write failing tests

```python
# tests/test_adapter_client.py
import pytest
import httpx
from pytest_httpx import HTTPXMock
from app.adapters.client import AdapterClient, AdapterResponse


@pytest.fixture
def client() -> AdapterClient:
    return AdapterClient(
        base_url="http://adapter:8081",
        timeout=5,
        retry_attempts=2,
        retry_backoff=0,
    )


async def test_query_returns_metrics(httpx_mock: HTTPXMock, client: AdapterClient) -> None:
    httpx_mock.add_response(
        method="POST",
        url="http://adapter:8081/query",
        json={"metrics": {"cpu": 55.3, "memory": 1024.0}, "errors": {}},
    )
    result = await client.query(
        indicators=["cpu", "memory"],
        start="2026-03-12T10:00:00Z",
        end="2026-03-12T10:30:00Z",
        variables={"vm_ip": "10.0.0.1"},
        sli_yaml="...",
    )
    assert result.metrics["cpu"] == 55.3
    assert result.errors == {}


async def test_query_retries_on_500(httpx_mock: HTTPXMock, client: AdapterClient) -> None:
    httpx_mock.add_response(status_code=500)
    httpx_mock.add_response(
        json={"metrics": {"cpu": 42.0}, "errors": {}},
    )
    result = await client.query(
        indicators=["cpu"],
        start="2026-03-12T10:00:00Z",
        end="2026-03-12T10:30:00Z",
        variables={},
        sli_yaml="...",
    )
    assert result.metrics["cpu"] == 42.0


async def test_query_raises_after_all_retries(httpx_mock: HTTPXMock, client: AdapterClient) -> None:
    httpx_mock.add_response(status_code=503)
    httpx_mock.add_response(status_code=503)
    httpx_mock.add_response(status_code=503)
    with pytest.raises(httpx.HTTPStatusError):
        await client.query(
            indicators=["cpu"],
            start="2026-03-12T10:00:00Z",
            end="2026-03-12T10:30:00Z",
            variables={},
            sli_yaml="...",
        )


async def test_health_check(httpx_mock: HTTPXMock, client: AdapterClient) -> None:
    httpx_mock.add_response(json={"status": "ok", "datasource": "prometheus"})
    ok = await client.health()
    assert ok is True


async def test_health_returns_false_on_error(httpx_mock: HTTPXMock, client: AdapterClient) -> None:
    httpx_mock.add_response(status_code=503)
    ok = await client.health()
    assert ok is False
```

- [ ] Run — expect failure

```bash
uv run pytest tests/test_adapter_client.py -v 2>&1 | head -5
```

- [ ] Implement `app/adapters/client.py`

```python
# app/adapters/client.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger()


@dataclass
class AdapterResponse:
    metrics: dict[str, float | None] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


class AdapterClient:
    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        retry_attempts: int = 3,
        retry_backoff: int = 2,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._retry_attempts = retry_attempts
        self._retry_backoff = retry_backoff

    async def query(
        self,
        *,
        indicators: list[str],
        start: str,
        end: str,
        variables: dict[str, str],
        sli_yaml: str,
    ) -> AdapterResponse:
        payload = {
            "indicators": indicators,
            "start": start,
            "end": end,
            "variables": variables,
            "sli_yaml": sli_yaml,
        }
        log = logger.bind(adapter=self._base_url, indicators=len(indicators))

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._retry_attempts),
            wait=wait_exponential(multiplier=self._retry_backoff, min=1, max=30),
            retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = client.post(f"{self._base_url}/query", json=payload)
                    response = await resp
                    response.raise_for_status()
                    data = response.json()
                    log.debug("Adapter query succeeded")
                    return AdapterResponse(
                        metrics=data.get("metrics", {}),
                        errors=data.get("errors", {}),
                    )

        # tenacity reraises, so this is unreachable — satisfy mypy
        raise RuntimeError("Adapter query failed after all retries")

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False
```

- [ ] Run tests

```bash
uv run pytest tests/test_adapter_client.py -v
```

Expected: all pass.

- [ ] Commit

```bash
git add app/adapters/ tests/test_adapter_client.py
git commit -m "feat: adapter HTTP client with tenacity retry logic"
```

---

### Task 4.3: Rerun Endpoint Logic

**Files:**
- Create: `quality-gate-api/app/modules/quality_gate/rerun.py`
- Create: `quality-gate-api/tests/test_rerun.py`

- [ ] Write failing tests

```python
# tests/test_rerun.py
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.modules.quality_gate.rerun import execute_rerun, RerunMode


@pytest.fixture
def eval_id() -> uuid.UUID:
    return uuid.uuid4()


async def test_soft_rerun_only_requeues(eval_id: uuid.UUID) -> None:
    """Soft rerun re-enqueues job without clearing existing sli_values."""
    mock_repo = AsyncMock()
    mock_repo.get.return_value = MagicMock(
        id=eval_id, status="partial", job_stats={}
    )
    mock_arq = AsyncMock()

    with patch("app.modules.quality_gate.rerun.EvaluationRepository", return_value=mock_repo):
        await execute_rerun(
            eval_id=eval_id,
            mode=RerunMode.SOFT,
            reason="partial timeout",
            triggered_by="user",
            session=AsyncMock(),
            arq_redis=mock_arq,
        )

    mock_repo.delete_sli_values.assert_not_called()
    mock_arq.enqueue_job.assert_called_once_with("run_evaluation_job", str(eval_id))


async def test_hard_rerun_clears_sli_values(eval_id: uuid.UUID) -> None:
    """Hard rerun deletes existing sli_values before re-enqueuing."""
    mock_repo = AsyncMock()
    mock_repo.get.return_value = MagicMock(
        id=eval_id, status="completed", job_stats={}
    )
    mock_arq = AsyncMock()

    with patch("app.modules.quality_gate.rerun.EvaluationRepository", return_value=mock_repo):
        await execute_rerun(
            eval_id=eval_id,
            mode=RerunMode.HARD,
            reason="prometheus returned zeros",
            triggered_by="ops-team",
            session=AsyncMock(),
            arq_redis=mock_arq,
        )

    mock_repo.delete_sli_values.assert_called_once_with(eval_id)
    mock_arq.enqueue_job.assert_called_once_with("run_evaluation_job", str(eval_id))


async def test_rerun_adds_annotation(eval_id: uuid.UUID) -> None:
    mock_repo = AsyncMock()
    mock_repo.get.return_value = MagicMock(id=eval_id, status="failed", job_stats={})
    mock_arq = AsyncMock()

    with patch("app.modules.quality_gate.rerun.EvaluationRepository", return_value=mock_repo):
        await execute_rerun(
            eval_id=eval_id,
            mode=RerunMode.HARD,
            reason="bad data",
            triggered_by="jane",
            session=AsyncMock(),
            arq_redis=mock_arq,
        )

    mock_repo.add_annotation.assert_called_once()
    call_kwargs = mock_repo.add_annotation.call_args.kwargs
    assert call_kwargs["category"] == "rerun"
    assert "hard" in call_kwargs["content"].lower()
```

- [ ] Implement `app/modules/quality_gate/rerun.py`

```python
# app/modules/quality_gate/rerun.py
from __future__ import annotations

import uuid
from enum import Enum

from arq import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.quality_gate.repository import EvaluationRepository


class RerunMode(str, Enum):
    SOFT = "soft"
    HARD = "hard"


async def execute_rerun(
    *,
    eval_id: uuid.UUID,
    mode: RerunMode,
    reason: str,
    triggered_by: str | None,
    session: AsyncSession,
    arq_redis: ArqRedis,
) -> None:
    repo = EvaluationRepository(session)
    ev = await repo.get(eval_id)
    if ev is None:
        raise ValueError(f"Evaluation {eval_id} not found")

    if mode == RerunMode.HARD:
        await repo.delete_sli_values(eval_id)

    # Reset status to pending
    from sqlalchemy import update
    from app.db.models import Evaluation
    await session.execute(
        update(Evaluation)
        .where(Evaluation.id == eval_id)
        .values(status="pending", result=None, score=None)
    )

    # Auto-annotation
    content = (
        f"{'Hard' if mode == RerunMode.HARD else 'Soft'} rerun triggered: {reason}"
    )
    await repo.add_annotation(
        eval_id,
        content=content,
        author=triggered_by,
        category="rerun",
        meta={"rerun_mode": mode.value, "triggered_by": triggered_by},
    )

    await arq_redis.enqueue_job("run_evaluation_job", str(eval_id))
```

- [ ] Run tests

```bash
uv run pytest tests/test_rerun.py -v
```

- [ ] Commit

```bash
git add app/modules/quality_gate/rerun.py tests/test_rerun.py
git commit -m "feat: soft/hard rerun logic with auto-annotation"
```
