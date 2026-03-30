# Prometheus SLI Adapter — Phase 1a (Aggregated-Mode Backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `mode: aggregated` in the Prometheus adapter and wire it through the TROPEK backend — no UI changes.

**Architecture:** The adapter gets a new `AggregatedQueryStrategy` that fetches time-series via `query_range`, chunks long ranges, flattens results into a 1-D array, and computes statistical methods (mean, p99, etc.). The TROPEK backend gets mode-dependent SLI validation, `method_criteria` on SLO templates for Level 2 method expansion, and worker changes to build aggregated-mode adapter requests and map expanded `{sli}.{method}` results to objectives. Metadata (sample counts) flows through to `Evaluation.job_stats`.

**Tech Stack:** Python 3.13, FastAPI, httpx, respx (mocking), pytest-asyncio, numpy (stats computation)

**Spec reference:** `docs/superpowers/specs/2026-03-29-prometheus-sli-adapter-design.md`

**Code style:** All Python strings must use single quotes (`'`), including f-strings. All imports must be at the top of the file — never inside functions or methods. Follow CLAUDE.md conventions.

**Design decision — StrEnum for methods:** Aggregation method names (`mean`, `p99`, etc.) are represented as a `StrEnum` (`AggregationMethod`) in both the adapter and the API. `StrEnum` values ARE strings, so they work transparently with JSON, Pydantic, dict keys, and f-strings — zero friction at service boundaries. Typos are caught at attribute-access time, not silently at runtime.

---

## File Map

### Adapter — New Files

| File | Responsibility |
|------|---------------|
| `adapters/prometheus/app/core/methods.py` | `AggregationMethod` StrEnum — single source of truth for adapter-side method names |
| `adapters/prometheus/app/core/stats.py` | Pure-function statistical computation using numpy, dispatched by `AggregationMethod` |
| `adapters/prometheus/app/core/strategies/aggregated.py` | `AggregatedQueryStrategy` — variable substitution, chunking, `query_range` fetch, flatten, stats dispatch |
| `adapters/prometheus/tests/test_stats.py` | Unit tests for stats module |
| `adapters/prometheus/tests/test_aggregated_strategy.py` | Unit tests for aggregated strategy with respx-mocked Prometheus |

### Adapter — Modified Files

| File | Change |
|------|--------|
| `adapters/prometheus/app/core/prometheus_client.py` | Add `range_query()` method |
| `adapters/prometheus/app/api/schemas.py` | Use `AggregationMethod` enum in `AggregatedQuerySpec` validation |
| `adapters/prometheus/app/main.py` | Register `AggregatedQueryStrategy` in strategies dict |
| `adapters/prometheus/app/core/coordinator.py` | Store per-SLI metadata in job results |
| `adapters/prometheus/app/api/routes.py` | Return `metadata` field in sync `/query` response |
| `adapters/prometheus/app/redis/repository.py` | Add `write_metadata()` / `get_metadata()` for per-job metadata storage |

### TROPEK Backend — Modified Files

| File | Change |
|------|--------|
| `api/app/modules/sli_registry/schemas.py` | Add `AggregationMethod` StrEnum + mode-dependent Pydantic validation |
| `api/app/modules/sli_registry/repository.py` | Accept and persist `mode`, `query_template`, `interval`, `methods` |
| `api/app/modules/sli_registry/router.py` | Pass new fields from schema to repository |
| `api/app/modules/slo_registry/schemas.py` | Add `method_criteria` field to `SLODefinitionCreate` / `SLODefinitionRead` |
| `api/app/db/models.py` | Add `method_criteria` column to `SLODefinition` |
| `api/app/modules/quality_gate/worker.py` | Build aggregated-mode query specs from SLI defs; handle metadata in response; map `{sli}.{method}` results |
| `api/app/modules/quality_gate/adapter_client.py` | Return metadata as third element from `query()` |

### Mock Adapter — Modified Files

| File | Change |
|------|--------|
| `adapters/mock/app/main.py` | Accept `mode: aggregated` queries, return multi-value results with metadata |

---

## Task 1: AggregationMethod StrEnum + Stats Module

Create the `AggregationMethod` enum (adapter-side) and the numpy-based stats computation module.

**Files:**
- Create: `adapters/prometheus/app/core/methods.py`
- Create: `adapters/prometheus/app/core/stats.py`
- Create: `adapters/prometheus/tests/test_stats.py`
- Modify: `adapters/prometheus/pyproject.toml` (add numpy dependency)
- Modify: `adapters/prometheus/app/api/schemas.py` (use enum in validation)

- [ ] **Step 1: Add numpy dependency**

In `adapters/prometheus/pyproject.toml`, add `'numpy>=2.0'` to the `dependencies` list:

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "httpx>=0.27",
    "pyyaml>=6.0",
    "tenacity>=8.3",
    "structlog>=24.0",
    "redis>=5.0",
    "numpy>=2.0",
]
```

Then install: `uv sync --directory adapters/prometheus`

- [ ] **Step 2: Create the AggregationMethod enum**

Create `adapters/prometheus/app/core/methods.py`:

```python
"""Aggregation method enum — single source of truth for method names."""

from enum import StrEnum


class AggregationMethod(StrEnum):
    """Statistical aggregation methods available in aggregated query mode.

    StrEnum values ARE strings, so AggregationMethod.P99 == 'p99' is True.
    Works transparently with JSON, Pydantic, dict keys, and f-strings.
    """

    MIN = 'min'
    MEAN = 'mean'
    MAX = 'max'
    STD = 'std'
    SUM = 'sum'
    MEDIAN = 'median'
    P75 = 'p75'
    P90 = 'p90'
    P95 = 'p95'
    P99 = 'p99'
```

- [ ] **Step 3: Update adapter schemas to use enum**

In `adapters/prometheus/app/api/schemas.py`, replace the `ALLOWED_METHODS` frozenset and the `AggregatedQuerySpec.validate_methods` validator.

Replace:

```python
ALLOWED_METHODS = frozenset(
    ["min", "mean", "max", "std", "sum", "median", "p75", "p90", "p95", "p99"]
)
```

with an import:

```python
from app.core.methods import AggregationMethod
```

Replace the `AggregatedQuerySpec` class:

```python
class AggregatedQuerySpec(BaseModel):
    """Range-query spec that aggregates results over the evaluation window."""

    mode: str = 'aggregated'
    query_template: str
    interval: str
    methods: list[AggregationMethod] = Field(min_length=1)
```

Remove the `validate_methods` field_validator — Pydantic validates `list[AggregationMethod]` automatically and rejects invalid values.

- [ ] **Step 4: Write the failing stats tests**

Create `adapters/prometheus/tests/test_stats.py`:

```python
"""Tests for statistical computation module."""

import pytest

from app.core.methods import AggregationMethod
from app.core.stats import compute_statistics


class TestComputeStatistics:
    """Tests for the compute_statistics function."""

    def test_mean_of_simple_array(self) -> None:
        result = compute_statistics([1.0, 2.0, 3.0, 4.0, 5.0], [AggregationMethod.MEAN])
        assert result == {AggregationMethod.MEAN: pytest.approx(3.0)}

    def test_min_max(self) -> None:
        result = compute_statistics(
            [10.0, 1.0, 5.0, 9.0], [AggregationMethod.MIN, AggregationMethod.MAX]
        )
        assert result == {
            AggregationMethod.MIN: pytest.approx(1.0),
            AggregationMethod.MAX: pytest.approx(9.0),
        }

    def test_sum(self) -> None:
        result = compute_statistics([1.0, 2.0, 3.0], [AggregationMethod.SUM])
        assert result == {AggregationMethod.SUM: pytest.approx(6.0)}

    def test_std_population(self) -> None:
        # std with ddof=0 (population std dev)
        # [2, 4, 4, 4, 5, 5, 7, 9] -> mean=5, variance=4, std=2
        result = compute_statistics(
            [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0], [AggregationMethod.STD]
        )
        assert result == {AggregationMethod.STD: pytest.approx(2.0)}

    def test_median(self) -> None:
        result = compute_statistics([1.0, 3.0, 5.0, 7.0, 9.0], [AggregationMethod.MEDIAN])
        assert result == {AggregationMethod.MEDIAN: pytest.approx(5.0)}

    def test_median_even_count(self) -> None:
        result = compute_statistics([1.0, 3.0, 5.0, 7.0], [AggregationMethod.MEDIAN])
        assert result == {AggregationMethod.MEDIAN: pytest.approx(4.0)}

    def test_p99_large_array(self) -> None:
        data = [float(i) for i in range(1, 101)]
        result = compute_statistics(data, [AggregationMethod.P99])
        assert result[AggregationMethod.P99] == pytest.approx(99.01)

    def test_p90(self) -> None:
        data = [float(i) for i in range(1, 101)]
        result = compute_statistics(data, [AggregationMethod.P90])
        assert result[AggregationMethod.P90] == pytest.approx(90.1)

    def test_p95(self) -> None:
        data = [float(i) for i in range(1, 101)]
        result = compute_statistics(data, [AggregationMethod.P95])
        assert result[AggregationMethod.P95] == pytest.approx(95.05)

    def test_p75(self) -> None:
        data = [float(i) for i in range(1, 101)]
        result = compute_statistics(data, [AggregationMethod.P75])
        assert result[AggregationMethod.P75] == pytest.approx(75.25)

    def test_multiple_methods_at_once(self) -> None:
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        methods = [AggregationMethod.MEAN, AggregationMethod.MIN, AggregationMethod.MAX]
        result = compute_statistics(data, methods)
        assert result == {
            AggregationMethod.MEAN: pytest.approx(3.0),
            AggregationMethod.MIN: pytest.approx(1.0),
            AggregationMethod.MAX: pytest.approx(5.0),
        }

    def test_single_element(self) -> None:
        methods = [
            AggregationMethod.MEAN, AggregationMethod.MIN,
            AggregationMethod.MAX, AggregationMethod.MEDIAN,
        ]
        result = compute_statistics([42.0], methods)
        for m in methods:
            assert result[m] == pytest.approx(42.0)

    def test_std_single_element_is_zero(self) -> None:
        result = compute_statistics([42.0], [AggregationMethod.STD])
        assert result == {AggregationMethod.STD: pytest.approx(0.0)}

    def test_empty_array_returns_none_for_all(self) -> None:
        methods = [
            AggregationMethod.MEAN, AggregationMethod.MIN,
            AggregationMethod.MAX, AggregationMethod.STD, AggregationMethod.P99,
        ]
        result = compute_statistics([], methods)
        for m in methods:
            assert result[m] is None

    def test_only_requested_methods_computed(self) -> None:
        result = compute_statistics([1.0, 2.0, 3.0], [AggregationMethod.MEAN])
        assert list(result.keys()) == [AggregationMethod.MEAN]

    def test_enum_has_all_ten_methods(self) -> None:
        assert len(AggregationMethod) == 10

    def test_nan_values_filtered_out(self) -> None:
        result = compute_statistics(
            [1.0, float('nan'), 3.0, float('nan'), 5.0], [AggregationMethod.MEAN]
        )
        assert result == {AggregationMethod.MEAN: pytest.approx(3.0)}

    def test_all_nan_returns_none(self) -> None:
        result = compute_statistics(
            [float('nan'), float('nan')],
            [AggregationMethod.MEAN, AggregationMethod.P99],
        )
        assert result == {AggregationMethod.MEAN: None, AggregationMethod.P99: None}

    def test_enum_values_are_strings(self) -> None:
        """StrEnum values work as plain strings in dicts and f-strings."""
        assert AggregationMethod.P99 == 'p99'
        assert f'cpu.{AggregationMethod.P99}' == 'cpu.p99'
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `uv run --directory adapters/prometheus pytest tests/test_stats.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.stats'`

- [ ] **Step 6: Implement the stats module**

Create `adapters/prometheus/app/core/stats.py`:

```python
"""Statistical computation for aggregated-mode query results.

Uses numpy for efficient array operations. NaN values are filtered
before computation. Empty arrays after filtering produce None for all methods.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from app.core.methods import AggregationMethod

_PERCENTILE_MAP: dict[AggregationMethod, float] = {
    AggregationMethod.MEDIAN: 50.0,
    AggregationMethod.P75: 75.0,
    AggregationMethod.P90: 90.0,
    AggregationMethod.P95: 95.0,
    AggregationMethod.P99: 99.0,
}

_SIMPLE_DISPATCH: dict[AggregationMethod, object] = {
    AggregationMethod.MIN: lambda a: float(np.min(a)),
    AggregationMethod.MAX: lambda a: float(np.max(a)),
    AggregationMethod.MEAN: lambda a: float(np.mean(a)),
    AggregationMethod.SUM: lambda a: float(np.sum(a)),
    AggregationMethod.STD: lambda a: float(np.std(a, ddof=0)),
}


def compute_statistics(
    values: list[float],
    methods: list[AggregationMethod],
) -> dict[AggregationMethod, float | None]:
    """Compute requested statistics on a 1-D array of floats.

    NaN values are dropped before computation. If the array is empty after
    filtering, all methods return None.

    Args:
        values: Raw float values (may contain NaN).
        methods: List of AggregationMethod members to compute.

    Returns:
        Dict mapping each requested method to its computed value or None.
    """
    arr = np.array(values, dtype=np.float64)
    clean: NDArray[np.float64] = arr[~np.isnan(arr)]

    if clean.size == 0:
        return {m: None for m in methods}

    result: dict[AggregationMethod, float | None] = {}
    for method in methods:
        if method in _SIMPLE_DISPATCH:
            result[method] = _SIMPLE_DISPATCH[method](clean)
        elif method in _PERCENTILE_MAP:
            result[method] = float(np.percentile(clean, _PERCENTILE_MAP[method]))

    return result
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run --directory adapters/prometheus pytest tests/test_stats.py -v`
Expected: All tests PASS

- [ ] **Step 8: Run existing adapter tests for regressions**

Run: `uv run --directory adapters/prometheus pytest tests/ -v`
Expected: All tests PASS (schemas test may need update if it tested `ALLOWED_METHODS` directly)

- [ ] **Step 9: Commit**

```
git add adapters/prometheus/pyproject.toml adapters/prometheus/app/core/methods.py adapters/prometheus/app/core/stats.py adapters/prometheus/app/api/schemas.py adapters/prometheus/tests/test_stats.py
git commit -m "feat(adapter): add AggregationMethod enum and numpy-based stats module"
```

---

## Task 2: `range_query()` on PrometheusClient

Add a `range_query()` method to the existing Prometheus HTTP client that fetches matrix results from the `query_range` API.

**Files:**
- Modify: `adapters/prometheus/app/core/prometheus_client.py`
- Create: `adapters/prometheus/tests/test_range_query.py`

- [ ] **Step 1: Write the failing tests**

Create `adapters/prometheus/tests/test_range_query.py`:

```python
"""Tests for PrometheusClient.range_query()."""

import math
from urllib.parse import parse_qs, urlparse

import pytest
import respx
from app.core.prometheus_client import PrometheusClient, PrometheusQueryError
from httpx import Response


@pytest.fixture
def client() -> PrometheusClient:
    return PrometheusClient(base_url='http://prom:9090', timeout=5.0)


@respx.mock
@pytest.mark.asyncio
async def test_range_query_returns_matrix_values(client: PrometheusClient) -> None:
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {
                    'resultType': 'matrix',
                    'result': [
                        {
                            'metric': {'instance': 'localhost:9090'},
                            'values': [
                                [1705312800, '1.5'],
                                [1705312860, '2.5'],
                                [1705312920, '3.5'],
                            ],
                        }
                    ],
                },
            },
        )
    )
    values = await client.range_query(
        'rate(cpu[1m])',
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:03:00Z',
        step='1m',
    )
    assert values == [1.5, 2.5, 3.5]


@respx.mock
@pytest.mark.asyncio
async def test_range_query_flattens_multiple_series(client: PrometheusClient) -> None:
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {
                    'resultType': 'matrix',
                    'result': [
                        {
                            'metric': {'instance': 'a'},
                            'values': [[1705312800, '1.0'], [1705312860, '2.0']],
                        },
                        {
                            'metric': {'instance': 'b'},
                            'values': [[1705312800, '3.0'], [1705312860, '4.0']],
                        },
                    ],
                },
            },
        )
    )
    values = await client.range_query('rate(cpu[1m])', start='s', end='e', step='1m')
    assert values == [1.0, 2.0, 3.0, 4.0]


@respx.mock
@pytest.mark.asyncio
async def test_range_query_empty_matrix(client: PrometheusClient) -> None:
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {'resultType': 'matrix', 'result': []},
            },
        )
    )
    values = await client.range_query('nonexistent', start='s', end='e', step='1m')
    assert values == []


@respx.mock
@pytest.mark.asyncio
async def test_range_query_nan_preserved_as_nan(client: PrometheusClient) -> None:
    """NaN values from Prometheus are kept — stats module handles filtering."""
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {
                    'resultType': 'matrix',
                    'result': [
                        {
                            'metric': {},
                            'values': [[1705312800, '1.0'], [1705312860, 'NaN']],
                        }
                    ],
                },
            },
        )
    )
    values = await client.range_query('q', start='s', end='e', step='1m')
    assert values[0] == 1.0
    assert math.isnan(values[1])


@respx.mock
@pytest.mark.asyncio
async def test_range_query_unexpected_result_type(client: PrometheusClient) -> None:
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {'resultType': 'vector', 'result': []},
            },
        )
    )
    with pytest.raises(PrometheusQueryError, match='expected matrix'):
        await client.range_query('q', start='s', end='e', step='1m')


@respx.mock
@pytest.mark.asyncio
async def test_range_query_sends_correct_params(client: PrometheusClient) -> None:
    route = respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {'resultType': 'matrix', 'result': []},
            },
        )
    )
    await client.range_query(
        'up', start='2026-01-15T10:00:00Z', end='2026-01-15T11:00:00Z', step='5m'
    )
    url = str(route.calls[0].request.url)
    params = parse_qs(urlparse(url).query)
    assert params['query'] == ['up']
    assert params['start'] == ['2026-01-15T10:00:00Z']
    assert params['end'] == ['2026-01-15T11:00:00Z']
    assert params['step'] == ['5m']
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory adapters/prometheus pytest tests/test_range_query.py -v`
Expected: FAIL — `AttributeError: 'PrometheusClient' object has no attribute 'range_query'`

- [ ] **Step 3: Implement `range_query()`**

Add the following methods to `PrometheusClient` in `adapters/prometheus/app/core/prometheus_client.py`, after `instant_query()`:

```python
    async def range_query(
        self,
        query: str,
        *,
        start: str,
        end: str,
        step: str,
    ) -> list[float]:
        """Execute a range query and return a flat list of float values.

        All series in the matrix result are concatenated into a single list.
        NaN/Inf values are preserved (caller is responsible for filtering).

        Raises PrometheusQueryError on any failure.
        """
        params = {'query': query, 'start': start, 'end': end, 'step': step}
        data = await self._get('/api/v1/query_range', params)
        return self._extract_matrix(data)

    def _extract_matrix(self, data: dict[str, Any]) -> list[float]:
        result_type = data['resultType']
        if result_type != 'matrix':
            raise PrometheusQueryError(f'expected matrix result type, got: {result_type}')

        values: list[float] = []
        for series in data['result']:
            for _ts, raw in series['values']:
                values.append(float(raw))
        return values
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory adapters/prometheus pytest tests/test_range_query.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```
git add adapters/prometheus/app/core/prometheus_client.py adapters/prometheus/tests/test_range_query.py
git commit -m "feat(adapter): add range_query() to PrometheusClient"
```

---

## Task 3: AggregatedQueryStrategy

The core aggregated-mode strategy: variable substitution (with `$interval` override), time-range chunking, parallel chunk fetches, flatten, stats computation, metadata assembly.

**Files:**
- Create: `adapters/prometheus/app/core/strategies/aggregated.py`
- Create: `adapters/prometheus/tests/test_aggregated_strategy.py`

- [ ] **Step 1: Write the failing tests**

Create `adapters/prometheus/tests/test_aggregated_strategy.py`:

```python
"""Tests for AggregatedQueryStrategy."""

from urllib.parse import parse_qs, unquote, urlparse

import pytest
import respx
from app.core.prometheus_client import PrometheusClient
from app.core.strategies.aggregated import AggregatedQueryStrategy
from httpx import Response


def _matrix_response(values: list[list]) -> Response:
    """Build a Prometheus matrix response from [[ts, val], ...] pairs."""
    return Response(
        200,
        json={
            'status': 'success',
            'data': {
                'resultType': 'matrix',
                'result': [{'metric': {}, 'values': values}],
            },
        },
    )


@pytest.fixture
def strategy() -> AggregatedQueryStrategy:
    client = PrometheusClient(base_url='http://prom:9090', timeout=5.0)
    return AggregatedQueryStrategy(client, chunk_size='4h', parallel_chunks=3)


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_basic_mean_and_max(strategy: AggregatedQueryStrategy) -> None:
    """Short eval window (< chunk_size) -> single query_range call."""
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=_matrix_response([
            [1705312800, '1.0'],
            [1705312860, '2.0'],
            [1705312920, '3.0'],
            [1705312980, '4.0'],
            [1705313040, '5.0'],
        ])
    )
    values, errors, metadata = await strategy.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '1m',
            'methods': ['mean', 'max'],
        },
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    assert values['cpu.mean'] == pytest.approx(3.0)
    assert values['cpu.max'] == pytest.approx(5.0)
    assert errors == {}
    assert metadata is not None
    assert metadata['mode'] == 'aggregated'
    assert metadata['actual_samples'] == 5


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_interval_substitution(
    strategy: AggregatedQueryStrategy,
) -> None:
    """$interval in query_template is replaced with the spec's interval value."""
    route = respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=_matrix_response([[1705312800, '1.0']])
    )
    await strategy.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '5m',
            'methods': ['mean'],
        },
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    url = unquote(str(route.calls[0].request.url))
    assert 'rate(cpu[5m])' in url


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_step_matches_interval(
    strategy: AggregatedQueryStrategy,
) -> None:
    """query_range step parameter must equal the spec's interval."""
    route = respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=_matrix_response([[1705312800, '1.0']])
    )
    await strategy.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '5m',
            'methods': ['mean'],
        },
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    params = parse_qs(urlparse(str(route.calls[0].request.url)).query)
    assert params['step'] == ['5m']


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_variable_substitution(
    strategy: AggregatedQueryStrategy,
) -> None:
    """User variables are substituted alongside $interval."""
    route = respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=_matrix_response([[1705312800, '1.0']])
    )
    await strategy.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu{job="$SERVICE"}[$interval])',
            'interval': '1m',
            'methods': ['mean'],
        },
        variables={'SERVICE': 'api'},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    url = unquote(str(route.calls[0].request.url))
    assert 'job="api"' in url


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_unresolved_variable_error(
    strategy: AggregatedQueryStrategy,
) -> None:
    values, errors, metadata = await strategy.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu{host=$HOST}[$interval])',
            'interval': '1m',
            'methods': ['mean'],
        },
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    assert values['cpu.mean'] is None
    assert 'unresolved' in errors['cpu.mean'].lower()


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_empty_result_returns_none(
    strategy: AggregatedQueryStrategy,
) -> None:
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=Response(
            200,
            json={
                'status': 'success',
                'data': {'resultType': 'matrix', 'result': []},
            },
        )
    )
    values, errors, metadata = await strategy.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '1m',
            'methods': ['mean', 'p99'],
        },
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    assert values == {'cpu.mean': None, 'cpu.p99': None}
    assert 'no valid data points' in errors['cpu.mean']


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_metadata_sample_counts(
    strategy: AggregatedQueryStrategy,
) -> None:
    """Metadata includes expected and actual sample counts."""
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=_matrix_response([
            [1705312800, '1.0'],
            [1705312860, '2.0'],
            [1705312920, '3.0'],
        ])
    )
    _values, _errors, metadata = await strategy.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '1m',
            'methods': ['mean'],
        },
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    assert metadata is not None
    assert metadata['expected_samples'] == 5
    assert metadata['actual_samples'] == 3
    assert metadata['missing_pct'] == pytest.approx(40.0)
    assert metadata['chunks_failed'] == 0


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_prometheus_error_captured(
    strategy: AggregatedQueryStrategy,
) -> None:
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=Response(500, text='internal server error')
    )
    values, errors, metadata = await strategy.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '1m',
            'methods': ['mean'],
        },
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    assert values['cpu.mean'] is None
    assert 'cpu.mean' in errors
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory adapters/prometheus pytest tests/test_aggregated_strategy.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.strategies.aggregated'`

- [ ] **Step 3: Implement AggregatedQueryStrategy**

Create `adapters/prometheus/app/core/strategies/aggregated.py`:

```python
"""Aggregated query strategy — fetches time-series via query_range, computes statistics."""

from __future__ import annotations

import asyncio
import logging
import math
import re
from datetime import datetime, timedelta
from typing import Any

from app.core.methods import AggregationMethod
from app.core.prometheus_client import PrometheusClient, PrometheusQueryError
from app.core.stats import compute_statistics
from app.core.variable_substitutor import UnresolvedVariableError, substitute

logger = logging.getLogger(__name__)

_DURATION_RE = re.compile(r'^(\d+)([smhd])$')
_DURATION_MULTIPLIERS = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}


def _parse_duration_seconds(duration: str) -> int:
    """Parse a Prometheus-style duration string (e.g. '4h', '1m') to seconds."""
    match = _DURATION_RE.match(duration)
    if not match:
        raise ValueError(f'invalid duration format: {duration}')
    return int(match.group(1)) * _DURATION_MULTIPLIERS[match.group(2)]


class AggregatedQueryStrategy:
    """Fetches time-series via query_range, computes requested statistical methods."""

    def __init__(
        self,
        client: PrometheusClient,
        chunk_size: str = '4h',
        parallel_chunks: int = 3,
    ) -> None:
        self._client = client
        self._chunk_size_seconds = _parse_duration_seconds(chunk_size)
        self._parallel_chunks = parallel_chunks

    async def execute(
        self,
        *,
        sli_name: str,
        query_spec: dict[str, Any],
        variables: dict[str, str],
        start: str,
        end: str,
    ) -> tuple[dict[str, float | None], dict[str, str], dict[str, Any] | None]:
        """Execute an aggregated query: fetch range data, compute stats."""
        query_template = query_spec['query_template']
        interval = query_spec['interval']
        method_strings: list[str] = query_spec['methods']
        methods = [AggregationMethod(m) for m in method_strings]

        # Substitute variables with $interval override
        try:
            query = substitute(
                query_template,
                variables,
                start_iso=start,
                end_iso=end,
                interval_override=interval,
            )
        except UnresolvedVariableError as exc:
            logger.warning('variable substitution failed: sli=%s error=%s', sli_name, exc)
            error_msg = str(exc)
            values = {f'{sli_name}.{m}': None for m in methods}
            errors = {f'{sli_name}.{m}': error_msg for m in methods}
            return values, errors, None

        # Fetch data (with chunking for long time ranges)
        all_values, chunks_failed = await self._fetch_range(
            query=query, start=start, end=end, step=interval
        )

        # Compute expected sample count
        interval_seconds = _parse_duration_seconds(interval)
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        eval_window_seconds = (end_dt - start_dt).total_seconds()
        expected_samples = max(1, int(eval_window_seconds / interval_seconds))

        # Filter NaN for actual count (stats module also filters, but we need count for metadata)
        actual_samples = sum(1 for v in all_values if not math.isnan(v))

        # Compute statistics
        stats = compute_statistics(all_values, methods)

        # Build result dicts — keys are plain strings for JSON serialization
        values: dict[str, float | None] = {}
        errors: dict[str, str] = {}
        for method in methods:
            key = f'{sli_name}.{method}'
            val = stats[method]
            values[key] = val
            if val is None:
                errors[key] = 'no valid data points'

        # Build metadata
        missing_pct = (
            round((1 - actual_samples / expected_samples) * 100, 1)
            if expected_samples > 0
            else 0.0
        )
        metadata: dict[str, Any] = {
            'mode': 'aggregated',
            'expected_samples': expected_samples,
            'actual_samples': actual_samples,
            'missing_pct': missing_pct,
            'chunks_failed': chunks_failed,
        }

        logger.info(
            'aggregated result: sli=%s methods=%s actual=%d/%d chunks_failed=%d',
            sli_name, methods, actual_samples, expected_samples, chunks_failed,
        )
        return values, errors, metadata

    async def _fetch_range(
        self, *, query: str, start: str, end: str, step: str
    ) -> tuple[list[float], int]:
        """Fetch range data, chunking if the window exceeds chunk_size.

        Returns (all_values, chunks_failed_count).
        """
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        window_seconds = (end_dt - start_dt).total_seconds()

        if window_seconds <= self._chunk_size_seconds:
            try:
                values = await self._client.range_query(
                    query, start=start, end=end, step=step
                )
                return values, 0
            except PrometheusQueryError:
                logger.exception('range query failed: query=%s', query)
                return [], 1

        # Split into chunks
        chunks: list[tuple[str, str]] = []
        chunk_start = start_dt
        while chunk_start < end_dt:
            chunk_end = min(chunk_start + timedelta(seconds=self._chunk_size_seconds), end_dt)
            chunks.append((chunk_start.isoformat(), chunk_end.isoformat()))
            chunk_start = chunk_end

        all_values: list[float] = []
        chunks_failed = 0

        # Process chunks with limited parallelism
        sem = asyncio.Semaphore(self._parallel_chunks)

        async def _fetch_chunk(c_start: str, c_end: str) -> list[float] | None:
            async with sem:
                try:
                    return await self._client.range_query(
                        query, start=c_start, end=c_end, step=step
                    )
                except PrometheusQueryError:
                    logger.exception(
                        'chunk failed: query=%s start=%s end=%s', query, c_start, c_end
                    )
                    return None

        tasks = [_fetch_chunk(cs, ce) for cs, ce in chunks]
        results = await asyncio.gather(*tasks)

        for chunk_result in results:
            if chunk_result is None:
                chunks_failed += 1
            else:
                all_values.extend(chunk_result)

        return all_values, chunks_failed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory adapters/prometheus pytest tests/test_aggregated_strategy.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```
git add adapters/prometheus/app/core/strategies/aggregated.py adapters/prometheus/tests/test_aggregated_strategy.py
git commit -m "feat(adapter): add AggregatedQueryStrategy with chunking and stats"
```

---

## Task 4: Chunking Tests

Add dedicated tests for chunking behavior — long eval windows, chunk failures, parallel limits.

**Files:**
- Modify: `adapters/prometheus/tests/test_aggregated_strategy.py`

- [ ] **Step 1: Write chunking tests**

Append to `adapters/prometheus/tests/test_aggregated_strategy.py`:

```python
@respx.mock
@pytest.mark.asyncio
async def test_aggregated_chunking_8h_window() -> None:
    """8h eval with 4h chunk_size -> 2 query_range calls."""
    client = PrometheusClient(base_url='http://prom:9090', timeout=5.0)
    strat = AggregatedQueryStrategy(client, chunk_size='4h', parallel_chunks=3)

    route = respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=_matrix_response([
            [1705312800, '1.0'],
            [1705312860, '2.0'],
        ])
    )

    values, errors, metadata = await strat.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '1m',
            'methods': ['mean'],
        },
        variables={},
        start='2026-01-15T00:00:00+00:00',
        end='2026-01-15T08:00:00+00:00',
    )
    # 2 chunks x 2 values each = 4 total values -> mean = 1.5
    assert len(route.calls) == 2
    assert values['cpu.mean'] == pytest.approx(1.5)
    assert metadata is not None
    assert metadata['chunks_failed'] == 0


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_chunk_failure_isolated() -> None:
    """If one chunk fails, remaining chunks still produce valid stats."""
    client = PrometheusClient(base_url='http://prom:9090', timeout=5.0)
    strat = AggregatedQueryStrategy(client, chunk_size='4h', parallel_chunks=3)

    call_count = 0

    def side_effect(request, route):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return Response(500, text='chunk error')
        return _matrix_response([[1705312800, '10.0'], [1705312860, '20.0']])

    respx.get('http://prom:9090/api/v1/query_range').mock(side_effect=side_effect)

    values, errors, metadata = await strat.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '1m',
            'methods': ['mean'],
        },
        variables={},
        start='2026-01-15T00:00:00+00:00',
        end='2026-01-15T08:00:00+00:00',
    )
    assert values['cpu.mean'] == pytest.approx(15.0)
    assert metadata is not None
    assert metadata['chunks_failed'] == 1


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_all_chunks_fail() -> None:
    """All chunks fail -> all methods return None with error."""
    client = PrometheusClient(base_url='http://prom:9090', timeout=5.0)
    strat = AggregatedQueryStrategy(client, chunk_size='4h', parallel_chunks=3)

    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=Response(500, text='error')
    )

    values, errors, metadata = await strat.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '1m',
            'methods': ['mean', 'p99'],
        },
        variables={},
        start='2026-01-15T00:00:00+00:00',
        end='2026-01-15T08:00:00+00:00',
    )
    assert values['cpu.mean'] is None
    assert values['cpu.p99'] is None
    assert 'no valid data points' in errors['cpu.mean']
    assert metadata is not None
    assert metadata['chunks_failed'] == 2


@respx.mock
@pytest.mark.asyncio
async def test_aggregated_short_window_no_chunking() -> None:
    """Window shorter than chunk_size -> exactly 1 query_range call."""
    client = PrometheusClient(base_url='http://prom:9090', timeout=5.0)
    strat = AggregatedQueryStrategy(client, chunk_size='4h', parallel_chunks=3)

    route = respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=_matrix_response([[1705312800, '5.0']])
    )

    await strat.execute(
        sli_name='cpu',
        query_spec={
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '1m',
            'methods': ['mean'],
        },
        variables={},
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:30:00Z',
    )
    assert len(route.calls) == 1
```

- [ ] **Step 2: Run all strategy tests**

Run: `uv run --directory adapters/prometheus pytest tests/test_aggregated_strategy.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```
git add adapters/prometheus/tests/test_aggregated_strategy.py
git commit -m "test(adapter): add chunking behavior tests for aggregated strategy"
```

---

## Task 5: Wire AggregatedQueryStrategy into Adapter

Register the strategy in the app factory and update coordinator + sync endpoint to handle metadata.

**Files:**
- Modify: `adapters/prometheus/app/main.py`
- Modify: `adapters/prometheus/app/core/coordinator.py`
- Modify: `adapters/prometheus/app/api/routes.py`
- Modify: `adapters/prometheus/app/redis/repository.py`
- Modify: `adapters/prometheus/app/core/job_manager.py`

- [ ] **Step 1: Register strategy in app factory**

In `adapters/prometheus/app/main.py`, add the import at the top with the other strategy import:

```python
from app.core.strategies.aggregated import AggregatedQueryStrategy
```

Then change the strategies dict in the `lifespan` function from:

```python
        strategies = {'raw': RawQueryStrategy(prom_client)}
```

to:

```python
        strategies = {
            'raw': RawQueryStrategy(prom_client),
            'aggregated': AggregatedQueryStrategy(
                prom_client,
                chunk_size=settings.default_chunk_size,
                parallel_chunks=settings.default_parallel_chunks,
            ),
        }
```

- [ ] **Step 2: Add metadata storage to Redis repository**

In `adapters/prometheus/app/redis/repository.py`, add two methods after `get_results()`:

```python
    async def write_metadata(
        self, job_id: str, sli_name: str, metadata: dict[str, Any]
    ) -> None:
        """Store per-SLI metadata (sample counts, etc.) for a job."""
        await self._r.hset(
            self._key('job', job_id, 'metadata'), sli_name, json.dumps(metadata)
        )

    async def get_metadata(self, job_id: str) -> dict[str, dict[str, Any]]:
        """Return all per-SLI metadata for a job."""
        raw = await self._r.hgetall(self._key('job', job_id, 'metadata'))
        return {_decode(k): json.loads(_decode(v)) for k, v in raw.items()}
```

Also update `mark_completed()` to set TTL on the metadata key — add this line after the existing `expire` calls:

```python
        await self._r.expire(self._key('job', job_id, 'metadata'), retention_seconds)
```

- [ ] **Step 3: Store metadata in coordinator**

In `adapters/prometheus/app/core/coordinator.py`, update the `_run_query` inner function. Change `_metadata` to `metadata`:

```python
                values, errors, metadata = await strategy.execute(
```

And after the result-writing loop (after the `for name, value in values.items():` block), add:

```python
                if metadata is not None:
                    await self._repo.write_metadata(job_id, sli_name, metadata)
```

- [ ] **Step 4: Return metadata in job status and sync endpoint**

In `adapters/prometheus/app/core/job_manager.py`, update the `get_status` method. After the line `result['results'] = [{'indicator': k, **v} for k, v in results.items()]`, add:

```python
            metadata = await self._repo.get_metadata(job_id)
            if metadata:
                result['metadata'] = metadata
```

In `adapters/prometheus/app/api/routes.py`, update the `sync_query` function. Change the return from:

```python
    return {'values': values, 'errors': errors}
```

to:

```python
    metadata = status.get('metadata', {})
    return {'values': values, 'errors': errors, 'metadata': metadata}
```

- [ ] **Step 5: Run existing tests to ensure no regressions**

Run: `uv run --directory adapters/prometheus pytest tests/ -v`
Expected: All existing tests PASS

- [ ] **Step 6: Commit**

```
git add adapters/prometheus/app/main.py adapters/prometheus/app/core/coordinator.py adapters/prometheus/app/api/routes.py adapters/prometheus/app/redis/repository.py adapters/prometheus/app/core/job_manager.py
git commit -m "feat(adapter): wire aggregated strategy into app, store and return metadata"
```

---

## Task 6: SLI Registry Mode-Dependent Validation

Add `AggregationMethod` StrEnum to the API and use it for mode-dependent Pydantic validation.

**Files:**
- Modify: `api/app/modules/sli_registry/schemas.py`
- Modify: `api/app/modules/sli_registry/repository.py`
- Modify: `api/app/modules/sli_registry/router.py`
- Create: `api/tests/test_sli_schema_validation.py`

- [ ] **Step 1: Write failing tests**

Create `api/tests/test_sli_schema_validation.py`:

```python
"""Tests for SLI definition mode-dependent validation."""

import pytest
from pydantic import ValidationError

from app.modules.sli_registry.schemas import AggregationMethod, SLIDefinitionCreate


class TestRawModeValidation:
    def test_raw_mode_with_indicators_valid(self) -> None:
        sli = SLIDefinitionCreate(
            name='test',
            adapter_type='prometheus',
            mode='raw',
            indicators={'cpu': 'rate(cpu[5m])'},
        )
        assert sli.mode == 'raw'
        assert sli.indicators == {'cpu': 'rate(cpu[5m])'}

    def test_raw_mode_without_indicators_rejected(self) -> None:
        with pytest.raises(ValidationError, match='indicators'):
            SLIDefinitionCreate(
                name='test',
                adapter_type='prometheus',
                mode='raw',
                indicators={},
            )

    def test_raw_mode_with_aggregated_fields_rejected(self) -> None:
        with pytest.raises(ValidationError, match='query_template'):
            SLIDefinitionCreate(
                name='test',
                adapter_type='prometheus',
                mode='raw',
                indicators={'cpu': 'rate(cpu[5m])'},
                query_template='rate(cpu[$interval])',
            )

    def test_raw_mode_default(self) -> None:
        sli = SLIDefinitionCreate(
            name='test',
            adapter_type='prometheus',
            indicators={'cpu': 'rate(cpu[5m])'},
        )
        assert sli.mode == 'raw'


class TestAggregatedModeValidation:
    def test_aggregated_mode_valid(self) -> None:
        sli = SLIDefinitionCreate(
            name='test',
            adapter_type='prometheus',
            mode='aggregated',
            query_template='rate(cpu[$interval])',
            interval='1m',
            methods=[AggregationMethod.MEAN, AggregationMethod.P99],
        )
        assert sli.mode == 'aggregated'

    def test_aggregated_mode_accepts_string_methods(self) -> None:
        """Pydantic coerces plain strings to AggregationMethod enum values."""
        sli = SLIDefinitionCreate(
            name='test',
            adapter_type='prometheus',
            mode='aggregated',
            query_template='rate(cpu[$interval])',
            interval='1m',
            methods=['mean', 'p99'],
        )
        assert sli.methods == [AggregationMethod.MEAN, AggregationMethod.P99]

    def test_aggregated_mode_without_query_template_rejected(self) -> None:
        with pytest.raises(ValidationError, match='query_template'):
            SLIDefinitionCreate(
                name='test',
                adapter_type='prometheus',
                mode='aggregated',
                interval='1m',
                methods=['mean'],
            )

    def test_aggregated_mode_without_interval_rejected(self) -> None:
        with pytest.raises(ValidationError, match='interval'):
            SLIDefinitionCreate(
                name='test',
                adapter_type='prometheus',
                mode='aggregated',
                query_template='rate(cpu[$interval])',
                methods=['mean'],
            )

    def test_aggregated_mode_without_methods_rejected(self) -> None:
        with pytest.raises(ValidationError, match='methods'):
            SLIDefinitionCreate(
                name='test',
                adapter_type='prometheus',
                mode='aggregated',
                query_template='rate(cpu[$interval])',
                interval='1m',
            )

    def test_aggregated_mode_empty_methods_rejected(self) -> None:
        with pytest.raises(ValidationError, match='methods'):
            SLIDefinitionCreate(
                name='test',
                adapter_type='prometheus',
                mode='aggregated',
                query_template='rate(cpu[$interval])',
                interval='1m',
                methods=[],
            )

    def test_aggregated_mode_invalid_method_rejected(self) -> None:
        with pytest.raises(ValidationError, match='invalid_method'):
            SLIDefinitionCreate(
                name='test',
                adapter_type='prometheus',
                mode='aggregated',
                query_template='rate(cpu[$interval])',
                interval='1m',
                methods=['mean', 'invalid_method'],
            )

    def test_aggregated_mode_with_indicators_rejected(self) -> None:
        with pytest.raises(ValidationError, match='indicators'):
            SLIDefinitionCreate(
                name='test',
                adapter_type='prometheus',
                mode='aggregated',
                query_template='rate(cpu[$interval])',
                interval='1m',
                methods=['mean'],
                indicators={'cpu': 'rate(cpu[5m])'},
            )

    def test_aggregated_mode_all_methods_valid(self) -> None:
        sli = SLIDefinitionCreate(
            name='test',
            adapter_type='prometheus',
            mode='aggregated',
            query_template='rate(cpu[$interval])',
            interval='1m',
            methods=list(AggregationMethod),
        )
        assert set(sli.methods) == set(AggregationMethod)

    def test_invalid_mode_rejected(self) -> None:
        with pytest.raises(ValidationError, match='mode'):
            SLIDefinitionCreate(
                name='test',
                adapter_type='prometheus',
                mode='unknown',
                indicators={'cpu': 'rate(cpu[5m])'},
            )

    def test_enum_has_ten_members(self) -> None:
        assert len(AggregationMethod) == 10
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/api-test.sh --tail 20 tests/test_sli_schema_validation.py -v`
Expected: Most tests FAIL — no validation logic yet

- [ ] **Step 3: Add AggregationMethod enum and mode-dependent validation to schema**

Replace the content of `api/app/modules/sli_registry/schemas.py`:

```python
"""Pydantic schemas for SLI definition versioned CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

ALLOWED_MODES = frozenset(['raw', 'aggregated'])


class AggregationMethod(StrEnum):
    """Statistical aggregation methods available in aggregated query mode."""

    MIN = 'min'
    MEAN = 'mean'
    MAX = 'max'
    STD = 'std'
    SUM = 'sum'
    MEDIAN = 'median'
    P75 = 'p75'
    P90 = 'p90'
    P95 = 'p95'
    P99 = 'p99'


class SLIDefinitionCreate(BaseModel):
    """Request body for creating an SLI definition."""

    name: str
    adapter_type: str
    display_name: str | None = None
    mode: str = 'raw'

    # Raw mode fields
    indicators: dict[str, str] = {}

    # Aggregated mode fields
    query_template: str | None = None
    interval: str | None = None
    methods: list[AggregationMethod] | None = None

    # Common fields
    notes: str | None = None
    author: str | None = None
    tags: dict[str, Any] = {}
    comparable_from_version: int | None = None

    @model_validator(mode='after')
    def validate_mode_fields(self) -> SLIDefinitionCreate:
        """Enforce mode-dependent field requirements."""
        if self.mode not in ALLOWED_MODES:
            msg = f'mode must be one of {sorted(ALLOWED_MODES)}, got {self.mode!r}'
            raise ValueError(msg)

        if self.mode == 'raw':
            if not self.indicators:
                msg = 'indicators must be non-empty for mode raw'
                raise ValueError(msg)
            if self.query_template is not None:
                msg = 'query_template must not be set for mode raw'
                raise ValueError(msg)
            if self.interval is not None:
                msg = 'interval must not be set for mode raw'
                raise ValueError(msg)
            if self.methods is not None:
                msg = 'methods must not be set for mode raw'
                raise ValueError(msg)

        elif self.mode == 'aggregated':
            if self.indicators:
                msg = 'indicators must be empty for mode aggregated'
                raise ValueError(msg)
            if not self.query_template:
                msg = 'query_template is required for mode aggregated'
                raise ValueError(msg)
            if not self.interval:
                msg = 'interval is required for mode aggregated'
                raise ValueError(msg)
            if not self.methods:
                msg = 'methods must be non-empty for mode aggregated'
                raise ValueError(msg)

        return self


class SLIDefinitionRead(BaseModel):
    """Response schema for an SLI definition."""

    id: uuid.UUID
    name: str
    adapter_type: str
    display_name: str | None
    version: int
    comparable_from_version: int
    indicators: dict[str, str]
    notes: str | None
    author: str | None
    tags: dict[str, Any]
    mode: str
    query_template: str | None
    interval: str | None
    methods: list[str] | None
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/api-test.sh --tail 20 tests/test_sli_schema_validation.py -v`
Expected: All tests PASS

- [ ] **Step 5: Update repository and router to persist aggregated fields**

In `api/app/modules/sli_registry/repository.py`, update the `create()` method signature to accept the new fields. Add parameters after `comparable_from_version`:

```python
        mode: str = 'raw',
        query_template: str | None = None,
        interval: str | None = None,
        methods: list[str] | None = None,
```

And set them on the `SLIDefinition` constructor, after `comparable_from_version=resolved_cfv,`:

```python
            mode=mode,
            query_template=query_template,
            interval=interval,
            methods=methods,
```

In `api/app/modules/sli_registry/router.py`, update the `create_sli_definition` handler. Change the `repo.create()` call to pass the new fields:

```python
    sli = await repo.create(
        body.name,
        indicators=body.indicators,
        adapter_type=body.adapter_type,
        display_name=body.display_name,
        notes=body.notes,
        author=body.author,
        tags=body.tags,
        comparable_from_version=body.comparable_from_version,
        mode=body.mode,
        query_template=body.query_template,
        interval=body.interval,
        methods=body.methods,
    )
```

- [ ] **Step 6: Run full unit test suite**

Run: `./scripts/api-test.sh --tail 5`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```
git add api/app/modules/sli_registry/schemas.py api/app/modules/sli_registry/repository.py api/app/modules/sli_registry/router.py api/tests/test_sli_schema_validation.py
git commit -m "feat(api): add AggregationMethod enum and mode-dependent SLI validation"
```

---

## Task 7: SLO Template `method_criteria` Column

Add the `method_criteria` JSONB column to `SLODefinition` and expose it in the schemas.

**Files:**
- Modify: `api/app/db/models.py`
- Modify: `api/app/modules/slo_registry/schemas.py`
- Modify: `api/app/modules/slo_registry/repository.py`

- [ ] **Step 1: Add column to model**

In `api/app/db/models.py`, in the `SLODefinition` class, add after the `sli_version` column (before `generated_by_group_id`):

```python
    method_criteria:         Mapped[dict[str, Any] | None]  = mapped_column(JSONB, nullable=True)
```

- [ ] **Step 2: Add field to schemas**

In `api/app/modules/slo_registry/schemas.py`, add `method_criteria` to both `SLODefinitionCreate` and `SLODefinitionRead`.

In `SLODefinitionCreate`, add after `sli_version`:

```python
    method_criteria: dict[str, Any] | None = None
```

In `SLODefinitionRead`, add after `sli_version`:

```python
    method_criteria: dict[str, Any] | None
```

- [ ] **Step 3: Update repository to persist method_criteria**

In `api/app/modules/slo_registry/repository.py`, add `method_criteria` to the `create()` parameter list and set it on the `SLODefinition` constructor. Read the file first to find the exact signature.

- [ ] **Step 4: Generate database migration**

Run: `./scripts/db-regen-migrations.sh`

Verify the migration creates the `method_criteria` column.

- [ ] **Step 5: Run unit tests**

Run: `./scripts/api-test.sh --tail 5`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```
git add api/app/db/models.py api/app/modules/slo_registry/schemas.py api/app/modules/slo_registry/repository.py api/alembic/versions/
git commit -m "feat(api): add method_criteria column to SLO definitions"
```

---

## Task 8: Worker — Build Aggregated-Mode Adapter Requests

Update the evaluation worker to build the correct query specs for aggregated-mode SLIs and map the expanded `{sli}.{method}` results back to objectives.

**Files:**
- Modify: `api/app/modules/quality_gate/worker.py`
- Modify: `api/app/modules/quality_gate/adapter_client.py`

- [ ] **Step 1: Update adapter_client to return metadata**

In `api/app/modules/quality_gate/adapter_client.py`, change the `query()` return type to a 3-tuple that includes metadata:

```python
    ) -> tuple[dict[str, float | None], dict[str, str], dict[str, Any]]:
```

Update the return statement at the end of `query()`:

```python
        metadata: dict[str, Any] = data.get('metadata', {})
        logger.info(
            'adapter response',
            url=url,
            values=len(metrics_fetched),
            errors=len(fetch_errors),
            metadata_slis=len(metadata),
        )
        return metrics_fetched, fetch_errors, metadata
```

Add `Any` to the typing import at the top if not already present.

- [ ] **Step 2: Add query spec builder function to worker**

In `api/app/modules/quality_gate/worker.py`, add before `run_evaluation`:

```python
def _build_query_specs(
    sli_def: SLIDefinition,
    resolved_queries: dict[str, str],
) -> dict[str, dict]:
    """Build adapter query specs from the SLI definition.

    For raw mode: wraps each resolved query string into {mode: raw, query: ...}.
    For aggregated mode: builds a single {mode: aggregated, ...} spec.
    """
    if sli_def.mode == 'aggregated':
        return {
            sli_def.name: {
                'mode': 'aggregated',
                'query_template': sli_def.query_template,
                'interval': sli_def.interval,
                'methods': sli_def.methods,
            }
        }
    return {
        name: {'mode': 'raw', 'query': query}
        for name, query in resolved_queries.items()
    }
```

- [ ] **Step 3: Update `_query_adapter_safe` signature**

Change the signature to accept `query_specs` and `variables` instead of `resolved_queries`:

```python
async def _query_adapter_safe(
    log: structlog.stdlib.BoundLogger,
    repo: EvaluationRepository,
    eval_id: uuid.UUID,
    ds: Any,
    query_specs: dict[str, dict],
    variables: dict[str, str],
    start: str,
    end: str,
) -> tuple[dict[str, float | None], dict[str, str], dict[str, Any]] | None:
```

Remove the raw-mode wrapping inside the function body. Pass `query_specs` and `variables` directly to `adapter_client.query()`.

- [ ] **Step 4: Update `run_evaluation` to use new functions**

Replace the variable substitution / query building section:

```python
    # Build variables and query specs
    asset_snapshot: dict[str, Any] = ev.asset_snapshot or {}
    variables = _build_eval_variables(ev, asset_snapshot, slo_def)

    # For raw mode, substitute variables into indicator queries locally
    resolved_queries: dict[str, str] = {}
    if sli_def.mode == 'raw':
        resolved_queries = {
            name: substitute_variables(tmpl, variables)
            for name, tmpl in sli_def.indicators.items()
        }

    query_specs = _build_query_specs(sli_def, resolved_queries)
```

Update the adapter call:

```python
    log.info('querying adapter', adapter_url=ds.adapter_url, metric_count=len(query_specs))
    adapter_result = await _query_adapter_safe(
        log=log, repo=repo, eval_id=eval_id, ds=ds,
        query_specs=query_specs, variables=variables,
        start=ev.period_start.isoformat(), end=ev.period_end.isoformat(),
    )
    if adapter_result is None:
        return
    metrics_fetched, fetch_errors, sli_metadata = adapter_result
```

Update baseline indicator names for aggregated mode:

```python
    indicator_names = (
        list(sli_def.indicators)
        if sli_def.mode == 'raw'
        else [obj.sli for obj in slo.objectives]
    )
    baselines, compared_eval_ids = await _resolve_baselines(
        baseline_repo=baseline_repo, slo=slo, ev=ev, indicator_names=indicator_names
    )
```

Include sli_metadata in job_stats:

```python
    job_stats: dict[str, Any] = {
        'fetch_errors': fetch_errors,
        'total_score_pass_pct': slo_def.total_score_pass_pct,
        'total_score_warning_pct': slo_def.total_score_warning_pct,
    }
    if sli_metadata:
        job_stats['sli_metadata'] = sli_metadata
```

Update SLI values to use method name as aggregation:

```python
    sli_rows: list[dict[str, Any]] = []
    for ir in eval_result.indicator_results:
        if ir.value is None:
            continue
        aggregation = 'raw'
        if sli_def.mode == 'aggregated' and '.' in ir.metric:
            aggregation = ir.metric.rsplit('.', 1)[1]
        sli_rows.append({
            'eval_id': eval_id,
            'eval_start': ev.period_start,
            'metric_name': ir.metric,
            'aggregation': aggregation,
            'value': ir.value,
            'asset_name': asset_snapshot.get('name'),
            'evaluation_name': ev.evaluation_name,
            'os_tag': asset_snapshot.get('tags', {}).get('os')
            or asset_snapshot.get('variables', {}).get('os'),
        })
```

- [ ] **Step 5: Run full unit test suite**

Run: `./scripts/api-test.sh --tail 5`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```
git add api/app/modules/quality_gate/worker.py api/app/modules/quality_gate/adapter_client.py
git commit -m "feat(api): build aggregated-mode query specs in worker, handle metadata"
```

---

## Task 9: Mock Adapter — Aggregated Mode Support

Extend the mock adapter to accept `mode: aggregated` queries and return multi-value results with metadata.

**Files:**
- Modify: `adapters/mock/app/main.py`

- [ ] **Step 1: Update mock adapter**

Replace the content of `adapters/mock/app/main.py`:

```python
"""TROPEK Mock adapter — serves CSV-backed time-series data."""

from __future__ import annotations

import os
import random
from datetime import datetime
from pathlib import Path
from typing import Any

from app.csv_store import CsvStore
from fastapi import FastAPI, Header
from pydantic import BaseModel

app = FastAPI(title='TROPEK Mock Adapter', version='0.1.0')

DATA_DIR = Path(os.getenv('MOCK_DATA_DIR', '/app/data'))
_store = CsvStore(DATA_DIR)

_INTERVAL_UNITS = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}

_METHOD_MULTIPLIERS = {
    'min': 0.3,
    'mean': 1.0,
    'median': 0.95,
    'max': 2.5,
    'sum': 50.0,
    'std': 0.3,
    'p75': 1.3,
    'p90': 1.7,
    'p95': 2.0,
    'p99': 2.3,
}


class QueryRequest(BaseModel):
    """Adapter query request body."""

    queries: dict[str, str | dict]
    variables: dict[str, str] = {}
    start: datetime
    end: datetime


class QueryResponse(BaseModel):
    """Adapter query response body."""

    values: dict[str, float | None]
    errors: dict[str, str]
    metadata: dict[str, Any] = {}


@app.post('/query', response_model=QueryResponse)
async def query_metrics(
    body: QueryRequest,
    x_datasource_name: str = Header(default='default'),
) -> QueryResponse:
    """Execute metric queries against CSV data store."""
    values: dict[str, float | None] = {}
    errors: dict[str, str] = {}
    metadata: dict[str, Any] = {}

    for name, spec in body.queries.items():
        if isinstance(spec, dict) and spec.get('mode') == 'aggregated':
            _handle_aggregated(name, spec, body, values, metadata)
        else:
            query = spec['query'] if isinstance(spec, dict) else spec
            result = _store.query(
                namespace=x_datasource_name,
                queries={name: query},
                start=body.start,
                end=body.end,
            )
            values.update(result.values)
            errors.update(result.errors)

    return QueryResponse(values=values, errors=errors, metadata=metadata)


def _handle_aggregated(
    name: str,
    spec: dict,
    body: QueryRequest,
    values: dict[str, float | None],
    metadata: dict[str, Any],
) -> None:
    """Generate mock aggregated-mode results with realistic metadata."""
    methods = spec.get('methods', ['mean'])
    interval_seconds = _parse_interval(spec.get('interval', '1m'))
    window = (body.end - body.start).total_seconds()
    expected = max(1, int(window / interval_seconds))
    actual = max(1, int(expected * random.uniform(0.85, 1.0)))

    base = random.uniform(1.0, 100.0)
    for method in methods:
        key = f'{name}.{method}'
        multiplier = _METHOD_MULTIPLIERS.get(method, 1.0)
        values[key] = round(base * multiplier, 3)

    metadata[name] = {
        'mode': 'aggregated',
        'expected_samples': expected,
        'actual_samples': actual,
        'missing_pct': round((1 - actual / expected) * 100, 1) if expected else 0.0,
        'chunks_failed': 0,
    }


def _parse_interval(interval: str) -> int:
    """Parse Prometheus duration to seconds (e.g. '1m' -> 60)."""
    return int(interval[:-1]) * _INTERVAL_UNITS.get(interval[-1], 60)


@app.get('/health')
async def health() -> dict[str, str]:
    """Return adapter health status."""
    return {'status': 'ok', 'datasource': 'mock'}
```

- [ ] **Step 2: Commit**

```
git add adapters/mock/app/main.py
git commit -m "feat(mock): extend mock adapter to support aggregated-mode queries"
```

---

## Task 10: Integration Test — Run All Tests

Verify all adapter and API tests pass together with no regressions.

**Files:** (no new files)

- [ ] **Step 1: Run complete adapter test suite**

Run: `uv run --directory adapters/prometheus pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run complete API test suite**

Run: `./scripts/api-test.sh --tail 10`
Expected: All tests PASS

- [ ] **Step 3: Run lint and type check**

Run: `uv run ruff check adapters/prometheus/`
Run: `uv run ruff check api/`
Expected: No errors

- [ ] **Step 4: Fix any lint/type issues found, then commit**

```
git add -u
git commit -m "fix: address lint and type check issues from phase 1a"
```

---

## Scoping Notes

The following items from the spec are **deferred** (not in Phase 1a scope):

- **SLO Template Level 2 Method Expansion (generator.py)** — There is no SLO generation pipeline in the codebase yet. The `generated_by_group_id` column and `kind` field exist on the model, but no generator code exists. The `method_criteria` column is added (Task 7) so the schema is ready, but the expansion logic is a separate body of work.
- **UI changes** — Phase 1b
- **Reference documentation** — Phase 2
- **Integration tests against real DB** — Requires `just test-env` infrastructure. Full integration tests can be added in a follow-up.
