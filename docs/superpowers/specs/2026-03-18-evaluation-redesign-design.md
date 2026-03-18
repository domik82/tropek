# Evaluation System Redesign

> Redesign evaluation baseline logic: rename `test_name` to `evaluation_name`, switch baseline
> scoping from name-based to `asset_id + slo_name`, add comparison rules for tag-based baseline
> selection, introduce SLI/SLO version compatibility markers, and build a re-evaluation engine
> that re-scores evaluations from stored SLI values.

## Context

The current baseline logic in `get_baselines()` scopes by `Evaluation.name` (the `test_name`
field). This is fragile: if a caller passes a commit hash or build number, every evaluation gets a
unique name and finds no baselines. TROPEK has proper `asset_id` and `slo_name` foreign keys on
evaluations — these are the correct natural scope.

Additionally, the system needs to handle several real-world scenarios that the current design
does not support:

- Comparing feature-branch evaluations against main-branch baselines
- Accepting new performance baselines after intentional changes (e.g., response time 2s to 3s)
- Bulk re-evaluation after SLO threshold changes
- SLI/SLO query changes that make old metric values incomparable
- Out-of-order evaluation completion during bulk imports or migrations

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Rename `test_name` | `evaluation_name` everywhere | Tool evaluates prod data too, not just tests |
| Primary baseline scope | `asset_id + slo_name` | Natural domain key; `name` is a free-form label |
| Period start guard | `period_start < current` on baseline query | Prevents logically impossible future-looking baselines |
| Tag-based comparison | Rules system on `AssetSLOLink` | Flexible branch/release/env comparison without hardcoded logic |
| SLI/SLO version compat | `comparable_from_version` column | Controls whether old metric values are valid baselines |
| Re-evaluation | Re-score from stored SLI values | Fixes bulk ordering, SLO changes, accepted perf shifts |
| Re-eval data handling | Overwrite in place + annotation | Simple, clean; annotation captures what changed |
| Comparison rule storage | On `AssetSLOLink` | Rules are specific to "this asset with this SLO" |
| Default comparison (no rules) | Compare to any recent eval for `asset_id + slo_name` | Permissive; works out of the box without configuration |

---

## Change 1: Rename `test_name` to `evaluation_name`

### Affected locations

| Location | Current | New |
|---|---|---|
| `Evaluation.name` | DB column `name` | Rename column to `evaluation_name` |
| `create_pending(name=...)` | parameter | `evaluation_name=` |
| `TriggerRequest.test_name` | schema field (end-to-end-wiring worktree) | `evaluation_name` |
| `BatchTriggerRequest.test_name` | schema field (end-to-end-wiring worktree) | `evaluation_name` |
| `SLIValue.test_name` | hypertable column | `evaluation_name` |
| `build_variables(..., test_name=)` | param + `$test_name` token | `evaluation_name=` / `$evaluation_name` |
| `worker.py` line 198 | `test_name=ev.name` | `evaluation_name=ev.evaluation_name` |
| Seed script | `f"seed-{asset_idx}"` | `f"seed-{asset_idx}"` (value unchanged, param name changes) |
| `get_trend()` in repository | `test_name` filter on SLIValue | `evaluation_name` |
| Index `idx_evaluations_name` | on `name` | on `evaluation_name` |

### Migration

Alembic autogenerate: `ALTER TABLE evaluations RENAME COLUMN name TO evaluation_name`. Same for
`sli_values.test_name` to `sli_values.evaluation_name`. Update indexes.

The `$test_name` variable token in SLI query templates must remain supported for backward
compatibility with existing SLI definitions. Add `$evaluation_name` as the canonical token;
`$test_name` maps to the same value.

---

## Change 2: Baseline Scope — `asset_id + slo_name`

### Current `get_baselines()` signature

```python
async def get_baselines(
    self, *, name: str, scope_tags: list[str], asset_snapshot: dict,
    include_result_with_score: str, limit: int, sli_name: str | None = None,
    asset_id: uuid.UUID | None = None, slo_name: str | None = None,
) -> list[Evaluation]
```

### New signature

```python
async def get_baselines(
    self, *,
    asset_id: uuid.UUID,
    slo_name: str,
    period_start_before: datetime,
    include_result_with_score: str,
    limit: int,
    tag_filters: dict[str, str] | None = None,
    sli_version_range: tuple[int, int] | None = None,
) -> list[Evaluation]
```

### Query logic

```python
q = select(Evaluation).where(
    Evaluation.asset_id == asset_id,
    Evaluation.slo_name == slo_name,
    Evaluation.period_start < period_start_before,  # no future-looking
    Evaluation.status == EvaluationStatus.COMPLETED,
    Evaluation.invalidated == False,
)

# Result quality filter
if include_result_with_score == "pass":
    q = q.where(Evaluation.result == "pass")
elif include_result_with_score == "pass_or_warn":
    q = q.where(Evaluation.result.in_(["pass", "warning"]))

# Tag-based comparison (from resolved comparison rule)
if tag_filters:
    for key, value in tag_filters.items():
        q = q.where(
            Evaluation.evaluation_metadata[(key,)].as_string() == value
        )

# SLI/SLO version compatibility
# Evaluations with null sli_version are excluded when a range is specified —
# they have no version metadata and cannot be verified as compatible.
if sli_version_range:
    q = q.where(Evaluation.sli_version.is_not(None))
    q = q.where(Evaluation.sli_version >= sli_version_range[0])
    q = q.where(Evaluation.sli_version <= sli_version_range[1])

# Pin-aware floor (existing worktree logic, unchanged)
# ... baseline_pinned_at check ...

q = q.order_by(Evaluation.period_start.desc()).limit(limit)
```

### Removed parameters

- `name` — no longer used for scoping; `evaluation_name` is a free-form label
- `scope_tags` — replaced by `tag_filters` (resolved from comparison rules)
- `asset_snapshot` — tag values now come from `evaluation_metadata`, resolved by the caller
- `sli_name` — replaced by `sli_version_range` (version compatibility is the correct concern)

---

## Change 3: Evaluation Tags

### Where tags live

Tags are stored in the existing `evaluation_metadata` JSONB column on `Evaluation`. No new
column needed. The `evaluation_metadata` field already accepts arbitrary key-value pairs from
the API caller.

### How tags are populated

1. **Explicitly via API:** Caller sends `metadata: {"branch": "feature-x", "env": "staging"}`
   in the trigger request. Already supported.
2. **From asset labels:** At trigger time, asset labels are merged into `evaluation_metadata`
   as defaults (caller-provided values take precedence). This happens in the trigger resolver.

### Tag vs asset label distinction

- **Asset labels** (on `Asset`): stable infrastructure properties (os, arch, region, team).
  Describe the target being evaluated.
- **Evaluation tags** (in `evaluation_metadata`): per-run context (branch, commit, env,
  pipeline_id). Describe the circumstances of the evaluation.

Both are available for comparison rules, but they serve different purposes.

---

## Change 4: Comparison Rules

### Data model

Comparison rules are stored on `AssetSLOLink` in a new `comparison_rules` JSONB column:

```python
class AssetSLOLink(Base):
    # ... existing columns ...
    comparison_rules: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'"), default=list
    )
```

### Rule structure

```json
[
  {
    "match": {"branch": "main"},
    "compare_to": {"branch": "main"}
  },
  {
    "match": {"branch": "!main"},
    "compare_to": {"branch": "main"}
  },
  {
    "match": {"branch": "release-*"},
    "compare_to": {"pinned": true}
  },
  {
    "match": {},
    "compare_to": {}
  }
]
```

### Rule validation

A Pydantic model validates the `comparison_rules` structure at write time (via the
`PUT /asset-slo-links/{id}/comparison-rules` endpoint). Invalid rules are rejected with 422.
The model enforces:
- `match` must be a `dict[str, str]`
- `compare_to` must be a `dict[str, str | bool]`
- At most one catch-all rule (`match: {}`) and it must be last

### Rule semantics

- **`match`**: tag conditions on the current evaluation. All conditions must match (AND logic).
  - `"branch": "main"` — exact match
  - `"branch": "!main"` — negation (any value except "main")
  - `"branch": "release-*"` — prefix glob
  - `{}` — matches everything (catch-all, must be last)

- **`compare_to`**: tag filters applied to the baseline query.
  - `{"branch": "main"}` — only use baselines where `evaluation_metadata.branch == "main"`
  - `{"pinned": true}` — only use baselines at or after the pinned evaluation
  - `{}` — no tag filtering (compare to any recent evaluation)

### Resolution algorithm

```
1. Get current evaluation's tags from evaluation_metadata
2. Load comparison_rules from the AssetSLOLink for this asset_id + slo_name
3. For each rule (in order):
   a. Check if all match conditions are satisfied by current tags
   b. If yes: use compare_to as the tag_filters for get_baselines()
   c. If no: try next rule
4. If no rule matches: use empty tag_filters (permissive default)
```

### Rule override via API

The trigger request can optionally include a `comparison_rule` that overrides the stored rules
for this evaluation only:

```json
POST /evaluations
{
  "asset_name": "checkout-api",
  "evaluation_name": "hotfix-check",
  "slo_name": "http-availability-slo",
  "comparison_rule": {"compare_to": {"branch": "release-1.0"}},
  ...
}
```

When provided, this rule is used instead of the stored rules on `AssetSLOLink`. The override
is stored in `evaluation_metadata._applied_comparison_rule` (underscore prefix marks it as
system-managed, not caller-provided) for observability. Structure:

```json
{
  "_applied_comparison_rule": {
    "source": "request_override",
    "compare_to": {"branch": "release-1.0"}
  }
}
```

When rules come from `AssetSLOLink`, the structure is:

```json
{
  "_applied_comparison_rule": {
    "source": "asset_slo_link",
    "rule_index": 1,
    "match": {"branch": "!main"},
    "compare_to": {"branch": "main"}
  }
}
```

### Default behavior (no rules configured)

When `comparison_rules` is empty (default), baseline resolution uses `asset_id + slo_name`
with no tag filtering. This matches the current behavior (minus the name-based scoping).

### Phased rollout

| Phase | Scope |
|---|---|
| P1 | Tags on evaluations (API + asset label merge). Default comparison: `asset_id + slo_name`, no tag filtering. |
| P2 | Comparison rules on `AssetSLOLink`. Match/compare_to with exact match and negation. |
| P3 | Prefix glob matching in rules. Rule override via API request. UI rule editor. |

---

## Change 5: SLI/SLO Version Compatibility

### Problem

SLI queries can change meaning across versions (e.g., `sum(requests) over 14d` to
`sum(requests) over 28d`). Comparing metric values across incompatible query versions produces
meaningless baselines. Conversely, some version bumps are cosmetic (comment changes, variable
renames) and values remain comparable.

### Data model

New column on `SLIDefinition` and `SLODefinition`:

```python
comparable_from_version: Mapped[int] = mapped_column(
    Integer, nullable=False, server_default=text("1")
)
```

### Semantics

- **Version 1** (first version): `comparable_from_version = 1`. Baselines include only v1
  evaluations (itself — there are no prior versions).
- **Version N** (subsequent): `comparable_from_version` defaults to the previous version
  (N - 1), meaning the new version is assumed compatible with the prior one. The user can
  change this.

### Version creation flow

Version numbers are already auto-incremented from DB (`SELECT max(version) + 1 FOR UPDATE`).
The `comparable_from_version` field is handled as follows:

**Via API (programmatic):**
- `comparable_from_version` is optional in the create request
- If omitted: set to `previous_version` (i.e., `max_version` before increment — the version
  that was just superseded). For version 1, set to `1`.
- If provided: use the caller's value (must be >= 1 and <= new version)

**Via UI:**
- When editing an SLI/SLO, the version bumps automatically (user does not choose version number)
- A "comparable from" dropdown shows the default pre-selected to the previous version
- A warning banner explains: "Values from versions before this will not be used as baselines"
- A "set to current version" button lets the user quickly reset baselines (equivalent to
  setting `comparable_from_version = new_version`)
- For version 1, the field is read-only and shows `1`

### Baseline query integration

At baseline resolution time:

```python
# Load current evaluation's SLI definition
sli_def = await sli_repo.get_version(ev.sli_name, ev.sli_version)

# Build version range: [comparable_from_version, current_version]
sli_version_range = (sli_def.comparable_from_version, sli_def.version)

# Pass to get_baselines()
baselines = await repo.get_baselines(
    ...,
    sli_version_range=sli_version_range,
)
```

### Edge cases

- **Bug in SLI query (v4 broken, v5 fixed):** Create v5 with `comparable_from_version = 1`.
  The range filter `sli_version >= 1 AND sli_version <= 5` includes v4 evaluations. To
  exclude v4 data, invalidate the v4 evaluations (set `invalidated = true`). The baseline
  query already filters out invalidated evaluations. This is the correct approach — if the
  query was broken, the data is bad and should be marked as such regardless of baseline logic.
- **Complete query rewrite:** Create v5 with `comparable_from_version = 5`. Baselines start
  from scratch — only v5+ evaluations count.
- **Cosmetic change:** Create v5 with `comparable_from_version = 1` (or accept default of `4`).
  All prior evaluations remain valid baselines.

### SLO version compatibility

Same concept applies to `SLODefinition.comparable_from_version`. When SLO thresholds change
(pass from `<2s` to `<4s`), the scores from prior evaluations are not comparable. The user
sets `comparable_from_version` to the current version to reset.

However, SLO version changes are better handled by **re-evaluation** (Change 6) — re-scoring
old evaluations against the new SLO produces correct results. The `comparable_from_version` on
SLO is a lighter-weight alternative for cases where re-evaluation is not desired.

---

## Change 6: Re-evaluation Engine

### Purpose

Re-evaluate completed evaluations from their stored SLI values without re-fetching metrics from
the adapter. This re-runs the scoring engine with current (or specified) SLO criteria and
freshly computed baselines.

### API

```
POST /evaluations/re-evaluate
```

#### Request body

```json
{
  "asset_name": "checkout-api",
  "slo_name": "http-availability-slo",

  "from_date": "2026-03-10T00:00:00Z",
  "from_baseline": false,
  "from_evaluation_id": null,

  "slo_version": null,
  "dry_run": false
}
```

**Scope parameters** (exactly one required):

| Parameter | Meaning |
|---|---|
| `from_date` | Re-evaluate all evaluations with `period_start >= from_date` |
| `from_baseline` | Re-evaluate from the last pinned baseline evaluation onward |
| `from_evaluation_id` | Re-evaluate from this specific evaluation onward (inclusive) |

**Optional parameters:**

| Parameter | Default | Meaning |
|---|---|---|
| `slo_version` | latest | Use this SLO version for scoring (enables re-eval with changed thresholds) |
| `dry_run` | `false` | If `true`, return what would change without writing to DB |

#### Response

```json
{
  "affected_evaluations": 8,
  "slo_version_used": 3,
  "results": [
    {
      "id": "uuid",
      "evaluation_name": "nightly-run",
      "period_start": "2026-03-10T00:00:00Z",
      "period_end": "2026-03-10T00:30:00Z",
      "old_result": "fail",
      "new_result": "pass",
      "old_score": 45.0,
      "new_score": 92.0
    }
  ]
}
```

### Execution flow

```
1. Resolve asset_id from asset_name
2. Determine starting point (from_date / pinned baseline / specific eval)
3. Load all evaluations for asset_id + slo_name with period_start >= start,
   ordered by period_start ASC
4. Load the SLO definition (specified version or latest)
5. For each evaluation in chronological order:
   a. Load stored SLI values from TimescaleDB hypertable
   b. Reconstruct metrics dict: {metric_name: value}
   c. Resolve baselines using get_baselines() — only previously-processed
      evaluations in this re-eval run are eligible (cascading baselines)
   d. Run evaluate(slo, metrics, baselines)
   e. If dry_run: record diff, continue
   f. If not dry_run:
      - Store original_result if not already set (first re-eval preserves it)
      - Update result, score, indicator_results
      - Add annotation: "re-evaluated: {old_result} -> {new_result},
        score {old_score} -> {new_score}"
6. Return summary
```

### Cascading baselines

During re-evaluation, baselines are resolved chronologically. Each re-evaluated evaluation
becomes available as a baseline for subsequent ones. This ensures that the re-evaluation
produces the same results as if the evaluations had originally run in order with the correct
SLO.

Implementation: the re-evaluation loop maintains a running list of re-evaluated eval IDs. An
additional `restrict_to_ids: list[uuid.UUID] | None` parameter is added to `get_baselines()`.
When provided, the query adds `WHERE id = ANY(restrict_to_ids)` to limit baselines to the
specified set. The re-evaluation loop passes the union of:
- All evaluation IDs before the re-eval window (valid pre-existing baselines)
- All evaluation IDs already processed in the current re-eval run

### Updated `get_baselines()` signature (with restrict parameter)

```python
async def get_baselines(
    self, *,
    asset_id: uuid.UUID,
    slo_name: str,
    period_start_before: datetime,
    include_result_with_score: str,
    limit: int,
    tag_filters: dict[str, str] | None = None,
    sli_version_range: tuple[int, int] | None = None,
    restrict_to_ids: list[uuid.UUID] | None = None,
) -> list[Evaluation]
```

When `restrict_to_ids` is provided:
```python
if restrict_to_ids is not None:
    q = q.where(Evaluation.id.in_(restrict_to_ids))
```

Normal evaluation flow passes `restrict_to_ids=None` (no restriction). Re-evaluation passes
the curated list.

### Data integrity

- `original_result` is set on the first re-evaluation and never overwritten. Multiple
  re-evaluations preserve the original. The `original_result` column already exists in the
  worktree branch.
- `original_score` is stored in `job_stats.original_score` (JSONB) rather than a dedicated
  column, since it is only needed for annotation/audit purposes, not for queries.
- Each re-evaluation adds an annotation with the change details. The annotation trail
  provides a complete audit history.
- The `job_stats` field is updated with `{"re_evaluated_at": timestamp, "re_eval_slo_version": N,
  "original_score": 45.0}`.

### Relationship to mark-as-baseline

The "mark as new baseline" action (pin) and re-evaluation are complementary:

1. User pins an evaluation as the new baseline (sets `baseline_pinned_at`)
2. User triggers re-evaluation from that pinned evaluation
3. All subsequent evaluations are re-scored with the pinned evaluation as the baseline floor

This handles the "week of failures after intentional performance change" scenario:

```
Day 1-22: 2s response, baseline=2s, SLO <=+10%, pass
Day 23:   3s response, baseline=2s, +50% → fail
Day 24-28: 3s response, baseline shifts slowly, still fail
   ↓
User pins Day 23 as new baseline
User triggers re-evaluation from Day 23
   ↓
Day 23: 3s, no prior baseline in pin window → relative criteria pass (no history)
Day 24: 3s vs baseline 3s → 0% change → pass
Day 25-28: 3s vs baseline avg(3s, 3s, ...) → pass
```

If the SLO used fixed criteria (`<2s`) instead of relative, the user would also need to
create a new SLO version with `<4s` and pass `slo_version` to the re-evaluate endpoint.

---

## Change 7: Period Start Guard

### Rationale

A baseline must always represent the past relative to the evaluation being scored. An
evaluation with `period_start = March 15` should never use an evaluation from March 20 as
a baseline, regardless of which one completed first.

### Implementation

Add `period_start_before: datetime` as a required parameter to `get_baselines()`. The caller
passes the current evaluation's `period_start`. The query adds:

```python
q = q.where(Evaluation.period_start < period_start_before)
```

This is a logical correctness invariant, not a solution for the bulk ordering problem (which
re-evaluation solves).

### Interaction with pin-aware filtering

The `period_start <` guard and the pin floor (`period_start >= pinned_eval.period_start`)
compose correctly:

```
WHERE period_start >= pin_floor AND period_start < current_eval.period_start
```

This creates a window: "baselines from the pin point up to (but not including) the current
evaluation."

---

## Migration Summary

### New columns

| Table | Column | Type | Default |
|---|---|---|---|
| `sli_definitions` | `comparable_from_version` | `INTEGER NOT NULL` | `1` |
| `slo_definitions` | `comparable_from_version` | `INTEGER NOT NULL` | `1` |
| `asset_slo_links` | `comparison_rules` | `JSONB NOT NULL` | `'[]'` |

### Renamed columns

| Table | Old | New |
|---|---|---|
| `evaluations` | `name` | `evaluation_name` |
| `sli_values` | `test_name` | `evaluation_name` |

### New indexes

| Index | Columns | Condition |
|---|---|---|
| `idx_evaluations_baseline_lookup` | `(asset_id, slo_name, period_start DESC)` | `WHERE status = 'completed' AND invalidated = false` |

This composite partial index covers the hot path for `get_baselines()`.

### Updated indexes

| Old | New |
|---|---|
| `idx_evaluations_name` on `name` | `idx_evaluations_evaluation_name` on `evaluation_name` |

### Existing columns used (no changes)

- `evaluations.evaluation_metadata` — used for tag storage (already exists)
- `evaluations.baseline_pinned_at` — used by pin-aware baseline (worktree branch)
- `evaluations.original_result` — used by re-evaluation (worktree branch)

---

## API Changes Summary

### Modified endpoints

| Endpoint | Change |
|---|---|
| `POST /evaluations` | `test_name` field renamed to `evaluation_name`. Optional `comparison_rule` added. |
| `POST /evaluations/batch` | `test_name` field renamed to `evaluation_name`. |

### New endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/evaluations/re-evaluate` | POST | Re-evaluate from stored SLI values |
| `/asset-slo-links/{id}/comparison-rules` | GET/PUT | View and update comparison rules |

### Variable substitution

| Old token | New token | Status |
|---|---|---|
| `$test_name` | `$evaluation_name` | Both supported; `$test_name` is a backward-compat alias |

---

## Implementation Priority

| Priority | Change | Complexity | Dependencies |
|---|---|---|---|
| P0 | Rename `test_name` to `evaluation_name` | Low | None |
| P0 | Primary scope: `asset_id + slo_name` | Low | None |
| P0 | Period start guard | Low | None |
| P1 | Evaluation tags (merge asset labels into metadata at trigger time) | Low | P0 |
| P1 | Re-evaluation engine | High | P0 |
| P1 | Mark-as-baseline + re-eval integration | Medium | P0 (worktree has pin columns) |
| P1 | SLI/SLO `comparable_from_version` | Medium | P0 |
| P2 | Comparison rules on `AssetSLOLink` | High | P1 (tags) |
| P2 | Rule override via API request | Low | P2 |
| P3 | Prefix glob matching in rules | Low | P2 |
| P3 | UI rule editor | High | P2 |
| P3 | Re-evaluation with different SLO version | Medium | P1 |

---

## Testing Strategy

### Unit tests (no DB)

- Comparison rule matching: exact match, negation, glob, catch-all, no-rules-default
- SLI version range computation from `comparable_from_version`
- Variable substitution with `$evaluation_name` and `$test_name` alias
- Re-evaluation result diff computation (dry run)

### Integration tests (test DB)

- `get_baselines()` with `asset_id + slo_name` scope (replaces name-based tests)
- `get_baselines()` with `period_start_before` guard
- `get_baselines()` with `tag_filters`
- `get_baselines()` with `sli_version_range`
- Re-evaluation: creates correct annotations, preserves `original_result`, cascading baselines
- Re-evaluation: dry run returns diffs without writing
- SLI/SLO creation with `comparable_from_version` defaults
- Column rename migration (evaluation_name)
