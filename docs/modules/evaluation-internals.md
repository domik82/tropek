# Evaluation Internals

## Purpose

How TROPEK's worker pipeline executes evaluations end to end. For the API consumer
perspective, see [evaluations.md](evaluations.md). For the full lifecycle including
scoring rules and baseline comparison, see
[../architecture/evaluation-lifecycle.md](../architecture/evaluation-lifecycle.md).


## Entity Hierarchy

```
EvaluationRun (table: evaluations)
  |-- 1:N ---> SLOEvaluation (table: slo_evaluations)
                  |-- 1:N ---> IndicatorResultRow (table: indicator_results)
                  |-- 1:N ---> SLIValue (table: sli_values, TimescaleDB hypertable)
```

**EvaluationRun** is the parent row, one per `(asset, eval_name, period)` trigger.
Its `result` is the worst-case of its children; `achieved_points` and `total_points`
are sums across children.

**SLOEvaluation** is one SLO scored against one asset for a given run. Carries the
full execution state: `status` (pending/running/completed/failed/partial),
`result` (pass/warning/fail/error), `score`, `job_stats`, `asset_snapshot`, and
baseline pin/override/invalidation metadata.

**IndicatorResultRow** stores one scored indicator per SLO objective per evaluation.
Columns include `value`, `compared_value`, `change_absolute`, `change_relative_pct`,
`status`, `score`, and `targets`. Linked to `SLOObjective` via FK for display name
and weight lookup.

**SLIValue** is a denormalized TimescaleDB hypertable row for Grafana time-series
queries. Partitioned by `eval_start`. Composite PK: `(slo_evaluation_id, eval_start,
metric_name, aggregation)`. Intentionally has no ORM relationship to SLOEvaluation to
prevent accidental lazy-loading of potentially thousands of rows.


## Worker Pipeline Phases

The worker executes each evaluation as a sequence of micro-transactions. The core
invariant is: **no DB transaction spans an HTTP call**. Each phase opens a fresh
`AsyncSession` via `session_factory()`, does its work, commits, and closes.

Source: `api/tropek/queue.py` function `run_evaluation_job`.

### Phase 1 -- Mark Running + Snapshot

Opens a session, calls `EvaluationRepository.mark_running()` to set status to
`running` with a `started_at` timestamp and worker ID, then loads the full ORM row
and builds an `EvaluationSnapshot`. Commits immediately.

If the evaluation is not found or already processed (status not pending/running),
returns `None` and the job exits.

### Phase 2a -- Load Definitions

Opens a short read session. Loads the versioned `SLODefinition` and `SLIDefinition`
by name+version from the snapshot, plus the `DataSource` by name. Commits and closes.

On any missing definition, marks the evaluation as failed via `_mark_failed` (separate
session) and exits.

### Phase 2b -- HTTP Query + Evaluate

Opens a read session for baseline resolution. Performs:

1. Builds the `SLO` engine model from the SLO definition.
2. Merges variables (priority: reserved < asset.variables < asset.tags < slo.variables
   < eval.variables).
3. For raw-mode SLIs, substitutes variables into indicator query templates. For
   aggregated-mode SLIs, passes the query template and methods to the adapter.
4. Queries the adapter over HTTP via `HttpAdapterClient.query()`.
5. Resolves baselines: fetches up to `comparison.number_of_comparison_results`
   previous completed, non-invalidated evaluations for the same asset+SLO, ordered
   by `period_start DESC`. Aggregates per-metric baseline values using the configured
   aggregate function (avg, p90, etc.).
6. Calls the pure `evaluate()` engine function with metrics, baselines, and compared
   evaluation IDs.

If the adapter call raises a connection/timeout/HTTP error, marks failed and exits.

### Phase 3a -- Write Results

Opens a session. Calls `EvaluationRepository.mark_completed()` with result, score,
achieved/total points, job stats, and compared evaluation IDs. Then bulk-inserts
`IndicatorResultRow` records (one per objective). Commits.

On completion, invalidates the baseline cache key (`baseline:{asset_id}:{slo_name}`)
and deletes the heatmap column cache fragment for the parent run.

### Phase 3b -- Write SLI Values

Opens a **separate session** from 3a. Builds SLI value rows and writes them to the
`sli_values` TimescaleDB hypertable. Commits.

This is deliberately a separate transaction to avoid deadlocks: TimescaleDB takes
`ShareUpdateExclusiveLock` on chunk creation, which conflicts with FK locks from
`mark_completed` on `slo_evaluations`. Splitting the writes eliminates this conflict.

### Finalize Enqueue

After phase 3b, the job enqueues a `finalize_run_job` for the parent run. Each child
enqueues its own finalize attempt. The job intentionally does **not** use a fixed
`_job_id` for deduplication -- arq persists a result key after the first execution,
so if the first finalize runs before all children complete, later children would be
unable to re-enqueue it, leaving the parent run stuck.


## EvaluationSnapshot

`EvaluationSnapshot` is a Pydantic model defined in
`api/tropek/modules/quality_gate/workflows/execution/evaluation_executor.py`. It
carries all data needed for phases 2 and 3 without holding a DB session open:

- `eval_id`, `parent_run_id` -- identity
- `slo_name`, `slo_version`, `sli_name`, `sli_version`, `data_source_name` --
  definition coordinates
- `evaluation_name`, `period_start`, `period_end` -- time window
- `asset_snapshot`, `asset_id` -- frozen asset state at trigger time
- `variables` -- per-run variable overrides

The snapshot exists because the pipeline must release the phase 1 DB session before
making HTTP calls in phase 2. Without it, the session would be held open across the
adapter query, violating the no-transaction-across-HTTP invariant.


## Trigger Flow

Source: `api/tropek/modules/quality_gate/workflows/trigger/trigger_service.py`.

### Single Trigger (`POST /evaluations`)

1. Resolves the asset by name.
2. Finds all SLO assignments for the asset (direct + via asset groups).
3. Creates one `EvaluationRun` (parent) row in pending status.
4. For each assigned SLO, resolves the full trigger context (SLO version, linked SLI,
   datasource) and creates one `SLOEvaluation` (child) row in pending status. SLOs
   that fail resolution (missing SLI, missing datasource) are silently skipped.
5. Commits the entire batch in one transaction.
6. Enqueues one `run_evaluation_job` per child SLOEvaluation ID to the arq queue.

The response returns immediately with the `evaluation_id` (parent run UUID) and the
list of `slo_evaluation_ids`.

### Batch Trigger

Two modes:

- **`by_date`**: one asset, multiple time periods. Calls `trigger_evaluate` once per
  period, producing one `EvaluationRun` per period.
- **`by_asset`**: multiple assets, one time period. Calls `trigger_evaluate` once per
  asset, producing one `EvaluationRun` per asset.

Both modes return the collected run IDs and SLO evaluation IDs.


## Finalization

Source: `api/tropek/queue.py` function `finalize_run_job`, repository method
`EvaluationRunRepository.finalize_if_all_done`.

When a `finalize_run_job` fires, it:

1. Loads all child `SLOEvaluation` rows for the parent run.
2. Checks if any child is still in a non-terminal status (pending, running, partial).
   If so, returns `None` -- the parent is not ready.
3. Computes the worst-case result across children using `RESULT_RANK` ordering.
4. Sums `achieved_points` and `total_points` across children.
5. Updates the parent `EvaluationRun` to `completed` with the aggregated values.

The method is idempotent: multiple finalize jobs for the same run are safe. If the
parent is already completed, subsequent calls are no-ops (all children are terminal,
so the update is a harmless re-write).

After successful finalization, the job warms the heatmap column cache by building a
`HeatmapColumnFragment` from the run and storing it in Redis. This is fire-and-forget:
failures are logged and swallowed. The `has_notes` flag is pinned to `False` because
a freshly completed run has no annotations; the read path overlays notes from a fresh
query at assembly time.


## Sweeper

Source: `api/tropek/queue.py` function `finalize_sweeper_job`, repository method
`EvaluationRunRepository.find_finalizable_pending_ids`.

The sweeper is a periodic reconciler that catches parent runs the fast-path finalize
missed. It runs as an arq cron job at a configurable interval (default: every 30
seconds, must be a divisor of 60).

Each tick:

1. Scans for parent runs whose status is not `completed`, that have at least one
   child, and whose children are all in terminal status. Ordered by `period_end ASC`
   so the oldest stuck runs are rescued first. Limited to a configurable batch size
   (default: 100).
2. For each candidate, calls `finalize_if_all_done` in a fresh session.
3. Logs the number of runs scanned and rescued per tick.

The sweeper is deadlock-safe: it never updates child rows, so it never holds
`FOR KEY SHARE` on the parent. Its parent `UPDATE` takes `FOR NO KEY UPDATE`, which
does not conflict with live child transactions' `FOR KEY SHARE` locks.


## Predecessor Deferral

Source: `api/tropek/queue.py`, constant `_MAX_PREDECESSOR_DEFERS = 60`.

When a batch trigger creates evaluations for multiple time periods of the same
asset+SLO, the baseline for period N depends on the completed result of period N-1.
Without ordering, a later period might execute first and see stale or missing baselines.

The deferral mechanism:

1. Before phase 1, the worker calls `has_pending_predecessor()`, which checks whether
   any `SLOEvaluation` for the same `(asset_id, slo_name)` with an earlier
   `period_start` is still in `pending` or `running` status.
2. If a predecessor exists and `defer_count < 60`, the job re-enqueues itself with
   `_defer_by=timedelta(seconds=2)` and an incremented defer count, then exits.
3. After 60 deferrals (2 minutes of waiting), the evaluation proceeds anyway to avoid
   infinite stalls.
4. If the predecessor check itself fails (DB error), the job proceeds normally to
   avoid blocking on transient issues.


## Performance Design

**Concurrency:** Workers run with `max_jobs` concurrent tasks (default: 10,
configurable via `config.yaml`). The arq pool uses a shared `httpx.AsyncClient` with
connection limits (20 max connections, 10 keepalive) initialized once at worker
startup.

**Deadlock prevention:** Phase 3a (evaluation result + indicator rows) and phase 3b
(SLI hypertable values) use separate transactions. TimescaleDB's chunk-level
`ShareUpdateExclusiveLock` on the `sli_values` hypertable would conflict with FK
locks from `mark_completed` writing to `slo_evaluations` if both happened in the
same transaction.

**Duplicate prevention:** A partial unique index
`uq_slo_evaluations_identity(asset_id, slo_name, evaluation_name, period_start,
period_end) WHERE status != 'failed'` prevents duplicate evaluations. Failed
evaluations are excluded so retries can create fresh rows.

**Stuck job detection:** The `find_stuck()` method on `EvaluationRepository` finds
evaluations in `running` status whose `started_at` exceeds a configurable threshold.
A partial index `idx_slo_evaluations_stuck` on `(status, started_at) WHERE status =
'running'` makes this scan efficient. The sweeper handles stuck parent runs; stuck
children require external watchdog integration.

**Cache invalidation:** Every mutation that changes a run's presented state
(mark_completed, invalidate, restore, override_status, pin/unpin baseline) invalidates
both the baseline cache (`baseline:{asset_id}:{slo_name}`) and the heatmap column
cache fragment for the parent run. Cache operations are fire-and-forget and never
block the primary transaction.

**Adapter timeout:** Configurable via `reliability.adapter_timeout_seconds` (default:
90 seconds). Applied to the shared `httpx.AsyncClient` at worker startup.
