# Evaluation Lifecycle

An **evaluation** measures how well an asset (service, application) meets its Service Level
Objectives over a time window. The client triggers an evaluation via the API, the system
fetches metric values, scores them against SLO criteria, and persists structured results.
This document covers the full lifecycle from trigger to finalization.

## Lifecycle States

```mermaid
stateDiagram-v2
    [*] --> pending: create_pending()
    pending --> running: mark_running()
    running --> completed: mark_completed()
    running --> failed: mark_failed()
    running --> partial: mark_partial() — worker crash
    partial --> pending: watchdog reschedule
```

| Status | Meaning |
|--------|---------|
| **pending** | Enqueued, waiting for a worker |
| **running** | Worker picked it up, fetching metrics or evaluating |
| **completed** | Engine ran, result + score + indicators persisted |
| **failed** | Unrecoverable error (adapter down, invalid SLO, etc.) |
| **partial** | Worker crashed mid-execution; watchdog can reschedule |

## Triggering

### Single evaluation — `POST /evaluations`

Evaluates **one asset** over **one time window**. All SLOs assigned to the asset (directly
or via asset groups) are evaluated.

```json
{
  "asset_name": "my-service",
  "eval_name": "daily",
  "period_start": "2026-04-24T00:00:00Z",
  "period_end": "2026-04-24T23:59:59Z",
  "variables": {"environment": "production"}
}
```

What happens:

1. Resolve all SLO assignments for the asset (direct + group assignments)
2. Create one `EvaluationRun` (parent, status=pending)
3. For each assigned SLO: resolve the SLO/SLI/DataSource chain via `resolve_single_trigger`,
   create one `SLOEvaluation` (child, status=pending) with pinned definition versions and
   a snapshot of the asset state
4. Commit all rows
5. Enqueue one `run_evaluation_job` per SLOEvaluation into the arq Redis queue

### Batch evaluation — `POST /evaluations/batch`

Evaluates **multiple (asset, period) pairs** in one request. Two modes:

- **`by_date`**: one asset, multiple time windows (historical backfill)
- **`by_asset`**: multiple assets, one time window (cross-asset snapshot)

Batch is a convenience wrapper. It loops over the pairs and calls `trigger_evaluate()` for
each one. Each pair produces its own `EvaluationRun`. There is no "batch run" entity.

### Trigger sequence

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API :8080
    participant DB as PostgreSQL
    participant R as Redis (arq)

    C->>A: POST /evaluations
    A->>DB: Resolve SLO assignments
    A->>DB: INSERT EvaluationRun (parent, pending)
    loop For each assigned SLO
        A->>DB: resolve_single_trigger (SLO / SLI / DataSource)
        A->>DB: INSERT SLOEvaluation (child, pending)
    end
    A->>DB: COMMIT
    loop For each SLOEvaluation
        A->>R: enqueue run_evaluation_job(slo_eval_id)
    end
    A-->>C: 201 Created {evaluation_id, slo_evaluation_ids}
```

`resolve_single_trigger` walks the assignment chain: Asset -> SLO Assignment -> SLO
Definition -> SLI Definition -> DataSource. All of this is resolved at trigger time and
pinned into the `SLOEvaluation` row, so the evaluation is reproducible even if definitions
change later.

**Implementation**: `api/tropek/modules/quality_gate/workflows/trigger/trigger_service.py`

## Ingestion Modes

The `ingestion_mode` field on `SLOEvaluation` tracks how metric values are supplied.
Only **pull** is fully implemented today.

### Pull mode (implemented)

The worker queries an adapter (e.g., Prometheus) via HTTP to fetch metric values.

```
Client -> API: POST /evaluations {asset_name, eval_name, period_start, period_end}
Worker -> Adapter: POST /query {queries, start, end, variables}
Adapter -> Prometheus: GET /api/v1/query_range
```

### Push mode (DB-allowed, not yet implemented)

The client provides metric values inline in the request body. The worker skips the adapter
call and uses the provided values directly.

### File mode (DB-allowed, not yet implemented)

The client uploads a CSV or JMeter results file. The worker parses it to extract metric values.

## Scoring

The `evaluate()` function in `api/tropek/modules/quality_gate/evaluation_engine/evaluator.py`
is a **pure function** — no I/O, no database, no network.

**Signature**: `evaluate(slo, metrics, baselines, compared_evaluation_ids) -> EvaluationResult`

```mermaid
flowchart TD
    E[evaluate] -->|for each objective| SO[score_objective]
    SO --> PC[parse criteria strings]
    PC -->|"fixed: &lt;600"| FX[Compare value vs threshold]
    PC -->|"relative: &lt;=+10%"| RL[Compute target from baseline]
    RL --> FX
    SO -->|PASS / WARNING / FAIL / INFO| OR[ObjectiveResult]
    E -->|collect all results| CTS[calculate_total_score]
    CTS -->|sum weighted scores| TS[TotalScore]
    CTS -->|check key SLI veto| TS
    TS -->|"score vs pass% / warning%"| ER[EvaluationResult]
```

### Criteria comparison modes

- **Fixed threshold**: `<600`, `>=99.9` — compare against a literal value
- **Relative percent**: `<=+10%` — compare against baseline with a percentage tolerance
- **Relative absolute**: `<=+50` — compare against baseline with an absolute tolerance

### Scoring rules

- **Within a criteria block**: AND logic — all criteria must pass for the block to pass
- **Across blocks**: OR logic — any block passing counts as pass
- **Key SLI**: if a key SLI fails, the entire evaluation fails regardless of total score
- **INFO status**: objectives with no pass criteria are informational — they don't affect score
- **Scoring**: pass = full weight, warning = 0.5 x weight, fail = 0

## Baseline Comparison

Relative criteria (e.g. `<=+10%`) compare the current value against a baseline derived
from previous evaluations:

1. Worker loads the last N completed evaluations for the same (asset, SLO)
2. Baselines are filtered by result score: all results, pass+warning only, or pass only
3. Values are aggregated using the configured function (avg, p50, p90, p95, p99)
4. If `scope_tags` is set, baselines are further filtered to matching asset tags
5. If no baselines exist, relative criteria **always pass** (no penalty for first run)

## Entity Hierarchy

```mermaid
erDiagram
    EvaluationRun ||--o{ SLOEvaluation : "has N children"
    SLOEvaluation ||--o{ IndicatorResultRow : "has N indicator results"
    SLOEvaluation ||--o{ EvaluationAnnotation : "has notes"
    EvaluationRun ||--o{ EvaluationAnnotation : "has column-level notes"
    SLOEvaluation }o--|| SLIValue : "writes to hypertable"

    EvaluationRun {
        uuid id PK
        uuid asset_id FK
        string eval_name
        datetime period_start
        datetime period_end
        string status "pending / running / completed / failed"
        string result "pass / warning / fail / error (worst-case of children)"
        int achieved_points "sum of children"
        int total_points "sum of children"
    }

    SLOEvaluation {
        uuid id PK
        uuid evaluation_id FK "to EvaluationRun"
        uuid asset_id FK
        string slo_name
        int slo_version
        string sli_name
        int sli_version
        string data_source_name
        datetime period_start
        datetime period_end
        string status "pending / running / completed / failed / partial"
        string result "pass / warning / fail / error"
        float score "0.0 to 100.0"
        jsonb asset_snapshot "denormalized asset state at trigger time"
        jsonb variables "merged variables for query substitution"
        string ingestion_mode "pull / push / file"
        bool invalidated "excluded from baselines if true"
    }

    IndicatorResultRow {
        uuid id PK
        uuid slo_evaluation_id FK
        uuid slo_objective_id FK
        float value "measured metric value"
        float compared_value "baseline value"
        string status "pass / warning / fail / error"
        float score "0 or weight"
        jsonb targets "resolved pass and warning criteria"
    }

    SLIValue {
        uuid slo_evaluation_id PK
        datetime eval_start PK
        string metric_name PK
        string aggregation PK
        float value
        string asset_name "denormalized"
        string evaluation_name "denormalized"
    }
```

### What each entity does

**EvaluationRun** (`evaluations` table) — the parent container for one evaluation cycle.
When you POST to `/evaluations`, one EvaluationRun is created for the target asset. Once all
children finish, it is finalized: result = worst-case across children, points = sum of children.
Think of it as the **roll-up row for the heatmap column** in the UI.

**SLOEvaluation** (`slo_evaluations` table) — the individual SLO result. One is created for
every SLO assigned to the asset. This is where the actual evaluation happens. The
`asset_snapshot` preserves the asset's name, tags, and variables at trigger time so results
remain interpretable even if the asset config changes later.

**IndicatorResultRow** (`indicator_results` table) — the per-metric breakdown within one
SLOEvaluation. One row per SLO objective, containing the measured value, baseline comparison,
and which criteria targets passed or failed.

**SLIValue** (`sli_values` hypertable) — TimescaleDB hypertable for trend charts and Grafana
dashboards. Intentionally denormalized to avoid joins in time-series queries. Written in a
**separate transaction** (Phase 3b) from the main results to avoid deadlocks.

## Worker Pipeline

Each `run_evaluation_job` processes one SLOEvaluation through multiple phases with **separate
database sessions**. The core invariant: **no DB transaction may span an HTTP call or hold
locks longer than ~15ms**.

```mermaid
graph LR
    subgraph "run_evaluation_job (arq job)"
        direction LR
        P1["<b>Session 1 — Phase 1</b><br/>~5ms<br/><br/>mark_running<br/>snapshot<br/><br/><i>COMMIT</i>"]
        P2a["<b>Session 2 — Phase 2a</b><br/>~10ms<br/><br/>load SLO def<br/>load SLI def<br/>load datasrc<br/><i>COMMIT</i>"]
        HTTP["<b>No DB — HTTP I/O</b><br/>1-10s<br/><br/>query adapter"]
        P2b["<b>Session 3 — Phase 2b</b><br/>~10ms<br/><br/>resolve baselines<br/><br/><i>COMMIT</i>"]
        P3a["<b>Session 4 — Phase 3a</b><br/>~10ms<br/><br/>mark_completed<br/>INSERT indicators<br/><i>COMMIT</i>"]
        P3b["<b>Session 5 — Phase 3b</b><br/>~10ms<br/><br/>INSERT sli_values<br/><br/><i>COMMIT</i>"]

        P1 --> P2a --> HTTP --> P2b --> P3a --> P3b
    end

    style HTTP fill:#2d333b,stroke:#f85149,stroke-width:2px
```

> **Snapshot (Pydantic model)** is captured in Phase 1 and carried across all subsequent
> phases as detached data — no SQLAlchemy objects cross session boundaries.

### Phase 1 — Mark running + snapshot

Opens a DB session, marks the `SLOEvaluation` as running, and copies all needed fields into
an `EvaluationSnapshot` (Pydantic model). Commits and closes the session (~5ms). No
SQLAlchemy objects are carried past this point.

### Phase 2a — Load definitions

Opens a fresh session, loads `SLODefinition`, `SLIDefinition`, and `DataSource` by the
pinned name+version from the snapshot. Read-only, ~10ms.

### HTTP adapter query (no DB session)

The adapter HTTP call (1-10 seconds) happens with **no open DB session and no locks held**.
Uses a shared `httpx.AsyncClient` per worker process for connection pooling.

### Phase 2b — Resolve baselines + evaluate

Opens a fresh session for read-only baseline queries, then calls `evaluate()` (pure
function). Produces a `FetchAndEvaluateResult` containing metrics, baselines, and the
scored result. ~10ms.

### Phase 3a — Write evaluation result + indicator rows

Opens a session for writes:
1. `UPDATE slo_evaluations SET status='completed', result=..., score=...`
2. `INSERT INTO indicator_results` — one row per SLI indicator (~8 rows)

Locks held: row exclusive on this `slo_evaluations` row, shared FK lock on the parent
`evaluations` row. Duration: ~10ms.

### Phase 3b — Write SLI values to hypertable

Opens a **separate session** for `INSERT INTO sli_values` (~8 rows). This split is critical
for deadlock prevention (see Performance Design below).

**Implementation**: `api/tropek/modules/quality_gate/workflows/execution/evaluation_executor.py`

## EvaluationSnapshot

The `EvaluationSnapshot` is **not a database entity** — it is a Pydantic model that bridges
execution phases. It carries `eval_id`, `parent_run_id`, `slo_name`, `sli_name`,
`period_start/end`, `asset_snapshot`, `variables`, and everything else needed to execute
phases 2 and 3 without going back to the database for the `SLOEvaluation` row.

This pattern exists because the worker uses **separate DB sessions** for each phase. Without
the snapshot, each phase would need to re-load the evaluation row. With it, the DB session
is opened only for the specific operation each phase needs.

Similarly, `FetchAndEvaluateResult` carries the adapter response and scored result from
Phase 2b into Phase 3 without a DB session.

## Finalization

Each child `SLOEvaluation` enqueues a `finalize_run_job` for its parent `EvaluationRun`.
The job is **idempotent** — multiple children can enqueue it safely, and only the execution
that finds all children in a terminal status actually updates the parent.

Finalization aggregates the parent run:
- **result** = worst-case across all children (pass < warning < fail < error)
- **achieved_points** = sum of all children's achieved points
- **total_points** = sum of all children's total points
- Updates the parent `EvaluationRun` status to `completed`
- Warms the heatmap column cache (fire-and-forget)

A **finalize sweeper** cron job runs periodically to catch any parent runs that the
fast-path missed (e.g., if a child's finalize enqueue was lost due to a Redis hiccup).

## Predecessor Deferral

When multiple evaluations for the same (asset, SLO) are enqueued close together (e.g.,
from a batch request), they must execute **in chronological order** to ensure baselines
are computed correctly.

Before Phase 1, the job checks if an earlier evaluation (by `period_start`) for the same
asset+SLO is still `pending` or `running`. If so, the current job is **deferred** by 2
seconds and re-enqueued. Maximum 60 retries (2 minutes) before giving up.

This ensures baseline comparisons always reference fully completed prior evaluations.

## Performance Design

### Scale reference

| Dimension | Count |
|-----------|-------|
| Assets per batch | 12 |
| SLOs per asset | 20 |
| SLIs (indicators) per SLO | 8 |
| SLOEvaluation jobs per batch | 240 |
| Indicator result rows per batch | 1,920 |
| SLI value rows per batch | 1,920 |
| arq worker replicas | 4 |
| `max_jobs` per worker | 10 |
| Effective concurrency | 40 |

### FK relationships and lock interactions

```mermaid
erDiagram
    evaluations ||--o{ slo_evaluations : "evaluation_id"
    slo_evaluations ||--o{ indicator_results : "slo_evaluation_id"
    slo_evaluations ||--o{ sli_values : "slo_evaluation_id"

    evaluations {
        uuid id PK
        string note "EvaluationRun — parent"
    }
    slo_evaluations {
        uuid id PK
        uuid evaluation_id FK
        string note "SLOEvaluation — one per asset+SLO"
    }
    indicator_results {
        uuid id PK
        uuid slo_evaluation_id FK
    }
    sli_values {
        uuid slo_evaluation_id PK
        timestamptz eval_start PK
        string note "TimescaleDB hypertable"
    }
```

Key lock interactions:
- `UPDATE slo_evaluations` takes a **row exclusive lock** on that row
- `INSERT INTO indicator_results` takes a **shared FK lock** on the parent `slo_evaluations` row
- `INSERT INTO sli_values` takes a **shared FK lock** on `slo_evaluations` AND a
  **ShareUpdateExclusiveLock** on the TimescaleDB time chunk (self-conflicting)

### Why Phase 3 is split into 3a and 3b

The deadlock that required the split:

```
Worker A (Phase 3, combined):
  UPDATE slo_evaluations SET status='completed'   -> row exclusive lock on eval row A
  INSERT INTO sli_values (slo_evaluation_id=A)     -> needs chunk lock, WAITS

Worker B (Phase 3, combined):
  UPDATE slo_evaluations SET status='completed'   -> row exclusive lock on eval row B
  INSERT INTO sli_values (slo_evaluation_id=B)     -> holds chunk lock (same time chunk),
                                                      needs FK shared lock on eval row B (OK),
                                                      but chunk lock conflicts -> DEADLOCK CYCLE
```

The problem: `UPDATE slo_evaluations` (row exclusive) + `INSERT sli_values` (chunk lock +
FK shared lock) in the **same transaction** creates a lock ordering conflict when multiple
workers target the same TimescaleDB time chunk.

The fix: separate them into two transactions so **row exclusive locks and chunk locks are
never held simultaneously**. In Phase 3a, `mark_completed` holds a row exclusive lock but
no chunk lock. In Phase 3b, `INSERT sli_values` holds a chunk lock and a shared FK lock
(not exclusive). Shared FK locks don't conflict with each other, so concurrent Phase 3b
transactions can queue for the chunk lock without deadlocking.

### Consistency guarantee

Phase 3a commits before Phase 3b starts. If Phase 3b fails (process crash, timeout),
the evaluation is marked `completed` with indicator results but missing `sli_values` rows.
This is acceptable because `sli_values` is a denormalized analytics table — the
authoritative result lives in `slo_evaluations.result` + `indicator_results`.

### Error handling

All failure paths use `_mark_failed()` — a helper that opens its own session, marks the
evaluation as failed with error details in `job_stats`, and commits independently.

Failure points:
- **Phase 1**: eval not found or already processed -> early return, no mark_failed
- **Phase 2a**: definition not found -> `_mark_failed` + return
- **HTTP adapter**: connect/timeout/status error -> `fetch_and_evaluate` returns `None` -> `_mark_failed`
- **Phase 3a/3b**: expected to succeed (data already validated); arq retry handles unexpected DB errors

## Post-Evaluation Operations

After completion, evaluations support:

- **Annotations**: contextual notes (e.g., "kernel updated before this test")
- **Invalidation**: mark as invalid without deleting — excluded from baselines, preserves audit trail
- **Baseline pinning**: declare a specific evaluation as the known-good baseline
- **Result override**: manually change the result with an audit trail (original result preserved)
- **Re-evaluation**: re-run from a specific date or from baseline, with delta annotations
- **Trend queries**: time-series data from the `sli_values` hypertable

## Key Files

| File | Role |
|------|------|
| `api/tropek/modules/quality_gate/workflows/trigger/trigger_service.py` | `TriggerService` — single and batch trigger orchestration |
| `api/tropek/modules/quality_gate/workflows/trigger/trigger_resolver.py` | `resolve_single_trigger` — SLO/SLI/DataSource chain resolution |
| `api/tropek/modules/quality_gate/workflows/execution/evaluation_executor.py` | Phase functions: `load_evaluation_snapshot`, `fetch_and_evaluate`, `write_results`, `write_sli_values_phase` |
| `api/tropek/modules/quality_gate/evaluation_engine/evaluator.py` | Pure `evaluate()` function — scoring logic |
| `api/tropek/modules/quality_gate/repositories/evaluation.py` | `EvaluationRepository` — `mark_running`, `mark_completed`, `create_pending` |
| `api/tropek/modules/quality_gate/repositories/baseline.py` | `BaselineRepository` — historical baseline queries |
| `api/tropek/db/models.py` | ORM: `SLOEvaluation`, `EvaluationRun`, `SLIValue`, `IndicatorResultRow` |
| `config.yaml` | `queue.max_jobs`, `reliability.adapter_timeout_seconds` |
