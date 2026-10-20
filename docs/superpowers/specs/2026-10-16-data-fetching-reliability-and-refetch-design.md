# Data-fetching reliability and refetch — design

**Date:** 2026-10-16 · **Branch:** `bug/improve-data-fetching-reliability` · **Status:** draft for review

## 1. Problem

An asset-day of 30 SLO evaluations was triggered against a Prometheus-backed data source. 23 of the 30 were
stored as `failed` (`result NULL`, `sli_metadata NULL`, `job_stats.error = 'adapter query failed'`); a second
attempt stored 4 failed, a third 0 — on identical source data. The same day scored 30/30 at the first attempt on
a second deployment whose only difference was a larger worker timeout. Read from the v0.1.5-alpha source, the
chain is:

1. **Worker → adapter.** `HttpAdapterClient` (`api/tropek/modules/quality_gate/workflows/execution/adapter_client.py`)
   holds one synchronous `POST /query` open per SLO evaluation, with `reliability.adapter_timeout_seconds` as
   the read timeout (30 s in the shipped `config.yaml`). It retries only `httpx.ConnectError` and
   `httpx.ReadError`, with a hardcoded policy; a read timeout, a 503 or a 504 is not retried. The executor
   (`evaluation_executor.fetch_and_evaluate`) then returns `None` and `run_evaluation_job` (`api/tropek/queue.py`)
   calls `_mark_failed`. The `reliability.adapter_retry_attempts` / `adapter_retry_backoff_seconds` settings and
   the `queue.max_retries` / `retry_delay_seconds` / `job_timeout_seconds` settings exist in `config.yaml` and
   `config.py` but are read by nothing: arq's `Retry` is never raised and `WorkerSettings` sets only `max_jobs`.
2. **Adapter sync endpoint.** `sync_query` (`adapters/prometheus/tropek_prometheus/api/routes.py`) submits an
   internal job and polls it for at most `2 × query_timeout_seconds` (60 s), then raises 504. Jobs queue behind
   `max_concurrent_jobs` (3) while the worker runs `queue.max_jobs` (10) evaluations, so under a burst a job may
   not have *started* within the poll budget. The job's own stored timeout is never enforced
   (`JobRepository.mark_timed_out` has no caller).
   *Ruling 2026-10-19: the coordinator was serial; it now runs up to `max_concurrent_jobs` jobs concurrently.*
3. **Adapter → Prometheus.** `PrometheusClient._get` has no retry. In the aggregated strategy a chunk whose range
   query fails is counted in `chunks_failed` and the metric is scored on the chunks that did arrive — a mean over
   two thirds of a day is reported as a valid number, with the gap visible only in metadata. Up to
   `max_concurrent_jobs × max_concurrent_queries × parallel_chunks` (3 × 10 × 3 = 90) range queries can be in
   flight at once, which is the most plausible reason a modest Prometheus "chokes".
4. **No repair path.** `/evaluations/re-evaluate/*` re-scores stored indicator rows and never re-fetches; a new
   trigger for the day answers 409 because the completed siblings exist (failed rows are already excluded from
   `uq_slo_evaluations_identity`). Operators repair such a day by deleting rows in the database.

## 2. Goals and rules

- A transient failure is retried with backoff **at the hop where it happened**: Prometheus request, adapter job,
  adapter HTTP call, evaluation job.
- **Incomplete data is an error, never a partial value.** A metric whose window could not be fetched completely
  is reported as an error flagged *transient*, so the next hop retries it.
- An SLO evaluation is stored `failed` **only after every retry at every hop is exhausted**, with the attempt
  history in `job_stats`.
- Tropek can **refetch** stored SLO evaluations from the source itself (API, Python client, UI), replacing the
  stored values in place; no database access is needed to repair a day.
- Config defaults are consistent along the chain and an inconsistent set refuses to start.
- The adapter protocol stays `POST /query`; the two protocol changes are additive and optional.

Out of scope: moving the worker to the adapter's asynchronous job API (a follow-up, §11), re-scoring later days
after a refetch (the existing re-evaluate from-date does that), storing a snapshot of the old values before a
refetch (only the previous result is kept for audit).

## 3. Worker → adapter

### 3.1 `HttpAdapterClient` retry policy

`_post_with_retry` becomes a policy object driven by settings:

| setting | meaning | default |
|---|---|---|
| `reliability.adapter_retry_attempts` | total attempts per `query()` call (1 = no retry) | 3 |
| `reliability.adapter_retry_backoff_seconds` | base of the exponential backoff (`base × 2^(attempt-1)`, ±25 % jitter) | 2 |
| `reliability.adapter_timeout_seconds` | read timeout of one attempt | 330 (§7) |

Retried: `httpx.ConnectError`, `httpx.ReadError`, `httpx.TimeoutException` (all subclasses), and responses
with status 429, 502, 503, 504. A `Retry-After` header (seconds) overrides the computed backoff when present.
Not retried: any other 4xx (raised as `httpx.HTTPStatusError` as today), a 200 (handled in 3.2). Every retry logs
`adapter request retried` with `attempt`, `max_attempts`, `backoff_s`, `cause` (exception class or status code).
The hardcoded `_TRANSIENT_ERRORS`, `_MAX_RETRIES`, `_RETRY_BACKOFF_SECONDS` constants are removed.

The request body gains `timeout_seconds` (§5.2): `adapter_timeout_seconds − 30`, floored at 30, so the adapter
stops waiting before the worker gives up on the request.

### 3.2 A transient 200

The protocol response gains an optional field (§6): `error_kinds: dict[str, Literal['transient', 'data']]`,
default empty, meaning every error is a data error (today's behaviour, so older adapters are unaffected). The
executor classifies the response:

- any metric with kind `transient` → the fetch **failed** (an `AdapterFetchError` carrying the error messages),
  regardless of how many other metrics succeeded. Partial re-fetching is deliberately not attempted: an SLO
  evaluation is one unit of work and its baselines are resolved once.
- no transient errors → evaluate as today (`data` errors become `None` metrics and score `error`).

### 3.3 The evaluation job retries before it fails

`fetch_and_evaluate` returns a result or raises `AdapterFetchError(cause: str, attempts: int, last_status: int | None, elapsed_s: float)`
instead of returning `None`. In `run_evaluation_job`:

```python
except AdapterFetchError as exc:
    attempt = ctx['job_try']                       # arq: 1 on the first run
    if attempt <= settings.queue.max_retries:
        await repo.mark_pending_retry(eval_id, job_stats_update={...})   # status back to 'pending'
        raise Retry(defer=settings.queue.retry_delay_seconds * attempt)
    await _mark_failed(session_factory, eval_id, exc.cause, job_stats=exc.as_job_stats())
```

- `queue.max_retries` (default 3) is the number of **additional** job runs; `queue.retry_delay_seconds`
  (default 10) is the base of a linear delay (10 s, 20 s, 30 s).
- Between attempts the SLO evaluation is `pending` again, `started_at` cleared, so the watchdog
  (`watchdog_stuck_evaluations_job`) does not count the wait as a stuck `running` job and
  `has_pending_predecessor` keeps later days deferred behind it.
- `job_stats` accumulates `fetch_attempts` (list of `{attempt, cause, status, elapsed_s, at}`); on the final
  failure `error` is `adapter query failed after N attempts: <last cause>`.
- `WorkerSettings` applies `job_timeout = settings.queue.job_timeout_seconds`, `max_tries = settings.queue.max_retries + 1`,
  `retry_jobs = True`, `keep_result = settings.queue.keep_result_seconds`.
- `_MAX_PREDECESSOR_DEFERS` deferral is unchanged and is not counted as a retry (`defer_count` stays a job
  argument; `job_try` counts only `Retry` re-runs).

The `finalize_run_job` / `finalize_sweeper_job` logic is unchanged: a run completes when no child is pending,
running or partial, which now includes children awaiting a retry.

## 4. Adapter → Prometheus

### 4.1 `PrometheusClient` retry policy

| setting (env) | meaning | default |
|---|---|---|
| `PROMETHEUS_RETRY_ATTEMPTS` | attempts per request | 3 |
| `PROMETHEUS_RETRY_BACKOFF_SECONDS` | exponential base, ±25 % jitter, `Retry-After` honoured | 1 |
| `QUERY_TIMEOUT_SECONDS` | per-request timeout | 60 (was 30) |
| `MAX_CONCURRENT_PROMETHEUS_REQUESTS` | global in-flight limit, all jobs and chunks | 8 |

Retried: `httpx.TimeoutException`, `httpx.ConnectError`, `httpx.ReadError`, status 429, 500, 502, 503, 504,
and a 200 whose body has `status: error` with `errorType` in `{'timeout', 'canceled', 'unavailable', 'internal'}`.
Final (no retry): 400, 422, `errorType: 'bad_data'` or `'execution'` (a bad query), a non-matrix / non-scalar
result. `PrometheusQueryError` gains `transient: bool`; the message keeps the attempt count.

The global limit is one `asyncio.Semaphore` owned by the shared `PrometheusClient` instance and acquired inside
`_get`, so it bounds every path (instant, range, chunked range) regardless of the coordinator's and the
strategy's own semaphores, which stay as per-job and per-query caps.

### 4.2 Incomplete data is an error

In `AggregatedStrategy._fetch_range`, a chunk that still fails after the client's retries is recorded and the
fetch returns `chunks_failed > 0`. `execute` then returns, for every method of the metric, `values[key] = None`
and `errors[key] = 'incomplete data: {chunks_failed} of {chunks} chunks failed (last: {message})'`, with
`error_kinds[key] = 'transient'` when the last chunk error was transient, else `'data'`. Metadata keeps
`expected_samples`, `actual_samples`, `missing_pct`, `chunks_failed` for observability. A single-chunk window
behaves the same (`1 of 1 chunks failed`). An empty but complete result (`actual_samples == 0`, no chunk failed)
keeps today's `no valid data points` as a `data` error.

`RawStrategy` maps `PrometheusQueryError.transient` to `error_kinds` the same way; its values/errors shape is
unchanged.

### 4.3 Job timeout is enforced

`Coordinator.process_one` wraps the query fan-out in `asyncio.wait_for(..., timeout=job.timeout_seconds)`. On
timeout every metric without a result gets `success=False`, `message='job timed out after {timeout}s'`,
`kind='transient'`, and the job is marked `timed_out` (the existing `JobRepository.mark_timed_out`). The
`results` hash gains a `kind` field per indicator (`transient` / `data`), written by `write_result`, so both
the async status endpoint and the sync endpoint can surface `error_kinds`.

## 5. Adapter HTTP surface

### 5.1 Settings

`default_job_timeout_seconds` 120 → 300, `max_job_timeout_seconds` 600 (unchanged), `max_concurrent_jobs`
3 → 10 (the worker's `max_jobs`; the adapter no longer queues behind a smaller limit, Prometheus load is bounded
by §4.1 instead), `max_concurrent_queries` 10 (unchanged), `query_timeout_seconds` 30 → 60. `Settings()` is
built once in `main.py` and read from `app.state.settings` everywhere (the sync endpoint currently re-instantiates
it per request).

*Ruling 2026-10-19: the coordinator was serial; it now runs up to `max_concurrent_jobs` jobs concurrently.*

### 5.2 `POST /query`

Request gains optional `timeout_seconds: int | None` (protocol §6). The endpoint submits the job with that
timeout (capped by `max_job_timeout_seconds`, defaulting to `default_job_timeout_seconds`), polls every 0.1 s
until the job is `completed`, `timed_out` or `cancelled`, or until `timeout_seconds + 5` elapsed. On budget
exhaustion it cancels the job and answers **504** with `Retry-After: 5` and a JSON body naming the job id. A
`timed_out` job answers 200 with every unfinished metric as a transient error (§4.3), which is what lets the
worker retry instead of failing. Queue full keeps its 503 + `Retry-After: 5`.
*Note 2026-10-19: a job `cancelled` while the caller waits ends the poll at once with 503 + `Retry-After: 5`
(body `{"detail": "job was cancelled", "job_id": …}`): its results are incomplete, and 503 is retryable.*

The response gains `error_kinds` built from the per-indicator `kind`.

### 5.3 `/health/ready`

Adds `queue_depth`, `running_jobs` and `prometheus_in_flight` to the existing readiness payload (numbers only;
no new status semantics).

## 6. Protocol package (`adapters/protocol`)

Additive, optional, backward compatible:

- `AdapterQueryRequest.timeout_seconds: int | None = None` — the caller's budget in seconds; an adapter may cap it.
- `AdapterQueryResponse.error_kinds: dict[str, Literal['transient', 'data']] = {}` — classification of
  `errors`; a missing key means `data`.
- `assert_query_response_valid` accepts and validates the new field (every key of `error_kinds` must be in
  `errors`). README documents both and the engine's rule from §3.2. The mock adapter needs no change beyond
  passing its existing tests with the new models; a `?transient=1` scenario is added so the worker path can be
  exercised in integration tests.

## 7. Configuration defaults and validation

`config.yaml` (shipped and mounted by `docker-compose.yml`) and `docker-compose.yml` adapter environment ship:

| key | old | new | why |
|---|---|---|---|
| adapter `QUERY_TIMEOUT_SECONDS` | 30 | 60 | one range query of a 4 h chunk on a slow source |
| adapter `DEFAULT_JOB_TIMEOUT_SECONDS` | 120 | 300 | a 24 h, 1 m-step job of 6 chunks with retries |
| adapter `MAX_CONCURRENT_JOBS` | 3 | 10 | match the worker's `max_jobs`; no adapter-side queueing |
| adapter `MAX_CONCURRENT_PROMETHEUS_REQUESTS` | — | 8 | the single knob for source load |
| `reliability.adapter_timeout_seconds` | 30 | 330 | job timeout + margin; the budget sent is 300 |
| `queue.job_timeout_seconds` | 120 | 400 | one adapter attempt + evaluation + change points |
| `reliability.stuck_job_threshold_seconds` | 180 | 600 | must exceed the job timeout, as its comment says |

`ReliabilitySettings` / `QueueSettings` get a cross-field validator (`model_validator` on `Settings`):
`adapter_timeout_seconds > 30` (the margin), `job_timeout_seconds > adapter_timeout_seconds`,
`stuck_job_threshold_seconds > job_timeout_seconds`, `max_retries >= 0`; a violation raises at startup with a
message naming all three values. The adapter's `Settings` validates `default_job_timeout_seconds <= max_job_timeout_seconds`
and `max_concurrent_prometheus_requests >= 1`. `docs/configuration.md` gains a "timeout chain" section with the
table above.

*Ruling 2026-10-19: `queue.job_timeout_seconds` must cover one adapter attempt plus evaluation work; long
failures (504 budget exhausted, read timeout) go straight to the job-level retry.* The validator requires
`adapter_timeout_seconds > 35` (budget floor 30 + adapter grace 5) and
`job_timeout_seconds > adapter_timeout_seconds + 60` (strict: at exactly +60 the deadline leaves no room for an
attempt); the worker client starts no HTTP attempt that could
outlast `job_timeout_seconds - 60`, and a 4xx other than 429 or a malformed 2xx fails the evaluation without a
job-level retry.

## 8. Refetch

### 8.1 API

`POST /evaluations/refetch` — body `RefetchRequest`:

```json
{"asset_name": "a", "from": "2026-10-15T00:00:00Z", "to": "2026-10-15T23:59:59Z",
 "evaluation_name": null, "slo_names": null, "only_failed": false, "dry_run": false, "reason": "adapter outage"}
```

`from`/`to` are inclusive on `period_start`. Scope: the asset's SLO evaluations whose `period_start` lies in
the range, optionally narrowed by `evaluation_name` and `slo_names`, and by `only_failed` (status `failed`).

`POST /evaluation-run/{run_id}/refetch` — body `RefetchRunRequest` `{only_failed, dry_run, reason}`; the same
semantics for one run.

Response `RefetchResponse`: `{"matched": n, "refetched": n, "skipped": [{"evaluation_id", "slo_name", "reason"}],
"run_ids": [...], "dry_run": bool}`. 409 when any matched row is `pending` or `running` (nothing changes);
404 for an unknown asset or run; 422 for `to < from` or a range wider than 400 days.

### 8.2 Semantics per SLO evaluation

Allowed statuses: `completed`, `partial`, `failed`. In one transaction per run:

1. `status = 'pending'`, `result`, `score`, `achieved_points`, `total_points`, `started_at` → NULL;
   `original_result`, `override_reason`, `override_author` → NULL (an override applied to values that no longer
   exist); `sli_metadata` cleared.
2. `indicator_results` and `sli_values` of the SLO evaluation deleted.
3. `change_points` of the asset and SLO whose `period_start` is in the refetched period deleted (detection
   re-runs when the job completes).
4. Kept: the row id, `evaluation_id`, `annotations`, `invalidated` + `invalidation_note`, `baseline_pinned_*`.
5. `job_stats` becomes `{"refetch": {"requested_at", "requested_by", "reason", "previous_result", "previous_status"}}`.
6. The run's status → `pending`; one run-level annotation (category `refetch`, seeded like the re-evaluation
   category): `refetched from source: {n} SLO evaluation(s) — {reason}`.
7. `run_evaluation_job` enqueued per row (the existing predecessor rule orders them); the finalize job completes
   the run as usual.
8. Caches: heatmap column of each run, trend fragments of each affected SLO, baseline cache for the asset and
   SLOs from `from` onward, via the existing `_invalidate_*` helpers.

`dry_run` returns the counts and the skipped list without changing anything. The trigger endpoint's 409 message
for a completed duplicate becomes "already evaluated; use re-evaluate to re-score stored data or refetch to fetch
it again from the source".

### 8.3 Python client

`client.evaluations.refetch(body: RefetchRequest) -> RefetchResponse` and
`client.evaluations.refetch_run(run_id, body: RefetchRunRequest) -> RefetchResponse`; models in
`tropek_client.models.evaluations`; CHANGELOG of the client. The client's own test suite covers both.

### 8.4 UI

`ReEvaluateForm.tsx` (the "Run Evaluations" dialog) gains a mode selector at the top: **Re-score from stored
data** (default; today's content and behaviour unchanged) and **Refetch from source**. In refetch mode the dialog
shows: start and end date (end defaults to the last evaluated day in view), a checkbox *Only SLO evaluations that
failed*, a warning block ("Stored values, SLI samples and change points for the selected SLOs between these dates
are deleted and fetched again from the source. If the source no longer holds this period, the data cannot be
recovered without a database restore."), a preview line from `dry_run` ("Will refetch 30 SLO evaluations across 1
day; 23 of them currently failed", refreshed on every scope change, debounced), and a confirmation checkbox that
the Run button requires. The baseline option is hidden in refetch mode. Run calls `POST /evaluations/refetch`
with the dialog's asset, selected SLO names and dates; on success the dialog closes and the heatmap query is
invalidated so the cells render as pending. Generated types come from `just export-schema` + `just codegen`.
Vitest: mode switch restores the default content, preview text, Run disabled until confirmed, request payload.

## 9. Observability

- Worker: `adapter request retried`, `adapter fetch failed, job will retry` (`attempt`, `defer_s`), `adapter fetch
  failed, evaluation marked failed` (`attempts`); `job_stats.fetch_attempts` as in §3.3.
- Adapter: `prometheus request retried` (`attempt`, `backoff_s`, `cause`), `job timed out` (`job_id`,
  `unfinished`), `sync query budget exhausted` (`job_id`, `budget_s`); readiness counters (§5.3).
- `docs/guides/` gains "Repairing a day that failed to fetch": what `failed` with `fetch_attempts` means, when to
  refetch, what refetch deletes and keeps.

## 10. Testing

Unit (no infrastructure):

- `api/tests/.../test_adapter_client.py`: timeout then success; 504 then success; `Retry-After` honoured;
  attempts exhausted raises; 400 not retried; `timeout_seconds` sent; `error_kinds` parsed.
- `api/tests/.../test_queue.py`: transient fetch → `Retry` raised, row back to `pending`, `job_stats.fetch_attempts`
  appended; exhaustion → `failed` with the summarised error; data-only errors → evaluated, no retry;
  `WorkerSettings` carries `job_timeout`/`max_tries`.
- `api/tests/.../test_config*.py`: validators accept the shipped defaults and reject each inconsistency.
- `adapters/prometheus/tests/test_prometheus_client.py`: retry matrix (timeout, 503, 429 + `Retry-After`,
  `errorType: timeout`), final errors, `transient` flag, global semaphore bounds in-flight requests.
- `test_aggregated_strategy.py`: a failed chunk → every method `None` + `incomplete data…` + `transient`; an
  empty complete result → `no valid data points` + `data`.
- `test_coordinator.py`: job timeout marks `timed_out` and writes transient results for unfinished metrics.
- `test_routes.py`: sync `/query` returns 200 with transient errors on a timed-out job; 504 + `Retry-After` on
  budget exhaustion with the job cancelled; `timeout_seconds` capped.
- Protocol: `assert_query_response_valid` with and without `error_kinds`; the mock adapter's transient scenario.

Integration (test database, `just test-int`): refetch by period and by run — reset semantics, deleted indicator
rows, SLI values and change points, kept annotations/invalidation/pins, 409 on a running row, `only_failed`,
`dry_run` changes nothing, run annotation written, jobs enqueued (arq pool stub), cache keys invalidated. Client
tests for the two new methods. `just check-schema-fresh` after `just export-schema` and `just codegen`.

## 11. Follow-ups (separate specs)

- **Asynchronous adapter protocol.** The worker submits `POST /api/v1/query-jobs` and polls, behind an adapter
  capability advertised on `/health/ready`; adapters without it keep the synchronous path. Removes the long-held
  HTTP request entirely.
- Re-scoring later days after a refetch as one action (refetch + re-evaluate from the day after).
- A source-retention hint on the data source so the UI can warn *before* a refetch that the period is likely gone.
- **Sweeper for orphaned `pending` evaluations.** A `pending` SLO evaluation can be left with no live job: arq
  can drop a job at its own `max_tries` when cancellations add to the retries, and a failed enqueue after a
  refetch commit leaves its rows `pending`. The watchdog scans only `running` rows, so nothing recovers them.
- **Predecessor-defer cap versus a retrying predecessor.** A successor's predecessor-defer cap (about 120 s) can
  be shorter than a predecessor that is still retrying its fetch, so the successor may run without that baseline.
- **A `reason` field in the refetch dialog.** The API accepts `reason`, but the UI dialog does not send one yet.

## 12. Changelog

Under `[Unreleased]` → **Fixed**: the failure chain of §1 in one paragraph (a queued or slow adapter job was
stored as a failed evaluation and could not be repaired); **Added**: refetch (API, client, UI), the transient error
classification in the adapter protocol, the global Prometheus concurrency limit, the enforced adapter job timeout,
the config validators; **Changed**: the default timeouts (§7).
