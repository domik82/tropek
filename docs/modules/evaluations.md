# Evaluations

## Purpose

Evaluations are TROPEK's core output -- the result of measuring an asset's SLI values
against SLO criteria. This document explains how to trigger evaluations, read results,
and use post-evaluation features like annotations, baseline pinning, and re-evaluation.

For how the pure scoring engine works (criteria parsing, per-objective scoring, total
score calculation), see [evaluation-internals.md](evaluation-internals.md). For the
end-to-end lifecycle with state diagrams, worker phase details, and deadlock-avoidance
design, see [evaluation-lifecycle.md](../architecture/evaluation-lifecycle.md).

## Key Concepts

| Concept | What It Is |
|---------|------------|
| **Evaluation Run** | A parent record created when you trigger an evaluation. One run fans out to one SLO Evaluation per bound SLO definition. Identified by `evaluation_id` (UUID). |
| **SLO Evaluation** | A child record under a run, holding the score and result for one SLO definition version. The `id` field in list/detail responses refers to this child. |
| **Result** | The outcome of a single SLO evaluation: `pass`, `warning`, or `fail`. Can be overridden manually or set to `invalidated`. |
| **Score** | A 0--100 numeric value computed from weighted indicator scores against pass/warning thresholds defined in the SLO. |
| **Key SLI** | An indicator flagged `key_sli: true` in the SLO. Failing a key SLI forces the overall result to `fail` regardless of score. |
| **Heatmap** | A grid visualization of evaluation results over time. Two variants: grouped (by SLO with per-indicator cells) and flat (metric x time slot). |
| **Baseline Pin** | Marks a specific evaluation as the reference point for relative comparisons (`<=+10%`). Only one pin is active per asset+SLO at a time. |
| **Invalidation** | Marks an evaluation as excluded from baseline calculations and trend analysis. Reversible via restore. |

## Triggering Evaluations

### Single evaluation

```
POST /evaluations
```

Triggers evaluation for all SLO definitions bound to an asset. The API resolves
bindings, creates an `EvaluationRun`, and enqueues a worker job per bound SLO.

**Request body** (`EvaluateSingleRequest`):
```json
{
  "asset_name": "web-server-01",
  "eval_name": "nightly-2026-04-30",
  "period_start": "2026-04-30T00:00:00Z",
  "period_end": "2026-04-30T06:00:00Z",
  "variables": {"env": "prod"}
}
```

- `eval_name` is a human-readable label that groups evaluation runs (e.g., by date or release).
- `variables` are substituted into SLI query templates (e.g., `$env` in a PromQL query).

**Response** (201):
```json
{
  "evaluation_id": "uuid-of-the-run",
  "slo_evaluation_ids": ["uuid-per-bound-slo", "..."]
}
```

### Batch evaluation

```
POST /evaluations/batch
```

Two modes for bulk triggering:

**`by_date`** -- same asset, multiple time windows:
```json
{
  "mode": "by_date",
  "asset_name": "web-server-01",
  "eval_name": "backfill",
  "periods": [
    {"period_start": "2026-04-28T00:00:00Z", "period_end": "2026-04-28T06:00:00Z"},
    {"period_start": "2026-04-29T00:00:00Z", "period_end": "2026-04-29T06:00:00Z"}
  ]
}
```

**`by_asset`** -- same time window, multiple assets:
```json
{
  "mode": "by_asset",
  "asset_names": ["web-server-01", "web-server-02"],
  "eval_name": "release-v3.2",
  "period_start": "2026-04-30T00:00:00Z",
  "period_end": "2026-04-30T06:00:00Z"
}
```

**Response** (201):
```json
{
  "evaluation_ids": ["run-uuid-1", "run-uuid-2"],
  "slo_evaluation_ids": ["slo-eval-uuid-1", "..."]
}
```

Batch is a convenience wrapper -- each `(asset, period)` pair produces its own
`EvaluationRun`. There is no "batch run" entity.

### What happens on trigger

1. `TriggerService.trigger_evaluate()` resolves the asset by name
2. Finds all SLO assignments (direct + via asset groups) with `resolve_all_slos_for_asset()`
3. Creates a parent `EvaluationRun` (status=pending)
4. For each assigned SLO: resolves the full definition chain via `resolve_single_trigger()`
   (Asset -> Assignment -> SLO Definition -> SLI Definition -> DataSource), then creates
   a pending `SLOEvaluation` with pinned definition versions and an asset snapshot
5. Commits all rows
6. Enqueues one `run_evaluation_job` arq job per SLO evaluation ID

SLOs that fail to resolve (e.g., missing datasource) are silently skipped -- a partially
resolvable asset still triggers evaluations for the SLOs that do resolve.

**Source**: `workflows/trigger/trigger_service.py` (`TriggerService`),
`workflows/trigger/trigger_resolver.py` (`resolve_single_trigger`, `resolve_all_slos_for_asset`)

### Trigger resolution chain

The `resolve_single_trigger()` function walks the assignment chain for a single
`(asset_name, slo_name)` pair and returns a `TriggerContext` with all resolved
references:

```
Asset (by name)
  -> SLO Assignment (via AssignmentReader.find_for_asset)
    -> SLO Definition (by assignment's slo_definition_id)
      -> SLI Definition (by SLO's sli_definition_id)
    -> DataSource (by assignment's data_source_id)
```

The resolver uses protocol-typed parameters (`AssetReader`, `SLOReader`, `SLIReader`,
`AssignmentReader`, `DataSourceReader`) defined in `shared/protocols.py`, keeping it
testable with any object satisfying the protocol contract.

## Execution (Worker Pipeline)

Each `run_evaluation_job` processes one SLO evaluation through a three-phase pipeline
with separate database sessions. The details of each phase (snapshot, fetch+evaluate,
write results, write SLI values) and the TimescaleDB deadlock-avoidance design are
covered in [evaluation-lifecycle.md](../architecture/evaluation-lifecycle.md).

### Adapter client

The `HttpAdapterClient` queries TROPEK-compatible metric adapters over HTTP.

**Query**: POSTs to `{adapter_url}/query` with:
```json
{
  "queries": {"response_time": {"mode": "raw", "query": "avg(http_duration{...})"}},
  "variables": {"env": "prod"},
  "start": "2026-04-30T00:00:00Z",
  "end": "2026-04-30T06:00:00Z"
}
```

Sends an `X-Datasource-Name` header. Returns an `AdapterQueryResponse` with three dicts:
- `values`: metric name to numeric value (or `null` if the query returned no data)
- `errors`: metric name to error message (metrics with errors are overridden to `null`)
- `metadata`: metric name to adapter-specific metadata (sample counts, chunks, etc.)

**Health check**: GETs `{adapter_url}/health`, returns `True`/`False`.

The client supports two query modes:
- **Raw**: each indicator has its own query string, variable-substituted locally before
  sending. Sent as `{mode: "raw", query: "resolved_query_string"}`.
- **Aggregated**: a single query template with interval and methods config, variable
  substitution delegated to the adapter. Sent as
  `{mode: "aggregated", query_template: "...", interval: "...", methods: [...]}`.

On adapter failure (`ConnectError`, `TimeoutException`, `HTTPStatusError`), the evaluation
is marked as failed.

**Source**: `workflows/execution/adapter_client.py` (`HttpAdapterClient`, `AdapterQueryResponse`)

### Variable merging

SLI queries can contain `$variable` tokens. Variables are merged from multiple sources
with increasing priority (highest wins):

1. Reserved built-ins: `$TROPEK_ASSET`, `$TROPEK_EVALUATION`, plus engine-built vars
   (`$asset_name`, `$evaluation_name`, `$start`, `$end`)
2. `asset.tags` (via `setdefault` -- won't overwrite reserved)
3. `asset.variables` (via `setdefault` -- won't overwrite reserved or tags)
4. `slo.variables` (direct assignment -- overwrites everything below)
5. `eval.variables` (direct assignment -- highest priority)

**Source**: `workflows/execution/evaluation_helpers.py` (`build_eval_variables`)

### Heatmap cache warming

After a run transitions to `completed`, the `finalize_run_job` calls
`warm_heatmap_column_cache()`. This builds a `HeatmapColumnFragment` from the completed
run and stores it in Redis so the next heatmap reader pays zero rebuild cost.

Cache warming is fire-and-forget: any failure is logged and swallowed. The `has_notes`
field is pinned to `False` because a fresh run has no annotations -- the router overlays
notes at assembly time from a fresh DB query.

**Source**: `workflows/execution/evaluation_executor.py` (`warm_heatmap_column_cache`)

## Reading Results

### List evaluations

```
GET /evaluations
```

Returns a paginated list of SLO evaluations with optional filters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `asset_name` | string | Filter by asset name |
| `slo_name` | string | Filter by SLO definition name |
| `evaluation_name` | string[] | Filter by one or more evaluation names |
| `result` | string | Filter by result (`pass`, `warning`, `fail`) |
| `date` | string | Date prefix filter (e.g., `2026-04`) |
| `group_name` | string | Filter by asset group name |
| `from` | datetime | Start of time range (mutually exclusive with `date`) |
| `to` | datetime | End of time range |
| `limit` | int | Page size (default 200, max 500) |
| `offset` | int | Pagination offset |

**Response**: `PagedResponse[EvaluationSummary]` with `items` and `total` fields.

Each `EvaluationSummary` includes the evaluation result, score, period, asset snapshot,
annotation count, top failures, and baseline/override metadata.

### Evaluation detail

```
GET /evaluation/{eval_id}
```

Returns full detail for a single SLO evaluation, including:
- All indicator results with values, scores, weights, and pass/warning targets
- Compared evaluation IDs (baseline references, from `job_stats`)
- All annotations (sorted)
- Pass/warning score thresholds
- SLI metadata (aggregation fidelity: expected/actual samples, missing percentage)
- Invalidation and override state

The presenter transforms ORM models into response schemas via `build_summary()` and
`build_detail()`.

**Source**: `workflows/presentation/presenter.py`

### Distinct evaluation names

```
GET /evaluations/names
```

Returns a list of distinct evaluation names with their run count and last-run timestamp.
Useful for populating filter dropdowns.

| Parameter | Type | Description |
|-----------|------|-------------|
| `asset_name` | string | Scope to one asset |
| `group_name` | string | Scope to all assets in a group |

### Heatmaps

**Grouped heatmap** (primary visualization):
```
GET /evaluations/heatmap
```

Returns a structured heatmap grouped by SLO, with per-indicator cells and composite
summary rows. Columns correspond to evaluation runs ordered oldest-to-newest.

| Parameter | Type | Description |
|-----------|------|-------------|
| `asset_name` | string | **Required.** Asset to show. |
| `evaluation_name` | string[] | Filter by evaluation names |
| `from` | datetime | Start of time range |
| `to` | datetime | End of time range |
| `cache` | bool | Bypass Redis column cache when `false` (default `true`) |

The response contains:
- `columns`: one `EvaluationColumn` per run (evaluation_id, period, eval_name, has_notes)
- `groups`: one `HeatmapSloGroupSection` per SLO (metrics, cells, per-SLO summary)
- `composite`: overall worst-case summary row across all groups

**Grouped heatmap read path** -- the endpoint implements a cache-aside pattern:

1. Run a lightweight inventory query (`list_runs_for_heatmap`) to list candidate runs
2. If cache enabled: batch-fetch cached fragments via `HeatmapColumnCache.get_many()`
3. For cache misses: load from DB via `get_grouped_metric_heatmap()`, build fragments
   with `build_column_fragment()`, and store them back to Redis via `set_many()`
4. Overlay `has_notes` from a fresh DB query (`get_run_ids_with_notes()`) -- notes are
   never cached so they always reflect the current state
5. Sort fragments by `(period_start, eval_name)` and assemble the final response with
   `assemble_grouped_response()`

Groups are collected alphabetically by `slo_name` for stable ordering (required for
cache correctness -- cached and uncached responses must be byte-identical).

**Source**: `router.py` (lines 158--222), `workflows/presentation/presenter.py`
(`build_column_fragment`, `assemble_grouped_response`),
`workflows/presentation/heatmap_cache.py` (`HeatmapColumnCache`)

**Flat metric heatmap**:
```
GET /evaluations/heatmap/by-metric
```

Returns a flat metric-by-time-slot grid. Same query parameters as the grouped heatmap
(minus `cache`). Each cell maps a metric name to a time slot with result, score, and
evaluation ID. This endpoint has no Redis caching.

### Heatmap column cache

Each `EvaluationRun`'s contribution to the grouped heatmap is cached as a single
`HeatmapColumnFragment` in Redis.

**Key format**: `heatmap:col:v{SCHEMA_VERSION}:{run_id}` (current schema version: 1)

**TTL**: 7 days (safety net -- invalidation is precise, TTL just catches orphans)

**Cache behavior**:
- All operations are fail-safe: Redis errors are caught and logged as warnings
- The DB is always the source of truth; the cache is opportunistic
- `get_many()` uses MGET for batch reads; corrupt/unparseable payloads are treated as
  cache misses (self-healing)
- `set_many()` uses a pipeline for batch writes
- Schema versioning: bumping `SCHEMA_VERSION` causes old entries to become unreachable
  orphans that expire on TTL -- no explicit migration needed

**Invalidation**: every repository mutation that changes a completed run's presented state
(mark_completed, invalidate, restore, pin/unpin baseline, override/restore status) deletes
exactly that run's cached fragment. Re-evaluation also invalidates affected columns.

**Source**: `workflows/presentation/heatmap_cache.py` (`HeatmapColumnCache`)

### Target resolution

Pass and warning target values shown in heatmap cells and detail views are computed by
the target resolver. For each criteria string, it parses the criteria, computes the
target value (which may depend on `compared_value` for relative criteria), and checks
whether the criteria is violated.

A hot-path variant (`resolve_targets_from_parsed`) accepts pre-parsed `ParsedCriteria`
objects for use in `build_column_fragment()`, where criteria are parsed once per
objective and reused across cells via an in-memory `parsed_cache`.

**Source**: `workflows/presentation/target_resolver.py`

### Trend queries

Time-series data for a single metric, scoped by asset+SLO or by evaluation:

```
GET /assets/{asset_name}/slos/{slo_name}/trend?metric={name}&from={ts}
GET /evaluation/{eval_id}/trend?metric={name}&from={ts}
```

Both require a `from` timestamp (datetime) and accept an optional `to`. Each point
includes the metric value, score (normalized to a 0--100 percentage), result, baseline
reference (`compared_value`), evaluation name, and resolved pass/warning targets.

Trend data is read from the `sli_values` TimescaleDB hypertable joined with
`indicator_results` for scores and targets. Invalidated evaluations are excluded.

## Post-Evaluation Actions

### Annotations (SLO-level)

Annotations are notes attached to individual SLO evaluations. They carry a category
(for color-coding on graphs), optional tags, and an author.

```
GET    /evaluation/{eval_id}/annotations          -- list annotations
POST   /evaluation/{eval_id}/annotations          -- create annotation
PATCH  /evaluation/{eval_id}/annotations/{ann_id} -- update annotation
POST   /evaluation/{eval_id}/annotations/{ann_id}/hide -- soft-delete
```

**Create request** (`AnnotationCreate`):
```json
{
  "content": "Deployment of v3.2 caused latency spike",
  "author": "alice",
  "category_id": "uuid-of-category",
  "tags": {"jira": "PERF-1234"}
}
```

### Annotations (run-level)

Run-level annotations are attached to the parent `EvaluationRun`, not a specific SLO
evaluation. They appear on heatmap columns.

```
POST /evaluation-run/{run_id}/annotations
```

Same `AnnotationCreate` request body as SLO-level annotations.

### Column annotations

Retrieves all annotations for one evaluation run -- merging run-level notes with
annotations from each child SLO evaluation. Sorted oldest-first.

```
GET /evaluations/column-annotations?evaluation_id={run_id}
```

### Trend annotations

Returns annotations for every point in an (asset, SLO) trend series, keyed by
`slo_evaluation_id`. Run-level annotations are fanned out across all child SLO
evaluations so each trend point shows both its own notes and its parent run's notes.

```
GET /evaluations/trend-annotations?asset={asset_name}&slo={slo_name}
```

### Annotation categories

Categories define the color and label for annotations. System categories (e.g.,
`re-evaluation`) cannot be renamed or deleted.

```
GET    /note-categories                    -- list all categories
POST   /note-categories                    -- create category
PATCH  /note-categories/{category_id}      -- update category
DELETE /note-categories/{category_id}      -- delete (reassigns annotations)
```

Allowed colors: `sky`, `green`, `amber`, `red`, `purple`, `pink`, `slate`, `gray`.
Deleting a category reassigns its annotations to the `info` category and returns the
count in the `X-Reassigned-Annotations` response header.

### Invalidation

Marks an evaluation as invalid -- excluded from baseline calculations and scored as
`invalidated` in heatmaps. Invalidation is applied to the evaluation and all siblings
in the same run.

```
PATCH /evaluation/{eval_id}/invalidate    -- invalidate (requires invalidation_note)
PATCH /evaluation/{eval_id}/restore       -- undo invalidation
```

### Baseline pinning

Pins a completed, non-invalidated evaluation as the reference point for relative
criteria comparisons. Only one pin is active per asset+SLO combination at a time --
pinning a new evaluation atomically unpins any existing one.

The pin establishes a floor for the baseline window: only evaluations at or after the
pinned evaluation's `period_start` are eligible as baselines.

```
PATCH /evaluation/{eval_id}/pin-baseline    -- pin (requires reason + author)
PATCH /evaluation/{eval_id}/unpin-baseline  -- remove pin
```

### Status override

Manually overrides the evaluation result (pass/warning/fail). The original result
and score are preserved in `original_result` and `original_score` and can be restored.

```
PATCH /evaluation/{eval_id}/override-status     -- override (requires new_result, reason, author)
PATCH /evaluation/{eval_id}/restore-override    -- revert to original result
```

## Re-evaluation

Re-evaluation re-scores historical evaluations using stored metric values against the
current (or a specific) SLO version. It does **not** re-fetch metrics from adapters --
it operates entirely on persisted indicator values.

### Entry points

Three endpoints determine which evaluations are re-scored, differing only in how they
identify the starting point:

```
POST /evaluations/re-evaluate/from-date
POST /evaluations/re-evaluate/from-baseline
POST /evaluations/re-evaluate/from-evaluation/{evaluation_id}
```

All three accept the same request body structure:

```json
{
  "scope": {"kind": "asset", "asset_name": "web-server-01"},
  "selector": {"kind": "slo", "slo_name": "latency-slo"},
  "slo_version": 3,
  "dry_run": true,
  "pin_strategy": "skip_to_pin"
}
```

- **scope**: which asset to re-evaluate (`AssetScope`). Group scope is defined in the
  schema but not yet implemented -- the API raises `ValueError` for `GroupScope`.
- **selector** (optional): limit to a single SLO (`SloSelector`) or a list of evaluation
  names (`EvalNamesSelector`). If omitted, all assigned SLOs are re-evaluated.
- **slo_version** (optional): pin to a specific SLO definition version. If omitted, uses
  the latest version.
- **dry_run**: when `true`, returns the would-be changes without persisting them.
- **pin_strategy**: controls behavior when a baseline pin is encountered.

### Starting point variants

- `from-date`: re-evaluates all evaluations with `period_start >= from_date`
- `from-baseline`: re-evaluates from the most recently pinned baseline's date
- `from-evaluation/{id}`: re-evaluates from the `period_start` of the specified evaluation

### How re-evaluation works

The `re_evaluate()` function in `re_evaluation_service.py` orchestrates the process:

1. Resolves the asset and determines which SLOs to re-evaluate
2. Creates a `note_group_id` to link all automatic re-evaluation annotations
3. Resolves the seeded `re-evaluation` annotation category
4. For each SLO, calls `_re_evaluate_single_slo()`:
   a. Loads the SLO definition (specified version or latest)
   b. Builds the engine SLO model via `build_slo_model()`
   c. Resolves the effective window start via `_resolve_from_date()`
   d. Checks for baseline pin conflicts via `_resolve_pin_conflict()`
   e. Loads evaluations to re-process from `baseline_repo.load_evaluations_for_reeval()`
      in chronological order
   f. Seeds eligible evaluation IDs from pre-window baselines
   g. For each evaluation in chronological order:
      - Extracts metrics from stored indicator rows
      - Fetches baselines (restricted to `eligible_ids` for cascading correctness)
      - Calls the pure engine `evaluate()` with the new SLO
      - If not `dry_run`: persists via `_persist_reeval_result()`
      - Appends the evaluation's ID to `eligible_ids` (cascading baselines)

### Cascading baselines

During re-evaluation, each processed evaluation's ID is appended to `eligible_ids`, so
later evaluations can use earlier re-evaluated ones as baselines. This preserves causal
ordering -- evaluation N's baseline is computed from evaluations 1..N-1 that have already
been re-scored.

### Persisting re-evaluation results

When `dry_run` is `false`, `_persist_reeval_result()`:

1. Updates the evaluation row with the new result, score, and SLO version
2. Preserves `original_result` and `original_score` in `job_stats` on first re-eval
3. Invalidates both the baseline cache and heatmap column cache
4. Adds an automatic annotation (under the `re-evaluation` category) describing the
   result change, linked by `note_group_id` for grouping
5. Deletes and re-inserts indicator rows with freshly computed values

### Baseline pin conflict handling

When a re-evaluation's `from_date` falls before an active baseline pin:

| Strategy | Behavior |
|----------|----------|
| (none) | Raises `BaselinePinConflictError` -- HTTP 409 with `pin_date` and `pin_evaluation_id` |
| `skip_to_pin` | Adjusts `from_date` forward to the pin date |
| `ignore_pin` | Proceeds with the original `from_date`, bypasses pin filtering in baseline queries |

### Response

```json
{
  "affected_evaluations": 12,
  "slo_version_used": 3,
  "results": [
    {
      "id": "uuid",
      "evaluation_name": "nightly-2026-04-29",
      "slo_name": "latency-slo",
      "slo_version": 3,
      "period_start": "2026-04-29T00:00:00Z",
      "period_end": "2026-04-29T06:00:00Z",
      "old_result": "fail",
      "new_result": "pass",
      "old_score": 45.0,
      "new_score": 82.5
    }
  ]
}
```

**Source**: `workflows/re_evaluation/re_evaluation_service.py`

## Endpoint Reference

### Trigger

| Method | Path | Response |
|--------|------|----------|
| POST | `/evaluations` | `EvaluateSingleResponse` (201) |
| POST | `/evaluations/batch` | `EvaluateBatchResponse` (201) |

### List and query

| Method | Path | Response |
|--------|------|----------|
| GET | `/evaluations` | `PagedResponse[EvaluationSummary]` |
| GET | `/evaluations/names` | `list[EvaluationNameEntry]` |
| GET | `/evaluations/heatmap` | `GroupedMetricHeatmapResponse` |
| GET | `/evaluations/heatmap/by-metric` | `MetricHeatmapResponse` |

### Single-resource actions

| Method | Path | Response |
|--------|------|----------|
| GET | `/evaluation/{eval_id}` | `EvaluationDetail` |
| PATCH | `/evaluation/{eval_id}/invalidate` | `EvaluationSummary` |
| PATCH | `/evaluation/{eval_id}/restore` | `EvaluationSummary` |
| PATCH | `/evaluation/{eval_id}/pin-baseline` | `EvaluationDetail` |
| PATCH | `/evaluation/{eval_id}/unpin-baseline` | `EvaluationDetail` |
| PATCH | `/evaluation/{eval_id}/override-status` | `EvaluationDetail` |
| PATCH | `/evaluation/{eval_id}/restore-override` | `EvaluationDetail` |

### Re-evaluation

| Method | Path | Response |
|--------|------|----------|
| POST | `/evaluations/re-evaluate/from-date` | `ReEvaluateResponse` |
| POST | `/evaluations/re-evaluate/from-baseline` | `ReEvaluateResponse` |
| POST | `/evaluations/re-evaluate/from-evaluation/{evaluation_id}` | `ReEvaluateResponse` |

### Annotations

| Method | Path | Response |
|--------|------|----------|
| GET | `/evaluation/{eval_id}/annotations` | `list[AnnotationRead]` |
| POST | `/evaluation/{eval_id}/annotations` | `AnnotationRead` (201) |
| PATCH | `/evaluation/{eval_id}/annotations/{ann_id}` | `AnnotationRead` |
| POST | `/evaluation/{eval_id}/annotations/{ann_id}/hide` | `AnnotationRead` |
| POST | `/evaluation-run/{run_id}/annotations` | `AnnotationRead` (201) |
| GET | `/evaluations/trend-annotations` | `dict[str, list[AnnotationRead]]` |
| GET | `/evaluations/column-annotations` | `list[AnnotationRead]` |

### Annotation categories

| Method | Path | Response |
|--------|------|----------|
| GET | `/note-categories` | `list[AnnotationCategoryRead]` |
| POST | `/note-categories` | `AnnotationCategoryRead` (201) |
| PATCH | `/note-categories/{category_id}` | `AnnotationCategoryRead` |
| DELETE | `/note-categories/{category_id}` | 204 + `X-Reassigned-Annotations` header |

### Trend

| Method | Path | Response |
|--------|------|----------|
| GET | `/assets/{asset_name}/slos/{slo_name:path}/trend` | `list[TrendPoint]` |
| GET | `/evaluation/{eval_id}/trend` | `list[TrendPoint]` |

## Design Decisions

- **Parent-child model.** Triggering one evaluation creates a parent `EvaluationRun`
  that fans out to N child `SLOEvaluation` records (one per bound SLO). The list and
  detail endpoints return SLO evaluations, not runs. Heatmap columns correspond to runs.

- **Plural vs singular URL prefixes.** Collection endpoints use `/evaluations` (plural),
  single-resource actions use `/evaluation/{id}` (singular). Run-level annotations use
  `/evaluation-run/{id}`.

- **Silent SLO resolution skipping.** When triggering, SLOs that fail to resolve
  (missing datasource, broken assignment) are silently skipped. The caller receives
  `slo_evaluation_ids` only for the SLOs that resolved successfully.

- **Invalidation is sibling-wide.** Invalidating one SLO evaluation invalidates all
  siblings in the same run, and vice versa for restore.

- **Baseline pin as floor.** A pinned evaluation establishes a lower bound
  (`period_start >= pin_start`) for baseline queries -- only evaluations at or after the
  pin are eligible as baselines.

- **`date` and `from`/`to` filters are mutually exclusive.** Passing both on
  `GET /evaluations` returns a 422 validation error.

- **Annotation hiding is soft-delete.** Hidden annotations are excluded from list
  responses but retained in the database with `hidden_at`, `hidden_by`, and
  `hidden_reason`.

- **Notes overlay not cached.** The `has_notes` field in heatmap columns is never stored
  in the cached fragment -- it is always resolved fresh from the DB and overlaid at
  assembly time. This means notes added after cache population are reflected without
  requiring cache invalidation.

- **Re-evaluation preserves originals.** On first re-eval, the original result and score
  are saved in `job_stats`. Subsequent re-evaluations update the result but do not
  overwrite the saved originals.

- **Re-evaluation does not re-fetch metrics.** It re-scores using stored indicator values
  against a (possibly new) SLO definition. This is fundamentally different from the
  initial evaluation which queries the adapter.

## Key Source Files

| File | Role |
|------|------|
| `quality_gate/router.py` | All evaluation, annotation, heatmap, trend, and re-evaluation endpoints |
| `quality_gate/workflows/trigger/trigger_service.py` | `TriggerService` -- single and batch trigger orchestration |
| `quality_gate/workflows/trigger/trigger_resolver.py` | `resolve_single_trigger`, `resolve_all_slos_for_asset` |
| `quality_gate/workflows/execution/evaluation_executor.py` | Three-phase worker pipeline, heatmap cache warming |
| `quality_gate/workflows/execution/adapter_client.py` | `HttpAdapterClient` -- HTTP client for metric adapters |
| `quality_gate/workflows/execution/evaluation_helpers.py` | `build_eval_variables`, `build_slo_model`, `compute_baselines` |
| `quality_gate/workflows/presentation/presenter.py` | `build_summary`, `build_detail`, `build_column_fragment`, `assemble_grouped_response` |
| `quality_gate/workflows/presentation/heatmap_cache.py` | `HeatmapColumnCache` -- per-column Redis cache |
| `quality_gate/workflows/presentation/target_resolver.py` | `resolve_targets`, `resolve_targets_from_parsed` |
| `quality_gate/workflows/re_evaluation/re_evaluation_service.py` | `re_evaluate`, `_re_evaluate_single_slo`, `_rescore_single` |
| `quality_gate/shared/dependencies.py` | `QualityGateRepos` DI bundle, `get_qg_repos` factory |
| `quality_gate/shared/exceptions.py` | `EvaluationError`, `SLONotConfiguredError`, `BaselinePinConflictError` |
| `quality_gate/shared/protocols.py` | Protocol types for trigger resolver decoupling |
| `quality_gate/shared/params.py` | `EvalCreateParams` |

All paths are relative to `api/tropek/modules/`.
