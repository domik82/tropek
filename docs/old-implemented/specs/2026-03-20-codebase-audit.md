# TROPEK Codebase Audit Report

**Date:** 2026-03-20
**Scope:** Full codebase — Python API, React UI, infrastructure, cross-cutting concerns

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Python API — SOLID Violations](#2-python-api--solid-violations)
3. [Python API — DRY Violations](#3-python-api--dry-violations)
4. [Python API — YAGNI Violations](#4-python-api--yagni-violations)
5. [Python API — Error Handling](#5-python-api--error-handling)
6. [Python API — Type Safety](#6-python-api--type-safety)
7. [Python API — Test Quality](#7-python-api--test-quality)
8. [React UI — Component Structure](#8-react-ui--component-structure)
9. [React UI — DRY Violations](#9-react-ui--dry-violations)
10. [React UI — Test Coverage](#10-react-ui--test-coverage)
11. [React UI — Type Safety & State](#11-react-ui--type-safety--state)
12. [React UI — Accessibility](#12-react-ui--accessibility)
13. [Infrastructure — Docker & Config](#13-infrastructure--docker--config)
14. [Infrastructure — Database & Migrations](#14-infrastructure--database--migrations)
15. [Infrastructure — Adapter Pattern](#15-infrastructure--adapter-pattern)
16. [Infrastructure — API Contract](#16-infrastructure--api-contract)
17. [Infrastructure — Worker & Queue](#17-infrastructure--worker--queue)
18. [Priority Matrix](#18-priority-matrix)
19. [What's Working Well](#19-whats-working-well)

---

## 1. Executive Summary

The TROPEK codebase has a solid foundation: clean async architecture, good separation between
pure evaluation engine and I/O layers, proper React Query integration, and sensible
infrastructure choices. However, there are structural issues that will compound as the project
grows.

**Biggest risks by area:**

| Area | Primary Risk | Impact |
|------|-------------|--------|
| Python API | God-classes (router 739L, repository 919L) | Untestable business logic |
| React UI | ~80% of components have zero tests | Silent regressions |
| React UI | Page components are god-components | Can't test or reuse pieces |
| Infrastructure | Missing Dockerfiles, hardcoded timeouts | Build failures, config drift |
| Cross-cutting | No structured logging anywhere | Blind in production |

---

## 2. Python API — SOLID Violations

### Single Responsibility

**CRITICAL: `quality_gate/repository.py` (919 lines)**
`EvaluationRepository` has 30+ methods spanning unrelated domains: basic CRUD, annotation
management, SLI value storage, trend queries, and baseline resolution. Should split into
`EvaluationRepository`, `AnnotationRepository`, `SLIValueRepository`, `TrendRepository`.

**CRITICAL: `quality_gate/router.py` (739 lines)**
Mixes HTTP concerns with business logic. Functions `_build_summary()` and `_build_detail()`
perform complex object transformation that belongs in a presenter/service layer. The batch
scan logic (`_scan_batch_members()`, 66 lines) is critical business logic buried in a router.

**HIGH: `quality_gate/worker.py` — `run_evaluation()`**
One 70+ line function with 5+ distinct responsibilities: mark running, load definitions,
substitute variables, query adapter, resolve baselines, evaluate, write results. Should be
a coordinator pattern with extracted service classes.

**MODERATE: `assets/repository.py` (616 lines)**
Single module with 5+ repository classes. `AssetRepository` mixes basic CRUD with complex
tree-building logic (`get_tree_with_bindings_and_links()`).

### Open/Closed Principle

**Adapter logic is hardcoded** — `worker.py`'s `_query_adapter()` is tightly coupled to httpx.
Adding a new adapter type or auth mechanism requires modifying this function. Should abstract
to an `AdapterClient` interface.

### Dependency Inversion

**`trigger.py` uses `Any` types for all repository parameters** — Lines 31-35 accept `Any`
for `asset_repo`, `slo_link_repo`, `sli_repo`, `slo_repo`, `ds_repo`. No protocol/interface,
no static type checking. Should use `Protocol` types.

**Global settings via `get_settings()`** — Called inside functions, making dependency flow
implicit and tests harder to write. Should be injected via FastAPI's dependency system.

### Missing Service Layer

No service/use-case layer exists between routers and repositories. Business logic lives in
routers (`trigger_evaluation()` directly calls repositories and resolver) or workers.
A `TriggerEvaluationService` class would be independently testable without FastAPI.

---

## 3. Python API — DRY Violations

### Repetitive Error Handling

Every endpoint reimplements:
```python
try:
    ctx = await resolve_single_trigger(...)
except ValueError as exc:
    raise HTTPException(status_code=404, detail=str(exc)) from exc
```
Appears in `trigger_evaluation()`, `trigger_batch()`, and other endpoints. Should use a
FastAPI exception handler or middleware.

### Repetitive Repository Instantiation

Manual repository creation repeats across routers:
```python
asset_repo = AssetRepository(session)
slo_link_repo = AssetSLOLinkRepository(session)
sli_repo = SLIRepository(session)
slo_repo = SLORepository(session)
ds_repo = DataSourceRepository(session)
```
Should be a factory function or FastAPI dependency.

### Duplicated Model Transformation

`_build_summary()` and `_build_detail()` both extract `indicator_results`, build
`FailingIndicator` objects, and process `job_stats`. Should be a shared presenter class.

### Criteria Parsing Duplication

`evaluator.py` (`_build_targets()`) and `scoring.py` (`_evaluate_criteria_block()`) both call
`parse_criteria_string()` for pass and warning criteria with similar patterns.

---

## 4. Python API — YAGNI Violations

| What | Where | Issue |
|------|-------|-------|
| Over-generalized `ComparisonRule` | `assets/comparison_rules.py` | Free-form `dict[str, str]` when usage is always the same pattern |
| Over-parameterized `get_baselines()` | `repository.py:289-359` | 8 parameters, 5+ levels of nesting. Two actual use cases should be two methods |
| Unused dependencies | `pyproject.toml` | `tenacity` (manual retry in queue.py instead), `hvac` (no Vault code), `python-multipart` |
| Duplicate adapter schemas | `adapters/prometheus/` vs `adapters/mock/` | `QueryRequest`/`QueryResponse` defined identically in both — no shared schema |

---

## 5. Python API — Error Handling

### String-Based Error Detection
`queue.py` line 24: `return "deadlock" in str(exc).lower()` — fragile. Should use PostgreSQL
SQLSTATE code `40P01`.

### Overly Broad Exception Handling
All `ValueError`s from `resolve_single_trigger()` become 404s, but some might be 500-level
errors. Needs specific exception types (`AssetNotFoundError`, `SLONotConfiguredError`).

### Silent Failures in Worker
`worker.py` lines 161-162: if evaluation doesn't exist, worker silently returns. No logging,
no alerting. Job status remains "running" forever.

### Weak Error Aggregation
`worker.py` lines 84-89: if all metrics fail, evaluation proceeds anyway. No distinction
between "metric not available" (acceptable) and "adapter unreachable" (should fail).

---

## 6. Python API — Type Safety

### `Any` Types in Critical Paths
`trigger.py` lines 31-35: all 5 repository parameters typed as `Any`. mypy won't catch errors.
Should use `Protocol` types.

### Dict Access Without Type Narrowing
`router.py` lines 61-70: `ind["metric"]` could `KeyError` if structure differs. Uses
`dict[str, Any]` where Pydantic models would give safety.

### Generic Return Types
`evaluator.py` line 60: `indicator_results: list[dict[str, Any]]` should be
`list[IndicatorResult]`. The `Any` defeats mypy.

### Unclear Union Returns
`worker.py` line 26: `_load_definitions() -> tuple[...] | str` — confusing. Should use a
`Result` dataclass or specific exception types.

---

## 7. Python API — Test Quality

### Coverage Assessment
- **27 integration test files** — good breadth for DB layer
- **Engine unit tests** — cover core evaluation logic well

### Gaps
| Missing Test | Risk |
|-------------|------|
| Worker deadlock retry logic (`queue.py:52-77`) | Retry logic is complex and untested |
| Router error handling (HTTPException conversions) | Wrong status codes won't be caught |
| `_scan_batch_members()` edge cases | 66-line business logic with no tests |
| Baseline aggregation with zero values | Division by zero in relative criteria |
| Variable shadowing (`$asset_name` vs metadata keys) | Silent incorrect queries |

### Test Design Issues
- Some tests check internal field structure rather than behavior
  (e.g., `test_indicator_results_contain_all_metrics()` checks dict keys, not evaluation outcome)
- Tests depend on YAML fixture structure — fixture changes break tests even when code is correct
- No factory functions for test data creation

---

## 8. React UI — Component Structure

### God Components

**EvaluationDetailPage (213 lines)** — manages ref handling, tab state, action state, scroll
position, data fetching/transformation, navigation/breadcrumb logic, and multiple nested
conditional renders. Should split into:
- `EvaluationSummary` (metadata + status)
- `EvaluationIndicatorSection` (table + tabs)
- `EvaluationTrendSection` (charts)
- `EvaluationNotesSection` (annotations)

**AssetPanel (325 lines)** — 11+ state variables, dual view mode logic, metric group filtering,
evaluation selection. Should extract: `ChartModeContainer`, `HeatmapModeContainer`,
`MetricGroupFilter`.

**AssetTree (355 lines)** — manages dialog state for 4 dialog types, tree filtering, expand/
collapse, menu state, rename state. Dialogs should be delegated to parent.

**SloRegistryPage (350 lines)** — manages 4+ dialog states, SLO filtering, expansion state,
delete confirmation, sidebar integration. Should extract: `SloList`, `SloItem`,
`GroupDialogContainer`.

### Missing Container/Presentational Split

**MetricTrendBlock (232 lines)** mixes data fetching (`useTrend`), state management (yMin,
yMax, showPass, showWarn), chart configuration, AND rendering. Should extract
`useMetricTrendState` hook and `buildChartOption` pure function.

### Monolithic Action Form

**EvaluationActionForm (172 lines)** handles 4 different action types with branching logic.
Should split into `InvalidateForm`, `OverrideForm`, `BaselineForm`, `ReEvaluateForm` with
a shared wrapper.

---

## 9. React UI — DRY Violations

### Duplicated Styling (~15 instances)

Identical Tailwind patterns repeat throughout:
```
px-3 py-1.5 text-xs font-medium rounded border          (buttons, ~15 times)
w-full px-3 py-2 bg-background border border-border ... (inputs, ~8 times)
```
Files affected: `EvaluationActions.tsx`, `SloRegistryPage.tsx`, `EvaluationDetailPage.tsx`,
`SloCreateForm.tsx`, `AnnotationForm.tsx`, `AddNoteForm.tsx`, `NoteEntry.tsx`.

Should extract to shared `<Button>` and `<Input>` components or Tailwind utility classes.

### Duplicated Deletion Confirmation

Three separate implementations of the same pattern (show form, collect reason/author, confirm):
- `NoteEntry.tsx` (lines 100-138)
- `EvaluationDetailPage.tsx` (lines 104-110)
- `SloRegistryPage.tsx` (lines 67-88)

Should extract `DeletionConfirmDialog` component.

### Duplicated Status Color Mappings

`STATUS_TEXT` mapping defined identically in:
- `SLIBreakdownTable.tsx` (lines 6-10)
- `MetricTrendBlock.tsx` (lines 25-29)
- `EvaluationActionForm.tsx` (lines 265-270) as inline logic

Should centralize in a constants file.

### Duplicated Tab/Filter Logic

`EvaluationDetailPage` (lines 39-58) and `AssetPanel` (lines 73-92) both calculate
`availableGroups`, `counts`, `resolvedTab`, `tabIndicators` with the same pattern.
Should extract `useTabState(ev)` custom hook.

---

## 10. React UI — Test Coverage

### Coverage: ~20% (9 test files for ~45 components)

**Components WITH tests:**
- `NoteEntry` — good (tests both compact + expanded, form behavior)
- `toggleColumnKey` pure function — basic
- `countLeafMembers` tree utility — good
- `collectGroupAssetNames` recursion — good

**Components with ZERO tests (critical gaps):**

| Category | Untested Components |
|----------|-------------------|
| Pages | EvaluationDetailPage, AssetNavigatorPage, SloRegistryPage, AssetsPage |
| Data hooks | useAssetEvaluations, useMetricHeatmap, useEvaluationDetail, useTrend |
| Charts | MetricTrendBlock, HeatmapChart, GroupScoreChart, AssetScoreChart |
| Forms | SloCreateForm, AnnotationForm, AddNoteForm, EvaluationActionForm |
| Dialogs | GroupCreateDialog, GroupEditDialog, GroupDeleteDialog, SloLinkDialog |
| Panels | AssetPanel, GroupPanel, AllEvaluationsPanel |
| Actions | EvaluationActions button group |

### Testability Blockers

- **Complex state in pages** — 5+ `useState` + 4+ `useMemo` in EvaluationDetailPage. Hard to
  test without mocking Router + React Query + custom hooks. Extract state into custom hooks.
- **Hard-coded DOM access** — `document.getElementById()` in EvaluationDetailPage and
  MetricTrendBlock. Not testable in jsdom. Use callback refs instead.
- **Imperative control** — AnnotationSection uses `useImperativeHandle`; parent calls
  `openForm()` imperatively. Testable but non-idiomatic React.

---

## 11. React UI — Type Safety & State

### Type Issues

| Issue | Where |
|-------|-------|
| `ActionKind` union type defined in multiple files | EvaluationActions, hooks types — should be in central types file |
| Missing null checks | AssetPanel line 74 destructures `ev.indicator_results` without null guard |
| No discriminated unions for eval states | Components check `ev.invalidated`, `ev.original_result`, `ev.override_author` individually — implicit state machine |
| Unused prop `selectedAsset` | AssetPanel line 14 — never read |

### State Management

**Good:** React Query as source of truth, URL params for navigation (shareable links),
no global state soup.

**Issues:**
- `AssetPanel` manages both `selectedEvalId` (user choice) AND `defaultEvalId` (computed).
  Creates confusion with `effectiveEvalId = selectedEvalId ?? defaultEvalId`.
- Over-engineered `useColumnVisibility` hook used in ONE place. Should be co-located with
  consumer.

---

## 12. React UI — Accessibility

**Critical gaps — no a11y testing whatsoever:**

| Issue | Example |
|-------|---------|
| Non-semantic HTML | `<div className="...cursor-pointer">` used as buttons (AssetTree) |
| Missing ARIA labels | MetricTrendBlock back button, AssetTreeNode expand/collapse |
| No focus management | Dialog opens don't trap focus; scroll actions don't move focus |
| Color-only indicators | Heatmap cells use only color, no alt text for status |
| Missing autocomplete | Author input fields lack `autocomplete="name"` |

---

## 13. Infrastructure — Docker & Config

### Docker Issues

| Severity | Issue |
|----------|-------|
| **Critical** | No `api/Dockerfile` — docker-compose will fail to build |
| **Critical** | No `adapters/prometheus/Dockerfile` — same issue |
| **High** | UI service `depends_on: api` without `condition: service_healthy` |
| **Medium** | Redis password: if `QG_REDIS_PASSWORD` unset, creates server with empty password |

### Configuration Issues

| Severity | Issue |
|----------|-------|
| **High** | No validation of required secrets at startup — missing `QG_DB_PASSWORD` causes cryptic connection errors later |
| **High** | `_load_yaml()` silently returns `{}` if config.yaml is malformed |
| **Medium** | `@lru_cache` on `get_settings()` makes test overrides difficult |
| **Low** | Nested `CacheTTLSettings` is a plain class, not `BaseSettings` — no type validation |

---

## 14. Infrastructure — Database & Migrations

### Positives
- Clean async SQLAlchemy with lazy initialization, proper pooling
- Deadlock handling with exponential backoff and jitter (sophisticated)
- TimescaleDB hypertable on `sli_values` for time-series performance
- `ENV_FILE` pattern for targeting test vs prod DB

### Issues
- Migration 001 is 546 lines (acceptable for autogeneration but hard to review)
- Migration 002 uses raw `op.execute()` for TimescaleDB SQL — fragile but necessary
- No connection pool metrics or health monitoring

---

## 15. Infrastructure — Adapter Pattern

### Design (Good)
Each adapter is a standalone FastAPI service with implicit contract:
`POST /query` (QueryRequest → QueryResponse), `GET /health`.

### Issues

| Severity | Issue |
|----------|-------|
| **High** | No formal adapter interface/ABC — contract is only in documentation |
| **High** | Hardcoded `timeout=30.0` in worker.py and router.py instead of using `config.yaml`'s `reliability.adapter_timeout_seconds` |
| **Medium** | No adapter registry — adding a new adapter requires code changes in worker |
| **Medium** | Error handling diverges between worker and adapter (adapter reads env, worker hardcodes) |

---

## 16. Infrastructure — API Contract

### Positives
- Resource-oriented endpoints with proper HTTP methods
- Pagination via query params, IDs in path
- Proper status codes (201 for create, 204 for delete)

### Issues

| Issue | Detail |
|-------|--------|
| Inconsistent naming | `/evaluation-batches` (hyphens) vs `/slo_definitions` (underscores) |
| Wrong status for batch trigger | `POST /evaluations/batch/trigger` returns 200, should be 202 Accepted |
| No API versioning | Version hardcoded as `"0.2.0"` but no URL prefix (`/v1/`) |
| Response envelope inconsistency | Lists use `PagedResponse{items[], total}`, details return unwrapped objects |

---

## 17. Infrastructure — Worker & Queue

### Positives
- Async-first, proper session lifecycle, deadlock retry with backoff
- Redis db separation (cache=0, queue=1)
- Job result persistence with configurable TTL

### Issues

| Severity | Issue |
|----------|-------|
| **High** | No job deduplication — same eval_id queued twice causes race condition |
| **Medium** | No structured logging — if a job fails, nothing is traceable |
| **Medium** | No job retry for non-deadlock failures (network, adapter down) |
| **Low** | No explicit timeout handling — job exceeds `job_timeout_seconds` with no DB status update |

---

## 18. Priority Matrix

### Tier 1 — Do First (structural blockers)

| # | Action | Area | Why |
|---|--------|------|-----|
| 1 | Extract shared `<Button>`, `<Input>` components | UI | Eliminates ~15 DRY violations, enables consistent styling |
| 2 | Split EvaluationDetailPage into 4-5 components | UI | Unblocks component testing |
| 3 | Add tests for critical UI flows (AssetPanel, forms, actions) | UI | ~80% of components untested |
| 4 | Extract service layer from routers | API | Business logic testable without FastAPI |
| 5 | Split `EvaluationRepository` (919L) into focused classes | API | SRP, testability |
| 6 | Fix silent worker failures + add logging | API | Invisible failures in production |
| 7 | Replace `Any` types with Protocols in trigger.py | API | Type safety in critical path |

### Tier 2 — Do Soon (code quality)

| # | Action | Area |
|---|--------|------|
| 8 | Centralize error handling (middleware/exception handlers) | API |
| 9 | Centralize status color constants | UI |
| 10 | Extract `useTabState`, `useMetricTrendState` hooks | UI |
| 11 | Create formal adapter interface/ABC | Infra |
| 12 | Use config values instead of hardcoded timeouts | Infra |
| 13 | Add startup validation for required secrets | Infra |
| 14 | Add edge-case tests (baseline=0, missing metrics) | API |

### Tier 3 — Do Later (structural improvements)

| # | Action | Area |
|---|--------|------|
| 15 | Implement discriminated union types for eval states | UI |
| 16 | Add accessibility audit + semantic HTML | UI |
| 17 | API URL versioning (`/v1/`) | Infra |
| 18 | Job deduplication in arq worker | Infra |
| 19 | Add structured logging (structlog) across API + worker | Infra |
| 20 | Reorganize modules: domain / application / adapter layers | API |

---

## 19. What's Working Well

**Python API:**
- Clean pure-function evaluation engine with zero I/O — excellent design
- Comprehensive integration tests (27 files) hitting real database
- Good async/await usage throughout
- Proper database schema with indexes and constraints
- Pydantic schemas for API validation
- Deadlock retry with exponential backoff — sophisticated

**React UI:**
- React Query integration is clean — no fetch() in components
- URL params for navigation (shareable links)
- Theme system with CSS custom properties
- Zod validation on forms
- No global state soup

**Infrastructure:**
- Docker Compose profiles (dev/test/e2e) are well-separated
- Migration scripts are idempotent and well-commented
- Shell scripts use strict mode (`set -euo pipefail`)
- Config separation (secrets in env, non-secrets in YAML)

**The foundation is solid.** The main investment needed is decomposition (splitting large
files/components) and test coverage (especially UI). The architecture doesn't need a rewrite —
it needs focused refactoring in the areas identified above.
