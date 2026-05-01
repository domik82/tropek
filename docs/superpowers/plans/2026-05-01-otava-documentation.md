# Otava Change-Points Documentation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Document all new and modified code on the `feat/otava-change-point-detection` branch — the change-point detection system, configuration module, UI feature, client extensions, and cross-cutting integration changes.

**Architecture:** Two-phase approach. Phase 1 launches 4 read-only research agents in parallel to analyse every new/modified file, producing structured reports. Phase 2 synthesises those reports into final documentation files split between `docs/modules/` (user-facing) and `api/docs/` / `ui/docs/` (contributor-facing).

---

## Phase 1: Research Agents

All agents are read-only — they produce a report file, no code changes.
All agents must be launched in a **single message** with 4 parallel Agent tool calls.
Each agent is `general-purpose` type with full instructions inlined in its prompt.

Working directory for reports: `api/docs/research/` (already exists, delete reports after Phase 2).

---

### Task 1: Research Agent — API Change Points Module + Configuration

**Files:**
- Create: `api/docs/research/01-change-points-module.md`

- [ ] **Step 1: Launch research agent**

Prompt for the agent (copy verbatim):

```
You are a documentation research agent. Read ALL files listed below in the TROPEK codebase
and produce a structured research report to `api/docs/research/01-change-points-module.md`.

## Codebase location

All files are under `.worktrees/otava-change-points/`. Use this prefix for all reads.

## Files to read (read EVERY file, skip none)

### Change Points Module (production code)
- `api/tropek/modules/change_points/__init__.py`
- `api/tropek/modules/change_points/engine/__init__.py`
- `api/tropek/modules/change_points/engine/base.py`
- `api/tropek/modules/change_points/engine/analysis.py`
- `api/tropek/modules/change_points/engine/calculator.py`
- `api/tropek/modules/change_points/engine/detector.py`
- `api/tropek/modules/change_points/engine/significance_test.py`
- `api/tropek/modules/change_points/engine/NOTICE`
- `api/tropek/modules/change_points/detector.py`
- `api/tropek/modules/change_points/worker_step.py`
- `api/tropek/modules/change_points/repository.py`
- `api/tropek/modules/change_points/router.py`
- `api/tropek/modules/change_points/schemas.py`

### Configuration Module (production code)
- `api/tropek/modules/configuration/__init__.py`
- `api/tropek/modules/configuration/repository.py`
- `api/tropek/modules/configuration/router.py`
- `api/tropek/modules/configuration/schemas.py`

### Tests
- `api/tests/change_points/__init__.py`
- `api/tests/change_points/generators.py`
- `api/tests/change_points/test_generators.py`
- `api/tests/change_points/test_detector.py`
- `api/tests/change_points/test_detection_scenarios.py`
- `api/tests/change_points/test_presenter_enrichment.py`
- `api/tests/change_points/test_worker_step.py`
- `api/tests/change_points/engine/__init__.py`
- `api/tests/change_points/engine/test_analysis.py`
- `api/tests/change_points/engine/test_calculator.py`
- `api/tests/change_points/engine/test_detector.py`
- `api/tests/change_points/db/__init__.py`
- `api/tests/change_points/db/conftest.py`
- `api/tests/change_points/db/test_repository.py`
- `api/tests/configuration/__init__.py`
- `api/tests/configuration/db/__init__.py`
- `api/tests/configuration/db/conftest.py`
- `api/tests/configuration/db/test_repository.py`

### DB Models (read the change_point and configuration sections)
- `api/tropek/db/models.py`

## Report structure

Write the report to `api/docs/research/01-change-points-module.md` with these sections:

### 1. Files Analysed
Table: file path | line count | purpose (one line each)

### 2. Engine Component Catalogue
For each class/function in `engine/`: name, purpose, key methods, inputs/outputs, dependencies.
Document the E-Divisive algorithm flow: how data enters, what each stage computes, what comes out.
Include the significance testing approach and the calculator's role.

### 3. Detector & Worker Step
How `detector.py` orchestrates the engine over evaluation series.
How `worker_step.py` integrates with the arq worker — when it runs, what triggers it,
what data it reads, what it writes. The full lifecycle from evaluation completion to
change point persistence.

### 4. Repository Layer
Every method in `repository.py`: what query it runs, parameters, return type.
Same for `configuration/repository.py`.

### 5. Router & Schemas
Every endpoint: method, path, parameters, request/response shapes.
Same for configuration router.

### 6. DB Models
New ORM models: table names, columns, relationships, indexes.

### 7. Data Flow
End-to-end: evaluation completes → worker step triggers → engine runs → results persisted → API serves.
Include the configuration module's role in parameterizing detection.

### 8. Patterns & Conventions
Shared patterns: DI, error handling, naming, test organization.

### 9. Test Coverage
What's tested, what's not. Test patterns (generators, scenarios, fixtures).
Integration vs unit test split.

### 10. Known Issues & Edge Cases
TODOs, workarounds, limitations, edge cases documented in tests or comments.

## Rules
- Read every file completely. Do not skim or summarize from file names.
- Verify all class names, function names, and method signatures against the actual code.
- If a file is empty (just `__init__.py`), note it and move on.
- Write the report as markdown. No code blocks longer than 20 lines — summarize instead.
```

---

### Task 2: Research Agent — API Cross-Cutting Integration Changes

**Files:**
- Create: `api/docs/research/02-cross-cutting-changes.md`

- [ ] **Step 1: Launch research agent**

Prompt for the agent (copy verbatim):

```
You are a documentation research agent. Read ALL files listed below in the TROPEK codebase
and produce a structured research report to `api/docs/research/02-cross-cutting-changes.md`.

These are EXISTING files that were MODIFIED to integrate change-point detection. Your job
is to understand what was added/changed and why.

## Codebase location

All files are under `.worktrees/otava-change-points/`. Use this prefix for all reads.

## Files to read (read EVERY file)

### Quality Gate — Workflows
- `api/tropek/modules/quality_gate/workflows/execution/adapter_client.py`
- `api/tropek/modules/quality_gate/workflows/execution/evaluation_executor.py`
- `api/tropek/modules/quality_gate/workflows/execution/evaluation_helpers.py`
- `api/tropek/modules/quality_gate/workflows/presentation/presenter.py`
- `api/tropek/modules/quality_gate/workflows/presentation/heatmap_cache.py`
- `api/tropek/modules/quality_gate/workflows/trigger/trigger_service.py`

### Quality Gate — Repositories
- `api/tropek/modules/quality_gate/repositories/baseline.py`
- `api/tropek/modules/quality_gate/repositories/evaluation_run.py`
- `api/tropek/modules/quality_gate/repositories/indicator.py`
- `api/tropek/modules/quality_gate/repositories/trend.py`

### Quality Gate — Router & Schemas
- `api/tropek/modules/quality_gate/router.py`
- `api/tropek/modules/quality_gate/schemas/evaluations.py`
- `api/tropek/modules/quality_gate/schemas/heatmap.py`
- `api/tropek/modules/quality_gate/schemas/trigger.py`
- `api/tropek/modules/quality_gate/schemas/annotation_categories.py`

### SLO Registry
- `api/tropek/modules/slo_registry/repository.py`
- `api/tropek/modules/slo_registry/schemas.py`
- `api/tropek/modules/slo_registry/params.py`

### Infrastructure
- `api/tropek/main.py`
- `api/tropek/queue.py`
- `api/tropek/logging_config.py`

### Migration files
- `api/alembic/versions/001_initial_schema.py`
- `api/alembic/versions/002_timescaledb_hypertable_and_seed_data.py`

### Modified tests
- `api/tests/db/test_baseline_query.py`
- `api/tests/engine/test_evaluation_helpers.py`
- `api/tests/workflows/execution/test_executor_phases.py`
- `api/tests/workflows/presentation/test_heatmap_builder.py`
- `api/tests/workflows/presentation/test_presenter_fragment_builder.py`
- `api/tests/schemathesis/test_schema.py`
- `api/tests/test_db_imports.py`

## Report structure

Write the report to `api/docs/research/02-cross-cutting-changes.md` with these sections:

### 1. Files Analysed
Table: file path | line count | what changed (one line each)

### 2. Evaluation Executor Integration
How the evaluation executor was extended to trigger change-point detection after eval.
What new parameters/steps were added. The adapter_client changes.

### 3. Presenter & Heatmap Changes
How the presenter was extended to include change-point data in responses.
Heatmap cache changes. New response fields.

### 4. Trigger Service Changes
What was added to the trigger flow.

### 5. Repository Extensions
New methods or modified queries in baseline, indicator, trend, evaluation_run repos.
Focus on what was ADDED, not the entire file.

### 6. SLO Registry Extensions
New query methods, schema fields, params for comparison rules.

### 7. Router Extensions
New endpoints or modified endpoints in the quality_gate router.

### 8. Infrastructure Changes
main.py: router registration. queue.py: new worker functions. logging_config.py changes.
Migration file changes (new tables, columns).

### 9. Schema Changes
New fields in evaluation, heatmap, trigger schemas.

### 10. Test Changes
What tests were added or modified and what they cover.

## Rules
- Read every file completely. Do not skim.
- Focus on what was ADDED or CHANGED for change-point support — not documenting
  the entire pre-existing module.
- Verify all names against actual code.
```

---

### Task 3: Research Agent — UI Change Points Feature + Existing Feature Modifications

**Files:**
- Create: `api/docs/research/03-ui-changes.md`

- [ ] **Step 1: Launch research agent**

Prompt for the agent (copy verbatim):

```
You are a documentation research agent. Read ALL files listed below in the TROPEK UI
codebase and produce a structured research report to `api/docs/research/03-ui-changes.md`.

## Codebase location

All files are under `.worktrees/otava-change-points/`. Use this prefix for all reads.

## Files to read (read EVERY file)

### New: Change Points Feature
- `ui/src/features/change-points/api.ts`
- `ui/src/features/change-points/components/ChangePointsPage.tsx`
- `ui/src/features/change-points/domain.ts`
- `ui/src/features/change-points/hooks.ts`
- `ui/src/features/change-points/index.ts`
- `ui/src/features/change-points/mappers.ts`

### Modified: Evaluations Feature
- `ui/src/features/evaluations/domain.ts`
- `ui/src/features/evaluations/mappers.ts`
- `ui/src/features/evaluations/hooks/useMetricTrendState.ts`
- `ui/src/features/evaluations/hooks/useMetricTrendState.test.ts`
- `ui/src/features/evaluations/components/SLIBreakdownTable.tsx`
- `ui/src/features/evaluations/components/SLIBreakdownGrouped.test.tsx`
- `ui/src/features/evaluations/components/SLIBreakdownTable.test.tsx`
- `ui/src/features/evaluations/components/EvaluationIndicatorSection.test.tsx`
- `ui/src/features/evaluations/actions/slo-scope/useSloScope.test.ts`
- `ui/src/features/evaluations/hooks/useTabState.test.ts`

### Modified: Navigator Feature
- `ui/src/features/navigator/components/AssetHeatmap.tsx`
- `ui/src/features/navigator/components/AssetPanel.tsx`
- `ui/src/features/navigator/components/AssetPanelChartView.tsx`
- `ui/src/features/navigator/components/AssetPanelHeatmapView.tsx`
- `ui/src/features/navigator/components/DeferredWhenOffscreen.tsx`
- `ui/src/features/navigator/components/SloMiniHeatmap.tsx`
- `ui/src/features/navigator/domain.ts`
- `ui/src/features/navigator/mappers.ts`
- `ui/src/features/navigator/mappers.test.ts`
- `ui/src/features/navigator/ui-types.ts`

### Modified: Registry & SLOs
- `ui/src/features/registry/forms/SloWizard.tsx`
- `ui/src/features/registry/forms/WizardStepComparison.tsx`
- `ui/src/features/slos/components/SloCreateForm.tsx`
- `ui/src/features/slos/mappers.ts`

### Modified: Shared / App-level
- `ui/src/App.tsx`
- `ui/src/components/charts/HeatmapChart.tsx`
- `ui/src/index.css`
- `ui/src/lib/format.ts`
- `ui/src/lib/format.test.ts`
- `ui/src/lib/chartAnnotations.test.ts`
- `ui/src/pages/EvaluationDetailPage.tsx`

### Generated (skim for new types only)
- `ui/src/generated/api.ts` (large — only read the change-point and configuration DTOs)

## Report structure

Write the report to `api/docs/research/03-ui-changes.md` with these sections:

### 1. Files Analysed
Table: file path | line count | new or modified | purpose

### 2. Change Points Feature (New)
Full catalogue of the new feature: page component, domain types, mappers, hooks, API
functions. How it follows the DTO/Domain/Mapper pattern. What the page shows, how data
flows from API to UI.

### 3. Evaluations Feature Changes
New domain types, mapper changes, useMetricTrendState hook purpose, SLI breakdown table
extensions. What change-point data is surfaced in evaluation views.

### 4. Navigator Feature Changes
AssetHeatmap changes for CP overlay, DeferredWhenOffscreen component, domain/mapper
additions, SloMiniHeatmap extensions. How change points appear on heatmaps.

### 5. Registry & SLO Changes
Wizard/form changes for comparison rules.

### 6. Shared Component Changes
HeatmapChart overlay support, CSS variables, format utilities.

### 7. Patterns & Architecture
How the new feature follows established patterns (DTO/Domain/Mapper, React Query, testing).
Deviations if any.

### 8. Test Coverage
What's tested, patterns used, coverage gaps.

## Rules
- Read every file completely.
- For `ui/src/generated/api.ts`, only read the sections related to change-points and
  configuration — it's a large generated file.
- Verify all component names, hook names, type names against actual code.
```

---

### Task 4: Research Agent — Client, Scripts, Mock Data & Existing Docs

**Files:**
- Create: `api/docs/research/04-client-scripts-docs.md`

- [ ] **Step 1: Launch research agent**

Prompt for the agent (copy verbatim):

```
You are a documentation research agent. Read ALL files listed below in the TROPEK codebase
and produce a structured research report to `api/docs/research/04-client-scripts-docs.md`.

## Codebase location

All files are under `.worktrees/otava-change-points/`. Use this prefix for all reads.

## Files to read (read EVERY file)

### Python Client
- `clients/python/tropek_client/client.py`
- `clients/python/tropek_client/models.py`

### Scripts
- `scripts/seed_evaluations.py`
- `scripts/e2e_tests.py`

### Mock Adapter Scenarios
- `adapters/mock/scenarios/office-apps.yaml`
- `adapters/mock/scenarios/plugin-health.yaml`
- `adapters/mock/scenarios/stable.yaml`
- `adapters/mock/scenarios/vm-infra.yaml`

### Bootstrap
- `bootstrap_mock/manifests/slo-definitions.yaml`

### Existing Docs (verify accuracy)
- `docs/superpowers/plans/2026-04-11-otava-change-point-detection.md`
- `docs/superpowers/plans/2026-04-25-change-point-config-redesign.md`
- `docs/superpowers/specs/2026-04-25-change-point-config-redesign.md`
- `docs/issues/edivisive-optimization-opportunities.md`
- `docs/issues/otava-upstream-bugs.md`

### OpenAPI spec (skim for change-point endpoints)
- `api/openapi.json` (large — only read change-point and configuration endpoint sections)

### Dependencies
- `api/pyproject.toml` (check for new dependencies added)
- `pyproject.toml` (root workspace)

## Report structure

Write the report to `api/docs/research/04-client-scripts-docs.md` with these sections:

### 1. Files Analysed
Table: file path | line count | purpose

### 2. Python Client Extensions
New methods added to the client. New models. How client maps to API endpoints.

### 3. Seed Script Changes
What `seed_evaluations.py` does now vs before. New scenarios, change-point seeding.

### 4. E2E Test Changes
New test scenarios in `e2e_tests.py`.

### 5. Mock Adapter Scenarios
What changed in each scenario file and why.

### 6. Bootstrap Changes
New SLO definitions added.

### 7. Existing Documentation Inventory
For each doc file: title, what it covers, whether it's still accurate given the
current code. Flag any claims that don't match the implementation.

### 8. New Dependencies
Any new Python packages added in pyproject.toml files.

### 9. OpenAPI Surface
New endpoints and schemas visible in openapi.json.

## Rules
- Read every file completely (except openapi.json — skim for change-point sections).
- For the existing docs, cross-reference claims against actual code you've seen.
- Verify all function names and endpoints against actual code.
```

---

## Phase 2: Synthesis

After all 4 research reports are complete, synthesise into final documentation.
Launch synthesis agents in parallel, each reading the relevant reports.

---

### Task 5: Synthesis — `docs/modules/change-points.md` (user-facing)

**Files:**
- Create: `docs/modules/change-points.md`

- [ ] **Step 1: Launch synthesis agent**

Read reports `01-change-points-module.md`, `02-cross-cutting-changes.md`, and
`04-client-scripts-docs.md`. Write a user-facing overview of the change-point
detection system: what it does, how it works (high-level algorithm), how to
configure it, API endpoints, how to use via the Python client.

---

### Task 6: Synthesis — `api/docs/change-points.md` (contributor-facing)

**Files:**
- Create: `api/docs/change-points.md`

- [ ] **Step 1: Launch synthesis agent**

Read reports `01-change-points-module.md` and `02-cross-cutting-changes.md`.
Write a contributor-facing deep dive: engine internals, worker step lifecycle,
repository query patterns, integration seams with quality_gate module, test
organization, known issues.

---

### Task 7: Synthesis — `api/docs/configuration.md` (contributor-facing)

**Files:**
- Create: `api/docs/configuration.md`

- [ ] **Step 1: Launch synthesis agent**

Read report `01-change-points-module.md` (configuration section).
Write a short contributor doc: the configuration module's purpose, repository,
router, schema, how it's used by change-point detection.

---

### Task 8: Synthesis — `docs/modules/change-points-ui.md` (user-facing)

**Files:**
- Create: `docs/modules/change-points-ui.md`

- [ ] **Step 1: Launch synthesis agent**

Read report `03-ui-changes.md`. Write a user-facing UI feature doc: what the
Change Points page shows, how CP data surfaces in evaluations and navigator
heatmaps, the DTO/Domain/Mapper structure, component catalogue.

---

### Task 9: Synthesis — Update existing docs

**Files:**
- Modify: `api/docs/architecture.md` — add change-points module to architecture overview
- Modify: `docs/modules/evaluations-ui.md` — add change-point overlay info
- Modify: `docs/modules/navigator-ui.md` — add CP heatmap overlay info

- [ ] **Step 1: Launch synthesis agent**

Read all 4 reports. Make targeted additions to existing docs to reference the
new change-point system. Do not rewrite — just add relevant sections/paragraphs.

---

## Phase 3: Cleanup & Commit

### Task 10: Delete research reports and commit

- [ ] **Step 1: Delete research reports**
- [ ] **Step 2: Commit all final docs as a single commit**

```bash
git add docs/modules/change-points.md docs/modules/change-points-ui.md \
       api/docs/change-points.md api/docs/configuration.md \
       api/docs/architecture.md docs/modules/evaluations-ui.md \
       docs/modules/navigator-ui.md
git commit -m "doc: comprehensive change-point detection documentation from codebase research"
```
