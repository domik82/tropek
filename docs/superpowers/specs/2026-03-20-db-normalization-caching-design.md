# DB Normalization + Redis Caching Layer

**Date:** 2026-03-20
**Status:** Draft
**Depends on:** Test Coverage Backfill (2026-03-21) — must land first to establish regression safety net
**Prerequisite for:** Otava Change Point Detection integration

## Problem

The `evaluations.indicator_results` column stores per-SLI breakdown as a JSONB blob. This was a convenience shortcut that works against PostgreSQL's relational strengths:

- No schema enforcement at DB level — silent data corruption from bad engine output goes undetected
- Querying individual indicators requires JSONB path extraction instead of WHERE clauses
- Duplicates data already present on `slo_objectives` (metric_name, display_name, criteria, weight, key_sli)
- Adding new features (change point detection) means evolving a blob schema rather than adding columns/tables
- Cross-referencing ("which evaluations had response_time_p95 fail?") is expensive

Additionally, normalizing introduces more joins. Redis is already deployed for the arq job queue but unused for caching. Immutable versioned entities (SLOs, SLIs, objectives) and infrequently-changing entities (assets, labels, annotations) are strong cache candidates that offset the join cost.

## Decisions

1. **Extract `indicator_results` JSONB into a proper relational table** with a foreign key to `slo_objectives`
2. **Drop duplicated columns** — `metric_name`, `display_name`, `weight`, `key_sli`, `pass_targets`, `warning_targets` are all derivable from the `slo_objectives` join
3. **Introduce a Redis caching layer** for read-heavy, infrequently-changing entities
4. **Keep small JSONB where appropriate** — `asset_snapshot` on evaluations (denormalized-by-design point-in-time capture) stays as-is

## Prerequisite: Add `tab_group` to `slo_objectives`

The `SLOObjective` model currently lacks a `tab_group` column, though the API schema exposes it. As part of this work, add `tab_group: str | null` to the `slo_objectives` table. This is where it logically belongs (it's a property of the objective definition, not the evaluation result).

## Data Model Changes

### New table: `indicator_results`

```
indicator_results
├── id: UUID (PK)
├── evaluation_id: UUID → evaluations.id (FK, indexed)
├── slo_objective_id: UUID → slo_objectives.id (FK, indexed)
├── value: float | null              -- measured metric value
├── compared_value: float | null     -- baseline value used for relative criteria
├── change_absolute: float | null    -- value - compared_value
├── change_relative_pct: float | null -- ((value/compared_value) - 1) * 100
├── status: str                      -- pass, warning, fail, info, error
├── score: float                     -- points toward weighted total
```

Note: `aggregation` is not stored here. It is a property of the SLI query definition, not of the evaluation result. If needed, it can be derived from the SLI definition via `evaluation.sli_name` + `evaluation.sli_version`.

Note: `score` is stored despite being derivable (`weight * status_multiplier`) because it is read on every evaluation list/detail/heatmap request and recomputing it requires loading the scoring logic. The minor duplication avoids repeated computation on the hot read path.

**What's NOT on this table (comes from joins):**
- `metric_name`, `display_name`, `tab_group` → from `slo_objectives.sli`, `slo_objectives.display_name`, `slo_objectives.tab_group`
- `weight`, `key_sli` → from `slo_objectives.weight`, `slo_objectives.key_sli`
- `pass_criteria`, `warning_criteria` → from `slo_objectives.pass_criteria`, `slo_objectives.warning_criteria`
- `pass_targets`, `warning_targets` (computed violated flags + resolved target values) → derivable at read time from `compared_value` + criteria strings

**Deriving pass_targets/warning_targets at read time:**
- Fixed criteria (`<600`): target_value = 600, violated = value >= 600
- Relative percent (`<=+10%`): target_value = compared_value * 1.10, violated = value > target_value
- Relative absolute (`<=+50`): target_value = compared_value + 50, violated = value > target_value
- This logic already exists in `criteria.py` — expose it as a read-time utility
- **Performance note:** this adds per-indicator computation on every detail request. For evaluations with 20+ indicators, this is measurable but acceptable (criteria parsing is string operations, not I/O). If it becomes a bottleneck, `pass_targets`/`warning_targets` can be cached in Redis per evaluation ID.

**Relationship to `SLIValue` hypertable:** The `sli_values` hypertable continues to serve its existing purpose — time-partitioned metric storage optimized for Grafana dashboards and time-range queries. The new `indicator_results` table stores the *evaluation judgment* of those values (status, score, compared_value). They are complementary: `sli_values` is "what was the number," `indicator_results` is "what did we think of the number."

### Dropped from `evaluations`

- `indicator_results: JSONB` column removed
- All other columns unchanged

### Indexes on `indicator_results`

- `(evaluation_id)` — fetch all indicators for an eval
- `(slo_objective_id, status)` — "which evals had this metric fail?"
- `(evaluation_id, slo_objective_id)` UNIQUE — one result per objective per eval

## Redis Caching Strategy

### Cache tiers

**Tier 1: Immutable (no invalidation needed, no TTL)**

These entities are versioned and never modified after creation. Cache permanently — a new version is a new cache key.

| Entity | Cache key | Value |
|---|---|---|
| SLO definition + objectives | `slo:{name}:v{version}` | Full SLO with objectives list |
| SLI definition | `sli:{name}:v{version}` | Full SLI with indicator configs |

**Tier 2: Infrequently changing (event-driven invalidation)**

These change on explicit user actions. Invalidate on write.

| Entity | Cache key | Invalidation event |
|---|---|---|
| Asset (by ID) | `asset:{id}` | Asset update/delete |
| Asset (by name) | `asset:name:{name}` | Asset update/delete |
| Asset labels | `asset:{id}:labels` | Label add/remove on asset |
| Latest SLO version | `slo:{name}:latest` | New SLO version created |
| Latest SLI version | `sli:{name}:latest` | New SLI version created |

**Tier 3: Moderate change frequency (TTL + event invalidation)**

| Entity | Cache key | TTL | Invalidation event |
|---|---|---|---|
| Baseline aggregates | `baseline:{asset_id}:{slo_name}` | 5 min | New eval completed |
| Annotation counts | `annot_count:{eval_id}` | 5 min | Annotation created/hidden |
| Latest annotation | `annot_latest:{eval_id}` | 5 min | Annotation created/hidden |

**Not cached (too varied or changes on every request):**
- Evaluation lists (paginated, filtered, different per request)
- Heatmap results (aggregated, filtered)
- Trend data (windowed queries)

### Cache implementation pattern

Repository methods follow a read-through pattern:

```python
async def get_slo(name: str, version: int) -> SLODefinition:
    key = f"slo:{name}:v{version}"
    cached = await redis.get(key)
    if cached:
        return SLODefinition.model_validate_json(cached)
    slo = await db_query(...)
    await redis.set(key, slo.model_dump_json())  # no TTL — immutable
    return slo
```

Invalidation on write:

```python
async def create_slo_version(slo: SLOCreate) -> SLODefinition:
    result = await db_insert(...)
    await redis.delete(f"slo:{slo.name}:latest")  # bust "latest" pointer
    # No need to bust versioned key — new version = new key
    return result
```

### Cache consistency

For Tier 1 (immutable), consistency is guaranteed — versioned keys never change, so stale reads are impossible.

For Tier 2 (event-driven invalidation), there is a small window between DB commit and Redis delete where the cache is stale. This is acceptable: the "latest" pointer will resolve to the previous version for at most one request. The next read fills the cache with the correct value. No transactional outbox is needed — eventual consistency within milliseconds is sufficient for this use case.

For Tier 3 (TTL-based), staleness up to the TTL (5 min) is acceptable by design — baseline aggregates and annotation counts are not latency-sensitive.

### Cache warming

On worker startup, pre-load:
- All "latest" SLO/SLI versions (small set, used on every eval)
- All active assets (used for every eval lookup)

This avoids cold-cache penalties on the first evaluation after deploy.

## Migration Strategy

### Data migration for existing evaluations

Existing `indicator_results` JSONB rows must be migrated into the new table. The migration:

1. Create `indicator_results` table
2. For each existing evaluation with non-null `indicator_results`:
   - Match each JSONB entry's `metric` field to the corresponding `slo_objective` (via `evaluation.slo_name`, `evaluation.slo_version`, and the objective's `sli` field)
   - **Fallback for null `slo_version`:** if `slo_version` is NULL, resolve to the latest version of the SLO that existed at `evaluation.created_at` (query `slo_definitions` by name + created_at). If no match is found, use the current latest version — log a warning for manual review.
   - Insert an `indicator_results` row with the matched `slo_objective_id`
3. Verify row counts match
4. Drop the `indicator_results` JSONB column from `evaluations`

### Write atomicity

The evaluation insert and its `indicator_results` rows must be written in a **single DB transaction**. If the process crashes between the evaluation insert and the indicator_results inserts, the evaluation would have no indicator data. The worker already uses a session-scoped transaction — ensure the indicator_results INSERT happens within the same session commit.

### Re-evaluation write strategy

The re-evaluator currently overwrites the entire `indicator_results` JSONB. With the normalized table, re-evaluation performs DELETE + INSERT (not upsert): delete all `indicator_results` rows for the evaluation, then insert the new set. The UNIQUE constraint `(evaluation_id, slo_objective_id)` prevents duplicates within a single evaluation. Change points linked to deleted indicator results are handled by ON DELETE SET NULL on the FK — the change point record survives (remember forever) but loses its link to the specific indicator result. The `detected_at_eval_id` on the change point (via the evaluation join) still provides the historical context.

### API response changes

The API schemas (`EvaluationDetail`, `IndicatorResult`, `EvaluationSummary`) remain identical from the client's perspective. The backend constructs the same response shape by joining `indicator_results` + `slo_objectives` and computing `pass_targets`/`warning_targets` at read time.

The `top_failures` field on `EvaluationSummary` becomes a join query instead of JSONB array slicing.

## Affected Components

### Backend
- `api/app/db/models.py` — new `IndicatorResult` model, add `tab_group` to `SLOObjective`, drop JSONB column
- `api/app/modules/quality_gate/repository.py` — all queries that read/write indicator_results
- `api/app/modules/quality_gate/re_evaluator.py` — `_metrics_from_indicator_results()` and `_compute_baselines()` currently iterate JSONB; must query `indicator_results` table + join `slo_objectives` for metric name
- `api/app/modules/quality_gate/trend_repository.py` — `get_trend_by_domain()` currently extracts `compared_value` from JSONB subquery; rewrite to join `indicator_results`
- `api/app/modules/quality_gate/baseline_repository.py` — `update_reeval_result()` writes JSONB; rewrite to update `indicator_results` rows
- `api/app/modules/quality_gate/presenter.py` — **central transformation layer**: `build_summary()` extracts `top_failures` from JSONB dicts (line 21-31), `build_detail()` constructs `IndicatorResult` objects from JSONB (line 49). Both must be rewritten to accept joined ORM results instead of raw dicts. This is the main file that changes.
- `api/app/modules/quality_gate/schemas.py` — response shapes stay identical (no UI breakage); `FailingIndicator.threshold` currently reads `pass_targets[0].criteria` from JSONB — after normalization, derive from `slo_objectives.pass_criteria[0]`
- `api/app/modules/quality_gate/engine/evaluator.py` — return type may change to structured objects instead of dicts
- `api/app/modules/quality_gate/router.py` — `_build_detail()` and `_build_summary()` currently read from JSONB; rewrite to construct from joined query results
- Worker job (`worker.py`) — writes to new table instead of JSONB (lines 90, 216, 235)
- New: `api/app/cache/` module for Redis cache utilities
- New: cache invalidation hooks in repositories

### Frontend
- No changes — API response shape is preserved. The normalization is entirely backend-internal.

### Testing strategy

**New: Repository-level round-trip tests (TDD — write before migrating)**

These tests validate that data written through the new `indicator_results` table produces identical API responses to the old JSONB approach. They must be written BEFORE the migration code and pass AFTER.

1. **Write → read round-trip:** create an evaluation with known indicator data via the repository, read it back through the presenter, assert the API response matches the input field-by-field. This catches join errors, null handling mismatches, type coercion bugs, and pass_targets recomputation drift.

2. **Re-evaluation round-trip:** write an evaluation, re-evaluate it (DELETE + INSERT cycle), verify the new indicator_results are returned and any old change point FKs are SET NULL (not lost).

3. **Heatmap query equivalence:** run `get_metric_heatmap()` against a known dataset, assert the cell data (metric name, status, display_name) matches expected output. This validates the join chain used by the heatmap endpoint.

4. **Trend query equivalence:** run `get_trend_by_domain()` against known data, assert trend points include correct `compared_value` (previously extracted from JSONB, now joined from `indicator_results`).

5. **Top failures derivation:** verify `build_summary()` produces the same `top_failures` list — particularly `threshold` field, which now comes from `slo_objectives.pass_criteria[0]` instead of `pass_targets[0].criteria` in JSONB.

6. **Edge cases:** null `compared_value` (no baseline), info-only objectives (no criteria), missing metrics (value=null), evaluations with 0 indicator results.

**Existing tests**

- `scripts/dev-start.sh` seeds evaluations via the Python client calling the API (POST `/evaluations`), which flows through the full stack: API → arq queue → worker → adapter → engine → DB write. The e2e tests (`scripts/e2e_tests.py`) then verify API responses. After normalization, the worker writes to the new table — the e2e tests validate the full round-trip is preserved.
- All existing unit tests (`api/tests/engine/`) test the pure evaluation engine — unaffected by storage changes.
- All existing API integration tests that assert on response shapes must pass unchanged.
- UI component tests mock API responses, not DB rows — unaffected.

### Infrastructure
- Redis usage increases (currently queue-only, now queue + cache)
- Monitor Redis memory usage after rollout

## API Contract Principle

This refactor **preserves the existing API contract exactly**. The UI receives the same `EvaluationSummary` and `EvaluationDetail` response shapes — `indicator_results` remains a JSON array in the API response, just constructed from joined tables instead of a JSONB column. The "fewer requests is better" principle holds: the UI should continue fetching indicator data as part of the evaluation detail response, not via separate requests. The normalization is storage-internal; the API is the boundary.
