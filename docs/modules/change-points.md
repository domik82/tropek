# Change-Point Detection

## Overview

TROPEK includes automatic change-point detection to identify statistically significant shifts in evaluation indicator time series. When a metric's distribution changes -- a response time jumps after a deployment, or error rates drop after a fix -- the system detects the shift, records its direction and magnitude, and surfaces it in heatmaps, trend charts, and evaluation detail views. This turns raw SLI history into actionable signals without manual threshold tuning.

## How It Works

TROPEK uses the E-Divisive algorithm (derived from Apache Otava) to find distributional shifts in time series data.

The algorithm operates in two phases. In the **split phase**, a sliding window moves across the indicator's historical values. Within each window, the detector builds a pairwise distance matrix measuring how different each pair of observations is, then searches for the split point that maximizes a divergence statistic called Q-hat. A t-test checks whether the candidate split is statistically significant. The split phase uses a relaxed p-value threshold to avoid missing real changes.

In the **merge phase**, the algorithm iteratively removes the weakest candidates -- those with the highest p-values or lowest magnitude -- recomputing statistics for neighboring change points after each removal. This continues until every remaining change point meets the strict significance and magnitude thresholds.

For each confirmed change point, the detector computes pre- and post-segment means and standard deviations, absolute and relative change magnitude, and a direction label (regression or improvement, based on whether higher values are better for that indicator).

The algorithm reliably detects abrupt mean shifts. It does not detect variance-only changes or very gradual drifts.

## Detection Lifecycle

1. An evaluation completes and its SLI values are written to the database.
2. The worker triggers change-point detection as a fault-isolated phase in a separate transaction. If detection fails, the evaluation result is unaffected.
3. For each SLO objective, the worker resolves the detection configuration (per-objective override or system defaults), gathers the indicator's historical time series, and runs the E-Divisive algorithm.
4. Detected change points pass through a deduplication pipeline: nearby timestamps (within one ordinal position) are checked for existing records, and same-direction points in the same statistical regime are suppressed.
5. New change points are persisted to the database with status "unprocessed."
6. Heatmap cells, trend chart points, and evaluation detail indicators are annotated with change-point markers on read.

## Configuration

Change-point detection uses a three-tier configuration resolution:

- **System-level defaults** are stored in the configuration table with the `change_point.*` prefix. They apply to all indicators unless overridden. Administrators update them at runtime via the configuration API.
- **Per-objective overrides** are stored as sparse rows linked to individual SLO objectives. Only fields that differ from defaults need to be set. When creating a new SLO version, per-objective config is copied forward from the previous version automatically.
- **Resolution order**: explicit per-objective value takes priority, then copy-forward from the previous SLO version, then system defaults. Two algorithm tuning parameters (`pvalue_strict_threshold` and `pvalue_moderate_threshold`) always come from system defaults regardless of per-objective overrides.

Key parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| enabled | true | Global or per-objective toggle for detection |
| max_pvalue | 0.001 | Significance threshold for the merge phase |
| window_size | 30 | Sliding window size for the split phase |
| min_magnitude | 0.0 | Minimum relative change to keep a change point |
| min_sample_size | 10 | Minimum number of historical evaluations before detection runs |
| higher_is_better | per-objective | Controls whether an increase is labeled regression or improvement |

## API Endpoints

### Change Points

| Method | Path | Description |
|--------|------|-------------|
| GET | /change-points | List change points with optional filters (status, direction, asset, SLO, metric, time range) |
| GET | /change-points/{id} | Get a single change point by ID |
| PATCH | /change-points/{id} | Triage a change point (update status, add notes, link a ticket) |
| PATCH | /change-points/bulk-triage | Triage multiple change points at once |

### Per-Objective Configuration

| Method | Path | Description |
|--------|------|-------------|
| GET | /change-points/config/{objective_id} | Get resolved config for an objective (falls back to system defaults) |
| PUT | /change-points/config/{objective_id} | Create or update per-objective config override |
| DELETE | /change-points/config/{objective_id} | Remove per-objective override (reverts to system defaults) |

### System Configuration

| Method | Path | Description |
|--------|------|-------------|
| GET | /configuration | List all system configuration entries (supports prefix filter) |
| GET | /configuration/{name} | Get a single configuration entry by name |
| PUT | /configuration/{name} | Update a configuration entry value |

## Where Change Points Appear

Change-point markers carry two fields: direction (regression or improvement) and relative change percentage. They appear in three places:

- **Evaluation detail view** -- each indicator result includes a change-point marker when one was detected at that evaluation's timestamp for that metric.
- **Navigator heatmap** -- each heatmap cell can carry a change-point overlay. The data is loaded fresh on every read (not cached with the heatmap fragment) so that triaged or hidden change points disappear immediately.
- **Trend charts** -- each point in the trend time series includes a change-point marker when applicable, loaded via a time-range query against the change-points table.

## Comparison Scoping

By default, change-point detection analyses the history of evaluations with the same name (the `evaluation_name` field on each evaluation run). This prevents mixing metrics from different evaluation series -- for example, nightly load tests and canary deployments -- which would produce meaningless distributional comparisons.

Callers can override this by passing a `compare_to` field when triggering an evaluation:

    {"compare_to": {"evaluation_name": "nightly-baseline"}}

This tells TROPEK to draw baseline history and scope change-point detection to the named series instead of the current evaluation's own name. When `compare_to` points to a different series than the current evaluation, change-point detection is skipped entirely, since cross-series distributional shifts are not statistically meaningful.

The same scoping mechanism applies to baseline comparisons used for pass/warning/fail scoring, keeping both systems aligned on which historical data to use.
