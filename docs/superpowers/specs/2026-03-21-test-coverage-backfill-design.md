# Test Coverage Backfill — Prerequisite for DB Normalization

**Date:** 2026-03-21
**Status:** Draft
**Prerequisite for:** DB Normalization + Redis Caching Layer (2026-03-20)

## Problem

The DB normalization migration rewrites how indicator results, baselines, heatmaps, and trends are stored and queried. Several critical code paths lack test coverage — endpoint tests, round-trip tests, and edge cases. Without these, the migration could introduce silent regressions that pass structural checks but produce wrong data.

This spec defines the test backfill required before any data layer changes begin.

## Scope

Backfill tests for existing behavior only. No new features, no refactoring — with one exception: the override double-apply bug (see Known Bug below) should be fixed as part of this work since the test would fail against current code.

## Known Bug: Override Double-Apply

The `override_status()` repository method unconditionally sets `original_result=ev.result` on every override call. If an eval's true original is "fail", gets overridden to "pass", then overridden again to "warning" — `original_result` becomes "pass" (the first override), not "fail" (the true original). The fix: only set `original_result` and `original_score` if they are currently NULL. This mirrors how re-evaluation already handles it (`test_update_reeval_result_preserves_original` tests this exact pattern). Fix this bug, then write the test.

## Coverage Gaps and Required Tests

### 1. Endpoint tests (router level)

These mutations exist but have no endpoint-level test coverage. Each needs an integration test that calls the endpoint via the test client against the real test database and verifies both DB state and API response.

Note: `api/tests/test_qg_router.py` already exists with validation error tests using mocked DB sessions. The new endpoint tests are integration tests (real DB) and should live in `api/tests/endpoints/`. The existing file stays as-is — it tests input validation, the new tests verify behavior.

**Annotations:**
- POST `/evaluations/{id}/annotations` — create annotation, verify it appears in evaluation detail response with correct content, author, category
- GET `/evaluations/{id}/annotations` — list annotations, verify hidden annotations excluded
- PATCH `/evaluations/{eval_id}/annotations/{ann_id}` — update annotation content, verify change persisted
- Verify annotation count increments in evaluation summary
- Verify hidden annotations are excluded from detail response but count is correct

**Invalidation:**
- PATCH `/evaluations/{id}/invalidate` — set invalidated=true with note, verify response
- PATCH `/evaluations/{id}/restore` — undo invalidation, verify response
- Invalidate → restore cycle: verify eval returns to original state
- Verify invalidated eval is excluded from subsequent baseline queries

**Override:**
- PATCH `/evaluations/{id}/override-status` — override result, verify original_result/original_score preserved
- PATCH `/evaluations/{id}/restore-override` — undo override, verify original values restored
- Override an already-overridden eval: verify original_result is NOT overwritten (preserves the true original) — **requires the bug fix above**

**Baseline pin/unpin:**
- PATCH `/evaluations/{id}/pin-baseline` — pin eval as baseline, verify baseline_pinned_at set
- PATCH `/evaluations/{id}/unpin-baseline` — unpin, verify baseline_unpinned_at set
- Pin → unpin cycle: verify eval returns to unpinned state
- Pin eval A, then pin eval B for same asset+SLO: verify A is atomically unpinned

**Re-evaluation:**
- POST `/evaluations/re-evaluate` — trigger re-evaluation, verify new results written
- Verify original_result/original_score set on first re-eval
- Verify second re-eval does NOT overwrite original_result

### 2. Repository round-trip tests

These test the DB layer directly — write data, read it back, assert equality. Critical for the normalization migration because they validate the read path that will be rewritten.

**Indicator results round-trip:**
- Write evaluation with known indicator_results via `mark_completed()`, read back via `get_by_id()`, pass through `build_detail()`, assert each `IndicatorResult` field matches input
- Cover all field types: float values, null values, boolean key_sli, list pass_targets/warning_targets

**Heatmap query:**
- Seed multiple evaluations with known indicator data
- Call `get_metric_heatmap()`, assert cell data matches expected (metric_name, status, display_name per cell)
- Note: `get_metric_heatmap()` filters by `status == COMPLETED` but does NOT exclude invalidated evals at the query level. Invalidation display is handled in the router (lines 155-163) which transforms the result. Test both layers:
  - Repository test: verify invalidated completed evals ARE returned by the query (current behavior)
  - Router/endpoint test: verify the router transforms invalidated evals' result to "invalidated" for display

**Trend query:**
- Seed evaluations with known metrics and baselines
- Call `get_trend_by_domain()`, assert trend points include correct `value`, `compared_value`, `result`
- **Prerequisite**: seed `sli_values` hypertable rows via `SLIValueRepository.write_sli_values()` — the trend query joins evaluations with sli_values
- Verify invalidated evaluations are excluded (trend repo filters `invalidated=false`)

**Baseline query:**
- Seed evaluations with mixed results (pass, fail, invalidated, overridden)
- Call `get_baselines()` via `BaselineRepository.get_evaluation_baselines()`, verify only eligible evaluations are returned
- Verify invalidated evals excluded, overridden evals use overridden result

### 3. Presenter edge cases

The presenter (`presenter.py`) is the central transformation layer that will be rewritten during normalization. Add edge case tests to the existing `api/tests/services/test_presenter.py` file (which already has `_make_evaluation` and `_make_annotation` helpers):

- Empty `indicator_results` list → `top_failures` is empty, `indicator_results` is `[]`
- Indicator with no `pass_targets` → `FailingIndicator.threshold` defaults gracefully (empty string)
- `job_stats` is None → `original_score` is None, `compared_evaluation_ids` is `[]`
- Indicator with null `value` (metric unavailable) → status is "fail", value is None in response
- Info-only objective (no pass/warning criteria) → status is "info", score is 0
- Combined flags: invalidated=true AND override exists → verify both flags present in response
- Annotation sorting: multiple annotations → verify sorted by `created_at` ascending
- Latest annotation selection: verify it picks the most recent visible annotation

### 4. UI component tests for mutation flows

The UI has component tests for form rendering but not for mutation submission. These should use mocked API responses (no backend needed).

- Annotation creation: submit form → mutation fires → list updates with new annotation
- Invalidation: submit form → mutation fires → eval state updates to invalidated
- Override: submit form → mutation fires → result badge updates
- Re-evaluation: submit form → mutation fires → loading state shown

### 5. Heatmap behavior tests

**Backend (router-level):**
- Heatmap cell result transformation: invalidated completed eval → cell result shows "invalidated" (router logic, lines 155-163)
- Overridden evaluation → cell uses overridden result, not original

**UI (component-level):**
- Invalidated cell in a time slot with other valid evals → correct color/styling
- Overridden evaluation → shows overridden result color
- Evaluation with 0 indicator results → cell shows "none" or equivalent

Note: `AssetHeatmap.test.tsx` does not exist yet — this is a **new** test file, not a modification.

## What's Already Covered (no backfill needed)

| Area | Existing coverage |
|---|---|
| Evaluation engine (scoring, criteria) | Comprehensive unit tests in `api/tests/engine/` |
| Annotation CRUD at DB layer | `test_evaluation_repository.py` — add + hide |
| Annotation UI display | `AnnotationForm.test.tsx`, `NoteEntry.test.tsx` |
| Invalidation baseline exclusion | `test_re_evaluation.py` via `BaselineRepository` |
| Override presenter — basic case | `test_presenter.py` — `test_build_detail_overridden_evaluation` (original_result), `test_build_summary_original_score_from_job_stats` (original_score). Only 2 of 10 tests touch override; the rest cover standard/annotation/invalidation paths. |
| Re-evaluation schema validation | `test_re_evaluator.py` — request shape validation (5 tests) |
| Re-evaluation DB operations | `test_re_evaluation.py` — baseline loading, original_result preservation |
| UI component rendering | 29 test files covering display states |
| Router input validation | `test_qg_router.py` — validation errors with mocked sessions |

## Testing Approach

- Backend endpoint + repository tests are `@pytest.mark.integration` — they hit the real test database via `./start_test_infra.sh`
- Endpoint tests use FastAPI's `TestClient` with the test database
- Presenter edge case tests are unit tests (no DB, use `_make_evaluation` helper)
- UI tests use Vitest + React Testing Library with mocked API responses
- TDD: write each test, verify it passes against current code, then the test becomes a regression guard for the migration

## Affected Files

### New test files
- `api/tests/endpoints/test_annotation_endpoints.py`
- `api/tests/endpoints/test_invalidation_endpoints.py`
- `api/tests/endpoints/test_override_endpoints.py`
- `api/tests/endpoints/test_baseline_pin_endpoints.py`
- `api/tests/endpoints/test_re_evaluation_endpoints.py`
- `api/tests/db/test_indicator_round_trip.py`
- `api/tests/db/test_heatmap_query.py`
- `api/tests/db/test_trend_query.py`
- `ui/src/features/navigator/components/AssetHeatmap.test.tsx` (new file)

### Modified files
- `api/app/modules/quality_gate/repository.py` — fix override double-apply bug in `override_status()`
- `api/tests/services/test_presenter.py` — add edge case tests to existing file
- `ui/src/features/evaluations/components/EvaluationActions.test.tsx` — add mutation tests
- `ui/src/features/evaluations/components/AnnotationForm.test.tsx` — add submit test
