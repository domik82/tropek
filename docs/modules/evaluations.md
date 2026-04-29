# Evaluations

## Purpose
Evaluations are TROPEK's core output -- the result of measuring an asset's SLI values
against SLO criteria. This document explains how to trigger evaluations, read results,
and use post-evaluation features like annotations, baseline pinning, and re-evaluation.

For how the worker pipeline executes evaluations internally, see
[evaluation-internals.md](evaluation-internals.md). For the end-to-end lifecycle
(trigger through result), see [evaluation-lifecycle.md](../architecture/evaluation-lifecycle.md).

## Key Concepts

| Concept | What It Is |
|---------|------------|
| **Evaluation Run** | A parent record created when you trigger an evaluation. One run fans out to one SLO Evaluation per bound SLO definition. Identified by `evaluation_id` (UUID). |
| **SLO Evaluation** | A child record under a run, holding the score and result for one SLO definition version. The `id` field in list/detail responses refers to this child. |
| **Result** | The outcome of a single SLO evaluation: `pass`, `warning`, or `fail`. Can be overridden manually or set to `invalidated`. |
| **Score** | A 0-100 numeric value computed from weighted indicator scores against pass/warning thresholds defined in the SLO. |
| **Key SLI** | An indicator flagged `key_sli: true` in the SLO. Failing a key SLI forces the overall result to `fail` regardless of score. |
| **Heatmap** | A grid visualization of evaluation results over time. Two variants: grouped (by SLO group with per-indicator cells) and flat (metric x time slot). |
| **Baseline Pin** | Marks a specific evaluation as the reference point for relative comparisons (`<=+10%`). Only one pin is active per asset+SLO at a time. |
| **Invalidation** | Marks an evaluation as excluded from baseline calculations and trend analysis. Reversible via restore. |

## Triggering Evaluations

### Single evaluation

```
POST /evaluations
```

Triggers evaluation for all SLO definitions bound to an asset. The API validates bindings,
creates an EvaluationRun, and enqueues a worker job per bound SLO.

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

### Ingestion modes

The evaluation worker supports three ways to obtain SLI values:
- **Pull** -- queries an adapter (e.g., Prometheus) using SLI query templates.
- **Push** -- accepts pre-computed SLI values submitted by the caller.
- **File** -- reads SLI values from an uploaded file.

The ingestion mode is determined by the SLO assignment's datasource configuration,
not by the trigger request. The `ingestion_mode` field appears on evaluation summaries.

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
- Compared evaluation IDs (baseline references)
- All annotations
- Pass/warning score thresholds
- SLI metadata (aggregation fidelity info)
- Invalidation and override state

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

The response contains `columns` (one per run), `groups` (one per SLO with metrics, cells,
and summary), and `composite` (overall worst-case row across all groups).

**Flat metric heatmap**:
```
GET /evaluations/heatmap/by-metric
```

Returns a flat metric-by-time-slot grid. Same query parameters as the grouped heatmap
(minus `cache`). Each cell maps a metric name to a time slot with result, score, and
evaluation ID.

## Post-Evaluation Features

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

Run-level annotations are attached to the parent EvaluationRun, not a specific SLO
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
evaluations.

```
GET /evaluations/trend-annotations?asset={asset_name}&slo={slo_name}
```

### Annotation categories

Categories define the color and label for annotations. System categories cannot be
renamed or deleted.

```
GET    /note-categories                    -- list all categories
POST   /note-categories                    -- create category
PATCH  /note-categories/{category_id}      -- update category
DELETE /note-categories/{category_id}      -- delete (reassigns annotations)
```

Allowed colors: `sky`, `green`, `amber`, `red`, `purple`, `pink`, `slate`, `gray`.
Deleting a category returns the count of reassigned annotations in the
`X-Reassigned-Annotations` response header.

### Invalidation

Marks an evaluation as invalid -- excluded from baseline calculations and scored as
`invalidated` in heatmaps.

```
PATCH /evaluation/{eval_id}/invalidate    -- invalidate (requires invalidation_note)
PATCH /evaluation/{eval_id}/restore       -- undo invalidation
```

### Baseline pinning

Pins a completed, non-invalidated evaluation as the reference point for relative
criteria comparisons. Only one pin is active per asset+SLO combination at a time.

```
PATCH /evaluation/{eval_id}/pin-baseline    -- pin (requires reason + author)
PATCH /evaluation/{eval_id}/unpin-baseline  -- remove pin
```

### Status override

Manually overrides the evaluation result (pass/warning/fail). The original result
and score are preserved and can be restored.

```
PATCH /evaluation/{eval_id}/override-status     -- override (requires new_result, reason, author)
PATCH /evaluation/{eval_id}/restore-override    -- revert to original result
```

### Re-evaluation

Re-evaluates historical evaluations using the current (or a specific) SLO version.
Three entry points determine which evaluations are re-scored:

```
POST /evaluations/re-evaluate/from-date
POST /evaluations/re-evaluate/from-baseline
POST /evaluations/re-evaluate/from-evaluation/{evaluation_id}
```

All three accept a **scope** (single asset or asset group) and an optional **selector**
(limit to one SLO name or a list of evaluation names):

```json
{
  "scope": {"kind": "asset", "asset_name": "web-server-01"},
  "selector": {"kind": "slo", "slo_name": "latency-slo"},
  "slo_version": 3,
  "dry_run": true,
  "pin_strategy": "skip_to_pin"
}
```

- `from-date` re-evaluates all evaluations after a given `from_date`.
- `from-baseline` re-evaluates from the most recently pinned baseline.
- `from-evaluation/{evaluation_id}` re-evaluates from the `period_start` of the
  specified evaluation.

`dry_run: true` returns the would-be changes without persisting them. `pin_strategy`
controls behavior when a baseline pin is encountered: `skip_to_pin` stops before the
pin, `ignore_pin` re-evaluates through it. Conflicts return HTTP 409 with pin details.

**Response** (`ReEvaluateResponse`):
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

### Trend queries

Time-series data for a single metric, scoped by asset+SLO or by evaluation:

```
GET /assets/{asset_name}/slos/{slo_name}/trend?metric={name}&from={ts}
GET /evaluation/{eval_id}/trend?metric={name}&from={ts}
```

Both require a `from` timestamp (datetime) and accept an optional `to`. Each point
includes the metric value, score, result, baseline reference, evaluation name, and
resolved pass/warning targets.

## Module Summary

| Endpoint Group | URL Pattern | What It Does |
|----------------|-------------|--------------|
| Trigger | `POST /evaluations` | Trigger single evaluation for an asset |
| Trigger (batch) | `POST /evaluations/batch` | Trigger batch evaluations (by_date or by_asset) |
| List | `GET /evaluations` | Paginated evaluation list with filters |
| Detail | `GET /evaluation/{eval_id}` | Full evaluation detail with indicators |
| Names | `GET /evaluations/names` | Distinct evaluation names with counts |
| Grouped Heatmap | `GET /evaluations/heatmap` | SLO-grouped indicator heatmap |
| Flat Heatmap | `GET /evaluations/heatmap/by-metric` | Metric x time slot heatmap grid |
| Invalidation | `PATCH /evaluation/{eval_id}/invalidate`, `/restore` | Mark/unmark as invalidated |
| Baseline Pin | `PATCH /evaluation/{eval_id}/pin-baseline`, `/unpin-baseline` | Pin/unpin as baseline reference |
| Status Override | `PATCH /evaluation/{eval_id}/override-status`, `/restore-override` | Override/restore evaluation result |
| Re-evaluation | `POST /evaluations/re-evaluate/from-date`, `/from-baseline`, `/from-evaluation/{id}` | Re-score historical evaluations |
| SLO Annotations | `GET/POST/PATCH /evaluation/{eval_id}/annotations` | CRUD for SLO-level notes |
| Run Annotations | `POST /evaluation-run/{run_id}/annotations` | Create run-level notes |
| Column Annotations | `GET /evaluations/column-annotations` | Merged annotations for a heatmap column |
| Trend Annotations | `GET /evaluations/trend-annotations` | Annotations keyed by trend point |
| Annotation Categories | `GET/POST/PATCH/DELETE /note-categories` | Manage annotation category definitions |
| Trend (asset+SLO) | `GET /assets/{name}/slos/{slo_name}/trend` | Metric trend by asset and SLO |
| Trend (evaluation) | `GET /evaluation/{eval_id}/trend` | Metric trend scoped to one evaluation's asset+SLO |

## Gotchas / Design Decisions

- **Parent-child model.** Triggering one evaluation creates a parent `EvaluationRun`
  that fans out to N child `SLOEvaluation` records (one per bound SLO). The list and
  detail endpoints return SLO evaluations, not runs. Heatmap columns correspond to runs.

- **Plural vs singular URL prefixes.** Collection endpoints use `/evaluations` (plural),
  single-resource actions use `/evaluation/{id}` (singular). Run-level annotations use
  `/evaluation-run/{id}`.

- **Redis column caching.** The grouped heatmap caches each column as an independent
  Redis fragment (`heatmap:col:v1:{run_id}`). The `cache=false` query parameter bypasses
  this for debugging. Column fragments include embedded criteria targets so they remain
  correct even after SLO version changes.

- **Invalidation excludes from baseline.** An invalidated evaluation is skipped when
  the engine looks for comparison baselines. Pinning an invalidated evaluation is rejected
  with HTTP 409.

- **Baseline pin conflict on re-evaluation.** If re-evaluation would cross a pinned
  baseline, the API returns 409 with `pin_date` and `pin_evaluation_id` so the caller
  can decide whether to skip or ignore the pin.

- **`date` and `from`/`to` filters are mutually exclusive.** Passing both on `GET /evaluations`
  returns a 422 validation error.

- **Annotation hiding is soft-delete.** Hidden annotations are excluded from list
  responses but retained in the database with `hidden_at`, `hidden_by`, and `hidden_reason`.

- **Override preserves original.** When a status is overridden, the original result and
  score are saved in `original_result` and `original_score`. The `restore-override`
  endpoint reverts to these saved values.
