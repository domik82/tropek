# Known Issues and Workarounds

Collected from all six research reports (2026-05-01). Organized by category
with severity indicators and actionability notes.

---

## Dead Code

### `CategoryInUseError` is declared but never raised

**File:** `api/tropek/modules/quality_gate/repositories/annotation_category.py:17`

The exception class is defined but never used anywhere in the codebase. The
`delete` method reassigns annotations to the "info" category instead of
raising this error.

**Severity:** Cosmetic. **Action:** Remove the dead class.

### `deactivate_slos` parameter is ignored

**File:** `api/tropek/modules/assets/repository.py:341-347`

`AssetGroupRepository.delete_group()` accepts `deactivate_slos: bool = False`
but ignores it. The parameter is kept for API compatibility and the router
still accepts it as a query parameter. Comment says SLO deactivation is now
handled via the assignment layer.

**Severity:** Cosmetic. **Action:** Remove parameter from repository and
router when the next breaking API change is made.

### `substitute_slo_variables` is a trivial wrapper

**File:** `api/tropek/modules/quality_gate/evaluation_engine/variables.py:50-63`

Just calls `substitute_variables` with no additional logic. Exists for
semantic clarity but adds no behavior.

**Severity:** Cosmetic. **Action:** Could be replaced with an alias. Low
priority.

### `method_criteria` / Level-2 expansion not implemented

**File:** `api/tropek/modules/slo_registry/schemas.py:45-56, 113`

`MethodCriteriaOverride` is stored on `SLODefinition.method_criteria` but
Level-2 expansion during SLO group generation is explicitly marked as not yet
implemented (docstring L55-56). The field is persisted and round-tripped but
has no runtime effect.

**Severity:** Low -- the field is correctly stored and serialized; it just has
no consumer yet. **Action:** Implement or document as future work.

---

## Type Safety Gaps

### `IndicatorResult.status` is `str`, not `IndicatorStatus`

**File:** `api/tropek/modules/quality_gate/evaluation_engine/result_models.py:85`

The `status` field is typed as `str` despite being populated from
`IndicatorStatus.value` (in `evaluator.py:77`). Consumers must compare
against raw strings rather than enum members.

**Severity:** Medium -- weakens type safety at the serialization boundary.
**Action:** Change to `IndicatorStatus` type. Requires checking all consumers.

### `build_slo_model()` uses four `type: ignore[attr-defined]`

**File:** `api/tropek/modules/quality_gate/workflows/execution/evaluation_helpers.py:73-79, 101, 105`

The function accepts `object` but relies on duck typing for ORM attributes
(`objectives`, `total_score_pass_threshold`, etc.). Six `type: ignore`
comments are needed.

**Severity:** Medium -- masks potential attribute errors. **Action:** Accept a
`Protocol` type or the concrete `SLODefinition` model instead of `object`.

### `type: ignore` comments in `main.py`

**File:** `api/tropek/main.py`

| Line | Suppression | Reason |
|------|------------|--------|
| 54 | `type: ignore[attr-defined]` | `redis.aclose()` -- aioredis type stubs incomplete |
| 62-65 | `type: ignore[arg-type]` (x4) | Exception handler registration -- FastAPI type mismatch |
| 199 | `type: ignore[method-assign]` | Custom OpenAPI override |

**Severity:** Low -- these are upstream library type stub gaps.
**Action:** Intentional tradeoffs. Monitor for upstream fixes.

### `type: ignore` comments in `tag_mixin.py`

**File:** `api/tropek/modules/common/tag_mixin.py:23, 45`

Two `type: ignore[attr-defined]` for model attribute access and `has_key`
method. The mixin uses `_tag_model` ClassVar but mypy cannot verify attribute
access on the generic model reference.

**Severity:** Low. **Action:** Intentional tradeoff of the mixin pattern.

---

## Naming Violations

### `stmt` variable in `list_evaluation_names`

**File:** `api/tropek/modules/quality_gate/repositories/evaluation.py:594`

The variable is named `stmt`, which CLAUDE.md explicitly forbids ("No cryptic
abbreviations like `stmt`"). Should be renamed to something like
`evaluation_names_query`.

**Severity:** Low -- code style violation. **Action:** Rename.

### `SLOGroupRepository` uses `.astext` instead of `.as_string()`

**File:** `api/tropek/modules/slo_groups/repository.py:69`

Uses `SLOGroup.tags[tag_key].astext` while all other repositories using
`TagQueryMixin` use `.as_string()`. Functionally equivalent but syntactically
inconsistent.

**Severity:** Cosmetic. **Action:** Align with other repositories.

---

## Production Code Quality

### `assert` in production code

**File:** `api/tropek/modules/quality_gate/router.py:727, 784`

`assert fetched is not None` after `get_annotation_by_id(created.id)`. These
assertions would be silently removed if Python is run with `-O` (optimized
mode), potentially causing `None` to reach response serialization.

**Severity:** Medium. **Action:** Replace with explicit `if fetched is None:
raise` or use the `NotFoundError` pattern.

### `_redis` private attribute accessed publicly

**Files:**
- `api/tropek/queue.py:103-104, 199-201`
- `api/tropek/modules/quality_gate/shared/dependencies.py:50`
- `api/tropek/modules/quality_gate/workflows/execution/evaluation_executor.py:521`

`RedisCache._redis` is accessed directly in four locations to get the
underlying `redis.asyncio` client. The attribute is documented as private but
used publicly. Both `dependencies.py` and `evaluation_executor.py` have
comments noting these call sites should be updated together when refactored.

**Severity:** Low -- working correctly, documented as intentional.
**Action:** Expose the underlying client via a property or method on
`RedisCache`.

### `SLOTestService` catches all exceptions silently

**File:** `api/tropek/modules/slo_registry/service.py:130`

`except Exception` (`BLE001` suppressed) when substituting variables into
queries. Failed substitutions are silently replaced with `'ERROR: {e}'`
strings, which are then sent to the adapter as invalid queries.

**Severity:** Medium -- masks real errors. **Action:** Narrow the exception
type or propagate the error to the caller.

### Silent SLO resolution failures in trigger

**File:** `api/tropek/modules/quality_gate/workflows/trigger/trigger_service.py:69`

`except EvaluationError: continue` silently skips SLOs that fail to resolve.
No feedback is given to the caller about which SLOs were skipped.

**Severity:** Medium -- user gets no indication that some SLOs were not
evaluated. **Action:** Collect skipped SLOs and include them in the response.

### `SLOGroupRouter` has complex orchestration in router

**File:** `api/tropek/modules/slo_groups/router.py`

~200 lines of helper functions (`_build_group_read`, `_load_template_slo`,
`_resolve_sli_indicators`, `_build_generated_slo_params`,
`_apply_regeneration_plan`, `_build_standalone_slo_params`,
`_shrink_gen_variables`) that would typically live in a service class. This
makes the router harder to test in isolation.

**Severity:** Low -- working correctly. **Action:** Extract to a service class
when the module needs significant changes.

### Assignment router manually sets ORM relationships

**File:** `api/tropek/modules/assignments/router.py:120-122`

Manually sets `row.slo_definition = slo_def` and `row.data_source = datasource`
on ORM rows after upsert because the repository does not eager-load
relationships. This is a workaround for the read helper accessing
`.slo_definition.version` and `.data_source.name`.

**Severity:** Low -- works but fragile. **Action:** Add eager loading to the
repository upsert method.

---

## Performance Considerations

### No pagination on timeline endpoint

**File:** `api/tropek/modules/asset_meta/repositories.py:79-127`

Neither `load_snapshots_for_derivation` nor the GET timeline endpoint impose
any limit on the number of snapshots or items returned. An asset with
thousands of snapshots would load all of them into memory.

**Severity:** Medium -- could cause memory issues with large datasets.
**Action:** Add a limit or pagination.

### Three-query load strategy for timeline

**File:** `api/tropek/modules/asset_meta/repositories.py:79-127`

Issues three separate SQL queries (snapshots, values, closures) and groups in
Python. Simple but could be slower than a single JOIN for assets with many
snapshots.

**Severity:** Low -- acceptable for current scale. **Action:** Monitor and
optimize if needed.

### Python-side recursive subgroup traversal

**File:** `api/tropek/modules/assets/repository.py:329-339`

`_collect_subgroup_ids()` uses Python-side recursion to collect descendant
group IDs, issuing one SQL query per hierarchy level. A SQL recursive CTE
would be more efficient for deep hierarchies.

**Severity:** Low -- hierarchies are typically shallow. **Action:** Replace
with SQL CTE if deep hierarchies become common.

### `IndicatorRepository.bulk_insert` is not truly bulk

**File:** `api/tropek/modules/quality_gate/repositories/indicator.py:57-77`

Iterates and adds each row individually via `session.add()`, then flushes
once. Not a true bulk insert (`insert().values(rows)`). Negligible for
typical SLOs with 5-20 indicators.

**Severity:** Low. **Action:** Convert to true bulk insert if large SLOs
become common.

### Baseline pin filter executes separate query

**File:** `api/tropek/modules/quality_gate/repositories/baseline.py:164-182`

`_apply_pin_filter` runs a separate SELECT to find the active pin instead of
using a correlated subquery or CTE. Two round-trips per baseline query.

**Severity:** Low -- baseline queries are relatively rare (one per evaluation).
**Action:** Acceptable tradeoff for simplicity.

### Correlated subquery in trend query

**File:** `api/tropek/modules/quality_gate/repositories/trend.py:215-222`

`get_trend_by_domain` has a correlated scalar subquery for `total_weight` that
runs once per outer row. Could become expensive for large result sets.

**Severity:** Low -- time-range filter limits row count. **Action:** Monitor.

### Metric heatmap endpoint has no cache

**File:** `api/tropek/modules/quality_gate/router.py:225-299`

The `/evaluations/heatmap/by-metric` endpoint builds its response entirely
from the database without Redis caching, unlike the grouped heatmap endpoint.

**Severity:** Low -- likely less frequently used. **Action:** Add caching if
usage increases.

---

## Design Inconsistencies

### `SLOGroupRepository` does not use `TagQueryMixin`

**File:** `api/tropek/modules/slo_groups/repository.py`

Despite having a `tags` column, implements its own tag filtering in
`list_all()` rather than inheriting `TagQueryMixin`. Does not expose
`tag-keys` or `tag-values` endpoints in its router, unlike SLO, SLI,
datasource, and asset registries.

**Severity:** Low -- inconsistent but functional. **Action:** Adopt
`TagQueryMixin` for consistency.

### Sub-settings reinstantiation

**File:** `api/tropek/config.py:213-251`

`Settings` properties create new `DatabaseSettings()`, `CacheSettings()`,
etc. on every access. Only `QueueSettings` is cached in `_queue_settings`.
The `@lru_cache` on `get_settings()` does not help because properties are on
the instance.

**Severity:** Low -- Pydantic Settings are lightweight. **Action:** Cache all
sub-settings properties for consistency, or document as intentional.

### Protocol usage is partial

**Files:**
- `api/tropek/modules/quality_gate/shared/protocols.py` (defines protocols)
- `api/tropek/modules/quality_gate/workflows/trigger/trigger_resolver.py` (uses protocols)
- `api/tropek/modules/quality_gate/workflows/execution/evaluation_executor.py` (does NOT use protocols)

The trigger resolver uses `Protocol` types for repository access, enabling
testing with stubs. The execution layer and re-evaluation service construct
repositories directly, creating asymmetric testability.

**Severity:** Low -- intentional tradeoff. **Action:** Consider extending
protocol usage to execution layer for consistency.

### Pipeline stages duplicated in summary endpoint

**File:** `api/tropek/modules/asset_meta/service.py:76-102`

`get_timeline_summary` manually chains three pipeline stages (derive, resolve
conflicts, clip) rather than calling `build_timeline_response` and counting
the result. If the pipeline gains new stages, the summary path must be
updated independently.

**Severity:** Low -- intentional optimization to skip tree builder and item
emitter. **Action:** Document the coupling.

### Random color assignment for groups

**File:** `api/tropek/modules/assets/repository.py:285`

`random.choice()` from a fixed 10-color palette (`S311` suppressed). Two
groups created in sequence could get the same color. No uniqueness check.

**Severity:** Cosmetic. **Action:** Consider round-robin or uniqueness check.

### URL naming convention mismatch

**File:** `api/tropek/modules/quality_gate/router.py`

Two patterns coexist:
- Plural collection routes: `/evaluations`, `/evaluations/heatmap`
- Singular resource routes: `/evaluation/{eval_id}`

Documented inline as "new singular single-resource routes" (L583).

**Severity:** Cosmetic -- documented as intentional migration.
**Action:** Complete migration when breaking changes are acceptable.

---

## Lint Suppressions

### `noqa: E712` -- SQLAlchemy boolean comparisons

**Files:** `baseline.py:157`, `evaluation.py` (multiple sites), `slo_registry/repository.py:113, 168, 193`, `sli_registry/repository.py:87, 151`

SQLAlchemy requires `Model.active == True` (not `is True`) to generate proper
SQL. The linter flags this as a style violation.

**Severity:** Cosmetic -- correct usage. **Action:** Consider project-wide
`E712` suppression for SQLAlchemy code.

### `noqa: PLR0913` -- too many arguments

**Files:**
- `api/tropek/modules/quality_gate/workflows/re_evaluation/re_evaluation_service.py:185, 232, 287`
- `api/tropek/modules/quality_gate/repositories/baseline.py:82`
- `api/tropek/modules/quality_gate/router.py` (list_evaluations)

Functions with many parameters due to domain complexity.

**Severity:** Cosmetic. **Action:** Consider parameter objects for the most
egregious cases.

### `noqa: N815` -- camelCase field name

**File:** `api/tropek/modules/asset_meta/timeline/types.py:31`

`ClippedSpan.className` uses camelCase to match the vis-timeline wire format.

**Severity:** Cosmetic -- intentional. **Action:** None needed.

---

## Missing Features

### GroupScope not implemented for split re-evaluate endpoints

**File:** `api/tropek/modules/quality_gate/workflows/re_evaluation/re_evaluation_service.py:539`

`_scope_to_asset_name()` raises `ValueError('group scope is not yet supported
on split re-evaluate endpoints')` for `GroupScope`. Only `AssetScope` is
supported.

**Severity:** Medium -- functional gap. **Action:** Implement group scope
support.

---

## Fragile Patterns

### `EvaluationResult.model_rebuild()` needed in test

**File:** `api/tests/quality_gate/evaluation_engine/test_evaluator_failures.py:16`

`EvaluationResult.model_rebuild()` is called at module level to resolve
Pydantic forward references. Not needed in production code, suggesting the
import order in production avoids the issue, but this is fragile.

**Severity:** Low -- only affects test imports. **Action:** Monitor; no fix
needed unless production imports break.

### `_percentile` uses floor-index, not interpolation

**File:** `api/tropek/modules/quality_gate/evaluation_engine/criteria.py:192-196`

For small datasets, gives coarse results (e.g., p90 of 10 values returns the
maximum). This matches Keptn's Go implementation intentionally.

**Severity:** Low -- intentional Keptn compatibility. **Action:** Document the
behavior difference from statistical libraries.

### Relative criteria with negative baselines

With `<=+10%` and baseline=-100: target becomes -110. A value of -90 is
"better" but fails because -90 > -110. Tests document this
(`test_criteria_edge_cases.py:29-33`) but there is no special handling.
Matches Go behavior.

**Severity:** Low -- documented, consistent with Keptn. **Action:** None.

### `RESULT_RANK` includes `invalidated` with no enum member

**File:** `api/tropek/modules/quality_gate/evaluation_engine/constants.py:82`

The rank dict maps 5 values including `invalidated`, but neither
`IndicatorStatus` nor `EvaluationOutcome` has an `invalidated` member. It
exists only in the rank dict for use at the persistence layer.

**Severity:** Low -- works correctly but surprising.
**Action:** Add a comment explaining why `invalidated` is in the rank dict
but not in the enums.

### Worker httpx timeout applied twice

**File:** `api/tropek/queue.py:94-97, 176-178`

The httpx client in `_worker_startup` is configured with
`timeout=settings.reliability.adapter_timeout_seconds`, and
`HttpAdapterClient` also receives the same timeout. The timeout is applied at
both the httpx level and the adapter client level.

**Severity:** Low -- probably intentional (httpx as fallback). **Action:**
Document the double-timeout design.

### OpenAPI schema patching workaround

**File:** `api/tropek/main.py:112-143`

`_inject_property_names_pattern()` recursively patches the OpenAPI schema
because Pydantic v2 does not emit `propertyNames.pattern` from
`patternProperties`. Comment says "delete when Pydantic emits
propertyNames.pattern natively."

**Severity:** Low -- working workaround. **Action:** Remove when Pydantic
adds native support.

### Schemathesis-only OpenAPI annotations in asset meta

**File:** `api/tropek/modules/asset_meta/schemas.py:43-51`

`MetaSnapshotCreate.model_config` includes `json_schema_extra` with `anyOf`
purely to guide schemathesis fuzzing. The model validator is the runtime
authority.

**Severity:** Cosmetic. **Action:** None needed; well documented.

### `SLOTestService._build_variables` uses unnecessary `getattr`

**File:** `api/tropek/modules/slo_registry/service.py:114-118`

Uses `getattr(asset, 'variables', {})` and `getattr(asset, 'tags', {})` but
the `Asset` ORM model always has these columns. Defensive but unnecessary.

**Severity:** Cosmetic. **Action:** Replace with direct attribute access.
