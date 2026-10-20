# Data-fetching reliability and refetch — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retry transient failures at every hop between the worker, the Prometheus adapter and Prometheus, store an
SLO evaluation as `failed` only when every retry is exhausted, and let Tropek refetch stored evaluations from the
source (API, client, UI) so no database surgery is ever needed to repair a day.

**Architecture:** Two services change (`api/` worker and `adapters/prometheus`), joined by two additive optional
fields in `adapters/protocol` (`timeout_seconds` on the request, `error_kinds` on the response). The worker's
adapter client and the adapter's Prometheus client each get a settings-driven retry policy; the adapter enforces
its job timeout and reports incomplete data as a *transient error*; the worker turns a transient fetch into an arq
`Retry` and only then into `failed`. Refetch is a new quality-gate workflow that resets stored rows in place and
re-enqueues the normal evaluation job, exposed on two endpoints, the Python client and the Run Evaluations dialog.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async + Alembic, arq, httpx, respx, pytest; React + Vite +
vitest (UI); uv; `just` recipes.

**Spec:** `docs/superpowers/specs/2026-10-16-data-fetching-reliability-and-refetch-design.md` (read it first; §
references below point into it).

## Who runs what

| task | implementer model | reviewer model | why |
|---|---|---|---|
| 1 protocol fields + mock | sonnet | sonnet | additive models, exact code given |
| 2 Prometheus client retries + semaphore | sonnet | sonnet | one file, exact policy given |
| 3 strategies: incomplete → transient error | sonnet | sonnet | two files, tests given |
| 4 coordinator timeout, repository kind, sync endpoint, readiness | sonnet | opus | four files that must agree on `kind` |
| 5 worker config validators + shipped defaults + docs | sonnet | sonnet | config and docs |
| 6 worker adapter client retry policy | sonnet | sonnet | one file, exact policy given |
| 7 executor + job retry loop | opus | opus | arq semantics, persisted attempt counter |
| 8 refetch repositories + migration | sonnet | opus | SQL semantics, integration tests |
| 9 refetch service + endpoints + 409 text + schema export | opus | opus | transactional reset, API surface |
| 10 Python client | sonnet | sonnet | mirrors existing methods |
| 11 UI refetch mode | sonnet | opus | React dialog + vitest |
| 12 changelog, guide, final checks | sonnet | sonnet | docs |
| final whole-branch review | — | opus | |

## Global Constraints

- Branch `bug/improve-data-fetching-reliability`; **agents stage by name (`git add <paths>`), never commit, never
  push, never amend** — the owner commits after each task's review (review packages come from index snapshots).
- Repo rules (`CLAUDE.md`): one command per Bash call, never chain with `&&`/`|`/`;`; `uv run --directory api …`
  and `uv run --directory adapters/prometheus …` instead of `cd`; `git -C <path> …`; bare `python` is denied —
  use `uv run python`; Read/Grep/Glob tools for file access.
- Lint/format/type: `uv run ruff check api/ adapters/`, `uv run ruff format --check api/ adapters/`,
  `uv run mypy api/tropek adapters/prometheus/tropek_prometheus` must stay clean. Line length as configured by the
  repo's ruff (120). Google-style docstrings are the repo convention in `api/` and the adapter — follow the file
  you are in.
- Tests: API unit `uv run --directory api pytest tests/ -m "not integration" --ignore=tests/schemathesis -q`;
  adapter `uv run --directory adapters/prometheus pytest tests/ -m "not e2e" -q`; mock
  `uv run --directory adapters/mock pytest tests/ -q`; integration (Task 8/9 only) via `just test-env`, then
  `just test-int`, then `just test-env-down` — **never against the dev database**; client
  `uv run --directory clients/python pytest tests/ -q`; UI `./scripts/ui-test.sh --tail 20` and
  `./scripts/ui-lint.sh --tail 20`.
- **A live Tropek deployment may be running on the development machine and must not be touched.** Allowed Docker
  use is exactly `just test-env` (project `tropek`, container `timescaledb-test`, port 5433) and
  `just test-env-down`. Never run `just dev`, `just up`, `just dev-docker`, `just dev-docker-clean`, `just e2e`,
  `just test-schema*`, `docker compose up`, `docker compose down`, `docker build`, `docker tag`,
  `docker rm`/`docker stop`, or `pnpm dev`; never kill processes by port; never point a test or script at a port
  the deployment uses.
- Migrations are incremental: a new file `api/alembic/versions/008_seed_refetch_annotation_category.py`,
  `revision='008'`, `down_revision='007'`; data-only (no DDL), idempotent (`ON CONFLICT (name) DO NOTHING`).
- No deployment-specific names (hosts, lab names, customer or product names other than Tropek's own) anywhere in
  code, tests, docs or the changelog.
- Settings names are exactly as the spec tables give them (§3.1, §4.1, §7); defaults exactly as §7.
- The adapter protocol stays `POST /query`; both new fields are optional with defaults that reproduce today's
  behaviour.
- Spec deviation recorded here (ruling for the plan): the retry attempt counter is persisted in
  `job_stats.fetch_attempts` and read from the database, **not** taken from arq's `ctx['job_try']`, because the
  predecessor deferral (`_MAX_PREDECESSOR_DEFERS`) re-enqueues a *new* arq job whose `job_try` restarts at 1. arq's
  own `max_tries` is set to `queue.max_retries + 2` so arq never pre-empts the worker's own final `failed` write.

## Review Focus

1. `Retry-After` given as an HTTP-date, not seconds — both retry policies must fall back to the computed backoff
   rather than crash or sleep for a parsed epoch. Pinned in Task 2 (`test_retry_after_http_date_falls_back`) and
   Task 6 (`test_retry_after_http_date_is_ignored`).
2. The worker's `timeout_seconds` budget exceeds the adapter's `max_job_timeout_seconds` — the adapter must cap
   the job timeout *and* its poll budget to the cap, and still answer before the worker's HTTP timeout. Pinned in
   Task 4 (`test_sync_query_caps_budget_to_max_job_timeout`) and Task 5 (validator: budget ≤ 600).
3. A refetch range containing one `running` row — the whole request must answer 409 and change nothing (no row
   reset, no change point deleted, no job enqueued). Pinned in Task 9 (`test_refetch_with_running_row_is_atomic_409`).
4. Every chunk of an aggregated query fails with a *data* error (`bad_data`, e.g. a malformed PromQL) — the metric
   must be a `data` error and the worker must **not** retry it (otherwise a bad query retries forever). Pinned in
   Task 3 (`test_bad_query_is_a_data_error_not_transient`) and Task 7 (`test_data_errors_only_do_not_retry`).
5. The watchdog's `requeue_stuck` overwrites `job_stats` wholesale and would erase `fetch_attempts`, resetting the
   retry cap — `mark_pending_retry` must merge (`||`) and `requeue_stuck` must preserve `fetch_attempts`. Pinned
   in Task 7 (`test_requeue_stuck_preserves_fetch_attempts`).

---

## File structure

```
adapters/protocol/tropek_adapter_protocol/models.py      + timeout_seconds, error_kinds, ErrorKind
adapters/protocol/tropek_adapter_protocol/testing.py     validator checks error_kinds ⊆ errors
adapters/protocol/tests/test_models.py                   NEW
adapters/mock/tropek_mock/main.py                        X-Mock-Transient header → transient error
adapters/prometheus/tropek_prometheus/config.py          new settings + validators
adapters/prometheus/tropek_prometheus/core/prometheus_client.py   retry policy, transient flag, global semaphore
adapters/prometheus/tropek_prometheus/core/retry.py      NEW shared backoff helper (used by client)
adapters/prometheus/tropek_prometheus/core/strategies/{base,raw,aggregated}.py   4-tuple with kinds
adapters/prometheus/tropek_prometheus/core/coordinator.py          job timeout, kind written
adapters/prometheus/tropek_prometheus/redis/repository.py          kind in results
adapters/prometheus/tropek_prometheus/api/routes.py                budget, 504+Retry-After, error_kinds
adapters/prometheus/tropek_prometheus/health/routes.py             counters
adapters/prometheus/tropek_prometheus/main.py                      settings on app.state, client semaphore
api/tropek/config.py                                      cross-field validators
api/tropek/modules/quality_gate/workflows/execution/adapter_client.py   AdapterRetryPolicy, AdapterFetchError
api/tropek/modules/quality_gate/workflows/execution/evaluation_executor.py  raises AdapterFetchError
api/tropek/modules/quality_gate/repositories/evaluation.py  mark_pending_retry, list_for_refetch, reset_for_refetch
api/tropek/modules/quality_gate/repositories/evaluation_run.py  mark_pending
api/tropek/modules/change_points/repository.py            delete_for_slo_range
api/tropek/queue.py                                       retry branch, WorkerSettings
api/tropek/modules/quality_gate/workflows/refetch/{__init__,service}.py   NEW
api/tropek/modules/quality_gate/schemas/refetch.py        NEW
api/tropek/modules/quality_gate/router.py                 two endpoints
api/tropek/modules/quality_gate/workflows/trigger/trigger_service.py   409 text
api/alembic/versions/008_seed_refetch_annotation_category.py   NEW
clients/python/tropek_client/{client.py,models/evaluations.py}
ui/src/features/evaluations/{domain.ts,api.ts,mappers.ts,hooks.ts}
ui/src/features/evaluations/components/actions/ReEvaluateForm.tsx (+ .test.tsx)
ui/src/mocks/handlers/evaluations.ts
config.yaml, docker-compose.yml, docs/configuration.md, docs/guides/adapter-protocol.md,
docs/guides/repairing-a-failed-fetch.md (NEW), CHANGELOG.md, clients/python/CHANGELOG.md
```

---

### Task 1: Protocol fields and the mock adapter's transient scenario

**Files:**
- Modify: `adapters/protocol/tropek_adapter_protocol/models.py`
- Modify: `adapters/protocol/tropek_adapter_protocol/testing.py`
- Create: `adapters/protocol/tests/__init__.py`, `adapters/protocol/tests/test_models.py`
- Modify: `adapters/mock/tropek_mock/main.py`
- Modify: `docs/guides/adapter-protocol.md` (sections "Request" and "Response")
- Modify: `.github/workflows/python-checks.yml` (one step: protocol tests)

**Interfaces:**
- Produces: `ErrorKind = Literal['transient', 'data']`; `AdapterQueryRequest.timeout_seconds: int | None`;
  `AdapterQueryResponse.error_kinds: dict[str, ErrorKind]`. Tasks 4 and 6 use these names and values verbatim.

- [ ] **Step 1: Write the failing tests**

```python
# adapters/protocol/tests/test_models.py
"""Shape tests for the two optional reliability fields."""

import pytest
from pydantic import ValidationError
from tropek_adapter_protocol.models import AdapterQueryRequest, AdapterQueryResponse
from tropek_adapter_protocol.testing import assert_query_response_valid


def test_request_timeout_seconds_is_optional() -> None:
    body = {'queries': {'m': {'mode': 'raw', 'query': 'up'}}, 'start': '2026-01-01T00:00:00Z', 'end': '2026-01-02T00:00:00Z'}
    assert AdapterQueryRequest.model_validate(body).timeout_seconds is None
    assert AdapterQueryRequest.model_validate({**body, 'timeout_seconds': 300}).timeout_seconds == 300


def test_response_error_kinds_default_empty() -> None:
    parsed = AdapterQueryResponse.model_validate({'values': {'m': None}, 'errors': {'m': 'boom'}})
    assert parsed.error_kinds == {}


def test_error_kinds_must_name_an_errored_metric() -> None:
    with pytest.raises(ValidationError, match='error_kinds'):
        assert_query_response_valid({'values': {}, 'errors': {}, 'error_kinds': {'m': 'transient'}})


def test_error_kinds_accepts_both_kinds() -> None:
    parsed = assert_query_response_valid(
        {'values': {'a': None, 'b': None}, 'errors': {'a': 'x', 'b': 'y'}, 'error_kinds': {'a': 'transient', 'b': 'data'}}
    )
    assert parsed.error_kinds == {'a': 'transient', 'b': 'data'}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --directory adapters/protocol pytest tests/ -q`
Expected: FAIL (`timeout_seconds`/`error_kinds` unknown; `assert_query_response_valid` does not raise).

- [ ] **Step 3: Implement the models**

In `models.py` add after the imports `from typing import Any, Literal` and:

```python
ErrorKind = Literal['transient', 'data']
```

Add to `AdapterQueryRequest` (after `end`), with a docstring line in `Fields:`:

```python
    timeout_seconds: int | None = Field(
        default=None,
        ge=1,
        description='caller budget in seconds; the adapter may cap it and must answer before it elapses',
    )
```

Add to `AdapterQueryResponse` (after `metadata`) and the `Fields:` docstring:

```python
    error_kinds: dict[str, ErrorKind] = Field(
        default_factory=dict,
        description="classification of `errors`: 'transient' = retry may succeed (timeout, 5xx, queue wait, "
        "incomplete data); 'data' = the source has no answer (empty series, bad query). Missing key = 'data'.",
    )

    @model_validator(mode='after')
    def _error_kinds_name_errored_metrics(self) -> AdapterQueryResponse:
        unknown = set(self.error_kinds) - set(self.errors)
        if unknown:
            raise ValueError(f'error_kinds names metrics that are not in errors: {sorted(unknown)}')
        return self
```

(`from pydantic import BaseModel, Field, model_validator`.) `testing.assert_query_response_valid` needs no code
change; its docstring gains "including the error_kinds ⊆ errors rule".

- [ ] **Step 4: Mock adapter — transient scenario**

In `adapters/mock/tropek_mock/main.py` the `QueryResponse` model gains `error_kinds: dict[str, str] = {}`;
`query_metrics` gains a header parameter `x_mock_transient: str | None = Header(default=None)`. After the loop:

```python
    if x_mock_transient:
        for name in (part.strip() for part in x_mock_transient.split(',') if part.strip()):
            values[name] = None
            errors[name] = 'simulated transient failure'
            error_kinds[name] = 'transient'
    return QueryResponse(values=values, errors=errors, metadata=metadata, error_kinds=error_kinds)
```

(declare `error_kinds: dict[str, str] = {}` next to `values`/`errors`). Add
`adapters/mock/tests/test_transient_header.py` with one test using `fastapi.testclient.TestClient(app)`: posting
`/query` with `X-Mock-Transient: m` yields `errors['m']` and `error_kinds['m'] == 'transient'`; without the header
`error_kinds == {}`.

- [ ] **Step 5: Docs and CI**

`docs/guides/adapter-protocol.md`: under "Request" add the `timeout_seconds` row; under "Response" add
`error_kinds` with the two kinds and the sentence "The engine retries the whole evaluation when any error is
`transient`; a `data` error scores the metric as `error`." In `.github/workflows/python-checks.yml` add a step after
the mock tests: `run: uv run --directory adapters/protocol pytest tests/ -q`.

- [ ] **Step 6: Run, lint, stage**

Run: `uv run --directory adapters/protocol pytest tests/ -q` → PASS; `uv run --directory adapters/mock pytest tests/ -q`
→ PASS; `uv run ruff check adapters/`; `uv run mypy adapters/prometheus/tropek_prometheus`.
Stage: `git add adapters/protocol adapters/mock/tropek_mock/main.py adapters/mock/tests docs/guides/adapter-protocol.md .github/workflows/python-checks.yml`.

---

### Task 2: Prometheus client retry policy, transient flag, global semaphore

**Files:**
- Create: `adapters/prometheus/tropek_prometheus/core/retry.py`
- Modify: `adapters/prometheus/tropek_prometheus/config.py`
- Modify: `adapters/prometheus/tropek_prometheus/core/prometheus_client.py`
- Modify: `adapters/prometheus/tropek_prometheus/main.py` (constructor args)
- Test: `adapters/prometheus/tests/test_retry.py` (new), `adapters/prometheus/tests/test_prometheus_client.py`, `test_config.py`

**Interfaces:**
- Produces: `PrometheusQueryError(message, *, transient: bool)` with attribute `.transient`;
  `compute_backoff(attempt: int, base_seconds: float, retry_after: str | None, jitter: float = 0.25) -> float`
  in `core/retry.py`; `PrometheusClient(base_url, timeout, auth=None, *, retry_attempts=3, retry_backoff_seconds=1.0, max_in_flight=8)`.
  Task 3 reads `.transient`; Task 4 reads `client.in_flight` (int property).

- [ ] **Step 1: Failing tests**

```python
# adapters/prometheus/tests/test_retry.py
import pytest
from tropek_prometheus.core.retry import compute_backoff


@pytest.mark.parametrize(('attempt', 'expected'), [(1, 1.0), (2, 2.0), (3, 4.0)])
def test_exponential_without_jitter(attempt: int, expected: float) -> None:
    assert compute_backoff(attempt, base_seconds=1.0, retry_after=None, jitter=0.0) == expected


def test_retry_after_seconds_wins() -> None:
    assert compute_backoff(1, base_seconds=1.0, retry_after='7', jitter=0.0) == 7.0


def test_retry_after_http_date_falls_back() -> None:
    # Review Focus 1: an HTTP-date is legal in Retry-After; we do not parse it, we fall back.
    assert compute_backoff(2, base_seconds=1.0, retry_after='Wed, 21 Oct 2026 07:28:00 GMT', jitter=0.0) == 2.0


def test_jitter_stays_within_band() -> None:
    values = {compute_backoff(1, base_seconds=4.0, retry_after=None, jitter=0.25) for _ in range(200)}
    assert all(3.0 <= v <= 5.0 for v in values)
```

Add to `test_prometheus_client.py` (respx; fixture `client` already builds `PrometheusClient('http://prom:9090', timeout=5)`):

```python
@respx.mock
async def test_range_query_retries_timeout_then_succeeds(client: PrometheusClient):
    route = respx.get('http://prom:9090/api/v1/query_range').mock(
        side_effect=[httpx.ReadTimeout('slow'), Response(200, json=_matrix([[1, '1.0']]))]
    )
    assert await client.range_query('up', start='s', end='e', step='1m') == [1.0]
    assert route.call_count == 2


@respx.mock
async def test_503_then_success_with_retry_after(client: PrometheusClient):
    route = respx.get('http://prom:9090/api/v1/query').mock(
        side_effect=[Response(503, headers={'Retry-After': '0'}), Response(200, json=_scalar('2'))]
    )
    assert await client.instant_query('up', time='t') == 2.0
    assert route.call_count == 2


@respx.mock
async def test_exhausted_attempts_raise_transient(client: PrometheusClient):
    respx.get('http://prom:9090/api/v1/query').mock(return_value=Response(502))
    with pytest.raises(PrometheusQueryError) as exc:
        await client.instant_query('up', time='t')
    assert exc.value.transient is True
    assert 'after 3 attempts' in str(exc.value)


@respx.mock
async def test_bad_data_is_final_and_not_transient(client: PrometheusClient):
    route = respx.get('http://prom:9090/api/v1/query').mock(
        return_value=Response(400, json={'status': 'error', 'errorType': 'bad_data', 'error': 'parse error'})
    )
    with pytest.raises(PrometheusQueryError) as exc:
        await client.instant_query('up(', time='t')
    assert exc.value.transient is False
    assert route.call_count == 1


@respx.mock
async def test_error_body_timeout_is_transient(client: PrometheusClient):
    respx.get('http://prom:9090/api/v1/query').mock(
        return_value=Response(200, json={'status': 'error', 'errorType': 'timeout', 'error': 'query timed out'})
    )
    with pytest.raises(PrometheusQueryError) as exc:
        await client.instant_query('up', time='t')
    assert exc.value.transient is True


async def test_global_semaphore_bounds_in_flight():
    client = PrometheusClient('http://prom:9090', timeout=5, max_in_flight=2, retry_attempts=1)
    peak = 0

    async def slow(request):
        nonlocal peak
        peak = max(peak, client.in_flight)
        await asyncio.sleep(0.01)
        return Response(200, json=_scalar('1'))

    with respx.mock:
        respx.get('http://prom:9090/api/v1/query').mock(side_effect=slow)
        await asyncio.gather(*(client.instant_query('up', time='t') for _ in range(6)))
    assert peak == 2
```

Define `_matrix` / `_scalar` helpers at the top of the test file (success envelopes). The client fixture must pass
`retry_backoff_seconds=0` so tests do not sleep; add `jitter` default handling for 0.

- [ ] **Step 2: Run to verify failure** — `uv run --directory adapters/prometheus pytest tests/test_retry.py tests/test_prometheus_client.py -q` → FAIL (import errors).

- [ ] **Step 3: Implement `core/retry.py`**

```python
"""Backoff computation shared by the Prometheus client (and any future outbound call)."""

from __future__ import annotations

import random


def compute_backoff(attempt: int, *, base_seconds: float, retry_after: str | None, jitter: float = 0.25) -> float:
    """Return the seconds to wait after a failed ``attempt`` (1-based).

    ``Retry-After`` in seconds wins when present and numeric; an HTTP-date value is ignored (we do not
    parse dates — the exponential value is a safe fallback). Otherwise ``base_seconds * 2**(attempt-1)``
    with ``±jitter`` relative noise.
    """
    if retry_after is not None:
        try:
            return float(retry_after)
        except ValueError:
            pass
    delay = base_seconds * (2 ** (attempt - 1))
    if jitter:
        delay *= 1 + random.uniform(-jitter, jitter)  # noqa: S311 - not security sensitive
    return delay
```

- [ ] **Step 4: Settings** — in `config.py` add `prometheus_retry_attempts: int = 3`,
  `prometheus_retry_backoff_seconds: float = 1.0`, `max_concurrent_prometheus_requests: int = 8`, change
  `query_timeout_seconds` to 60, `default_job_timeout_seconds` to 300, `max_concurrent_jobs` to 10, and a
  `model_validator(mode='after')` `_validate_limits` raising `ValueError` when
  `default_job_timeout_seconds > max_job_timeout_seconds`, `max_concurrent_prometheus_requests < 1`,
  `prometheus_retry_attempts < 1`. Tests in `test_config.py`: defaults as above; each violation raises.

- [ ] **Step 5: Implement the client**

`PrometheusQueryError.__init__(self, message: str, *, transient: bool = False)` storing `self.transient`.
Constructor gains the three keyword args and `self._semaphore = asyncio.Semaphore(max_in_flight)`,
`self._in_flight = 0`, property `in_flight`. Replace `_get`:

```python
    _TRANSIENT_STATUS = {429, 500, 502, 503, 504}
    _TRANSIENT_ERROR_TYPES = {'timeout', 'canceled', 'unavailable', 'internal'}

    async def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        url = f'{self._base_url}{path}'
        auth = httpx.BasicAuth(*self._auth) if self._auth else None
        last_error: PrometheusQueryError | None = None
        for attempt in range(1, self._retry_attempts + 1):
            async with self._semaphore:
                self._in_flight += 1
                try:
                    outcome = await self._attempt(path, params, auth)
                finally:
                    self._in_flight -= 1
            if isinstance(outcome, dict):
                return outcome
            last_error = outcome
            if not outcome.transient or attempt == self._retry_attempts:
                break
            delay = compute_backoff(attempt, base_seconds=self._retry_backoff, retry_after=outcome.retry_after)
            logger.warning('prometheus request retried: url=%s attempt=%d/%d backoff=%.2fs cause=%s',
                           url, attempt, self._retry_attempts, delay, outcome)
            await asyncio.sleep(delay)
        assert last_error is not None
        if last_error.transient:
            raise PrometheusQueryError(f'{last_error} (after {self._retry_attempts} attempts)', transient=True)
        raise last_error
```

`_attempt` performs one request and **returns** either the `data` dict or a `PrometheusQueryError` (with a
`retry_after: str | None` attribute set from the response header when there was a response): connect/timeout →
transient; status in `_TRANSIENT_STATUS` → transient; other non-200 → final; body `status != 'success'` →
transient iff `errorType` in `_TRANSIENT_ERROR_TYPES`, else final. Keep the existing log lines. `main.py` passes
`retry_attempts=settings.prometheus_retry_attempts`, `retry_backoff_seconds=settings.prometheus_retry_backoff_seconds`,
`max_in_flight=settings.max_concurrent_prometheus_requests` and stores `app.state.prometheus_client = prom_client`.

- [ ] **Step 6: Run, lint, stage** — adapter tests → PASS; ruff; mypy. Stage the four files + tests.

---

### Task 3: Strategies report incomplete data as a transient error

**Files:**
- Modify: `adapters/prometheus/tropek_prometheus/core/strategies/base.py`, `raw.py`, `aggregated.py`
- Test: `adapters/prometheus/tests/test_aggregated_strategy.py`, `test_raw_strategy.py`, `test_coordinator.py` (the `ExplodingStrategy` double returns the 4-tuple)

**Interfaces:**
- Produces: `Strategy.execute(...) -> tuple[dict[str, float | None], dict[str, str], dict[str, Any] | None, dict[str, str]]`
  — the fourth element is `kinds` (`metric -> 'transient' | 'data'`) and names exactly the keys of `errors`.
  Task 4 consumes it.

- [ ] **Step 1: Failing tests** (aggregated; `_matrix_response` helpers exist in the file; strategy built with a
  client whose `retry_attempts=1`, `retry_backoff_seconds=0`, chunk_size `4h` so a 24 h window has 6 chunks):

```python
@respx.mock
async def test_failed_chunk_makes_every_method_a_transient_error(strategy):
    calls = {'n': 0}

    def responder(request):
        calls['n'] += 1
        return Response(503) if calls['n'] == 2 else _matrix_response([[0, '1.0']])

    respx.get('http://prom:9090/api/v1/query_range').mock(side_effect=responder)
    values, errors, metadata, kinds = await strategy.execute(
        sli_name='cpu', query_spec={'query_template': 'up', 'interval': '1m', 'methods': ['mean', 'p95']},
        variables={}, start='2026-01-01T00:00:00+00:00', end='2026-01-02T00:00:00+00:00',
    )
    assert values == {'cpu.mean': None, 'cpu.p95': None}
    assert errors['cpu.mean'].startswith('incomplete data: 1 of 7 chunks failed')
    assert kinds == {'cpu.mean': 'transient', 'cpu.p95': 'transient'}
    assert metadata['chunks_failed'] == 1


@respx.mock
async def test_bad_query_is_a_data_error_not_transient(strategy):
    # Review Focus 4
    respx.get('http://prom:9090/api/v1/query_range').mock(
        return_value=Response(400, json={'status': 'error', 'errorType': 'bad_data', 'error': 'parse error'})
    )
    _values, errors, _meta, kinds = await strategy.execute(
        sli_name='cpu', query_spec={'query_template': 'up(', 'interval': '1m', 'methods': ['mean']},
        variables={}, start='2026-01-01T00:00:00+00:00', end='2026-01-01T01:00:00+00:00',
    )
    assert errors['cpu.mean'].startswith('incomplete data: 1 of 1 chunks failed')
    assert kinds == {'cpu.mean': 'data'}


@respx.mock
async def test_empty_complete_result_stays_a_data_error(strategy):
    respx.get('http://prom:9090/api/v1/query_range').mock(return_value=_matrix_response([]))
    values, errors, _meta, kinds = await strategy.execute(
        sli_name='cpu', query_spec={'query_template': 'up', 'interval': '1m', 'methods': ['mean']},
        variables={}, start='2026-01-01T00:00:00+00:00', end='2026-01-01T01:00:00+00:00',
    )
    assert values == {'cpu.mean': None}
    assert errors == {'cpu.mean': 'no valid data points'}
    assert kinds == {'cpu.mean': 'data'}
```

Raw: `test_transient_query_error_sets_kind_transient` (client raising `PrometheusQueryError('x', transient=True)`
→ `kinds == {sli: 'transient'}`) and `test_data_error_sets_kind_data`. Existing raw/aggregated tests unpack three
values — update them to four.

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement**

`base.py`: the abstract return annotation becomes the 4-tuple; docstring explains `kinds`. `raw.py`: every early
return adds `{sli_name: 'data'}` (substitution) or `{sli_name: 'transient' if exc.transient else 'data'}`
(query error); success adds `{}`. `aggregated.py`: `_fetch_range` returns `(all_values, chunks_failed, series_count, chunks_total, last_error)`
where `last_error: PrometheusQueryError | None` is the last chunk failure; in `execute`, after the fetch:

```python
        if chunks_failed:
            message = f'incomplete data: {chunks_failed} of {chunks_total} chunks failed (last: {last_error})'
            kind = 'transient' if last_error is not None and last_error.transient else 'data'
            values = {f'{sli_name}.{m}': None for m in methods}
            errors = {key: message for key in values}
            kinds = {key: kind for key in values}
            metadata = {... as today, 'chunks_failed': chunks_failed}
            logger.warning('aggregated result incomplete: sli=%s %s', sli_name, message)
            return values, errors, metadata, kinds
```

The normal path returns `kinds = {key: 'data' for key in errors}` (the `no valid data points` case). The early
returns (inverted window, unresolved variable) add `{key: 'data' …}`.

- [ ] **Step 4: Run, lint, stage.**

---

### Task 4: Coordinator job timeout, `kind` in results, sync endpoint budget, readiness counters

**Files:**
- Modify: `adapters/prometheus/tropek_prometheus/redis/repository.py` (`write_result(kind=...)`, `get_results`)
- Modify: `adapters/prometheus/tropek_prometheus/core/coordinator.py`
- Modify: `adapters/prometheus/tropek_prometheus/core/job_manager.py` (expose `timeout_seconds` in status)
- Modify: `adapters/prometheus/tropek_prometheus/api/routes.py`, `api/schemas.py` (`IndicatorResult.kind`, `SyncQueryRequest.timeout_seconds`)
- Modify: `adapters/prometheus/tropek_prometheus/health/routes.py`, `main.py` (`app.state.settings`)
- Test: `tests/test_coordinator.py`, `tests/test_routes.py`, `tests/test_redis_repository.py`

**Interfaces:**
- Consumes: strategy 4-tuple (Task 3); `client.in_flight` (Task 2).
- Produces: sync `/query` response `{values, errors, metadata, error_kinds}`; request field `timeout_seconds`;
  504 body `{'detail': 'job did not complete within budget', 'job_id': ...}` with `Retry-After: 5`. Task 6 relies
  on 504/503 + `Retry-After` and on `error_kinds`.

- [ ] **Step 1: Failing tests**

`test_redis_repository.py`: `write_result(..., kind='transient')` round-trips `kind`; default `kind='data'`.
`test_coordinator.py`:

```python
@pytest.mark.asyncio
async def test_job_timeout_marks_timed_out_and_writes_transient_results():
    redis = fakeredis.aioredis.FakeRedis()
    repo = JobRepository(redis, prefix='test:')
    settings = Settings(max_concurrent_queries=2, max_concurrent_jobs=1, default_job_timeout_seconds=1)

    class Hanging:
        async def execute(self, **_):
            await asyncio.sleep(10)

    coordinator = Coordinator(repo, settings, strategies={'raw': Hanging()})
    job_id = await repo.create_job({'m': {'mode': 'raw', 'query': 'up'}}, {}, 1, 's', 'e')
    await repo.enqueue(job_id)
    await coordinator.process_one()
    status = await repo.get_status(job_id)
    assert status['status'] == 'timed_out'
    results = await repo.get_results(job_id)
    assert results['m']['success'] is False
    assert results['m']['kind'] == 'transient'
    assert 'job timed out after 1s' in results['m']['message']
```

`test_routes.py` (fixture `client` from `create_app(use_fakeredis=True)`; the coordinator runs in the lifespan):

```python
@pytest.mark.asyncio
async def test_sync_query_returns_error_kinds(client, monkeypatch):
    # make the raw strategy raise a transient error without a real Prometheus
    ...patch app.state.coordinator._strategies['raw'] with a double raising PrometheusQueryError('down', transient=True)
    resp = await client.post('/query', json={'queries': {'m': {'mode': 'raw', 'query': 'up'}}, 'start': 's', 'end': 'e'})
    assert resp.status_code == 200
    assert resp.json()['errors']['m'] and resp.json()['error_kinds'] == {'m': 'transient'}


@pytest.mark.asyncio
async def test_sync_query_budget_exhausted_is_504_with_retry_after(client):
    ...patch the raw strategy with a coroutine that sleeps 5 s; post with 'timeout_seconds': 1
    assert resp.status_code == 504
    assert resp.headers['Retry-After'] == '5'
    job_id = resp.json()['job_id']
    status = await client.get(f'/api/v1/query-jobs/{job_id}')
    assert status.json()['status'] in ('cancelled', 'timed_out')


@pytest.mark.asyncio
async def test_sync_query_caps_budget_to_max_job_timeout(client):
    # Review Focus 2: a 10 000 s budget is capped at max_job_timeout_seconds; the job record carries the cap
    resp = await client.post('/query', json={..., 'timeout_seconds': 10_000})
    ...assert the submitted job's timeout (via app.state.job_manager.get_status) equals Settings().max_job_timeout_seconds
```

Readiness: `test_readiness_reports_counters` asserts keys `queue_depth`, `running_jobs`, `prometheus_in_flight`.

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement**

Repository: `write_result(..., kind: str = 'data')` stores `'kind': kind`; `get_results` returns it (old entries
without the key read as `'data'` via `.setdefault`). `JobRepository.get_status` also returns `timeout_seconds`
(stored by `create_job`; check its hash field name — it is stored today as `timeout`).

Coordinator `process_one`:

```python
        timeout = int(status.get('timeout_seconds') or self._settings.default_job_timeout_seconds)
        try:
            outcomes = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout)
        except TimeoutError:
            written = await self._repo.get_results(job_id)
            for name in queries:
                if name not in written:
                    await self._repo.write_result(job_id, name, value=None, success=False,
                                                  message=f'job timed out after {timeout}s', kind='transient')
            await self._repo.mark_timed_out(job_id, self._settings.job_retention_seconds)
            logger.warning('job timed out: id=%s timeout=%ds unfinished=%d', job_id, timeout, ...)
            return True
```

(`asyncio.wait_for` cancels the gathered tasks on timeout.) `_run_query` unpacks the 4-tuple and passes
`kind=kinds.get(name, 'data')` to `write_result`; the exception branch writes `kind='transient'` only for
`PrometheusQueryError(transient=True)`, else `'data'`.

Routes: `SyncQueryRequest.timeout_seconds: int | None = None`; `sync_query` reads `settings = request.app.state.settings`,
submits with `timeout_seconds=body.timeout_seconds`, computes `budget = min(body.timeout_seconds or settings.default_job_timeout_seconds, settings.max_job_timeout_seconds) + 5`,
polls until terminal or `time.monotonic() > deadline`; on exhaustion `await manager.cancel(job_id)` and
`raise HTTPException(status_code=504, detail={'detail': 'job did not complete within budget', 'job_id': job_id}, headers={'Retry-After': '5'})`.
Build `error_kinds = {name: indicator.get('kind', 'data') for indicators with success False}` and return it.
`main.py`: `app.state.settings = settings` before the lifespan, and the health route reads
`app.state.job_manager` (`queue_depth` via `repo.queue_depth()`, `running_jobs` as a counter the coordinator
increments/decrements around `process_one`, `prometheus_in_flight = app.state.prometheus_client.in_flight`).

- [ ] **Step 4: Run, lint, mypy, stage.**

---

### Task 5: Worker config validators, shipped defaults, configuration docs

**Files:**
- Modify: `api/tropek/config.py` (`ReliabilitySettings`, `QueueSettings`, `Settings` cross-field validator)
- Modify: `config.yaml`, `docker-compose.yml` (adapter-prometheus `environment`)
- Modify: `docs/configuration.md` (new section "The timeout chain")
- Test: `api/tests/configuration/test_settings_validators.py` (new)

**Interfaces:**
- Produces: `Settings.reliability.adapter_budget_seconds` property = `adapter_timeout_seconds - 30` (floored at
  30); Task 6 sends it as `timeout_seconds`.

- [ ] **Step 1: Failing tests** (settings classes read `_yaml` at import; test via constructor kwargs):

```python
from pydantic import ValidationError
from tropek.config import QueueSettings, ReliabilitySettings, validate_timeout_chain


def test_shipped_defaults_are_consistent() -> None:
    validate_timeout_chain(ReliabilitySettings(adapter_timeout_seconds=330, stuck_job_threshold_seconds=600),
                           QueueSettings(job_timeout_seconds=400))


def test_adapter_budget_is_timeout_minus_margin_floored() -> None:
    assert ReliabilitySettings(adapter_timeout_seconds=330).adapter_budget_seconds == 300
    assert ReliabilitySettings(adapter_timeout_seconds=40).adapter_budget_seconds == 30


@pytest.mark.parametrize(('reliability', 'queue', 'message'), [
    ({'adapter_timeout_seconds': 30}, {}, 'adapter_timeout_seconds must exceed 30'),
    ({'adapter_timeout_seconds': 330}, {'job_timeout_seconds': 300}, 'job_timeout_seconds must exceed adapter_timeout_seconds'),
    ({'adapter_timeout_seconds': 330, 'stuck_job_threshold_seconds': 400}, {'job_timeout_seconds': 400}, 'stuck_job_threshold_seconds must exceed job_timeout_seconds'),
    ({'adapter_timeout_seconds': 700}, {'job_timeout_seconds': 800}, 'adapter budget 670 exceeds the adapter maximum 600'),
])
def test_inconsistent_chain_is_refused(reliability, queue, message) -> None:
    with pytest.raises(ValueError, match=message):
        validate_timeout_chain(ReliabilitySettings(**reliability), QueueSettings(**queue))
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement** — in `config.py`:

```python
ADAPTER_BUDGET_MARGIN_SECONDS = 30
ADAPTER_MAX_JOB_TIMEOUT_SECONDS = 600  # the adapter's max_job_timeout_seconds; a larger budget is capped there


class ReliabilitySettings(BaseSettings):
    ...
    @property
    def adapter_budget_seconds(self) -> int:
        """Budget sent to the adapter as ``timeout_seconds``: the HTTP timeout minus a margin, floored."""
        return max(ADAPTER_BUDGET_MARGIN_SECONDS, self.adapter_timeout_seconds - ADAPTER_BUDGET_MARGIN_SECONDS)


def validate_timeout_chain(reliability: ReliabilitySettings, queue: QueueSettings) -> None:
    """Refuse a settings combination in which one hop gives up before the hop it waits on."""
    if reliability.adapter_timeout_seconds <= ADAPTER_BUDGET_MARGIN_SECONDS:
        raise ValueError(f'reliability.adapter_timeout_seconds must exceed {ADAPTER_BUDGET_MARGIN_SECONDS} (got {reliability.adapter_timeout_seconds})')
    if reliability.adapter_budget_seconds > ADAPTER_MAX_JOB_TIMEOUT_SECONDS:
        raise ValueError(f'adapter budget {reliability.adapter_budget_seconds} exceeds the adapter maximum {ADAPTER_MAX_JOB_TIMEOUT_SECONDS}; lower reliability.adapter_timeout_seconds')
    if queue.job_timeout_seconds <= reliability.adapter_timeout_seconds:
        raise ValueError(f'queue.job_timeout_seconds must exceed adapter_timeout_seconds ({queue.job_timeout_seconds} <= {reliability.adapter_timeout_seconds})')
    if reliability.stuck_job_threshold_seconds <= queue.job_timeout_seconds:
        raise ValueError(f'reliability.stuck_job_threshold_seconds must exceed job_timeout_seconds ({reliability.stuck_job_threshold_seconds} <= {queue.job_timeout_seconds})')
```

`Settings.__init__`/post-init (where `required secrets` are checked) calls
`validate_timeout_chain(self.reliability, self.queue)`. Defaults in code: `adapter_timeout_seconds` 330,
`stuck_job_threshold_seconds` 600, `job_timeout_seconds` 400 (so a missing `config.yaml` is consistent).

`config.yaml`: the same three values with the comment block from spec §7 (the chain, one line each). `docker-compose.yml`
adapter service `environment`: `QUERY_TIMEOUT_SECONDS: ${ADAPTER_QUERY_TIMEOUT_SECONDS:-60}`,
`DEFAULT_JOB_TIMEOUT_SECONDS: ${ADAPTER_DEFAULT_JOB_TIMEOUT_SECONDS:-300}`,
`MAX_CONCURRENT_JOBS: ${ADAPTER_MAX_CONCURRENT_JOBS:-10}`,
`MAX_CONCURRENT_PROMETHEUS_REQUESTS: ${ADAPTER_MAX_CONCURRENT_PROMETHEUS_REQUESTS:-8}`.
`docs/configuration.md`: section "The timeout chain" with the §7 table and the rule each validator enforces.

- [ ] **Step 4: Run, lint, stage.** Also run the whole API unit suite: existing tests constructing `Settings` must
  still pass with the new defaults.

---

### Task 6: Worker adapter client — settings-driven retry policy, budget, `error_kinds`

**Files:**
- Modify: `api/tropek/modules/quality_gate/workflows/execution/adapter_client.py`
- Modify: `api/tropek/queue.py` (construct the client with the policy; see Task 7 for the rest)
- Test: `api/tests/quality_gate/workflows/execution/test_adapter_client.py`

**Interfaces:**
- Produces:

```python
class AdapterRetryPolicy(BaseModel):
    attempts: int = 3
    backoff_seconds: float = 2.0
    jitter: float = 0.25

class AdapterFetchError(Exception):
    def __init__(self, cause: str, *, attempts: int, last_status: int | None, elapsed_s: float) -> None: ...
    def as_attempt_record(self) -> dict[str, Any]: ...   # {'cause','status','elapsed_s','at'}

class HttpAdapterClient:
    def __init__(self, timeout: float, http_client=None, *, policy: AdapterRetryPolicy | None = None, budget_seconds: int | None = None) -> None
    async def query(...) -> tuple[dict[str, float | None], dict[str, str], dict[str, Any], dict[str, str]]  # + error_kinds
```

  `query` raises `AdapterFetchError` when attempts are exhausted (or on a non-retryable transport error).
  Task 7 consumes all three.

- [ ] **Step 1: Failing tests** (existing tests use `httpx.MockTransport`; keep that style):

```python
async def test_read_timeout_then_success_is_retried() -> None:
    calls = {'n': 0}

    def handler(request):
        calls['n'] += 1
        if calls['n'] == 1:
            raise httpx.ReadTimeout('slow', request=request)
        return httpx.Response(200, json={'values': {'m': 1.0}, 'errors': {}, 'metadata': {}})

    client = HttpAdapterClient(timeout=1, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
                               policy=AdapterRetryPolicy(attempts=3, backoff_seconds=0, jitter=0))
    values, errors, metadata, kinds = await client.query(adapter_url='http://a', datasource_name='d', queries={}, variables={}, start='s', end='e')
    assert values == {'m': 1.0} and calls['n'] == 2


async def test_504_with_retry_after_then_success() -> None: ...  # Retry-After: '0'; call_count == 2


async def test_retry_after_http_date_is_ignored() -> None: ...  # Review Focus 1: 503 with an HTTP-date header → retried after backoff 0, no exception


async def test_exhausted_attempts_raise_adapter_fetch_error() -> None:
    ...always 502; with pytest.raises(AdapterFetchError) as exc; exc.value.attempts == 3; exc.value.last_status == 502


async def test_400_is_not_retried_and_raises() -> None:
    ...one 400 → AdapterFetchError with attempts == 1 and last_status == 400 (non-retryable transport error)


async def test_budget_is_sent_as_timeout_seconds() -> None:
    ...client(budget_seconds=300); captured request json has 'timeout_seconds': 300


async def test_error_kinds_parsed_and_default_empty() -> None: ...
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement** — remove the three hardcoded constants; `AdapterQueryResponse` (the worker-side copy)
  gains `error_kinds: dict[str, str] = Field(default_factory=dict)`; `_post_with_retry` becomes:

```python
    _RETRYABLE_STATUS = {429, 502, 503, 504}

    async def _post_with_retry(self, url, *, headers, payload) -> httpx.Response:
        started = time.perf_counter()
        last_cause, last_status = 'unknown', None
        for attempt in range(1, self._policy.attempts + 1):
            try:
                response = await self._post_once(url, headers=headers, payload=payload)
            except (httpx.ConnectError, httpx.ReadError, httpx.TimeoutException) as error:
                last_cause, last_status, retry_after = f'{type(error).__name__}: {error}', None, None
            else:
                if response.status_code not in self._RETRYABLE_STATUS:
                    if response.is_success:
                        return response
                    raise AdapterFetchError(f'adapter returned {response.status_code}', attempts=attempt,
                                            last_status=response.status_code, elapsed_s=time.perf_counter() - started)
                last_cause, last_status = f'adapter returned {response.status_code}', response.status_code
                retry_after = response.headers.get('Retry-After')
            if attempt == self._policy.attempts:
                break
            delay = compute_backoff(attempt, base_seconds=self._policy.backoff_seconds, retry_after=retry_after, jitter=self._policy.jitter)
            logger.warning('adapter request retried', url=url, attempt=attempt, max_attempts=self._policy.attempts, backoff_s=round(delay, 2), cause=last_cause)
            await asyncio.sleep(delay)
        raise AdapterFetchError(f'{last_cause} after {self._policy.attempts} attempts', attempts=self._policy.attempts,
                                last_status=last_status, elapsed_s=time.perf_counter() - started)
```

`compute_backoff` is copied into `adapter_client.py` as a private function with the same semantics as Task 2 (the
two packages do not share code). `query()` adds `'timeout_seconds': self._budget_seconds` to the payload when set,
removes its own `raise_for_status()` (handled above), and returns the 4-tuple including `parsed.error_kinds`. In
`queue.py` both `HttpAdapterClient(...)` constructions pass
`policy=AdapterRetryPolicy(attempts=settings.reliability.adapter_retry_attempts, backoff_seconds=settings.reliability.adapter_retry_backoff_seconds)`
and `budget_seconds=settings.reliability.adapter_budget_seconds`.

- [ ] **Step 4: Run, lint, mypy, stage.**

---

### Task 7: Executor raises on a transient fetch; the job retries before failing

**Files:**
- Modify: `api/tropek/modules/quality_gate/workflows/execution/evaluation_executor.py` (`fetch_and_evaluate`, `_log_adapter_response`)
- Modify: `api/tropek/modules/quality_gate/repositories/evaluation.py` (`mark_pending_retry`, `requeue_stuck` merge)
- Modify: `api/tropek/queue.py` (`run_evaluation_job`, `WorkerSettings`)
- Test: `api/tests/quality_gate/workflows/execution/test_queue.py`, `test_evaluation_executor.py` (new or existing),
  `api/tests/quality_gate/db/test_evaluation_repository.py` (integration, if such a file exists; else add to the
  repository integration tests folder used by Task 8)

**Interfaces:**
- Consumes: `AdapterFetchError`, 4-tuple `query()` (Task 6); `settings.queue.max_retries`, `retry_delay_seconds`,
  `job_timeout_seconds`, `keep_result_seconds` (Task 5).
- Produces: `fetch_and_evaluate(...) -> FetchAndEvaluateResult` (never `None`; raises `AdapterFetchError`);
  `EvaluationRepository.mark_pending_retry(eval_id, *, attempt_record: dict[str, Any]) -> None`;
  `job_stats.fetch_attempts: list[dict]` shape `{'attempt': int, 'cause': str, 'status': int | None, 'elapsed_s': float, 'at': iso}`.

- [ ] **Step 1: Failing tests** (test_queue.py; reuse `_make_snapshot`, `_session_factory_from_list`, `_make_ctx`):

```python
async def test_transient_fetch_raises_retry_and_resets_to_pending() -> None:
    eval_id = uuid.uuid4()
    snapshot = _make_snapshot(eval_id=eval_id)
    sessions = [_mock_session() for _ in range(5)]
    mock_eval_repo = AsyncMock()
    mock_eval_repo.get_by_id = AsyncMock(return_value=MagicMock(job_stats={}))
    error = AdapterFetchError('adapter returned 504 after 3 attempts', attempts=3, last_status=504, elapsed_s=12.5)
    with (
        ...same patches as test_adapter_failure_marks_failed, but fetch_and_evaluate side_effect=error,
        patch('tropek.queue.EvaluationRepository', return_value=mock_eval_repo),
    ):
        with pytest.raises(Retry) as exc:
            await run_evaluation_job(_make_ctx(), str(eval_id))
    assert exc.value.defer == timedelta(seconds=get_settings().queue.retry_delay_seconds)
    mock_eval_repo.mark_pending_retry.assert_awaited_once()
    record = mock_eval_repo.mark_pending_retry.await_args.kwargs['attempt_record']
    assert record['attempt'] == 1 and record['status'] == 504
    mock_eval_repo.mark_failed.assert_not_awaited()


async def test_retry_cap_marks_failed_with_attempt_history() -> None:
    ...job_stats={'fetch_attempts': [{...}, {...}, {...}]}  # already max_retries records → no Retry
    mock_eval_repo.mark_failed.assert_awaited_once()
    stats = mock_eval_repo.mark_failed.await_args.kwargs['job_stats']
    assert stats['error'].startswith('adapter query failed after 4 attempts')
    assert len(stats['fetch_attempts']) == 4


async def test_data_errors_only_do_not_retry() -> None:
    # Review Focus 4: a 200 with only data errors evaluates normally
    ...fetch_and_evaluate returns a FetchAndEvaluateResult; mark_pending_retry never awaited; write_results awaited


def test_worker_settings_apply_queue_timeouts() -> None:
    assert WorkerSettings.job_timeout == get_settings().queue.job_timeout_seconds
    assert WorkerSettings.max_tries == get_settings().queue.max_retries + 2
    assert WorkerSettings.keep_result == get_settings().queue.keep_result_seconds
```

Executor tests (`test_evaluation_executor.py`; stub `adapter_client.query` with an `AsyncMock`):
`test_transient_error_kind_raises_adapter_fetch_error` (200 with `error_kinds={'m': 'transient'}` → raises, cause
contains the metric name and message), `test_data_error_kind_scores_none` (kinds `data` → returns result with the
metric `None` in `metrics_fetched`). Repository integration test: `test_requeue_stuck_preserves_fetch_attempts`
(Review Focus 5) and `test_mark_pending_retry_merges_job_stats_and_clears_started_at`.

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement**

Executor: the adapter call becomes

```python
    try:
        metrics_fetched, fetch_errors, sli_metadata, error_kinds = await adapter_client.query(...)
    except AdapterFetchError:
        log.exception('adapter query failed', adapter_url=datasource.adapter_url)
        raise
    transient = sorted(name for name, kind in error_kinds.items() if kind == 'transient')
    if transient:
        detail = '; '.join(f'{name}: {fetch_errors.get(name, "")}' for name in transient)
        raise AdapterFetchError(f'transient adapter errors for {detail}', attempts=1, last_status=200, elapsed_s=0.0)
```

(the `except (httpx.ConnectError, ...)` branch and `-> ... | None` go away; `_log_adapter_response` logs
`error_kinds` too). Repository:

```python
    async def mark_pending_retry(self, eval_id: uuid.UUID, *, attempt_record: dict[str, Any]) -> None:
        """Return a running evaluation to pending after a transient fetch failure, appending the attempt.

        Merges into ``job_stats`` with JSONB ``||`` so ``stuck_job_retries`` and earlier ``fetch_attempts``
        survive; ``started_at`` is cleared so the watchdog does not count the wait as a stuck job.
        """
        row = await self.get_by_id(eval_id)
        attempts = list((row.job_stats or {}).get('fetch_attempts', [])) if row else []
        attempts.append(attempt_record)
        await self._session.execute(
            update(SLOEvaluation).where(SLOEvaluation.id == eval_id).values(
                status=EvaluationStatus.PENDING, started_at=None,
                job_stats=SLOEvaluation.job_stats.op('||')(cast({'fetch_attempts': attempts}, JSONB)),
            )
        )
```

`requeue_stuck` switches to the same `||` merge (`{'stuck_job_retries': n}`) so `fetch_attempts` survive. Queue:

```python
    try:
        async with session_factory() as session:
            ... fetch_and_evaluate(...)
            await session.commit()
    except AdapterFetchError as exc:
        async with session_factory() as session:
            repo = EvaluationRepository(session)
            row = await repo.get_by_id(eval_id)
            previous = list((row.job_stats or {}).get('fetch_attempts', [])) if row else []
            attempt = len(previous) + 1
            record = {'attempt': attempt, **exc.as_attempt_record()}
            if attempt <= settings.queue.max_retries:
                await repo.mark_pending_retry(eval_id, attempt_record=record)
                await session.commit()
                delay = settings.queue.retry_delay_seconds * attempt
                log.warning('adapter fetch failed, job will retry', attempt=attempt, defer_s=delay, cause=exc.cause)
                raise Retry(defer=timedelta(seconds=delay)) from exc
            await repo.mark_failed(eval_id, job_stats={
                'error': f'adapter query failed after {attempt} attempts: {exc.cause}',
                'fetch_attempts': [*previous, record],
            })
            await session.commit()
        log.error('adapter fetch failed, evaluation marked failed', attempts=attempt, cause=exc.cause)
        return
```

(`from arq import Retry`; `settings = get_settings()` is read once at the top of the job.) `WorkerSettings`:
`job_timeout = get_settings().queue.job_timeout_seconds`, `max_tries = get_settings().queue.max_retries + 2`,
`retry_jobs = True`, `keep_result = get_settings().queue.keep_result_seconds`. Remove the now-dead `if fetch_result is None:` branch.

- [ ] **Step 4: Run unit tests, then the repository integration tests** (`just test-env`, `just test-int -q -k "requeue_stuck or mark_pending_retry"`, `just test-env-down`), lint, mypy, stage.

---

### Task 8: Refetch repositories and the `refetch` annotation category

**Files:**
- Create: `api/alembic/versions/008_seed_refetch_annotation_category.py`
- Modify: `api/tropek/modules/quality_gate/repositories/evaluation.py` (`list_for_refetch`, `reset_for_refetch`)
- Modify: `api/tropek/modules/quality_gate/repositories/evaluation_run.py` (`mark_pending`)
- Modify: `api/tropek/modules/change_points/repository.py` (`delete_for_slo_range`)
- Test: `api/tests/quality_gate/db/test_refetch_repositories.py` (new, `@pytest.mark.integration`)

**Interfaces:**
- Produces:

```python
class RefetchScope(BaseModel):            # api/tropek/modules/quality_gate/shared/params.py
    asset_id: uuid.UUID
    period_from: datetime
    period_to: datetime                   # inclusive on period_start
    evaluation_name: str | None = None
    slo_names: list[str] | None = None
    only_failed: bool = False

EvaluationRepository.list_for_refetch(scope: RefetchScope) -> list[SLOEvaluation]
EvaluationRepository.reset_for_refetch(eval_ids: list[uuid.UUID], *, job_stats_by_id: dict[uuid.UUID, dict[str, Any]]) -> None
EvaluationRunRepository.mark_pending(run_id: uuid.UUID) -> None
ChangePointRepository.delete_for_slo_range(*, asset_id: uuid.UUID, slo_name: str, period_from: datetime, period_to: datetime) -> int
```

  Task 9 consumes all four.

- [ ] **Step 1: Migration** (data-only; follow `002`'s `op.execute` style):

```python
"""Seed the 'refetch' annotation category used by run-level refetch notes."""

from alembic import op

revision = '008'
down_revision = '007'


def upgrade() -> None:
    op.execute("""
        INSERT INTO annotation_categories (id, name, label, color, show_on_graph, is_system) VALUES
            (gen_random_uuid(), 'refetch', 'Refetch', 'gray', false, true)
        ON CONFLICT (name) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM annotation_categories WHERE name = 'refetch'")
```

Verify with `just test-env` then `just migrate-test` (applies to the test DB).

- [ ] **Step 2: Failing integration tests** (set up asset + SLO + two completed evaluations with indicator rows,
  SLI values and a change point, like `test_re_evaluation_endpoints._setup_re_eval`):

```python
async def test_list_for_refetch_filters_by_range_name_slo_and_failed(session): ...
async def test_reset_for_refetch_clears_results_and_children_but_keeps_annotations_and_invalidation(session):
    # after reset: status pending, result/score/achieved/total/started_at None, original_result/override_* None,
    # indicator_results and sli_values gone, annotations still present, invalidated flag and note unchanged,
    # baseline_pinned_at unchanged, job_stats == the given dict
async def test_delete_for_slo_range_only_touches_the_slo_and_period(session): ...
async def test_mark_pending_sets_run_status(session): ...
```

- [ ] **Step 3: Implement**

`list_for_refetch`: `select(SLOEvaluation).where(asset_id ==, period_start >= from, period_start <= to)` plus the
optional filters, `order_by(period_start, slo_name)`. `reset_for_refetch`: one `update(SLOEvaluation).where(id.in_(...))`
per id (job_stats differ) setting the columns of spec §8.2 step 1; then
`IndicatorRepository(self._session).delete_for_evaluation(id)` and `SLIValueRepository(self._session).delete_sli_values(id)`
for each id (both exist). `mark_pending`: `update(EvaluationRun).values(status=EvaluationStatus.PENDING, completed_at=None)`
(check the run model's column names before writing). `delete_for_slo_range`: `delete(ChangePoint).where(asset_id ==, slo_name ==, period_start >= from, period_start <= to)` returning `rowcount`.

- [ ] **Step 4: Run** `just test-int -q -k refetch`, lint, mypy, `just test-env-down`, stage.

---

### Task 9: Refetch service, schemas, endpoints, 409 text, schema export

**Files:**
- Create: `api/tropek/modules/quality_gate/schemas/refetch.py`, export from `schemas/__init__.py`
- Create: `api/tropek/modules/quality_gate/workflows/refetch/__init__.py`, `.../refetch/service.py`
- Modify: `api/tropek/modules/quality_gate/router.py` (two endpoints after the re-evaluate ones)
- Modify: `api/tropek/modules/quality_gate/workflows/trigger/trigger_service.py` (the duplicate 409 text; grep `find_duplicate` to find it)
- Modify: `api/openapi.json` via `just export-schema`
- Test: `api/tests/quality_gate/endpoints/test_refetch_endpoints.py` (integration), `api/tests/quality_gate/workflows/test_refetch_service.py` (unit, repos mocked)

**Interfaces:**
- Consumes: Task 8 repository methods; `QualityGateRepos` (has `eval_repo`, `eval_run_repo`, `annotation_repo`,
  `category_repo`, `asset_repo`, `cache`, `heatmap_cache`, `trend_cache`, `session`); `get_arq_pool`.
- Produces (schemas, exact field names — the client and UI copy them):

```python
class RefetchRequest(StrictInput):
    asset_name: str
    from_: datetime = Field(alias='from')
    to: datetime
    evaluation_name: str | None = None
    slo_names: list[str] | None = None
    only_failed: bool = False
    dry_run: bool = False
    reason: str | None = Field(default=None, max_length=500)
    requested_by: str | None = Field(default=None, max_length=120)

class RefetchRunRequest(StrictInput):
    only_failed: bool = False
    dry_run: bool = False
    reason: str | None = None
    requested_by: str | None = None

class RefetchSkipped(BaseModel):
    evaluation_id: uuid.UUID
    slo_name: str
    reason: str

class RefetchResponse(BaseModel):
    matched: int
    refetched: int
    skipped: list[RefetchSkipped]
    run_ids: list[uuid.UUID]
    dry_run: bool
```

  Endpoints: `POST /evaluations/refetch` and `POST /evaluation-run/{run_id}/refetch`, both `response_model=RefetchResponse`,
  status 200.

- [ ] **Step 1: Failing tests**

Unit (`test_refetch_service.py`, repos as `AsyncMock`s): `test_dry_run_counts_without_changes`,
`test_running_row_raises_conflict_before_any_write`, `test_only_failed_narrows_scope`,
`test_reset_enqueues_one_job_per_row_and_one_run_note`. Integration (`test_refetch_endpoints.py`, pattern of
`test_re_evaluation_endpoints.py`; patch the arq pool dependency with an `AsyncMock` recording `enqueue_job` calls):

```python
async def test_refetch_by_period_resets_rows_and_enqueues(client, session): ...
async def test_refetch_run_endpoint(client, session): ...
async def test_refetch_with_running_row_is_atomic_409(client, session):
    # Review Focus 3: one running + one completed in range → 409; completed row unchanged; no enqueue; CP still present
async def test_refetch_range_validation_422(client): ...   # to < from; range > 400 days
async def test_refetch_unknown_asset_404(client): ...
async def test_refetch_keeps_pin_and_invalidation(client, session): ...
async def test_trigger_duplicate_409_mentions_refetch(client, session): ...
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement the service** (`workflows/refetch/service.py`):

```python
REFETCH_CATEGORY_NAME = 'refetch'
MAX_RANGE_DAYS = 400


async def refetch(request: RefetchRequest, repos: QualityGateRepos, arq_pool: ArqRedis) -> RefetchResponse:
    asset = await repos.asset_repo.get_by_name(request.asset_name)      # NotFoundError('asset', name) when None
    _validate_range(request.from_, request.to)                         # DomainValidationError on to<from or >400 days
    scope = RefetchScope(asset_id=asset.id, period_from=request.from_, period_to=request.to,
                         evaluation_name=request.evaluation_name, slo_names=request.slo_names, only_failed=request.only_failed)
    rows = await repos.eval_repo.list_for_refetch(scope)
    return await _refetch_rows(rows, request, repos, arq_pool)


async def refetch_run(run_id: uuid.UUID, request: RefetchRunRequest, repos, arq_pool) -> RefetchResponse:
    run = await repos.eval_run_repo.get_by_id(run_id)                   # NotFoundError('evaluation run', ...)
    rows = await repos.eval_repo.get_by_run_id(run_id)
    if request.only_failed:
        rows = [r for r in rows if r.status == EvaluationStatus.FAILED]
    return await _refetch_rows(rows, request, repos, arq_pool)


async def _refetch_rows(rows, request, repos, arq_pool) -> RefetchResponse:
    in_progress = [r for r in rows if r.status in (EvaluationStatus.PENDING, EvaluationStatus.RUNNING)]
    if in_progress:
        raise ConflictError('evaluation', str(in_progress[0].id), 'in progress')   # nothing written yet
    eligible = [r for r in rows if r.status in (COMPLETED, PARTIAL, FAILED)]
    skipped = [RefetchSkipped(evaluation_id=r.id, slo_name=r.slo_name, reason=f'status {r.status}') for r in rows if r not in eligible]
    run_ids = sorted({r.evaluation_id for r in eligible})
    if request.dry_run:
        return RefetchResponse(matched=len(rows), refetched=len(eligible), skipped=skipped, run_ids=run_ids, dry_run=True)
    now = datetime.now(UTC).isoformat()
    job_stats_by_id = {r.id: {'refetch': {'requested_at': now, 'requested_by': request.requested_by, 'reason': request.reason,
                                          'previous_result': r.result, 'previous_status': r.status}} for r in eligible}
    await repos.eval_repo.reset_for_refetch([r.id for r in eligible], job_stats_by_id=job_stats_by_id)
    for r in eligible:   # change points of the asset+SLO within the refetched period (per row's own period)
        await ChangePointRepository(repos.session).delete_for_slo_range(asset_id=r.asset_id, slo_name=r.slo_name,
                                                                        period_from=r.period_start, period_to=r.period_start)
    category = await repos.category_repo.get_by_name(REFETCH_CATEGORY_NAME)   # migration 008 guarantees it
    for run_id in run_ids:
        await repos.eval_run_repo.mark_pending(run_id)
        count = sum(1 for r in eligible if r.evaluation_id == run_id)
        await repos.annotation_repo.add_run_annotation(run_id, content=f'refetched from source: {count} SLO evaluation(s)'
                                                       + (f' — {request.reason}' if request.reason else ''),
                                                       author=request.requested_by or 'system', category_id=category.id, tags={})
    await repos.eval_repo._invalidate_caches_for(eligible)          # baseline + heatmap; make it public: invalidate_caches_for
    if repos.trend_cache is not None:
        await repos.trend_cache.delete_many([r.id for r in eligible])
    for r in eligible:
        await arq_pool.enqueue_job('run_evaluation_job', str(r.id))
    return RefetchResponse(matched=len(rows), refetched=len(eligible), skipped=skipped, run_ids=run_ids, dry_run=False)
```

Rename `_invalidate_caches_for` to `invalidate_caches_for` (keep a private alias if other callers exist). The
router endpoints mirror the re-evaluate ones (`repos: QualityGateRepos = Depends(get_qg_repos)`, `arq_pool: ArqRedis = Depends(get_arq_pool)`),
mapping `ConflictError`/`NotFoundError`/`DomainValidationError` as the module already does. Trigger 409 text for a
completed duplicate: `already evaluated; use re-evaluate to re-score stored data or refetch to fetch it again from the source`.
Run `just export-schema` and commit-stage `api/openapi.json`.

- [ ] **Step 4: Run** unit + `just test-int -q -k refetch`, `just check-schema-fresh`, lint, mypy; `just test-env-down`; stage.

---

### Task 10: Python client

**Files:**
- Modify: `clients/python/tropek_client/models/evaluations.py`, `models/__init__.py` (exports), `client.py`
- Modify: `clients/python/CHANGELOG.md`
- Test: `clients/python/tests/test_evaluations.py`

**Interfaces:**
- Consumes: Task 9 schemas (same field names; `RefetchRequest` uses `from_` with `alias='from'` and
  `model_config = ConfigDict(populate_by_name=True)` so callers write `RefetchRequest(from_=..., to=...)`).
- Produces: `client.evaluations.refetch(body: RefetchRequest) -> RefetchResponse`,
  `client.evaluations.refetch_run(run_id: str, body: RefetchRunRequest) -> RefetchResponse`.

- [ ] **Step 1: Failing tests** (respx, pattern of the file):

```python
@respx.mock
def test_refetch_posts_period_body(client):
    route = respx.post(f'{BASE_URL}/evaluations/refetch').mock(
        return_value=httpx.Response(200, json={'matched': 30, 'refetched': 23, 'skipped': [], 'run_ids': [UUID1], 'dry_run': False})
    )
    body = RefetchRequest(asset_name='a', from_=TIMESTAMP, to=TIMESTAMP, only_failed=True, reason='outage')
    result = client.evaluations.refetch(body)
    assert result.refetched == 23
    sent = json.loads(route.calls.last.request.content)
    assert sent['from'] == TIMESTAMP and sent['only_failed'] is True and 'from_' not in sent


@respx.mock
def test_refetch_run(client): ...  # POST /evaluation-run/{UUID1}/refetch
```

- [ ] **Step 2: Run to verify failure.** `uv run --directory clients/python pytest tests/test_evaluations.py -q`.

- [ ] **Step 3: Implement** — models as in Task 9 (client-side copies; `model_dump(mode='json', by_alias=True, exclude_none=True)`
  in the two methods, placed after `re_evaluate_from_evaluation`). CHANGELOG entry under Unreleased: "Added
  `evaluations.refetch` and `evaluations.refetch_run` (requires Tropek ≥ the release carrying refetch)".

- [ ] **Step 4: Run, lint (`uv run ruff check clients/`), stage.**

---

### Task 11: UI — refetch mode in the Run Evaluations dialog

**Files:**
- Modify: `ui/src/features/evaluations/domain.ts` (`RefetchInput`, `RefetchResponse`), `api.ts` (`refetch()`), `mappers.ts` (`refetchInputToDto`, `dtoToRefetchResponse`), `hooks.ts` (`useRefetch`, `useRefetchPreview`)
- Modify: `ui/src/features/evaluations/components/actions/ReEvaluateForm.tsx`, `ReEvaluateForm.test.tsx`
- Modify: `ui/src/mocks/handlers/evaluations.ts`
- Regenerate: `ui/src/generated/api.ts` via `just codegen` (after Task 9's `just export-schema`)

**Interfaces:**
- Consumes: `POST /evaluations/refetch` (Task 9) with body keys `asset_name, from, to, slo_names, only_failed, dry_run, reason`.
- Produces: in `domain.ts`

```ts
export interface RefetchInput {
  assetName: string
  sloNames: string[]
  from: string          // ISO
  to: string            // ISO
  onlyFailed: boolean
  dryRun: boolean
  reason: string | null
}
export interface RefetchResponse { matched: number; refetched: number; skipped: { evaluationId: string; sloName: string; reason: string }[]; runIds: string[]; dryRun: boolean }
```

- [ ] **Step 1: Failing vitest** (extend `ReEvaluateForm.test.tsx`; mock `refetch` like `reEvaluate`):

```ts
it('refetch mode hides the baseline option, shows the warning and disables Run until confirmed', async () => {
  const user = userEvent.setup()
  render(...ReEvaluateForm with defaultFromDate='2026-10-15T00:00' ...)
  await user.click(screen.getByLabelText(/refetch from source/i))
  expect(screen.queryByLabelText(/run from last baseline/i)).toBeNull()
  expect(screen.getByText(/deleted and fetched again/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /run/i })).toBeDisabled()
  await user.click(screen.getByLabelText(/i understand/i))
  expect(screen.getByRole('button', { name: /run/i })).toBeEnabled()
})

it('refetch preview comes from a dry run and the run sends dryRun=false', async () => {
  refetchSpy.mockResolvedValue({ matched: 30, refetched: 23, skipped: [], runIds: ['r1'], dryRun: true })
  ...switch to refetch mode; expect text /will refetch 23 of 30/i
  ...confirm + run; expect refetchSpy last call payload.dryRun === false and payload.sloNames === ['latency-slo']
})

it('switching back to re-score restores the original content', async () => { ... })
```

- [ ] **Step 2: Run** `./scripts/ui-test.sh --tail 20` → FAIL.

- [ ] **Step 3: Implement**

`api.ts`: `refetch(input)` POSTs `/evaluations/refetch` with `refetchInputToDto` (`{asset_name, from, to, slo_names, only_failed, dry_run, reason}`),
throws `Error(body.detail)` on non-2xx, maps with `dtoToRefetchResponse` (snake → camel). `hooks.ts`:
`useRefetch()` = `useMutation` invalidating the same keys as `useReEvaluate`; `useRefetchPreview(input | null)` =
`useQuery({ queryKey: ['refetch-preview', input], queryFn: () => refetch({ ...input, dryRun: true }), enabled: !!input, staleTime: 0 })`
(the component debounces `input` by 400 ms with a small `useDebouncedValue` helper, local to the file).
`ReEvaluateForm.tsx`: state `mode: 'rescore' | 'refetch'` (default `'rescore'`), rendered as two radio inputs with
labels "Re-score from stored data" / "Refetch from source" at the top of the form; `ACTION_DEF.description`
switches to "Delete stored values for the selected SLOs and fetch them again from the source." in refetch mode;
refetch mode renders: start `datetime-local` (reuses `fromDate`), end `datetime-local` (`toDate`, default
`defaultToDate ?? defaultFromDate`; add optional prop `defaultToDate`), checkbox "Only SLO evaluations that
failed", the warning block (`text-fail bg-fail/10 border-fail/20`, text from spec §8.4), the preview line
("Will refetch {refetched} of {matched} SLO evaluations between {from} and {to}" or "Nothing to refetch"), and the
checkbox "I understand that the stored data for this period is deleted". `canConfirm` in refetch mode =
`confirmed && !!fromDate && !!toDate && scope.selected.size > 0 && preview?.refetched > 0`. On confirm call
`refetchMutation.mutate({...input, dryRun: false}, { onSuccess: onComplete })`. Add the msw handler
`http.post('/api/evaluations/refetch', …)` returning `{matched, refetched, skipped: [], run_ids: [], dry_run}`.
Run `just codegen` so `generated/api.ts` carries the new paths.

- [ ] **Step 4: Run** `./scripts/ui-test.sh --tail 20`, `./scripts/ui-lint.sh --tail 20`, `just check-schema-fresh`; stage.

---

### Task 12: Changelog, operator guide, final checks

**Files:**
- Modify: `CHANGELOG.md` (Unreleased: Fixed / Added / Changed per spec §12)
- Create: `docs/guides/repairing-a-failed-fetch.md`
- Modify: `docs/configuration.md` (link to the guide from "The timeout chain")

- [ ] **Step 1: Write the guide** — sections: "How a day ends up `failed`" (the retry chain in four sentences, what
  `job_stats.fetch_attempts` shows), "Refetch versus re-evaluate" (re-score stored data vs delete-and-fetch; what is
  deleted, what is kept, later days not re-scored), "From the UI" (the dialog mode, the preview, the confirmation),
  "From the API or client" (both endpoints with one example body each, `dry_run` first), "When the source no
  longer has the period" (the evaluation ends `failed` again; only a database restore brings the old values back).
- [ ] **Step 2: Changelog** — one `### Fixed` paragraph for the chain (no deployment names), `### Added` bullets
  (refetch API/client/UI, `error_kinds` and `timeout_seconds` in the protocol, global Prometheus concurrency limit,
  enforced adapter job timeout, config validators, readiness counters), `### Changed` (the default timeouts table).
- [ ] **Step 3: Final checks** — `just check`; API unit suite; adapter suite; mock suite; protocol suite; client
  suite; `./scripts/ui-test.sh --tail 20`; `just check-schema-fresh`. Stage.

---

## Execution notes for the controller

- Tasks 1–4 (adapter side) and 5–7 (worker side) are independent chains; 6 depends on 1 only for the field names
  (copies them). Run them in order 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12; never two implementers at once.
- Task 7's integration tests and Tasks 8–9 need `just test-env` (port 5433). The implementer runs
  `just test-env-down` before reporting.
- Review packages: index snapshots (`git write-tree` on a temporary index), path-scoped to the task's files; the
  owner commits after each approved task with the repo's conventional prefixes
  (`fix(adapter): …`, `fix(worker): …`, `feat(api): …`, `feat(client): …`, `feat(ui): …`, `docs: …`).
- Final whole-branch review on opus over `main..HEAD` before `superpowers:finishing-a-development-branch`.
