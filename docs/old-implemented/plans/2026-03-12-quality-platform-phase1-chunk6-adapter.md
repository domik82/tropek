# Quality Platform Phase 1 — Chunk 6: Prometheus Adapter

> **For agentic workers:** Use superpowers:executing-plans to implement this chunk.
> **Depends on:** Chunks 1–5

**Goal:** Prometheus adapter service fully functional with PromQL query, variable substitution, per-indicator retry, and concurrency limiting.

---

## Chunk 6a: Prometheus Adapter

### Task 6.1: Adapter Query Endpoint

**Files:**
- Create: `adapter-prometheus/app/router.py`
- Create: `adapter-prometheus/app/schemas.py`
- Create: `adapter-prometheus/app/prometheus_client.py`
- Create: `adapter-prometheus/tests/test_router.py`

- [ ] Write failing tests

```python
# adapter-prometheus/tests/test_router.py
import pytest
from httpx import AsyncClient, ASGITransport
from pytest_httpx import HTTPXMock

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_query_substitutes_variables(
    client: AsyncClient, httpx_mock: HTTPXMock
) -> None:
    # Mock Prometheus instant query response
    httpx_mock.add_response(
        url__startswith="http://localhost:9090/api/v1/query",
        json={
            "status": "success",
            "data": {"resultType": "vector", "result": [{"value": [1710000000, "450.3"]}]},
        },
    )
    sli_yaml = """spec_version: '1.0'
indicators:
  cpu: 'avg_over_time(cpu{instance="$vm_ip"}[5m])'
"""
    resp = await client.post("/query", json={
        "indicators": ["cpu"],
        "start": "2026-03-12T10:00:00Z",
        "end": "2026-03-12T10:30:00Z",
        "variables": {"vm_ip": "10.0.0.1"},
        "sli_yaml": sli_yaml,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "cpu" in data["metrics"]
    assert data["metrics"]["cpu"] == pytest.approx(450.3)


async def test_query_missing_indicator_returns_error(
    client: AsyncClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        url__startswith="http://localhost:9090",
        json={"status": "success", "data": {"resultType": "vector", "result": []}},
    )
    sli_yaml = "spec_version: '1.0'\nindicators:\n  missing_metric: 'empty_query()'\n"
    resp = await client.post("/query", json={
        "indicators": ["missing_metric"],
        "start": "2026-03-12T10:00:00Z",
        "end": "2026-03-12T10:30:00Z",
        "variables": {},
        "sli_yaml": sli_yaml,
    })
    assert resp.status_code == 200
    assert "missing_metric" in resp.json()["errors"]


async def test_query_unresolved_variable_returns_422(client: AsyncClient) -> None:
    sli_yaml = "spec_version: '1.0'\nindicators:\n  cpu: 'cpu{instance=\"$unset\"}'\n"
    resp = await client.post("/query", json={
        "indicators": ["cpu"],
        "start": "2026-03-12T10:00:00Z",
        "end": "2026-03-12T10:30:00Z",
        "variables": {},
        "sli_yaml": sli_yaml,
    })
    assert resp.status_code == 422
```

- [ ] Create `app/schemas.py`

```python
# adapter-prometheus/app/schemas.py
from __future__ import annotations
from pydantic import BaseModel


class QueryRequest(BaseModel):
    indicators: list[str]
    start: str
    end: str
    variables: dict[str, str] = {}
    sli_yaml: str


class QueryResponse(BaseModel):
    metrics: dict[str, float | None] = {}
    errors: dict[str, str] = {}
```

- [ ] Create `app/prometheus_client.py`

```python
# adapter-prometheus/app/prometheus_client.py
from __future__ import annotations

import re
from datetime import datetime

import httpx
import structlog
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = structlog.get_logger()
_VAR_RE = re.compile(r"\$([a-zA-Z_][a-zA-Z0-9_]*)")


def substitute(template: str, variables: dict[str, str]) -> str:
    def replace(m: re.Match[str]) -> str:
        name = m.group(1)
        if name not in variables:
            raise ValueError(f"Unresolved variable: ${name}")
        return variables[name]
    return _VAR_RE.sub(replace, template)


async def query_scalar(
    query: str,
    end: str,
    timeout: int,
    retry_attempts: int,
    retry_backoff: int,
) -> float | None:
    """Execute a PromQL instant query at `end` time and return single scalar."""
    settings = get_settings()
    url = f"{settings.prometheus_url}/api/v1/query"
    ts = datetime.fromisoformat(end.replace("Z", "+00:00")).timestamp()

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(retry_attempts),
        wait=wait_exponential(multiplier=retry_backoff, min=1, max=30),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        reraise=True,
    ):
        with attempt:
            auth = None
            s = settings
            if s.username:
                auth = (s.username, s.password.get_secret_value())
            async with httpx.AsyncClient(timeout=timeout, auth=auth) as client:
                resp = await client.get(url, params={"query": query, "time": ts})
                resp.raise_for_status()
                data = resp.json()

    if data["status"] != "success":
        return None
    results = data["data"]["result"]
    if not results:
        return None
    try:
        return float(results[0]["value"][1])
    except (IndexError, KeyError, ValueError):
        return None
```

- [ ] Create `app/router.py`

```python
# adapter-prometheus/app/router.py
from __future__ import annotations

import asyncio

import structlog
import yaml
from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.prometheus_client import query_scalar, substitute
from app.schemas import QueryRequest, QueryResponse

router = APIRouter()
logger = structlog.get_logger()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "datasource": "prometheus"}


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    settings = get_settings()

    # Parse SLI YAML to get indicator→query map
    try:
        sli_data = yaml.safe_load(req.sli_yaml) or {}
        indicators_map: dict[str, str] = sli_data.get("indicators", {})
    except yaml.YAMLError as e:
        raise HTTPException(422, f"Invalid sli_yaml: {e}") from e

    # Apply variable substitution
    try:
        resolved_queries = {
            name: substitute(query, req.variables)
            for name, query in indicators_map.items()
            if name in req.indicators
        }
    except ValueError as e:
        raise HTTPException(422, str(e)) from e

    # Execute queries with concurrency limit
    sem = asyncio.Semaphore(10)
    metrics: dict[str, float | None] = {}
    errors: dict[str, str] = {}

    async def execute_one(name: str, promql: str) -> None:
        async with sem:
            try:
                value = await query_scalar(
                    promql,
                    req.end,
                    timeout=settings.timeout_seconds,
                    retry_attempts=settings.retry_attempts,
                    retry_backoff=settings.retry_backoff_seconds,
                )
                if value is None:
                    errors[name] = "no data in time range"
                else:
                    metrics[name] = value
            except Exception as exc:
                logger.warning("Indicator query failed", indicator=name, error=str(exc))
                errors[name] = str(exc)

    await asyncio.gather(*[execute_one(n, q) for n, q in resolved_queries.items()])
    return QueryResponse(metrics=metrics, errors=errors)
```

- [ ] Update `app/main.py`

```python
# adapter-prometheus/app/main.py
from fastapi import FastAPI
from app.router import router

app = FastAPI(title="Prometheus Adapter", version="0.1.0")
app.include_router(router)
```

- [ ] Run tests

```bash
cd adapter-prometheus
uv run pytest tests/ -v
```

- [ ] Commit

```bash
git add .
git commit -m "feat: Prometheus adapter with PromQL query, variable substitution, per-indicator retry"
```

