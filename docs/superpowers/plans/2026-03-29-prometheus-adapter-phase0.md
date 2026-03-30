# Phase 0: Raw-Mode Prometheus Adapter — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Prometheus SLI adapter as a production-ready service with raw-mode query execution, async job queue, concurrency controls, and a protocol designed to accommodate future aggregated mode.

**Architecture:** Standalone FastAPI service with Redis-backed job queue. Queries are submitted as batches via POST, processed asynchronously with semaphore-limited concurrency, and polled for results. The strategy pattern isolates query mode logic — Phase 0 implements only `RawQueryStrategy`. The SLI registry gains a `mode` field (default: `raw`) to prepare for Phase 1.

**Tech Stack:** Python 3.13, FastAPI, Redis (job state + queue), httpx (async HTTP), Pydantic v2, asyncio (semaphore, background tasks), respx (HTTP mocking in tests), fakeredis (Redis mocking in tests).

**Spec:** `docs/superpowers/specs/2026-03-29-prometheus-sli-adapter-design.md`

**Current state:** `adapters/prometheus/app/main.py` has a basic synchronous `POST /query` endpoint. No job queue, no concurrency controls, no strategy pattern, no variable substitution. Tests directory exists but is empty.

---

## File Structure

### Adapter service (`adapters/prometheus/`)

```
adapters/prometheus/
  app/
    __init__.py                        # (exists)
    main.py                            # Rewrite: FastAPI app, lifespan, CORS
    config.py                          # NEW: Pydantic Settings from env vars
    api/
      __init__.py                      # NEW
      routes.py                        # NEW: POST/GET/DELETE /query-jobs endpoints
      schemas.py                       # NEW: Request/response Pydantic models
    core/
      __init__.py                      # NEW
      job_manager.py                   # NEW: Job creation, status, cancellation
      coordinator.py                   # NEW: Background task, LPOP queue, fan out
      worker.py                        # NEW: Execute single query via strategy
      strategies/
        __init__.py                    # NEW
        base.py                        # NEW: Strategy protocol
        raw.py                         # NEW: RawQueryStrategy (instant query)
      prometheus_client.py             # NEW: httpx wrapper for Prometheus API
      variable_substitutor.py          # NEW: $VARIABLE replacement
    redis/
      __init__.py                      # NEW
      client.py                        # NEW: Connection pool lifecycle
      repository.py                    # NEW: Job/result CRUD on Redis keys
    health/
      __init__.py                      # NEW
      routes.py                        # NEW: /health/live, /health/ready
  tests/
    __init__.py                        # NEW
    conftest.py                        # NEW: Shared fixtures (fakeredis, respx)
    test_variable_substitutor.py       # NEW
    test_raw_strategy.py               # NEW
    test_prometheus_client.py          # NEW
    test_job_manager.py                # NEW
    test_routes.py                     # NEW: API endpoint tests
    test_coordinator.py                # NEW
  Dockerfile                           # NEW
  pyproject.toml                       # Modify: add redis, fakeredis deps
```

### TROPEK backend changes

```
api/app/modules/sli_registry/
  schemas.py                           # Modify: add mode field
api/app/db/models.py                   # Modify: add mode column to SLIDefinition
api/app/modules/quality_gate/
  adapter_protocol.py                  # Modify: v2 protocol with mode support
  adapter_client.py                    # Modify: v2 request building
```

---

## Task 1: Adapter Config Module

**Files:**
- Create: `adapters/prometheus/app/config.py`
- Test: `adapters/prometheus/tests/test_config.py`

- [ ] **Step 1: Write failing test for config defaults**

```python
# tests/test_config.py
from app.config import Settings


def test_default_settings():
    s = Settings()
    assert s.port == 8080
    assert s.prometheus_url == "http://localhost:9090"
    assert s.redis_url == "redis://localhost:6379/0"
    assert s.redis_key_prefix == "prom-sli:"
    assert s.max_concurrent_queries == 10
    assert s.max_concurrent_jobs == 3
    assert s.max_queue_depth == 100
    assert s.max_queries_per_job == 400
    assert s.default_job_timeout_seconds == 120
    assert s.max_job_timeout_seconds == 600
    assert s.query_timeout_seconds == 30
    assert s.job_retention_seconds == 3600
    assert s.default_chunk_size == "4h"
    assert s.default_parallel_chunks == 3
    assert s.log_level == "INFO"


def test_settings_from_env(monkeypatch: object):
    import os

    monkeypatch.setenv("MAX_CONCURRENT_QUERIES", "20")
    monkeypatch.setenv("PROMETHEUS_URL", "http://prom:9090")
    s = Settings()
    assert s.max_concurrent_queries == 20
    assert s.prometheus_url == "http://prom:9090"
```

- [ ] **Step 2: Run test — expect FAIL (module not found)**

Run: `uv run --directory adapters/prometheus pytest tests/test_config.py -v`

- [ ] **Step 3: Implement config module**

```python
# app/config.py
"""Adapter configuration from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All settings have safe defaults. Override via env vars."""

    port: int = 8080
    prometheus_url: str = "http://localhost:9090"
    prometheus_username: str | None = None
    prometheus_password: str | None = None

    redis_url: str = "redis://localhost:6379/0"
    redis_key_prefix: str = "prom-sli:"

    max_concurrent_queries: int = 10
    max_concurrent_jobs: int = 3
    max_queue_depth: int = 100
    max_queries_per_job: int = 400

    default_job_timeout_seconds: int = 120
    max_job_timeout_seconds: int = 600
    query_timeout_seconds: int = 30
    job_retention_seconds: int = 3600

    default_chunk_size: str = "4h"
    default_parallel_chunks: int = 3

    log_level: str = "INFO"
```

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Commit**

```
git add adapters/prometheus/app/config.py adapters/prometheus/tests/test_config.py
git commit -m "feat(adapter): add config module with env-var-based settings"
```

---

## Task 2: Variable Substitutor

Pure function, zero dependencies. TDD is ideal here.

**Files:**
- Create: `adapters/prometheus/app/core/variable_substitutor.py`
- Test: `adapters/prometheus/tests/test_variable_substitutor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_variable_substitutor.py
import pytest

from app.core.variable_substitutor import substitute, UnresolvedVariableError


def test_simple_substitution():
    result = substitute(
        template='rate(http_requests{job="$SERVICE"}[$interval])',
        variables={"SERVICE": "carts", "interval": "5m"},
    )
    assert result == 'rate(http_requests{job="carts"}[5m])'


def test_multiple_occurrences_of_same_variable():
    result = substitute(
        template="$X + $X",
        variables={"X": "1"},
    )
    assert result == "1 + 1"


def test_no_variables():
    result = substitute(
        template="rate(http_requests[5m])",
        variables={},
    )
    assert result == "rate(http_requests[5m])"


def test_unresolved_variable_raises():
    with pytest.raises(UnresolvedVariableError, match="MISSING"):
        substitute(
            template="rate($MISSING[5m])",
            variables={},
        )


def test_dollar_sign_in_value_not_treated_as_variable():
    result = substitute(
        template='query{label="$VALUE"}',
        variables={"VALUE": "$literal"},
    )
    assert result == 'query{label="$literal"}'


def test_underscore_and_dot_in_variable_name():
    result = substitute(
        template="$LABEL.host + $my_var",
        variables={"LABEL.host": "10.0.0.1", "my_var": "test"},
    )
    assert result == "10.0.0.1 + test"


def test_duration_seconds_auto_computed():
    result = substitute(
        template="rate(metric[$DURATION_SECONDS])",
        variables={},
        start_iso="2026-01-15T10:00:00Z",
        end_iso="2026-01-15T10:05:00Z",
    )
    assert result == "rate(metric[300s])"


def test_duration_seconds_not_overridden_if_provided():
    result = substitute(
        template="rate(metric[$DURATION_SECONDS])",
        variables={"DURATION_SECONDS": "600s"},
    )
    assert result == "rate(metric[600s])"


def test_interval_reserved_in_aggregated_mode():
    """When interval_override is set, $interval resolves to it, not variables dict."""
    result = substitute(
        template="rate(metric[$interval])",
        variables={"interval": "should_be_ignored"},
        interval_override="1m",
    )
    assert result == "rate(metric[1m])"
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `uv run --directory adapters/prometheus pytest tests/test_variable_substitutor.py -v`

- [ ] **Step 3: Implement substitutor**

```python
# app/core/variable_substitutor.py
"""$VARIABLE placeholder replacement for PromQL templates."""

import math
import re
from datetime import datetime

_VAR_PATTERN = re.compile(r"\$([a-zA-Z_][a-zA-Z0-9_.]*)")


class UnresolvedVariableError(Exception):
    """Raised when a $VARIABLE has no matching value after substitution."""


def substitute(
    template: str,
    variables: dict[str, str],
    *,
    start_iso: str | None = None,
    end_iso: str | None = None,
    interval_override: str | None = None,
) -> str:
    """Replace $VARIABLE placeholders in a PromQL template.

    Args:
        template: PromQL string with $VARIABLE placeholders.
        variables: User-provided variable dict.
        start_iso: Evaluation start (ISO 8601). Used to auto-compute DURATION_SECONDS.
        end_iso: Evaluation end (ISO 8601). Used to auto-compute DURATION_SECONDS.
        interval_override: If set, $interval resolves to this value (not from variables).

    Returns:
        Substituted PromQL string.

    Raises:
        UnresolvedVariableError: If any $VARIABLE remains after substitution.
    """
    merged = dict(variables)

    if interval_override is not None:
        merged["interval"] = interval_override

    if "DURATION_SECONDS" not in merged and start_iso and end_iso:
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso)
        seconds = math.ceil((end - start).total_seconds())
        merged["DURATION_SECONDS"] = f"{seconds}s"

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in merged:
            return merged[name]
        return match.group(0)

    result = _VAR_PATTERN.sub(_replace, template)

    remaining = _VAR_PATTERN.findall(result)
    if remaining:
        raise UnresolvedVariableError(
            f"unresolved variables: {', '.join('$' + v for v in remaining)}"
        )

    return result
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```
git add adapters/prometheus/app/core/ adapters/prometheus/tests/test_variable_substitutor.py
git commit -m "feat(adapter): add variable substitutor with $VARIABLE replacement"
```

---

## Task 3: Prometheus HTTP Client

Thin wrapper around httpx for Prometheus API calls.

**Files:**
- Create: `adapters/prometheus/app/core/prometheus_client.py`
- Test: `adapters/prometheus/tests/test_prometheus_client.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_prometheus_client.py
import pytest
import respx
from httpx import Response

from app.core.prometheus_client import PrometheusClient, PrometheusQueryError


@pytest.fixture
def client():
    return PrometheusClient(base_url="http://prom:9090", timeout=5.0)


@respx.mock
@pytest.mark.asyncio
async def test_instant_query_returns_scalar(client: PrometheusClient):
    respx.get("http://prom:9090/api/v1/query").mock(
        return_value=Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [{"metric": {}, "value": [1705312800, "0.245"]}],
                },
            },
        )
    )
    value = await client.instant_query("some_query", time="2026-01-15T10:00:00Z")
    assert value == 0.245


@respx.mock
@pytest.mark.asyncio
async def test_instant_query_zero_results_raises(client: PrometheusClient):
    respx.get("http://prom:9090/api/v1/query").mock(
        return_value=Response(
            200,
            json={
                "status": "success",
                "data": {"resultType": "vector", "result": []},
            },
        )
    )
    with pytest.raises(PrometheusQueryError, match="0 results"):
        await client.instant_query("some_query", time="2026-01-15T10:00:00Z")


@respx.mock
@pytest.mark.asyncio
async def test_instant_query_multiple_results_raises(client: PrometheusClient):
    respx.get("http://prom:9090/api/v1/query").mock(
        return_value=Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [
                        {"metric": {"a": "1"}, "value": [1705312800, "1.0"]},
                        {"metric": {"a": "2"}, "value": [1705312800, "2.0"]},
                    ],
                },
            },
        )
    )
    with pytest.raises(PrometheusQueryError, match="2 results"):
        await client.instant_query("some_query", time="2026-01-15T10:00:00Z")


@respx.mock
@pytest.mark.asyncio
async def test_instant_query_nan_raises(client: PrometheusClient):
    respx.get("http://prom:9090/api/v1/query").mock(
        return_value=Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [{"metric": {}, "value": [1705312800, "NaN"]}],
                },
            },
        )
    )
    with pytest.raises(PrometheusQueryError, match="NaN"):
        await client.instant_query("some_query", time="2026-01-15T10:00:00Z")


@respx.mock
@pytest.mark.asyncio
async def test_instant_query_scalar_result_type(client: PrometheusClient):
    respx.get("http://prom:9090/api/v1/query").mock(
        return_value=Response(
            200,
            json={
                "status": "success",
                "data": {"resultType": "scalar", "result": [1705312800, "42.5"]},
            },
        )
    )
    value = await client.instant_query("some_query", time="2026-01-15T10:00:00Z")
    assert value == 42.5


@respx.mock
@pytest.mark.asyncio
async def test_instant_query_http_error(client: PrometheusClient):
    respx.get("http://prom:9090/api/v1/query").mock(
        return_value=Response(500, text="Internal Server Error")
    )
    with pytest.raises(PrometheusQueryError, match="500"):
        await client.instant_query("some_query", time="2026-01-15T10:00:00Z")
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `uv run --directory adapters/prometheus pytest tests/test_prometheus_client.py -v`

- [ ] **Step 3: Implement Prometheus client**

```python
# app/core/prometheus_client.py
"""Async HTTP wrapper for the Prometheus query API."""

import math

import httpx


class PrometheusQueryError(Exception):
    """Raised when a Prometheus query fails or returns invalid data."""


class PrometheusClient:
    """Thin async client for Prometheus instant and range queries."""

    def __init__(
        self,
        base_url: str,
        timeout: float,
        auth: tuple[str, str] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._auth = auth

    async def instant_query(self, query: str, *, time: str) -> float:
        """Execute an instant query and return a single float value.

        Raises PrometheusQueryError on any failure.
        """
        params = {"query": query, "time": time}
        data = await self._get("/api/v1/query", params)
        return self._extract_scalar(data)

    async def _get(self, path: str, params: dict[str, str]) -> dict:
        auth = httpx.BasicAuth(*self._auth) if self._auth else None
        async with httpx.AsyncClient(
            base_url=self._base_url, timeout=self._timeout, auth=auth
        ) as client:
            resp = await client.get(path, params=params)
            if resp.status_code != 200:
                raise PrometheusQueryError(
                    f"prometheus returned {resp.status_code}: {resp.text[:200]}"
                )
            body = resp.json()
            if body.get("status") != "success":
                raise PrometheusQueryError(
                    f"prometheus error: {body.get('error', 'unknown')}"
                )
            return body["data"]

    def _extract_scalar(self, data: dict) -> float:
        result_type = data["resultType"]

        if result_type == "scalar":
            return self._parse_value(data["result"][1])

        if result_type == "vector":
            results = data["result"]
            if len(results) == 0:
                raise PrometheusQueryError("query returned 0 results")
            if len(results) > 1:
                raise PrometheusQueryError(
                    f"query returned {len(results)} results, expected exactly 1"
                )
            return self._parse_value(results[0]["value"][1])

        raise PrometheusQueryError(f"unexpected result type: {result_type}")

    def _parse_value(self, raw: str) -> float:
        val = float(raw)
        if math.isnan(val) or math.isinf(val):
            raise PrometheusQueryError(f"query returned {raw}")
        return val
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```
git add adapters/prometheus/app/core/prometheus_client.py adapters/prometheus/tests/test_prometheus_client.py
git commit -m "feat(adapter): add async Prometheus HTTP client with result validation"
```

---

## Task 4: Raw Query Strategy

**Files:**
- Create: `adapters/prometheus/app/core/strategies/base.py`
- Create: `adapters/prometheus/app/core/strategies/raw.py`
- Test: `adapters/prometheus/tests/test_raw_strategy.py`

- [ ] **Step 1: Write strategy protocol and failing test**

```python
# app/core/strategies/base.py
"""Strategy interface for query mode execution."""

from typing import Protocol


class QueryStrategy(Protocol):
    """Each query mode implements this interface."""

    async def execute(
        self,
        *,
        sli_name: str,
        query_spec: dict,
        variables: dict[str, str],
        start: str,
        end: str,
    ) -> tuple[dict[str, float | None], dict[str, str], dict | None]:
        """Execute a query and return (values, errors, metadata).

        Returns:
            values: {metric_name: float_value} — for raw mode, single entry.
            errors: {metric_name: error_message} — for failed queries.
            metadata: Optional metadata dict (sample counts, etc.). None for raw mode.
        """
        ...
```

```python
# tests/test_raw_strategy.py
import pytest
import respx
from httpx import Response

from app.core.strategies.raw import RawQueryStrategy
from app.core.prometheus_client import PrometheusClient


@pytest.fixture
def strategy():
    client = PrometheusClient(base_url="http://prom:9090", timeout=5.0)
    return RawQueryStrategy(client)


@respx.mock
@pytest.mark.asyncio
async def test_raw_strategy_returns_single_value(strategy: RawQueryStrategy):
    respx.get("http://prom:9090/api/v1/query").mock(
        return_value=Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [{"metric": {}, "value": [1705312800, "0.245"]}],
                },
            },
        )
    )
    values, errors, metadata = await strategy.execute(
        sli_name="response_time_p99",
        query_spec={"mode": "raw", "query": "histogram_quantile(0.99, ...)"},
        variables={},
        start="2026-01-15T10:00:00Z",
        end="2026-01-15T10:05:00Z",
    )
    assert values == {"response_time_p99": 0.245}
    assert errors == {}
    assert metadata is None


@respx.mock
@pytest.mark.asyncio
async def test_raw_strategy_substitutes_variables(strategy: RawQueryStrategy):
    route = respx.get("http://prom:9090/api/v1/query").mock(
        return_value=Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [{"metric": {}, "value": [1705312800, "1.0"]}],
                },
            },
        )
    )
    await strategy.execute(
        sli_name="cpu",
        query_spec={"mode": "raw", "query": 'rate(cpu{job="$SERVICE"}[5m])'},
        variables={"SERVICE": "api"},
        start="2026-01-15T10:00:00Z",
        end="2026-01-15T10:05:00Z",
    )
    assert 'job="api"' in str(route.calls[0].request.url)


@respx.mock
@pytest.mark.asyncio
async def test_raw_strategy_captures_error(strategy: RawQueryStrategy):
    respx.get("http://prom:9090/api/v1/query").mock(
        return_value=Response(
            200,
            json={
                "status": "success",
                "data": {"resultType": "vector", "result": []},
            },
        )
    )
    values, errors, metadata = await strategy.execute(
        sli_name="missing_metric",
        query_spec={"mode": "raw", "query": "nonexistent_metric"},
        variables={},
        start="2026-01-15T10:00:00Z",
        end="2026-01-15T10:05:00Z",
    )
    assert values == {"missing_metric": None}
    assert "0 results" in errors["missing_metric"]
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement raw strategy**

```python
# app/core/strategies/raw.py
"""Raw query strategy — executes complete PromQL as instant query."""

from app.core.prometheus_client import PrometheusClient, PrometheusQueryError
from app.core.variable_substitutor import substitute, UnresolvedVariableError


class RawQueryStrategy:
    """Executes a complete PromQL expression as an instant query at end timestamp."""

    def __init__(self, client: PrometheusClient) -> None:
        self._client = client

    async def execute(
        self,
        *,
        sli_name: str,
        query_spec: dict,
        variables: dict[str, str],
        start: str,
        end: str,
    ) -> tuple[dict[str, float | None], dict[str, str], dict | None]:
        query_template = query_spec["query"]

        try:
            query = substitute(query_template, variables, start_iso=start, end_iso=end)
        except UnresolvedVariableError as exc:
            return {sli_name: None}, {sli_name: str(exc)}, None

        try:
            value = await self._client.instant_query(query, time=end)
        except PrometheusQueryError as exc:
            return {sli_name: None}, {sli_name: str(exc)}, None

        return {sli_name: value}, {}, None
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```
git add adapters/prometheus/app/core/strategies/ adapters/prometheus/tests/test_raw_strategy.py
git commit -m "feat(adapter): add raw query strategy with variable substitution"
```

---

## Task 5: API Schemas (Protocol v2)

Request/response models designed for both modes, only raw implemented.

**Files:**
- Create: `adapters/prometheus/app/api/schemas.py`
- Test: `adapters/prometheus/tests/test_schemas.py`

- [ ] **Step 1: Write failing validation tests**

```python
# tests/test_schemas.py
import pytest
from pydantic import ValidationError

from app.api.schemas import JobSubmitRequest, RawQuerySpec, AggregatedQuerySpec


def test_raw_query_spec_valid():
    spec = RawQuerySpec(mode="raw", query="rate(http_requests[5m])")
    assert spec.mode == "raw"
    assert spec.query == "rate(http_requests[5m])"


def test_aggregated_query_spec_valid():
    spec = AggregatedQuerySpec(
        mode="aggregated",
        query_template="rate(cpu[$interval])",
        interval="1m",
        methods=["mean", "p99"],
    )
    assert spec.mode == "aggregated"
    assert spec.methods == ["mean", "p99"]


def test_aggregated_query_spec_invalid_method():
    with pytest.raises(ValidationError):
        AggregatedQuerySpec(
            mode="aggregated",
            query_template="rate(cpu[$interval])",
            interval="1m",
            methods=["mean", "invalid_method"],
        )


def test_aggregated_query_spec_empty_methods():
    with pytest.raises(ValidationError):
        AggregatedQuerySpec(
            mode="aggregated",
            query_template="rate(cpu[$interval])",
            interval="1m",
            methods=[],
        )


def test_job_submit_request_valid():
    req = JobSubmitRequest(
        queries={
            "cpu": {"mode": "raw", "query": "rate(cpu[5m])"},
        },
        start="2026-01-15T10:00:00Z",
        end="2026-01-15T10:05:00Z",
    )
    assert len(req.queries) == 1


def test_job_submit_request_too_many_queries():
    queries = {f"metric_{i}": {"mode": "raw", "query": "x"} for i in range(401)}
    with pytest.raises(ValidationError, match="at most 400"):
        JobSubmitRequest(
            queries=queries,
            start="2026-01-15T10:00:00Z",
            end="2026-01-15T10:05:00Z",
        )
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement schemas**

```python
# app/api/schemas.py
"""Pydantic models for the adapter's REST API."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

ALLOWED_METHODS = frozenset(
    ["min", "mean", "max", "std", "sum", "median", "p75", "p90", "p95", "p99"]
)


class RawQuerySpec(BaseModel):
    mode: str = "raw"
    query: str


class AggregatedQuerySpec(BaseModel):
    mode: str = "aggregated"
    query_template: str
    interval: str
    methods: list[str] = Field(min_length=1)

    @field_validator("methods")
    @classmethod
    def validate_methods(cls, v: list[str]) -> list[str]:
        invalid = set(v) - ALLOWED_METHODS
        if invalid:
            msg = f"invalid aggregation methods: {', '.join(sorted(invalid))}"
            raise ValueError(msg)
        return v


class JobSubmitRequest(BaseModel):
    queries: dict[str, dict] = Field(max_length=400)
    variables: dict[str, str] = {}
    start: datetime
    end: datetime
    timeout_seconds: int | None = None


class JobSubmitResponse(BaseModel):
    job_id: str
    status: str = "queued"
    created_at: datetime
    poll_url: str
    total_queries: int


class JobProgress(BaseModel):
    total: int
    completed: int
    failed: int


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: JobProgress | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    results: list[dict] | None = None
    metadata: dict | None = None


class IndicatorResult(BaseModel):
    indicator: str
    value: float | None
    success: bool
    message: str = ""
    query_executed: str = ""
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```
git add adapters/prometheus/app/api/ adapters/prometheus/tests/test_schemas.py
git commit -m "feat(adapter): add v2 API schemas with raw and aggregated query specs"
```

---

## Task 6: Redis Repository

Job state CRUD on Redis keys.

**Files:**
- Create: `adapters/prometheus/app/redis/client.py`
- Create: `adapters/prometheus/app/redis/repository.py`
- Test: `adapters/prometheus/tests/test_redis_repository.py`

- [ ] **Step 1: Add fakeredis dependency**

In `adapters/prometheus/pyproject.toml`, add to `[dependency-groups] dev`:
```
fakeredis>=2.21
```

Run: `uv sync --directory adapters/prometheus`

- [ ] **Step 2: Write failing tests**

```python
# tests/test_redis_repository.py
import json

import fakeredis.aioredis
import pytest

from app.redis.repository import JobRepository


@pytest.fixture
async def repo():
    redis = fakeredis.aioredis.FakeRedis()
    return JobRepository(redis, prefix="test:")


@pytest.mark.asyncio
async def test_create_job(repo: JobRepository):
    job_id = await repo.create_job(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout=120,
    )
    assert job_id is not None
    status = await repo.get_status(job_id)
    assert status["status"] == "queued"
    assert status["total_queries"] == 1


@pytest.mark.asyncio
async def test_mark_running(repo: JobRepository):
    job_id = await repo.create_job(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout=120,
    )
    await repo.mark_running(job_id)
    status = await repo.get_status(job_id)
    assert status["status"] == "running"


@pytest.mark.asyncio
async def test_write_result(repo: JobRepository):
    job_id = await repo.create_job(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout=120,
    )
    await repo.write_result(job_id, "cpu", value=4.3, success=True, message="")
    results = await repo.get_results(job_id)
    assert results["cpu"]["value"] == 4.3
    assert results["cpu"]["success"] is True


@pytest.mark.asyncio
async def test_mark_completed_sets_ttl(repo: JobRepository):
    job_id = await repo.create_job(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout=120,
    )
    await repo.mark_completed(job_id, retention_seconds=60)
    status = await repo.get_status(job_id)
    assert status["status"] == "completed"


@pytest.mark.asyncio
async def test_cancel_queued_job(repo: JobRepository):
    job_id = await repo.create_job(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout=120,
    )
    cancelled = await repo.cancel(job_id)
    assert cancelled is True
    status = await repo.get_status(job_id)
    assert status["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_completed_job_returns_false(repo: JobRepository):
    job_id = await repo.create_job(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout=120,
    )
    await repo.mark_completed(job_id, retention_seconds=60)
    cancelled = await repo.cancel(job_id)
    assert cancelled is False


@pytest.mark.asyncio
async def test_enqueue_and_dequeue(repo: JobRepository):
    job_id = await repo.create_job(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout=120,
    )
    await repo.enqueue(job_id)
    dequeued = await repo.dequeue()
    assert dequeued == job_id


@pytest.mark.asyncio
async def test_dequeue_empty_returns_none(repo: JobRepository):
    dequeued = await repo.dequeue()
    assert dequeued is None


@pytest.mark.asyncio
async def test_queue_depth(repo: JobRepository):
    for _ in range(3):
        jid = await repo.create_job(queries={"x": {"mode": "raw", "query": "x"}}, variables={}, timeout=120)
        await repo.enqueue(jid)
    assert await repo.queue_depth() == 3
```

- [ ] **Step 3: Implement Redis client and repository**

```python
# app/redis/client.py
"""Redis connection pool lifecycle."""

import redis.asyncio as redis


async def create_redis_pool(url: str) -> redis.Redis:
    return redis.from_url(url, decode_responses=True)
```

```python
# app/redis/repository.py
"""Job state CRUD on Redis keys."""

import json
import uuid
from datetime import datetime, timezone

import redis.asyncio as redis


class JobRepository:
    """Manages job state in Redis using hash + list keys."""

    def __init__(self, redis_client: redis.Redis, prefix: str = "prom-sli:") -> None:
        self._r = redis_client
        self._p = prefix

    def _key(self, *parts: str) -> str:
        return self._p + ":".join(parts)

    async def create_job(
        self,
        queries: dict[str, dict],
        variables: dict[str, str],
        timeout: int,
        start: str = "",
        end: str = "",
    ) -> str:
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
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

    async def get_status(self, job_id: str) -> dict | None:
        data = await self._r.hgetall(self._key("job", job_id))
        if not data:
            return None
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

    async def get_queries(self, job_id: str) -> dict[str, dict]:
        raw = await self._r.get(self._key("job", job_id, "queries"))
        return json.loads(raw) if raw else {}

    async def get_variables(self, job_id: str) -> dict[str, str]:
        raw = await self._r.hget(self._key("job", job_id), "variables")
        return json.loads(raw) if raw else {}

    async def get_start_end(self, job_id: str) -> tuple[str, str]:
        data = await self._r.hmget(self._key("job", job_id), "start", "end")
        return data[0] or "", data[1] or ""

    async def mark_running(self, job_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
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

    async def get_results(self, job_id: str) -> dict[str, dict]:
        raw = await self._r.hgetall(self._key("job", job_id, "results"))
        return {k: json.loads(v) for k, v in raw.items()}

    async def mark_completed(self, job_id: str, retention_seconds: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        job_key = self._key("job", job_id)
        created = await self._r.hget(job_key, "created_at")
        duration_ms = 0
        if created:
            start = datetime.fromisoformat(created)
            duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
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
        now = datetime.now(timezone.utc).isoformat()
        await self._r.hset(
            self._key("job", job_id),
            mapping={"status": "timed_out", "completed_at": now},
        )
        await self._r.expire(self._key("job", job_id), retention_seconds)

    async def cancel(self, job_id: str) -> bool:
        status = await self._r.hget(self._key("job", job_id), "status")
        if status in ("completed", "timed_out", "cancelled"):
            return False
        await self._r.hset(self._key("job", job_id), "status", "cancelled")
        return True

    async def enqueue(self, job_id: str) -> None:
        await self._r.rpush(self._key("queue", "pending"), job_id)

    async def dequeue(self) -> str | None:
        return await self._r.lpop(self._key("queue", "pending"))

    async def queue_depth(self) -> int:
        return await self._r.llen(self._key("queue", "pending"))
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `uv run --directory adapters/prometheus pytest tests/test_redis_repository.py -v`

- [ ] **Step 5: Commit**

```
git add adapters/prometheus/app/redis/ adapters/prometheus/tests/test_redis_repository.py adapters/prometheus/pyproject.toml
git commit -m "feat(adapter): add Redis job repository with queue and state management"
```

---

## Task 7: Job Manager

Wires together job creation, status reads, and cancellation.

**Files:**
- Create: `adapters/prometheus/app/core/job_manager.py`
- Test: `adapters/prometheus/tests/test_job_manager.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_job_manager.py
import fakeredis.aioredis
import pytest

from app.config import Settings
from app.core.job_manager import JobManager
from app.redis.repository import JobRepository


@pytest.fixture
async def manager():
    redis = fakeredis.aioredis.FakeRedis()
    repo = JobRepository(redis, prefix="test:")
    settings = Settings()
    return JobManager(repo, settings)


@pytest.mark.asyncio
async def test_submit_job(manager: JobManager):
    result = await manager.submit(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout_seconds=None,
        start="2026-01-15T10:00:00Z",
        end="2026-01-15T10:05:00Z",
    )
    assert result["status"] == "queued"
    assert result["total_queries"] == 1
    assert "job_id" in result


@pytest.mark.asyncio
async def test_submit_respects_max_timeout(manager: JobManager):
    result = await manager.submit(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout_seconds=9999,
    )
    # Should be capped to max_job_timeout_seconds (600)
    status = await manager.get_status(result["job_id"])
    assert status is not None


@pytest.mark.asyncio
async def test_submit_rejects_when_queue_full(manager: JobManager):
    # Fill queue to max_queue_depth
    for i in range(manager._settings.max_queue_depth):
        await manager.submit(
            queries={f"m{i}": {"mode": "raw", "query": "x"}},
            variables={},
            timeout_seconds=None,
        )
    with pytest.raises(manager.QueueFullError):
        await manager.submit(
            queries={"overflow": {"mode": "raw", "query": "x"}},
            variables={},
            timeout_seconds=None,
        )


@pytest.mark.asyncio
async def test_get_status_not_found(manager: JobManager):
    status = await manager.get_status("nonexistent")
    assert status is None


@pytest.mark.asyncio
async def test_cancel_job(manager: JobManager):
    result = await manager.submit(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout_seconds=None,
    )
    cancelled = await manager.cancel(result["job_id"])
    assert cancelled is True
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement job manager**

```python
# app/core/job_manager.py
"""Job lifecycle management — submit, poll, cancel."""

from datetime import datetime, timezone

from app.config import Settings
from app.redis.repository import JobRepository


class JobManager:
    """Coordinates job creation, status queries, and cancellation."""

    class QueueFullError(Exception):
        """Raised when the pending queue exceeds max depth."""

    def __init__(self, repo: JobRepository, settings: Settings) -> None:
        self._repo = repo
        self._settings = settings

    async def submit(
        self,
        queries: dict[str, dict],
        variables: dict[str, str],
        timeout_seconds: int | None,
        start: str = "",
        end: str = "",
    ) -> dict:
        depth = await self._repo.queue_depth()
        if depth >= self._settings.max_queue_depth:
            raise self.QueueFullError(
                f"queue depth {depth} >= max {self._settings.max_queue_depth}"
            )

        timeout = min(
            timeout_seconds or self._settings.default_job_timeout_seconds,
            self._settings.max_job_timeout_seconds,
        )

        job_id = await self._repo.create_job(queries, variables, timeout, start, end)
        await self._repo.enqueue(job_id)

        return {
            "job_id": job_id,
            "status": "queued",
            "created_at": datetime.now(timezone.utc),
            "poll_url": f"/api/v1/query-jobs/{job_id}",
            "total_queries": len(queries),
        }

    async def get_status(self, job_id: str) -> dict | None:
        status = await self._repo.get_status(job_id)
        if status is None:
            return None

        result = {
            "job_id": job_id,
            "status": status["status"],
        }

        if status["status"] == "running":
            result["progress"] = {
                "total": status["total_queries"],
                "completed": status["completed_count"],
                "failed": status["failed_count"],
            }
        elif status["status"] in ("completed", "timed_out"):
            result["completed_at"] = status.get("completed_at")
            result["duration_ms"] = status.get("duration_ms")
            results = await self._repo.get_results(job_id)
            result["results"] = [
                {"indicator": k, **v} for k, v in results.items()
            ]

        return result

    async def cancel(self, job_id: str) -> bool:
        return await self._repo.cancel(job_id)
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```
git add adapters/prometheus/app/core/job_manager.py adapters/prometheus/tests/test_job_manager.py
git commit -m "feat(adapter): add job manager with submit, poll, cancel, and back-pressure"
```

---

## Task 8: Coordinator (Background Worker)

Picks jobs from queue, fans out queries through semaphore.

**Files:**
- Create: `adapters/prometheus/app/core/coordinator.py`
- Test: `adapters/prometheus/tests/test_coordinator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_coordinator.py
import asyncio

import fakeredis.aioredis
import pytest

from app.config import Settings
from app.core.coordinator import Coordinator
from app.core.strategies.raw import RawQueryStrategy
from app.core.prometheus_client import PrometheusClient
from app.redis.repository import JobRepository


class FakePrometheusClient:
    """Returns canned values for testing coordinator logic."""

    async def instant_query(self, query: str, *, time: str) -> float:
        return 42.0


@pytest.fixture
async def coordinator():
    redis = fakeredis.aioredis.FakeRedis()
    repo = JobRepository(redis, prefix="test:")
    settings = Settings(max_concurrent_queries=2, max_concurrent_jobs=1)
    client = FakePrometheusClient()
    strategy = RawQueryStrategy(client)
    return Coordinator(repo, settings, strategies={"raw": strategy})


@pytest.mark.asyncio
async def test_coordinator_processes_single_job(coordinator: Coordinator):
    repo = coordinator._repo
    job_id = await repo.create_job(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout=120,
    )
    await repo.enqueue(job_id)

    await coordinator.process_one()

    status = await repo.get_status(job_id)
    assert status["status"] == "completed"
    results = await repo.get_results(job_id)
    assert results["cpu"]["value"] == 42.0
    assert results["cpu"]["success"] is True


@pytest.mark.asyncio
async def test_coordinator_handles_multiple_queries(coordinator: Coordinator):
    repo = coordinator._repo
    queries = {f"metric_{i}": {"mode": "raw", "query": f"q{i}"} for i in range(5)}
    job_id = await repo.create_job(queries=queries, variables={}, timeout=120)
    await repo.enqueue(job_id)

    await coordinator.process_one()

    status = await repo.get_status(job_id)
    assert status["status"] == "completed"
    results = await repo.get_results(job_id)
    assert len(results) == 5


@pytest.mark.asyncio
async def test_coordinator_skips_cancelled_job(coordinator: Coordinator):
    repo = coordinator._repo
    job_id = await repo.create_job(
        queries={"cpu": {"mode": "raw", "query": "x"}},
        variables={},
        timeout=120,
    )
    await repo.enqueue(job_id)
    await repo.cancel(job_id)

    await coordinator.process_one()

    status = await repo.get_status(job_id)
    assert status["status"] == "cancelled"
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement coordinator**

```python
# app/core/coordinator.py
"""Background coordinator: picks jobs from queue, fans out queries."""

import asyncio
import logging

from app.config import Settings
from app.redis.repository import JobRepository

logger = logging.getLogger(__name__)


class Coordinator:
    """Dequeues jobs and processes them with semaphore-limited concurrency."""

    def __init__(
        self,
        repo: JobRepository,
        settings: Settings,
        strategies: dict,
    ) -> None:
        self._repo = repo
        self._settings = settings
        self._strategies = strategies
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_queries)
        self._job_semaphore = asyncio.Semaphore(settings.max_concurrent_jobs)
        self._running = False

    async def process_one(self) -> bool:
        """Process a single job from the queue. Returns True if a job was processed."""
        job_id = await self._repo.dequeue()
        if job_id is None:
            return False

        status = await self._repo.get_status(job_id)
        if status is None or status["status"] == "cancelled":
            return True

        await self._repo.mark_running(job_id)
        queries = await self._repo.get_queries(job_id)
        variables = await self._repo.get_variables(job_id)
        start, end = await self._repo.get_start_end(job_id)

        async def _run_query(sli_name: str, query_spec: dict) -> None:
            mode = query_spec.get("mode", "raw")
            strategy = self._strategies.get(mode)
            if strategy is None:
                await self._repo.write_result(
                    job_id, sli_name, value=None, success=False,
                    message=f"unsupported mode: {mode}",
                )
                return

            async with self._semaphore:
                # Check cancellation before executing
                current = await self._repo.get_status(job_id)
                if current and current["status"] == "cancelled":
                    return

                values, errors, metadata = await strategy.execute(
                    sli_name=sli_name,
                    query_spec=query_spec,
                    variables=variables,
                    start=start,
                    end=end,
                )

                for name, value in values.items():
                    error_msg = errors.get(name, "")
                    await self._repo.write_result(
                        job_id, name,
                        value=value,
                        success=name not in errors,
                        message=error_msg,
                        query_executed=query_spec.get("query", query_spec.get("query_template", "")),
                    )

        tasks = [_run_query(name, spec) for name, spec in queries.items()]
        await asyncio.gather(*tasks)

        # Check if cancelled during processing
        final_status = await self._repo.get_status(job_id)
        if final_status and final_status["status"] != "cancelled":
            await self._repo.mark_completed(
                job_id, self._settings.job_retention_seconds
            )

        return True

    async def run(self) -> None:
        """Main loop: continuously process jobs from the queue."""
        self._running = True
        while self._running:
            async with self._job_semaphore:
                processed = await self.process_one()
            if not processed:
                await asyncio.sleep(0.1)

    def stop(self) -> None:
        self._running = False
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```
git add adapters/prometheus/app/core/coordinator.py adapters/prometheus/tests/test_coordinator.py
git commit -m "feat(adapter): add job coordinator with semaphore-limited query fan-out"
```

---

## Task 9: API Routes

Wire everything into FastAPI endpoints.

**Files:**
- Create: `adapters/prometheus/app/api/routes.py`
- Create: `adapters/prometheus/app/health/routes.py`
- Rewrite: `adapters/prometheus/app/main.py`
- Test: `adapters/prometheus/tests/test_routes.py`

- [ ] **Step 1: Write failing route tests**

```python
# tests/test_routes.py
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def client():
    app = create_app(use_fakeredis=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health_live(client: AsyncClient):
    resp = await client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_submit_job(client: AsyncClient):
    resp = await client.post(
        "/api/v1/query-jobs",
        json={
            "queries": {"cpu": {"mode": "raw", "query": "up"}},
            "start": "2026-01-15T10:00:00Z",
            "end": "2026-01-15T10:05:00Z",
        },
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert "job_id" in body
    assert body["total_queries"] == 1


@pytest.mark.asyncio
async def test_get_job_status(client: AsyncClient):
    submit = await client.post(
        "/api/v1/query-jobs",
        json={
            "queries": {"cpu": {"mode": "raw", "query": "up"}},
            "start": "2026-01-15T10:00:00Z",
            "end": "2026-01-15T10:05:00Z",
        },
    )
    job_id = submit.json()["job_id"]
    resp = await client.get(f"/api/v1/query-jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] in ("queued", "running", "completed")


@pytest.mark.asyncio
async def test_get_nonexistent_job(client: AsyncClient):
    resp = await client.get("/api/v1/query-jobs/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_job(client: AsyncClient):
    submit = await client.post(
        "/api/v1/query-jobs",
        json={
            "queries": {"cpu": {"mode": "raw", "query": "up"}},
            "start": "2026-01-15T10:00:00Z",
            "end": "2026-01-15T10:05:00Z",
        },
    )
    job_id = submit.json()["job_id"]
    resp = await client.delete(f"/api/v1/query-jobs/{job_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_queue_full_returns_503(client: AsyncClient):
    # Submit max_queue_depth + 1 jobs
    for i in range(101):
        resp = await client.post(
            "/api/v1/query-jobs",
            json={
                "queries": {f"m{i}": {"mode": "raw", "query": "up"}},
                "start": "2026-01-15T10:00:00Z",
                "end": "2026-01-15T10:05:00Z",
            },
        )
        if resp.status_code == 503:
            assert "Retry-After" in resp.headers
            return
    pytest.fail("Expected 503 but queue never filled")
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement health routes**

```python
# app/health/routes.py
"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness():
    return {"status": "ok"}


@router.get("/ready")
async def readiness():
    # Phase 0: basic check. Future: verify Redis ping + workers active.
    return {"status": "ok"}
```

- [ ] **Step 4: Implement API routes**

```python
# app/api/routes.py
"""Job submission, polling, and cancellation endpoints."""

from fastapi import APIRouter, HTTPException, Request, Response

from app.api.schemas import JobSubmitRequest, JobSubmitResponse
from app.core.job_manager import JobManager

router = APIRouter(prefix="/api/v1", tags=["jobs"])


@router.post("/query-jobs", status_code=202)
async def submit_job(body: JobSubmitRequest, request: Request):
    manager: JobManager = request.app.state.job_manager
    try:
        result = await manager.submit(
            queries=body.queries,
            variables=body.variables,
            timeout_seconds=body.timeout_seconds,
            start=body.start.isoformat(),
            end=body.end.isoformat(),
        )
    except JobManager.QueueFullError:
        return Response(
            content='{"error": "queue full"}',
            status_code=503,
            headers={"Retry-After": "5"},
            media_type="application/json",
        )
    return result


@router.get("/query-jobs/{job_id}")
async def get_job(job_id: str, request: Request):
    manager: JobManager = request.app.state.job_manager
    status = await manager.get_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="job not found")
    return status


@router.delete("/query-jobs/{job_id}", status_code=204)
async def cancel_job(job_id: str, request: Request):
    manager: JobManager = request.app.state.job_manager
    cancelled = await manager.cancel(job_id)
    if cancelled is None:
        raise HTTPException(status_code=404, detail="job not found")
    if not cancelled:
        raise HTTPException(status_code=409, detail="job already in terminal state")
    return Response(status_code=204)
```

- [ ] **Step 5: Rewrite main.py**

```python
# app/main.py
"""FastAPI application factory with lifespan management."""

import asyncio
from contextlib import asynccontextmanager

import fakeredis.aioredis
import redis.asyncio as aioredis
from fastapi import FastAPI

from app.api.routes import router as api_router
from app.config import Settings
from app.core.coordinator import Coordinator
from app.core.job_manager import JobManager
from app.core.prometheus_client import PrometheusClient
from app.core.strategies.raw import RawQueryStrategy
from app.health.routes import router as health_router
from app.redis.repository import JobRepository


def create_app(use_fakeredis: bool = False) -> FastAPI:
    settings = Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if use_fakeredis:
            redis_client = fakeredis.aioredis.FakeRedis()
        else:
            redis_client = aioredis.from_url(
                settings.redis_url, decode_responses=True
            )

        repo = JobRepository(redis_client, prefix=settings.redis_key_prefix)

        auth = None
        if settings.prometheus_username and settings.prometheus_password:
            auth = (settings.prometheus_username, settings.prometheus_password)

        prom_client = PrometheusClient(
            base_url=settings.prometheus_url,
            timeout=settings.query_timeout_seconds,
            auth=auth,
        )

        strategies = {"raw": RawQueryStrategy(prom_client)}

        app.state.job_manager = JobManager(repo, settings)
        app.state.coordinator = Coordinator(repo, settings, strategies)

        coordinator_task = asyncio.create_task(app.state.coordinator.run())

        yield

        app.state.coordinator.stop()
        coordinator_task.cancel()
        await redis_client.aclose()

    app = FastAPI(title="Prometheus SLI Adapter", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(api_router)
    return app


app = create_app()
```

- [ ] **Step 6: Run tests — expect PASS**

Run: `uv run --directory adapters/prometheus pytest tests/test_routes.py -v`

- [ ] **Step 7: Commit**

```
git add adapters/prometheus/app/ adapters/prometheus/tests/test_routes.py
git commit -m "feat(adapter): wire FastAPI routes, job manager, and coordinator with lifespan"
```

---

## Task 10: Dockerfile

**Files:**
- Create: `adapters/prometheus/Dockerfile`

- [ ] **Step 1: Create Dockerfile**

```dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml .
RUN uv sync --no-dev --no-install-project

COPY app/ app/

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 2: Verify build**

Run: `docker build -t prometheus-sli-adapter adapters/prometheus/`

- [ ] **Step 3: Commit**

```
git add adapters/prometheus/Dockerfile
git commit -m "feat(adapter): add Dockerfile for prometheus-sli-adapter"
```

---

## Task 11: SLI Registry — Add `mode` Field

Prepare the TROPEK backend for future aggregated mode.

**Files:**
- Modify: `api/app/db/models.py`
- Modify: `api/app/modules/sli_registry/schemas.py`
- Test: `api/tests/db/test_sli_repository.py` (add mode-related tests)

- [ ] **Step 1: Write failing integration test**

Add to existing SLI repository test file:

```python
# In api/tests/db/test_sli_repository.py — add new test

@pytest.mark.integration
async def test_create_sli_with_mode_defaults_to_raw(sli_repo, db_session):
    created = await sli_repo.create(SLIDefinitionCreate(
        name="test-mode-default",
        adapter_type="prometheus",
        indicators={"cpu": "rate(cpu[5m])"},
    ))
    assert created.mode == "raw"


@pytest.mark.integration
async def test_create_aggregated_sli(sli_repo, db_session):
    created = await sli_repo.create(SLIDefinitionCreate(
        name="test-aggregated",
        adapter_type="prometheus",
        mode="aggregated",
        query_template="sum(rate(cpu[$interval]))",
        interval="1m",
        methods=["mean", "p99", "max"],
    ))
    assert created.mode == "aggregated"
    assert created.query_template == "sum(rate(cpu[$interval]))"
    assert created.interval == "1m"
    assert created.methods == ["mean", "p99", "max"]
    assert created.indicators == {}
```

- [ ] **Step 2: Run test — expect FAIL (columns don't exist)**

Run: `./scripts/api-test.sh --tail 5 -m integration tests/db/test_sli_repository.py -v -k "test_create_sli_with_mode"` (after `just test-env`)

- [ ] **Step 3: Add columns to SLIDefinition model**

In `api/app/db/models.py`, add to the `SLIDefinition` class:

```python
    mode: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'raw'"), default="raw"
    )
    query_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    interval: Mapped[str | None] = mapped_column(Text, nullable=True)
    methods: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
```

- [ ] **Step 4: Update SLI schemas**

In `api/app/modules/sli_registry/schemas.py`, add to `SLIDefinitionCreate`:

```python
    mode: str = "raw"
    query_template: str | None = None
    interval: str | None = None
    methods: list[str] | None = None
```

And to `SLIDefinitionRead`:

```python
    mode: str
    query_template: str | None
    interval: str | None
    methods: list[str] | None
```

- [ ] **Step 5: Regenerate migrations**

Run: `./scripts/db-regen-migrations.sh`

- [ ] **Step 6: Run tests — expect PASS**

- [ ] **Step 7: Commit**

```
git add api/app/db/models.py api/app/modules/sli_registry/schemas.py api/alembic/
git commit -m "feat(sli): add mode, query_template, interval, methods fields to SLI registry"
```

---

## Task 12: Update Adapter Protocol v2

Update the TROPEK adapter client to support the v2 request format. The key change: `queries` values
go from `str` (bare query string) to `dict` (mode-aware query spec).

**Files:**
- Modify: `api/app/modules/quality_gate/adapter_protocol.py`
- Modify: `api/app/modules/quality_gate/adapter_client.py`
- Modify: `api/app/modules/quality_gate/worker.py` (caller)

- [ ] **Step 1: Update protocol dataclasses**

In `adapter_protocol.py`, change `AdapterQueryRequest.queries` from `dict[str, str]` to
`dict[str, dict]` and add `variables`. Update `AdapterQueryResponse` to include `metadata`.
Also update the `AdapterClient` protocol signature.

```python
# api/app/modules/quality_gate/adapter_protocol.py
"""Formal adapter query contract as a Protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class AdapterQueryRequest:
    """Request payload for an adapter metric query."""

    queries: dict[str, dict]  # metric_name → {"mode": "raw", "query": "..."} or aggregated spec
    variables: dict[str, str] = field(default_factory=dict)
    start: str = ""
    end: str = ""


@dataclass
class AdapterQueryResponse:
    """Response payload from an adapter metric query."""

    values: dict[str, float | None] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, dict] = field(default_factory=dict)


class AdapterClient(Protocol):
    """Protocol defining the adapter client contract."""

    async def query(
        self,
        *,
        adapter_url: str,
        datasource_name: str,
        queries: dict[str, dict],
        variables: dict[str, str],
        start: str,
        end: str,
    ) -> tuple[dict[str, float | None], dict[str, str]]:
        """Query an adapter for metric values. Returns (values, errors)."""
        ...

    async def health(self, adapter_url: str) -> bool:
        """Check adapter health."""
        ...
```

- [ ] **Step 2: Update HttpAdapterClient.query()**

In `adapter_client.py`, update the `query` method signature to accept `dict[str, dict]` queries
and a `variables` dict. The request body changes from `{"queries": {"cpu": "rate(...)"},
"start": ..., "end": ...}` to `{"queries": {"cpu": {"mode": "raw", "query": "rate(...)"}},
"variables": {...}, "start": ..., "end": ...}`.

```python
# api/app/modules/quality_gate/adapter_client.py
"""HTTP implementation of the AdapterClient protocol."""

from __future__ import annotations

import httpx


class HttpAdapterClient:
    """Concrete adapter client that queries adapters over HTTP."""

    def __init__(self, timeout: float) -> None:
        self._timeout = timeout

    async def query(
        self,
        *,
        adapter_url: str,
        datasource_name: str,
        queries: dict[str, dict],
        variables: dict[str, str],
        start: str,
        end: str,
    ) -> tuple[dict[str, float | None], dict[str, str]]:
        async with httpx.AsyncClient(timeout=self._timeout) as http_client:
            resp = await http_client.post(
                f"{adapter_url}/query",
                headers={"X-Datasource-Name": datasource_name},
                json={
                    "queries": queries,
                    "variables": variables,
                    "start": start,
                    "end": end,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        metrics_fetched: dict[str, float | None] = {
            name: float(val) if val is not None else None
            for name, val in data.get("values", {}).items()
        }
        fetch_errors: dict[str, str] = {
            name: str(err) for name, err in data.get("errors", {}).items()
        }
        return metrics_fetched, fetch_errors

    async def health(self, adapter_url: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as http_client:
                resp = await http_client.get(f"{adapter_url}/health")
                return bool(resp.is_success)
        except (httpx.ConnectError, httpx.TimeoutException):
            return False
```

- [ ] **Step 3: Update the worker caller**

In `api/app/modules/quality_gate/worker.py`, update `_query_adapter_safe` to wrap the existing
`resolved_queries: dict[str, str]` into v2 query specs and pass an empty `variables` dict (the
worker already performs variable substitution before calling the adapter in the current flow):

Change the function signature from `resolved_queries: dict[str, str]` to build query specs:

```python
# In worker.py, update _query_adapter_safe:

async def _query_adapter_safe(
    log: structlog.stdlib.BoundLogger,
    repo: EvaluationRepository,
    eval_id: uuid.UUID,
    ds: Any,
    resolved_queries: dict[str, str],
    start: str,
    end: str,
) -> tuple[dict[str, float | None], dict[str, str]] | None:
    """Query adapter, mark failed on error. Returns None if query failed."""
    # Wrap bare query strings into v2 raw-mode query specs
    query_specs = {
        name: {"mode": "raw", "query": query}
        for name, query in resolved_queries.items()
    }
    try:
        adapter_client = HttpAdapterClient(
            timeout=get_settings().reliability.adapter_timeout_seconds,
        )
        return await adapter_client.query(
            adapter_url=ds.adapter_url,
            datasource_name=ds.name,
            queries=query_specs,
            variables={},
            start=start,
            end=end,
        )
    except httpx.ConnectError:
        log.exception("adapter unreachable", adapter_url=ds.adapter_url)
        await repo.mark_failed(
            eval_id, job_stats={"error": f"could not reach adapter at {ds.adapter_url}"}
        )
        return None
    except httpx.TimeoutException:
        log.exception("adapter timeout", adapter_url=ds.adapter_url)
        await repo.mark_failed(eval_id, job_stats={"error": "adapter query timed out"})
        return None
    except httpx.HTTPStatusError as exc:
        log.exception("adapter error", status=exc.response.status_code)
        await repo.mark_failed(
            eval_id, job_stats={"error": f"adapter returned {exc.response.status_code}"}
        )
        return None
```

- [ ] **Step 4: Run existing tests to verify no regressions**

Run: `./scripts/api-test.sh --tail 10`

- [ ] **Step 5: Commit**

```
git add api/app/modules/quality_gate/adapter_protocol.py api/app/modules/quality_gate/adapter_client.py api/app/modules/quality_gate/worker.py
git commit -m "feat(api): update adapter protocol to v2 with mode-aware query specs"
```

---

## Task 13: Update pyproject.toml Dependencies

**Files:**
- Modify: `adapters/prometheus/pyproject.toml`

- [ ] **Step 1: Add missing dependencies**

Add `redis` and `respx` to the appropriate sections:

```toml
[project]
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "httpx>=0.27",
    "redis>=5.0",
    "structlog>=24.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "respx>=0.21",
    "fakeredis>=2.21",
    "mypy>=1.10",
    "ruff>=0.4",
]
```

- [ ] **Step 2: Sync dependencies**

Run: `uv sync --directory adapters/prometheus`

- [ ] **Step 3: Run all tests**

Run: `uv run --directory adapters/prometheus pytest tests/ -v`

- [ ] **Step 4: Commit**

```
git add adapters/prometheus/pyproject.toml adapters/prometheus/uv.lock
git commit -m "chore(adapter): update dependencies for redis, respx, fakeredis"
```

---

## Task 14: Run Full Test Suite and Verify

- [ ] **Step 1: Run all adapter tests**

Run: `uv run --directory adapters/prometheus pytest tests/ -v --tb=short`

Expected: All tests pass (config, substitutor, prometheus client, raw strategy, redis repo, job manager, coordinator, routes).

- [ ] **Step 2: Run TROPEK API tests (regression check)**

Run: `./scripts/api-test.sh --tail 10`

Expected: All existing tests still pass. New mode field defaults to `"raw"` and doesn't break existing SLI creation.

- [ ] **Step 3: Run linting and type checking**

Run: `uv run --directory adapters/prometheus ruff check app/ tests/`
Run: `uv run --directory adapters/prometheus mypy app/`

- [ ] **Step 4: Final commit if any fixes needed**

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | Config module | 2 tests |
| 2 | Variable substitutor | 9 tests |
| 3 | Prometheus HTTP client | 6 tests |
| 4 | Raw query strategy | 3 tests |
| 5 | API schemas (v2) | 6 tests |
| 6 | Redis repository | 9 tests |
| 7 | Job manager | 5 tests |
| 8 | Coordinator | 3 tests |
| 9 | API routes + main.py | 6 tests |
| 10 | Dockerfile | build verification |
| 11 | SLI registry mode field | 2 integration tests |
| 12 | Adapter protocol v2 | regression tests |
| 13 | Dependencies | all tests pass |
| 14 | Full verification | all tests pass |

Total: ~51 tests across 14 tasks.
