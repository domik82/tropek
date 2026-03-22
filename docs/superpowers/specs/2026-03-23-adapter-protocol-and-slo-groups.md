# Adapter Protocol Evolution & SLO Group Generator

**Date:** 2026-03-23
**Status:** Approved (brainstorm)

---

## Context

TROPEK needs to evolve from its current POC adapter protocol (thin synchronous HTTP wrapper) to a production-ready architecture that handles:

- Batch query execution against Prometheus (and future backends: Datadog, CloudWatch, Grafana)
- Concurrency and backpressure control to avoid overwhelming data sources
- A templating system for managing large numbers of uniform SLOs (e.g., 30 plugins × 10 indicators)

Key architectural principle: **TROPEK owns meaning, adapters own execution.** Variable substitution, SLO semantics, and evaluation logic stay in the TROPEK backend. Adapters receive ready-to-execute queries and handle efficient execution against their specific backend.

---

## 1. Adapter Protocol

### Design: Async Job Model

The adapter exposes an async batch query interface. The worker submits queries, gets a job ID, polls for results.

**Endpoints:**

| Endpoint | Method | Purpose |
|---|---|---|
| `/query` | POST | Submit query batch → `202 {job_id, poll_url}` |
| `/query-jobs/{job_id}` | GET | Poll status and results |
| `/query-jobs/{job_id}` | DELETE | Cancel a running job |
| `/health` | GET | Liveness/readiness |

### Submit: `POST /query`

**Request:**
```json
{
  "queries": {
    "query_id_1": "rate(cpu_seconds_total{plugin='abc'}[5m])",
    "query_id_2": "rate(memory_bytes{plugin='abc'}[5m])",
    "query_id_3": "rate(cpu_seconds_total{plugin='xyz'}[5m])"
  },
  "start": "2026-03-22T00:00:00Z",
  "end": "2026-03-22T01:00:00Z",
  "options": {
    "max_concurrent": 10,
    "per_query_timeout_seconds": 30
  }
}
```

- `queries`: dict of `{opaque_id: promql_string}`. IDs assigned by TROPEK worker, adapter doesn't interpret them.
- `start`/`end`: ISO 8601 timestamps defining the evaluation period.
- `options.max_concurrent`: hint for adapter-side concurrency cap. Adapter may cap further based on its own limits.
- `options.per_query_timeout_seconds`: per-query HTTP timeout hint.
- `datasource_name` is sent as the `X-Datasource-Name` HTTP header (consistent with current adapter protocol). It identifies which datasource config the adapter should use (e.g., Prometheus URL, auth).

**Response `202`:**
```json
{
  "job_id": "a1b2c3d4-...",
  "status": "queued",
  "poll_url": "/query-jobs/a1b2c3d4-...",
  "total_queries": 3
}
```

**Error responses:**
- `400`: validation error (empty queries, bad timestamps)
- `503`: adapter overloaded / queue full. Include `Retry-After` header.

### Poll: `GET /query-jobs/{job_id}`

**While running:**
```json
{
  "job_id": "...",
  "status": "running",
  "progress": {"total": 300, "completed": 45, "failed": 2}
}
```

**When done:**
```json
{
  "job_id": "...",
  "status": "completed",
  "values": {"query_id_1": 0.45, "query_id_2": 1024000},
  "errors": {"query_id_3": "query returned 0 results"},
  "meta": {
    "total": 3,
    "succeeded": 2,
    "failed": 1,
    "duration_ms": 4500
  }
}
```

- Every query ID appears in exactly one of `values` or `errors`.
- `meta` is informational. Worker counts results itself.

**Statuses:** `queued → running → completed | timed_out | cancelled`

- `completed`: all queries finished (some may have individual errors).
- `timed_out`: job-level timeout hit. Partial results included — completed queries have values, timed-out ones appear in `errors`.
- `cancelled`: worker cancelled via DELETE.

**`404`:** job expired (garbage-collected after adapter's retention period).

### Cancel: `DELETE /query-jobs/{job_id}`

`204 No Content` on success. `404` if not found. `409` if already terminal.

### Health: `GET /health`

Returns `200` if the adapter process is alive and can accept work. Adapter-specific readiness checks (e.g., Prometheus reachable) are internal.

### AdapterClient Protocol (TROPEK side)

The existing `AdapterClient` Protocol (sync `query()` method) is replaced by `AsyncAdapterClient`. During migration, both can coexist — the worker selects based on a config flag (`QG_ADAPTER_ASYNC_ENABLED`, default `true`). Once all adapters implement the async protocol, the sync path is removed.

```python
class AsyncAdapterClient(Protocol):
    async def submit_queries(
        self,
        adapter_url: str,
        datasource_name: str,
        queries: dict[str, str],
        start: str,
        end: str,
        options: QueryOptions | None = None,
    ) -> JobSubmission: ...

    async def poll_job(
        self,
        adapter_url: str,
        job_id: str,
    ) -> JobResult: ...

    async def cancel_job(
        self,
        adapter_url: str,
        job_id: str,
    ) -> None: ...

    async def health(self, adapter_url: str) -> bool: ...
```

### Worker Batch Control

The worker decides how many queries to send per adapter call. For large evaluations (e.g., 300 queries), the worker may split into multiple batches:

- `ADAPTER_BATCH_SIZE` (default: 50) — max queries per adapter job
- `ADAPTER_MAX_CONCURRENT_JOBS` (default: 2) — max adapter jobs in flight simultaneously

For 300 queries with batch_size=50: 6 adapter jobs, 2 running at a time. Worker polls all active jobs, collects results, maps query IDs back to evaluations.

**503 handling:** if an adapter returns `503` with `Retry-After`, the worker respects the delay and re-submits the batch. After 3 consecutive `503` responses, the batch is marked failed and individual queries get `"adapter overloaded"` errors.

**Constraint:** `ADAPTER_BATCH_SIZE` must be ≤ the adapter's `MAX_QUERIES_PER_JOB`, otherwise the adapter rejects every batch with `400`.

---

## 2. Variable Substitution Ownership

**Rule: TROPEK worker performs all variable substitution. Adapters receive only ready-to-execute queries.**

### Merge Priority (highest wins)

```
1. Per-evaluation overrides (request-provided at trigger time)
2. SLO-level variables (SLODefinition.variables)
3. Asset-level variables (Asset.variables)
4. Reserved variables ($asset_name, $evaluation_name, $start, $end)
```

Asset tags are **not** variable sources. Tags are for filtering and grouping only. **Note:** the current worker (`_build_eval_variables`) still merges asset tags into the variable dict — this must be removed as part of the Phase 1 tag/variable split (already planned). This spec assumes Phase 1 is complete.

### Substitution Flow

1. Worker builds merged variable dict per the priority above
2. `variables.substitute(sli_template, variables)` replaces all `$VARIABLE` tokens
3. If any `$VARIABLE` tokens remain unresolved → `UnresolvedVariableError` → indicator fails
4. Substituted queries are assigned opaque IDs and sent to the adapter

No changes to `variables.py` needed. The worker's `_build_eval_variables` needs updating to remove the tag-to-variable merge (Phase 1 prerequisite).

---

## 3. SLO Group Generator

### Concept

An SLO Group is a **creation and maintenance convenience** that generates real SLO definitions from a template. It has **no runtime role** — at evaluation time, generated SLOs are indistinguishable from manually created ones.

### Template SLOs

An SLO template is a regular `SLODefinition` record with a new `kind` column set to `"template"` (new column, default `"standard"`):

- Stored in the same table, same columns, same validation
- Has real objectives, criteria, variables — all normal SLO fields
- Contains generator placeholders in variables and name: `$__gen_process_name`
- Excluded from evaluation (worker filters `kind = "standard"` only)
- Versioned like any SLO

**Placeholder convention:** `$__gen_<variable_name>` prefix distinguishes generator-time placeholders from runtime variables (`$VARIABLE`). The `__gen_` prefix avoids collisions with user-defined variables.

**Example template SLO:**

```
name: "app_x/$__gen_process_name"
kind: "template"
variables: {
  "process_name": "$__gen_process_name",
  "AGGREGATION_WINDOW": "5m"
}
objectives:
  - sli: "cpu_usage"
    pass_criteria: ["<80"]
    warning_criteria: ["<90"]
    weight: 1
    key_sli: true
  - sli: "memory_usage"
    pass_criteria: ["<1073741824"]
    weight: 1
```

### SLO Group Entity

```
SLOGroup
  id: UUID
  name: str                         # "app_x_plugins"
  display_name: str
  template_slo_name: str            # references the template SLO
  template_slo_version: int
  sli_name: str                     # shared SLI definition — used to create AssetSLOLink for each generated SLO
  asset_name: str                   # target asset for auto-linking
  gen_variables: JSONB              # {"__gen_process_name": ["abc", "xyz", ...]} — single key only (validated)
  tags: JSONB
  author: str
  version: int                      # auto-incremented on regeneration
  active: bool
```

### Generation Rules

When a group is created or regenerated:

1. Load the template SLO at `template_slo_name:template_slo_version`
2. For each value in the expansion list (e.g., `["abc", "xyz", ...]`):
   a. Copy the template SLO into a new `SLODefinition` with `kind = "standard"`
   b. Replace all `$__gen_*` tokens in `name` and `variables` with the expansion value
   c. Tag with `{"slo_group": "app_x_plugins", "generated": "true"}`
   d. Create `AssetSLOLink` to the group's target asset, using the group's `sli_name` as the SLI reference
3. Generated SLO `variables` after expansion: `{"process_name": "abc", "AGGREGATION_WINDOW": "5m"}`
4. `gen_variables` is validated to contain exactly one key. Multi-axis expansion (cartesian product) is not supported in this version — use separate groups for separate axes.

**Example — expanding for "abc":**

```
Template:
  name: "app_x/$__gen_process_name"
  variables: {"process_name": "$__gen_process_name", "AGGREGATION_WINDOW": "5m"}

Generated:
  name: "app_x/abc"
  kind: "standard"
  variables: {"process_name": "abc", "AGGREGATION_WINDOW": "5m"}
  tags: {"slo_group": "app_x_plugins", "generated": "true"}
```

At evaluation time, the worker sees a standard SLO with `variables: {"process_name": "abc", "AGGREGATION_WINDOW": "5m"}`. It substitutes into the SLI template `rate(cpu_seconds{plugin='$process_name'}[$AGGREGATION_WINDOW])` → `rate(cpu_seconds{plugin='abc'}[5m])`. No group awareness needed.

### Regeneration

Triggered when the group is edited (template change, values added/removed):

- **Modified SLOs** (template changed): new version of each generated SLO. If criteria changed, set `comparable_from_version` to the new version to prevent cross-version baseline comparison.
- **Added values**: new SLO + asset link created.
- **Removed values**: generated SLO marked `active = false` (soft delete). Evaluation history preserved.
- Group `version` incremented on each regeneration.

### Extraction (Customizing One Plugin)

When a plugin needs custom criteria:

1. Copy the generated SLO into a new standalone `SLODefinition` (new name, e.g., `app_x/abc_custom`)
2. Set `kind = "standard"`, clear `generated` tag
3. Add `forked_from_group: "app_x_plugins"` tag for traceability
4. Remove the value from the group's `gen_variables` list and bump group version (atomic operation — extraction and group update are in the same transaction to prevent concurrent regeneration conflicts)
5. The extracted SLO is fully independent — group regeneration doesn't touch it

The extracted SLO can reuse the same SLI definition (same query templates) but has its own criteria, variables, and evaluation history.

### UI Representation

- SLO Group appears as a collapsible node in the asset's SLO list
- Inside: generated SLOs (read-only, managed by the group)
- Editing a generated SLO redirects to the group editor
- "Customize" action on a single SLO triggers extraction
- Extracted SLOs show a subtle "forked from app_x_plugins" indicator

---

## 4. Prometheus Adapter Implementation

The prometheus adapter implements the async job protocol from Section 1. It cherry-picks the concurrency and execution model from the `prometheus-sli-adapter` spec but skips the Redis state machine — adapter stays stateless (in-memory job tracking is sufficient for single-instance deployment).

### Architecture

```
POST /query → create in-memory job → start asyncio task
                                          |
                                   Fan out queries through Semaphore
                                          |
                                   httpx.AsyncClient with connection pooling
                                          |
                                   Write results to in-memory job dict
                                          |
GET /query-jobs/{id} ← read from in-memory job dict
```

### Key Internals

- **Concurrency:** `asyncio.Semaphore(max_concurrent)` — only N queries hit Prometheus simultaneously
- **Connection pooling:** single `httpx.AsyncClient` per job, reuses connections
- **Prometheus API:** instant query via `GET /api/v1/query?query=<promql>&time=<end>`
- **Result validation:** same as current adapter — single vector element → float, 0 results → error, N>1 → error, NaN/Inf → error
- **Timeout:** per-query timeout from `options.per_query_timeout_seconds`, job-level timeout from adapter config
- **Retry:** 1 retry on TCP connection reset only (PromQL is deterministic)
- **Job retention:** completed jobs garbage-collected after configurable TTL (default 5 minutes)

### What Changes From Current Adapter

| Current (`adapters/prometheus/`) | Evolved |
|---|---|
| Synchronous single-request | Async job model with polling |
| Sequential query execution | Concurrent with semaphore |
| No concurrency control | `max_concurrent` from request + server-side cap |
| No progress reporting | Progress available via poll |
| No cancellation | `DELETE` cancels in-flight queries |
| `query_range` API | `query` (instant) API — TROPEK evaluations always produce a single value per indicator, so instant query at `end` timestamp is correct. No range-based evaluations exist. |

### Scaling Path

Phase 1 (now): single instance, in-memory job state. Sufficient for POC and small deployments.

Phase 2 (later, if needed): Redis-backed job state for horizontal scaling. The async protocol doesn't change — just the storage backend. This is where the full prometheus-sli-adapter spec applies.

---

## 5. Migration Path

This design is additive — no breaking changes to existing components.

### Phase 1: Adapter Protocol
1. Add async job endpoints to prometheus adapter (`POST /query`, `GET/DELETE /query-jobs/{id}`)
2. Implement `HttpAdapterClient` with `submit_queries`, `poll_job`, `cancel_job`
3. Worker uses new client. Old synchronous path can remain as fallback.

### Phase 2: SLO Templates & Groups
4. Add `kind` column to `SLODefinition` (`"standard"` default, `"template"`)
5. Create `SLOGroup` model and repository
6. Build generator logic (template expansion, regeneration, extraction)
7. Wire into SLO registry API

### Phase 3: UI
8. SLO Group CRUD UI (template editor, expansion value list)
9. Group view in asset SLO list (collapsible, read-only generated SLOs)
10. Extract/customize action on individual generated SLOs

Each phase is independently deployable and testable.

---

## 6. Configuration

### New Worker Settings

| Variable | Default | Description |
|---|---|---|
| `QG_ADAPTER_BATCH_SIZE` | `50` | Max queries per adapter job |
| `QG_ADAPTER_MAX_CONCURRENT_JOBS` | `2` | Max adapter jobs in flight per evaluation |
| `QG_ADAPTER_POLL_INTERVAL_SECONDS` | `1` | Polling interval for adapter job status |
| `QG_ADAPTER_JOB_TIMEOUT_SECONDS` | `120` | Max wait time for a single adapter job |

### Prometheus Adapter Settings

| Variable | Default | Description |
|---|---|---|
| `MAX_CONCURRENT_QUERIES` | `10` | Semaphore limit for Prometheus calls |
| `MAX_QUERIES_PER_JOB` | `400` | Reject jobs exceeding this |
| `PER_QUERY_TIMEOUT_SECONDS` | `30` | Per-query HTTP timeout |
| `JOB_RETENTION_SECONDS` | `300` | TTL for completed jobs in memory |
| `PROMETHEUS_DEFAULT_URL` | (none) | Fallback if not provided in datasource config |
