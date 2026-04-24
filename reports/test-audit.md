# Integration Test Coverage Audit

Audited: 2026-04-24
Scope: All `@pytest.mark.integration` test files in `api/tests/`

## Summary

**All ~164 integration tests are kept.** No tests removed.

The overwhelming majority exercise repository-layer logic (direct DB calls, not HTTP) or
multi-step business workflows that Schemathesis cannot reach.

14 tests overlap in *coverage area* with Schemathesis (status codes, input validation), but
they are **designed tests for specific scenarios** while Schemathesis probes heuristically
with random inputs. Designed tests pin expected behavior and won't drift if the schema
changes — Schemathesis coverage of the same paths is incidental, not guaranteed. Both layers
provide complementary value.

---

## Schemathesis-overlapping tests (kept)

These 14 tests check status codes or input validation that Schemathesis also probes.
Kept because they are designed tests pinned to specific scenarios — Schemathesis reaches
the same paths heuristically but not deterministically.

### `quality_gate/endpoints/test_annotation_endpoints.py`

| Test | Rationale |
|---|---|
| `test_create_annotation_on_missing_eval` | Only checks 404 for nonexistent eval — Schemathesis covers 404 for invalid resource IDs |
| `test_create_run_annotation_on_missing_run` | Only checks 404 for nonexistent run — same pattern |

### `quality_gate/endpoints/test_smoke.py`

| Test | Rationale |
|---|---|
| `test_health_endpoint` | Only checks GET /health returns 200 — basic schema conformance |

### `asset_meta/db/test_ingest_endpoint.py`

| Test | Rationale |
|---|---|
| `test_post_snapshot_values_only_returns_201` | Status-code-only check on valid input |
| `test_post_snapshot_closed_only_returns_201` | Status-code-only check on valid input |
| `test_post_snapshot_empty_body_returns_422` | Empty body validation — Schemathesis covers invalid inputs |
| `test_post_snapshot_unknown_asset_returns_404` | 404 for random UUID — Schemathesis covers this |
| `test_post_snapshot_invalid_source_returns_422` | Input validation 422 — Schemathesis covers invalid field values |
| `test_post_snapshot_naive_datetime_returns_422` | Non-UTC datetime 422 — Schemathesis covers schema constraint violations |
| `test_post_snapshot_path_too_deep_returns_422` | Array length 422 — Schemathesis covers array length constraints |

### `asset_meta/db/test_summary_endpoint.py`

| Test | Rationale |
|---|---|
| `test_summary_404_for_unknown_asset` | 404 for random UUID — Schemathesis covers this |

### `asset_meta/db/test_read_endpoint.py`

| Test | Rationale |
|---|---|
| `test_validation_errors_for_missing_from_or_to` | 422 for missing required query params — Schemathesis covers this |
| `test_unknown_asset_returns_404` | 404 for random UUID — Schemathesis covers this |

### `db/test_note_category_router.py`

| Test | Rationale |
|---|---|
| `test_create_rejects_bad_color` | 422 for invalid enum value — Schemathesis covers invalid enums |
| `test_create_rejects_long_label` | 422 for string length constraint — Schemathesis covers maxLength |

---

## Tests to Keep (unique-business-logic)

### `quality_gate/db/` — Repository and DB-layer tests

All 67 tests in this directory are **unique-business-logic**. They call repository methods directly
(no HTTP), testing DB state invariants that Schemathesis cannot reach.

| File | Tests | What it covers |
|---|---|---|
| `test_column_annotations.py` | 5 | UNION query across run-level and SLO-level annotations, hidden exclusion |
| `test_indicator_repository.py` | 3 | Bulk insert/delete/reinsert, JSONB targets round-trip |
| `test_grouped_heatmap.py` | 4 | Grouped heatmap query: completed/pending filtering, eval_name filter, cache parity |
| `test_evaluation_names.py` | 2 | Distinct name aggregation with count, last_run, ordering |
| `test_heatmap_query.py` | 2 | TrendRepository: completed evals, invalidated inclusion |
| `test_grouped_heatmap_has_notes.py` | 2 | has_notes computation per-column, hidden annotation exclusion |
| `test_finalize_sweeper.py` | 6 | Sweeper job: stuck run rescue, batch limit, idempotency, fast-path convergence |
| `test_trend_query.py` | 3 | Trend JOIN with baseline, invalidated exclusion, JSONB targets |
| `test_evaluation_run_repository.py` | 8 | Run lifecycle: create, finalize worst-case, skip-when-not-done, sweeper queries |
| `test_baseline_query.py` | 2 | Baseline query: invalidated exclusion, pass-only filter |
| `test_re_evaluation.py` | 7 | Re-eval: original preservation, dry run, cascading baselines, SLO name filter |
| `test_trigger_evaluate.py` | 3 | Trigger flow: run+children creation, batch by date, unknown asset 404 |
| `test_duplicate_prevention.py` | 6 | Duplicate detection: completed/pending/failed/different-name, constraint violation |
| `test_evaluation_repository.py` | 18 | Full eval lifecycle: CRUD, annotations, baselines, tag filters, version range, override |
| `test_heatmap_cache.py` | 17 | Redis cache: round-trip, corrupted payload, cold/warm paths, mutation invalidation |
| `test_indicator_round_trip.py` | 3 | Detail/summary presenter pipeline with all field types |

### `quality_gate/endpoints/` — Endpoint behavior tests

All endpoint tests except the 3 listed above are **unique-business-logic**. They verify
multi-step behavioral sequences (override→restore, invalidate→restore, pin→unpin) that
Schemathesis cannot detect.

| File | Tests | What it covers |
|---|---|---|
| `test_override_endpoints.py` | 3 | Override status, restore, double-override preserves original |
| `test_re_evaluation_endpoints.py` | 2 | Re-eval sets original_result, second re-eval preserves original_score |
| `test_baseline_pin_endpoints.py` | 3 | Pin/unpin lifecycle, pin-new-unpins-previous atomic invariant |
| `test_annotation_endpoints.py` | 9 | Annotation CRUD, eval detail aggregation, hide, run-level, trend fan-out, eager-load regression |
| `test_invalidation_endpoints.py` | 3 | Invalidate/restore cycle, full multi-step state verification |
| `test_heatmap_endpoints.py` | 2 | Presentation rules: invalidated→'invalidated', overridden uses new result |

### `slo_registry/db/`

| File | Tests | What it covers |
|---|---|---|
| `test_slo_repository.py` | 15 | SLO versioning, deactivate, display_name, variables, tag filter, SLI reference, kind filter |

### `sli_registry/db/`

| File | Tests | What it covers |
|---|---|---|
| `test_sli_repository.py` | 13 | SLI versioning, deactivate, adapter_type, tag filter, tag aggregation |
| `test_comparable_from_version.py` | 6 | comparable_from_version defaults and overrides for both SLI and SLO |

### `assets/db/`

| File | Tests | What it covers |
|---|---|---|
| `test_asset_repositories.py` | 20 | Asset/type/group CRUD, set_default swap, delete cascade, tag aggregation, group tree |

### `assignments/db/`

| File | Tests | What it covers |
|---|---|---|
| `test_assignments.py` | 7 | SLO assignment CRUD, uniqueness, upgrade, group assignment, resolution precedence |
| `test_binding_resolution.py` | 7 | End-to-end binding discovery: direct, group, template, override rules, mixed types |

### `datasource/db/`

| File | Tests | What it covers |
|---|---|---|
| `test_datasource_repository.py` | 11 | Datasource CRUD, adapter_type filter, tag filter/keys/values, delete_by_name |

### `common/db/`

| File | Tests | What it covers |
|---|---|---|
| `test_tag_mixin.py` | 2 | TagQueryMixin edge cases: empty tags, missing key |

### `display_groups/db/`

| File | Tests | What it covers |
|---|---|---|
| `test_display_groups.py` | 3 | Display group creation, nesting, SLO member addition |

### `slo_groups/db/`

| File | Tests | What it covers |
|---|---|---|
| `test_slo_groups.py` | 8 | Template expansion, rejection, collision, add/remove row, extract, cascade deactivate, tag filter |

### `asset_meta/db/` — kept tests

| File | Tests | What it covers |
|---|---|---|
| `test_ingest_endpoint.py` | 2 | Duplicate-path validation (not in JSON Schema), DB persistence verification |
| `test_summary_endpoint.py` | 4 | Computed itemCount, count growth, cross-endpoint parity, cross-field from>=to rule |
| `test_read_endpoint.py` | 7 | Round-trip, multi-source, cascading closure, large snapshot, window clipping, cross-field rule |
| `test_repository.py` | 7 | Repository: insert/load snapshots, until-bound, ordering, hydration, cascade delete |

### `db/` — kept tests

| File | Tests | What it covers |
|---|---|---|
| `test_annotation_category_repository.py` | 8 | Category CRUD, system guards, delete reassignment |
| `test_note_category_router.py` | 5 | Seeded categories, create, system update/delete guards, reassigned header |

---

## Methodology

Each test function was read by a human-assisted reviewer and classified based on:

1. **What it actually asserts** — not just what endpoint it calls
2. **Whether Schemathesis can reach the same assertion** — Schemathesis tests every OpenAPI endpoint
   for schema conformance, valid/invalid inputs, and status codes, but does NOT test multi-step
   business logic, specific DB state, or repository-layer code
3. **Conservative bias** — when in doubt, classified as unique-business-logic

Repository-level tests (calling repo methods directly, not HTTP) are inherently outside
Schemathesis scope and were all classified as unique-business-logic.
