# Quality Gate Repositories

Data access layer for the evaluation lifecycle. All repositories live in
`api/tropek/modules/quality_gate/repositories/`.

For registry repositories (SLO, SLI, DataSource, Asset), see
[`docs/modules/registries.md`](../../docs/modules/registries.md) and
[`docs/modules/assets.md`](../../docs/modules/assets.md).

## Conventions

- All repositories take `AsyncSession` as first constructor argument
- Optional `RedisCache` for cache-enabled repos
- Repositories never commit -- callers manage transaction boundaries
- All methods use `flush()` after writes to surface DB errors immediately
- Three-level `selectinload` chains for eager loading relationship trees

```python
selectinload(SLOEvaluation.indicator_rows).joinedload(IndicatorResultRow.objective)
selectinload(SLOEvaluation.annotations).selectinload(EvaluationAnnotation.category)
```

## EvaluationRepository

Source: `repositories/evaluation.py` (~610 lines). The largest repository.

Constructor: `__init__(session, cache=None, heatmap_cache=None)`.

### State Machine

| Method | Transition | Side Effects |
|--------|-----------|--------------|
| `create_pending(params)` | -- -> PENDING | Auto-creates parent `EvaluationRun` if absent. Merges asset tags into `variables`. Catches `UniqueViolationError` -> `ConflictError`. |
| `mark_running(eval_id)` | PENDING -> RUNNING | Sets `started_at`, optional `worker_id` in `job_stats` |
| `mark_completed(eval_id, ...)` | RUNNING -> COMPLETED | Sets result/score/points. Merges `compared_evaluation_ids` into `job_stats`. Invalidates caches. |
| `mark_failed(eval_id)` | * -> FAILED | Sets error `job_stats` |
| `mark_partial(eval_id)` | * -> PARTIAL | Crashed mid-execution |

### Query Methods

| Method | Purpose |
|--------|---------|
| `find_duplicate(...)` | Identity tuple check: `(asset_id, slo_name, evaluation_name, period_start, period_end)` excluding failed |
| `has_pending_predecessor(...)` | Checks for earlier eval for same asset+SLO still pending/running |
| `get_by_id(eval_id)` | Single eval with eager-loaded annotations and indicator rows |
| `list_evaluations(...)` | Filterable list by name, asset, result, time range. Paginated. |
| `list_with_counts(...)` | Paginated list + total count + annotation counts + latest annotation per eval. Uses `DISTINCT ON` for latest annotation. |
| `list_evaluation_names(...)` | Distinct eval names with count and last-run timestamp |
| `find_stuck(...)` | Running evaluations past stuck threshold (watchdog) |
| `get_by_run_id(run_id)` | All SLO evaluations for a parent run |

### Mutation Methods

| Method | Purpose | Cache Invalidation |
|--------|---------|-------------------|
| `invalidate(eval_id)` | Soft-invalidate eval + all siblings in same run | baseline + heatmap |
| `restore(eval_id)` | Clear invalidation on eval + siblings | baseline + heatmap |
| `pin_baseline(eval_id)` | Atomically unpin existing, then pin target | baseline + heatmap |
| `unpin_baseline(eval_id)` | Sets `baseline_unpinned_at` | baseline + heatmap |
| `override_status(eval_id, ...)` | Changes result, preserving `original_result` on first override | baseline + heatmap |
| `restore_override(eval_id)` | Reverts to `original_result` | baseline + heatmap |

### Cache Invalidation Pattern

Every mutation calls both:
```
baseline:{asset_id}:{slo_name}     # Redis key deletion
heatmap column cache delete(run_id) # HeatmapColumnCache.delete()
```

Annotation cache uses separate keys: `annot_count:{slo_eval_id}`, `annot_latest:{slo_eval_id}`.

## EvaluationRunRepository

Source: `repositories/evaluation_run.py` (~139 lines). No cache.

| Method | Purpose |
|--------|---------|
| `create(...)` | Creates PENDING parent run |
| `get_by_id(run_id)` | Primary key lookup |
| `mark_completed(run_id)` | Direct status update |
| `mark_running(run_id)` | Status transition for first child start |
| `finalize_if_all_done(run_id)` | Aggregates child results: worst-case result via `RESULT_RANK`, sums points. Returns None if any child is pending/running/partial. |
| `find_finalizable_pending_ids(limit)` | Sweeper query: parent runs not completed, have children, no pending/running/partial children. Uses EXISTS/NOT EXISTS subqueries. |

## BaselineRepository

Source: `repositories/baseline.py` (~219 lines).

Constructor: `__init__(session, cache=None)`.

### Base Query Construction

`_base_baseline_query()` builds the shared WHERE clause:
- `asset_id` + `slo_name` scoping
- `period_start < current_eval_start` (strict less-than)
- `status == COMPLETED`, `invalidated == False`
- `include_result_with_score` filter: `"pass"` / `"pass_or_warn"` / `"all"`

### Pin-Aware Filtering

`_apply_pin_filter()` runs a separate SELECT to find the active pin's `period_start`,
then adds `period_start >= pin_start`. The pin establishes a floor, not a ceiling.

A pin is active when `pinned_at IS NOT NULL AND unpinned_at IS NULL`.

### Query Methods

| Method | Used By | Extra Filters |
|--------|---------|---------------|
| `get_active_pin(asset_id, slo_name)` | Pin management | -- |
| `get_evaluation_baselines(...)` | Worker scoring | Pin-aware. Eager-loads `indicator_rows -> objective`. |
| `get_reeval_baselines(...)` | Re-evaluator | Adds: `sli_version_range`, `restrict_to_ids`, `tag_filters` (JSONB path), `skip_pin_filter` |
| `load_evaluations_for_reeval(...)` | Re-evaluator | From-date forward, chronological order, eager-loads indicator rows |

## TrendRepository

Source: `repositories/trend.py` (~336 lines). No cache.

### Heatmap Queries

| Method | Level | Eager Loading | Safety Cap |
|--------|-------|--------------|-----------|
| `get_metric_heatmap(...)` | SLOEvaluation | `indicator_rows -> objective` | 500 |
| `get_grouped_metric_heatmap(...)` | EvaluationRun | `slo_evaluations -> indicator_rows -> objective` | 100 |
| `get_run_with_slo_evaluations(run_id)` | Single run | Full chain | -- |
| `list_runs_for_heatmap(...)` | EvaluationRun | None (lightweight) | 100 |
| `get_run_ids_with_notes(...)` | UNION query | -- | -- |

`list_runs_for_heatmap()` is the cache-key query: returns the same run set as
`get_grouped_metric_heatmap()` but without eagerly loaded children. Used as step 1
of the cache-optimized read path.

`get_run_ids_with_notes()` returns `set[UUID]` by UNION of SLO-level annotation hits
and run-level annotation hits, filtering `hidden_at IS NULL`.

### Trend Queries

| Method | Complexity | Purpose |
|--------|-----------|---------|
| `get_trend_by_domain(...)` | High | 4-table JOIN (`sli_values`, `slo_evaluations`, `indicator_results`, `slo_objectives`) + correlated scalar subquery for `total_weight`. Returns time-series with value, score (normalized to percentage), baseline, targets. |
| `get_trend(...)` | Medium | `sli_values` JOIN `slo_evaluations`. Filters by `evaluation_name` + `metric_name`. |

## AnnotationRepository

Source: `repositories/annotation.py` (~203 lines).

Constructor: `__init__(session, cache=None)`.

| Method | Purpose |
|--------|---------|
| `add_annotation(slo_evaluation_id, ...)` | SLO-level annotation. Invalidates `annot_count` and `annot_latest` cache. |
| `add_run_annotation(evaluation_run_id, ...)` | Run-level (column) annotation. No per-eval cache invalidation. |
| `list_for_trend(asset_id, slo_name)` | Two-phase: collect SLO eval IDs, then fetch non-hidden annotations for those + their parent run IDs. Returns fan-out mapping. |
| `list_for_run(run_id)` | Non-hidden run-level annotations. |
| `get_annotation_by_id(id)` | With eager-loaded category. |
| `update_annotation(id, ...)` | Partial update. Invalidates cache. |
| `hide_annotation(id, ...)` | Soft-delete: sets `hidden_at`, `hidden_by`, `hidden_reason`. |

Annotations attach polymorphically (XOR) to either `slo_evaluation_id` or
`evaluation_run_id`, never both.

## AnnotationCategoryRepository

Source: `repositories/annotation_category.py` (~131 lines). No cache.

| Method | Purpose |
|--------|---------|
| `list_all()` | Alphabetical. |
| `get_by_id(id)` / `get_by_name(name)` | Lookups. |
| `create(...)` | User-defined only (`is_system=False`). |
| `update(id, ...)` | Raises `SystemCategoryError` if renaming a system category. |
| `delete(id)` | Reassigns referencing annotations to `info` category. Raises `SystemCategoryError` for system rows. Returns reassignment count. |

## IndicatorRepository

Source: `repositories/indicator.py` (~85 lines). No cache.

| Method | Purpose |
|--------|---------|
| `bulk_insert(eval_id, rows)` | Inserts `IndicatorResultRow` records. |
| `delete_for_evaluation(eval_id)` | Deletes all rows for an eval (used by re-evaluation). |

`build_indicator_row_dicts()` (module-level function) converts engine `IndicatorResult`
objects to row dicts, looking up `slo_objective_id` from a metric-to-UUID mapping.

## SLIValueRepository

Source: `repositories/sli_value.py` (~49 lines). No cache.

| Method | Purpose |
|--------|---------|
| `write_sli_values(rows)` | Batch insert via `insert().values(rows)`. |
| `delete_sli_values(eval_id)` | Hard delete for rerun. |
| `get_sli_values_for_eval(eval_id)` | Fetch all values. |
