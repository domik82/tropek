# Evaluation Workflows

The quality gate module organizes evaluation logic into four workflow packages
under `api/tropek/modules/quality_gate/workflows/`:

```
workflows/
  trigger/         -- resolve assignments, create pending evals, enqueue jobs
  execution/       -- 3-phase worker job: snapshot, fetch+evaluate, write
  re_evaluation/   -- re-score historical evals against new SLO versions
  presentation/    -- ORM-to-schema transforms, heatmap cache, target resolution
```

For the pure scoring engine, see [`docs/modules/evaluation-internals.md`](../../docs/modules/evaluation-internals.md).
For repository internals, see [repositories.md](repositories.md).

## Shared Infrastructure

Source: `api/tropek/modules/quality_gate/shared/`.

### Repository Bundle (`QualityGateRepos`)

`dependencies.py` defines a `dataclass` bundling all 14 repositories needed by
quality gate endpoints, plus the raw `AsyncSession`, optional `RedisCache`, and
optional `HeatmapColumnCache`. Every endpoint receives one via `Depends(get_qg_repos)`.

**Fields**: `eval_repo`, `eval_run_repo`, `annotation_repo`, `category_repo`,
`sli_repo`, `trend_repo`, `baseline_repo`, `asset_repo`, `asset_group_repo`,
`assignment_repo`, `sli_def_repo`, `slo_repo`, `ds_repo`, `session`, `cache`,
`heatmap_cache`.

### Protocol Types

`protocols.py` defines five `Protocol` interfaces for read-only repository access,
used by the trigger resolver to decouple from concrete implementations:

| Protocol | Key Methods |
|----------|------------|
| `AssetReader` | `get_by_name(name)` |
| `SLIReader` | `get_latest(name)`, `get_version(name, version)`, `get_by_id(id)` |
| `SLOReader` | `get_latest(name)`, `get_version(name, version)`, `get_by_id(id)` |
| `AssignmentReader` | `resolve_for_asset(asset_id, group_ids)`, `find_for_asset(...)` |
| `DataSourceReader` | `get_by_id(id)` |

The execution and re-evaluation layers construct repositories directly -- protocols
are only used by the trigger resolver.

### Domain Exceptions

| Exception | Parent | HTTP Status | Purpose |
|-----------|--------|-------------|---------|
| `EvaluationError` | `DomainValidationError` | 422 | Precondition not met (e.g., no SLO assignments) |
| `SLONotConfiguredError` | `DomainValidationError` | 422 | No SLO linked to an asset |
| `BaselinePinConflictError` | `Exception` | 409 | Re-evaluation start date before active baseline pin |

### `EvalCreateParams`

`params.py` defines a `StrictInput` model carrying all fields needed to create a
pending `SLOEvaluation` row. Passed from `TriggerService` to
`EvaluationRepository.create_pending()`.

## Trigger Workflow

Source: `workflows/trigger/trigger_resolver.py`, `trigger_service.py`.

### Resolution Chain

`resolve_single_trigger(asset_name, slo_name)` resolves a single evaluation target:

1. Look up asset by name
2. Find winning assignment via `AssignmentReader.find_for_asset()`
3. Load the SLO definition from the assignment
4. Load the SLI definition via SLO's FK
5. Load the datasource from the assignment

Returns a `TriggerContext` dataclass with all resolved references.

`resolve_all_slos_for_asset()` returns sorted SLO names assigned to an asset
(direct + via groups).

### TriggerService

`trigger_evaluate(request)`:

1. Resolves the asset
2. Lists group IDs for the asset
3. Finds all assigned SLOs
4. Creates a parent `EvaluationRun`
5. For each SLO: resolves context, creates pending `SLOEvaluation`
6. Commits the transaction
7. Enqueues one `run_evaluation_job` per SLO evaluation ID

Resolution failures for individual SLOs are silently skipped (`except EvaluationError: continue`).

`trigger_evaluate_batch(request)` supports two modes:
- `by_date`: one asset, many time periods
- `by_asset`: many assets, one time period

## Execution Workflow (Worker)

Source: `workflows/execution/evaluation_executor.py`, `evaluation_helpers.py`, `adapter_client.py`.
Queue integration: `api/tropek/queue.py`.

### Three-Phase Execution Model

The worker splits evaluation into three phases to manage transaction boundaries:

**Phase 1: `load_evaluation_snapshot()`**
- Marks evaluation as `running`
- Loads ORM row, builds detached `EvaluationSnapshot`
- Deduplication guard: skips if not pending/running
- Caller commits

**Phase 2: `fetch_and_evaluate()`** (no DB session)
- Builds SLO model via `build_slo_model(slo_def)`
- Merges variables from reserved, asset, SLO, and eval layers
- Substitutes variables into indicator query templates (raw mode)
- Calls `adapter_client.query()` for SLI values
- Overrides errored metrics to `None`
- Resolves baselines via `baseline_repo`
- Calls the pure engine `evaluate(slo, metrics, baselines, compared_ids)`

**Phase 3a: `write_results()`**
- Marks completed with result, score, job stats
- Writes normalized indicator rows
- Caller commits

**Phase 3b: `write_sli_values_phase()`**
- Separate transaction to avoid TimescaleDB chunk lock deadlocks
- Writes SLI value rows to the hypertable
- Caller commits separately

A failure in 3b leaves the evaluation marked as completed with indicator rows
but without SLI values -- a partial success state.

### Variable Merge Priority

`build_eval_variables()` merges from lowest to highest priority:

1. Reserved vars (`TROPEK_ASSET`, `TROPEK_EVALUATION`, engine-built vars)
2. `asset.variables`
3. `asset.tags`
4. `slo.variables`
5. `eval.variables` (user-provided at trigger time)

### Predecessor Deferral

`_has_pending_predecessor()` checks for earlier pending/running evaluations for the
same asset+SLO. If found, the job re-enqueues with 2s delay (max 60 defers = 2-minute
window). This prevents out-of-order baseline comparisons.

### Run Finalization

Two paths ensure parent runs are finalized:

1. **Fast path**: each child enqueues `finalize_run_job` after completion.
   `finalize_if_all_done()` aggregates worst-case result across children.
2. **Sweeper**: `finalize_sweeper_job` cron scans for stuck parent runs whose
   children are all terminal but parent is still pending/running.

## Adapter Client

Source: `workflows/execution/adapter_client.py`.

`HttpAdapterClient` queries TROPEK-compatible metric adapters:

- `query()` -- POSTs to `{adapter_url}/query` with `{queries, variables, start, end}`
- Sends `X-Datasource-Name` header
- Returns `(metrics_fetched, fetch_errors, metadata)`
- Supports injected `httpx.AsyncClient` or ephemeral client

Two query modes:

| Mode | Description |
|------|-------------|
| **Raw** | Each indicator has its own query template, variable-substituted locally |
| **Aggregated** | Single query template with interval/methods config, delegated to adapter |

Adapter protocol specification: [`docs/guides/adapter-protocol.md`](../../docs/guides/adapter-protocol.md)

## Re-evaluation Workflow

Source: `workflows/re_evaluation/re_evaluation_service.py`.

Re-evaluation does **not** re-fetch metrics from adapters. It re-scores using stored
indicator values against a (possibly new) SLO definition.

### Entry Points

Three bridge functions convert split request schemas into the internal `ReEvaluateRequest`:

| Endpoint | Bridge |
|----------|--------|
| `POST /evaluations/re-evaluate/from-date` | `re_evaluate_from_date()` |
| `POST /evaluations/re-evaluate/from-baseline` | `re_evaluate_from_baseline()` |
| `POST /evaluations/re-evaluate/from-evaluation/{id}` | `re_evaluate_from_evaluation()` |

### Core Flow

`re_evaluate()`:
1. Resolves the asset
2. Determines SLO list (explicit, single, or all assigned)
3. Creates a note group for the action
4. For each SLO, calls `_re_evaluate_single_slo()`

`_re_evaluate_single_slo()`:
1. Loads SLO definition (specified version or latest)
2. Determines window start
3. Checks for baseline pin conflict
4. Loads evaluations to re-process in chronological order
5. Seeds eligible IDs from pre-window baselines
6. Iterates evaluations, re-scoring each and appending its ID to `eligible_ids`

### Cascading Baselines

Each processed evaluation's ID is appended to `eligible_ids`, so later evaluations
can use earlier re-evaluated ones as baselines. This preserves causal ordering.

### Baseline Pin Conflict Resolution

When `from_date` falls before an active baseline pin:

| Strategy | Effect |
|----------|--------|
| (none) | Raises `BaselinePinConflictError` (HTTP 409 with pin details) |
| `skip_to_pin` | Adjusts `from_date` forward to the pin date |
| `ignore_pin` | Proceeds with original `from_date`, bypasses pin filtering |

### Result Persistence

`_persist_reeval_result()`:
- Updates row with new result/score
- Preserves `original_result`/`original_score` on first re-eval
- Invalidates baseline and heatmap column caches
- Adds automatic re-evaluation annotation
- Replaces indicator rows with freshly computed ones

## Presentation Workflow

Source: `workflows/presentation/presenter.py`, `heatmap_cache.py`, `target_resolver.py`.

### Presenter Functions

| Function | Purpose |
|----------|---------|
| `build_summary(ev, annotation_count, latest_ann)` | Creates `EvaluationSummary` from ORM row |
| `build_detail(ev)` | Creates `EvaluationDetail` with full indicator results |
| `build_column_fragment(run, has_notes)` | Core heatmap builder for a single `EvaluationRun` |
| `assemble_grouped_response(asset_name, fragments)` | Merges per-run fragments into full heatmap response |
| `worst_result(results)` | Returns worst result using `RESULT_RANK` ordering |

### Heatmap Column Cache

`HeatmapColumnCache` (`heatmap_cache.py`) provides per-column Redis caching for the
grouped heatmap endpoint.

**Key format**: `heatmap:col:v{SCHEMA_VERSION}:{run_id}` (schema version = 1, TTL = 7 days)

| Method | Pattern |
|--------|---------|
| `get_many(run_ids)` | MGET batch read, silently omits misses and corrupt payloads |
| `set_many(fragments)` | Pipeline batch write |
| `delete(run_id)` | Single key deletion |
| `delete_many(run_ids)` | Batch deletion |

All operations are fail-safe: Redis errors are caught and logged as warnings.
The cache is opportunistic -- never blocks reads or writes.

Schema version bump causes old entries to become orphans that fall out on TTL.

### Grouped Heatmap Read Path

The router implements a cache-aside pattern:

1. List candidate runs from DB (lightweight, no joins)
2. Batch-fetch cached fragments via `column_cache.get_many()`
3. For misses: load from DB, build fragments, cache them
4. Overlay `has_notes` from fresh DB query (not cached -- always current)
5. Sort by `(period_start, eval_name)`, assemble response

The `cache` query parameter (default `True`) allows bypassing Redis for debugging.

### Heatmap Cache Warming

`warm_heatmap_column_cache()` is called from `finalize_run_job` after a run
transitions to completed. Builds and caches a `HeatmapColumnFragment` so the next
reader pays zero rebuild cost. Fire-and-forget: failures are logged and swallowed.

### Target Resolver

`resolve_targets(criteria, value, compared_value)` computes pass/warning target
values from raw criteria strings. Used by the presenter for indicator result display.

`resolve_targets_from_parsed()` is the hot-path variant accepting pre-parsed criteria,
used by `build_column_fragment()` where criteria are parsed once per objective.
