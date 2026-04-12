# Quality Gate Module Restructuring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the flat `quality_gate/` module into a layered architecture with `evaluation_engine/`, `shared/`, `repositories/`, and `workflows/` folders — improving discoverability and making the import path tell you what layer you're in.

**Architecture:** Pure structural refactoring — file moves, renames, and import updates only. No logic, class name, or function signature changes. Each task moves one layer of files and updates all imports pointing to them (production + test code), so the test suite passes after every task.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, pytest, ruff, mypy

**Spec:** `docs/superpowers/specs/2026-04-11-quality-gate-restructuring-design.md`

---

### Task 1: Create directory structure

**Files:**
- Create: `api/app/modules/quality_gate/shared/__init__.py`
- Create: `api/app/modules/quality_gate/repositories/__init__.py`
- Create: `api/app/modules/quality_gate/workflows/__init__.py`
- Create: `api/app/modules/quality_gate/workflows/trigger/__init__.py`
- Create: `api/app/modules/quality_gate/workflows/execution/__init__.py`
- Create: `api/app/modules/quality_gate/workflows/re_evaluation/__init__.py`
- Create: `api/app/modules/quality_gate/workflows/presentation/__init__.py`
- Create: `api/tests/quality_gate/shared/__init__.py`
- Create: `api/tests/quality_gate/workflows/__init__.py`
- Create: `api/tests/quality_gate/workflows/trigger/__init__.py`
- Create: `api/tests/quality_gate/workflows/execution/__init__.py`
- Create: `api/tests/quality_gate/workflows/re_evaluation/__init__.py`
- Create: `api/tests/quality_gate/workflows/presentation/__init__.py`

- [ ] **Step 1: Create source directories**

```bash
mkdir -p api/app/modules/quality_gate/shared
mkdir -p api/app/modules/quality_gate/repositories
mkdir -p api/app/modules/quality_gate/workflows/trigger
mkdir -p api/app/modules/quality_gate/workflows/execution
mkdir -p api/app/modules/quality_gate/workflows/re_evaluation
mkdir -p api/app/modules/quality_gate/workflows/presentation
```

- [ ] **Step 2: Create test directories**

```bash
mkdir -p api/tests/quality_gate/shared
mkdir -p api/tests/quality_gate/evaluation_engine
mkdir -p api/tests/quality_gate/workflows/trigger
mkdir -p api/tests/quality_gate/workflows/execution
mkdir -p api/tests/quality_gate/workflows/re_evaluation
mkdir -p api/tests/quality_gate/workflows/presentation
```

- [ ] **Step 3: Create all `__init__.py` files**

Create empty `__init__.py` in each new directory (source and test). All 13 files listed above.

- [ ] **Step 4: Commit**

```
chore: create directory structure for quality_gate restructuring
```

---

### Task 2: Rename `engine/` to `evaluation_engine/`

This is the highest-impact rename — 62 import lines across the codebase reference `engine.*`.

**Files:**
- Rename: `api/app/modules/quality_gate/engine/` → `api/app/modules/quality_gate/evaluation_engine/`
- Rename: `api/tests/quality_gate/engine/` → `api/tests/quality_gate/evaluation_engine/`
- Modify: All files importing from `quality_gate.engine.*` (listed below)

- [ ] **Step 1: Rename source directory**

```bash
git mv api/app/modules/quality_gate/engine api/app/modules/quality_gate/evaluation_engine
```

- [ ] **Step 2: Rename test directory**

```bash
git mv api/tests/quality_gate/engine api/tests/quality_gate/evaluation_engine
```

- [ ] **Step 3: Update imports inside `evaluation_engine/` itself**

These files import from sibling modules using `quality_gate.engine.*`:

`api/app/modules/quality_gate/evaluation_engine/evaluator.py` — 4 imports:
```
quality_gate.engine.criteria → quality_gate.evaluation_engine.criteria
quality_gate.engine.result_models → quality_gate.evaluation_engine.result_models
quality_gate.engine.scoring → quality_gate.evaluation_engine.scoring
quality_gate.engine.slo_models → quality_gate.evaluation_engine.slo_models
```

`api/app/modules/quality_gate/evaluation_engine/scoring.py` — 4 imports:
```
quality_gate.engine.constants → quality_gate.evaluation_engine.constants
quality_gate.engine.criteria → quality_gate.evaluation_engine.criteria
quality_gate.engine.result_models → quality_gate.evaluation_engine.result_models
quality_gate.engine.slo_models → quality_gate.evaluation_engine.slo_models
```

`api/app/modules/quality_gate/evaluation_engine/result_models.py` — 2 imports:
```
quality_gate.engine.constants → quality_gate.evaluation_engine.constants
quality_gate.engine.slo_models → quality_gate.evaluation_engine.slo_models
```

`api/app/modules/quality_gate/evaluation_engine/slo_models.py` — 1 import:
```
quality_gate.engine.constants → quality_gate.evaluation_engine.constants
```

`api/app/modules/quality_gate/evaluation_engine/slo_parser.py` — 1 import:
```
quality_gate.engine.slo_models → quality_gate.evaluation_engine.slo_models
```

- [ ] **Step 4: Update imports in quality_gate source files**

`api/app/modules/quality_gate/repository.py`:
```
quality_gate.engine.constants → quality_gate.evaluation_engine.constants
```

`api/app/modules/quality_gate/evaluation_run_repository.py`:
```
quality_gate.engine.constants → quality_gate.evaluation_engine.constants
```

`api/app/modules/quality_gate/baseline_repository.py`:
```
quality_gate.engine.constants → quality_gate.evaluation_engine.constants
```

`api/app/modules/quality_gate/trend_repository.py`:
```
quality_gate.engine.constants → quality_gate.evaluation_engine.constants
```

`api/app/modules/quality_gate/indicator_repository.py`:
```
quality_gate.engine.result_models → quality_gate.evaluation_engine.result_models
```

`api/app/modules/quality_gate/presenter.py`:
```
quality_gate.engine.constants → quality_gate.evaluation_engine.constants
```

`api/app/modules/quality_gate/target_resolver.py`:
```
quality_gate.engine.criteria → quality_gate.evaluation_engine.criteria
```

`api/app/modules/quality_gate/evaluation_helpers.py` — 4 imports:
```
quality_gate.engine.criteria → quality_gate.evaluation_engine.criteria
quality_gate.engine.slo_models → quality_gate.evaluation_engine.slo_models
quality_gate.engine.slo_parser → quality_gate.evaluation_engine.slo_parser
quality_gate.engine.variables → quality_gate.evaluation_engine.variables
```

`api/app/modules/quality_gate/worker.py` — 4 imports:
```
quality_gate.engine.evaluator → quality_gate.evaluation_engine.evaluator
quality_gate.engine.slo_models → quality_gate.evaluation_engine.slo_models
quality_gate.engine.variables → quality_gate.evaluation_engine.variables
```

`api/app/modules/quality_gate/re_evaluator.py` — 2 imports:
```
quality_gate.engine.evaluator → quality_gate.evaluation_engine.evaluator
quality_gate.engine.slo_models → quality_gate.evaluation_engine.slo_models
```

- [ ] **Step 5: Update imports in external consumers**

`api/app/modules/slo_registry/router.py` — 2 imports:
```
quality_gate.engine.criteria → quality_gate.evaluation_engine.criteria
quality_gate.engine.slo_models → quality_gate.evaluation_engine.slo_models
quality_gate.engine.slo_parser → quality_gate.evaluation_engine.slo_parser
```

`api/app/modules/slo_registry/service.py` — 5 imports:
```
quality_gate.engine.criteria → quality_gate.evaluation_engine.criteria
quality_gate.engine.evaluator → quality_gate.evaluation_engine.evaluator
quality_gate.engine.slo_models → quality_gate.evaluation_engine.slo_models
quality_gate.engine.slo_parser → quality_gate.evaluation_engine.slo_parser
quality_gate.engine.variables → quality_gate.evaluation_engine.variables
```

- [ ] **Step 6: Update imports in test files**

`api/tests/conftest.py` — 2 imports:
```
quality_gate.engine.slo_models → quality_gate.evaluation_engine.slo_models
quality_gate.engine.slo_parser → quality_gate.evaluation_engine.slo_parser
```

`api/tests/quality_gate/evaluation_engine/test_criteria.py`:
```
quality_gate.engine.criteria → quality_gate.evaluation_engine.criteria
```

`api/tests/quality_gate/evaluation_engine/test_criteria_edge_cases.py`:
```
quality_gate.engine.criteria → quality_gate.evaluation_engine.criteria
```

`api/tests/quality_gate/evaluation_engine/test_evaluator.py`:
```
quality_gate.engine.evaluator → quality_gate.evaluation_engine.evaluator
```

`api/tests/quality_gate/evaluation_engine/test_evaluator_failures.py` — 3 imports:
```
quality_gate.engine.constants → quality_gate.evaluation_engine.constants
quality_gate.engine.evaluator → quality_gate.evaluation_engine.evaluator
quality_gate.engine.result_models → quality_gate.evaluation_engine.result_models
quality_gate.engine.slo_models → quality_gate.evaluation_engine.slo_models
```

`api/tests/quality_gate/evaluation_engine/test_scoring.py` — 2 imports:
```
quality_gate.engine.scoring → quality_gate.evaluation_engine.scoring
quality_gate.engine.slo_models → quality_gate.evaluation_engine.slo_models
quality_gate.engine.slo_parser → quality_gate.evaluation_engine.slo_parser
```

`api/tests/quality_gate/evaluation_engine/test_scoring_edge_cases.py` — 4 imports:
```
quality_gate.engine.constants → quality_gate.evaluation_engine.constants
quality_gate.engine.evaluator → quality_gate.evaluation_engine.evaluator
quality_gate.engine.scoring → quality_gate.evaluation_engine.scoring
quality_gate.engine.slo_models → quality_gate.evaluation_engine.slo_models
```

`api/tests/quality_gate/evaluation_engine/test_slo_builder.py` — 2 imports:
```
quality_gate.engine.slo_models → quality_gate.evaluation_engine.slo_models
quality_gate.engine.slo_parser → quality_gate.evaluation_engine.slo_parser
```

`api/tests/quality_gate/evaluation_engine/test_variables.py`:
```
quality_gate.engine.variables → quality_gate.evaluation_engine.variables
```

`api/tests/quality_gate/evaluation_engine/test_variables_edge_cases.py`:
```
quality_gate.engine.variables → quality_gate.evaluation_engine.variables
```

`api/tests/quality_gate/test_worker_helpers.py`:
```
quality_gate.engine.variables → quality_gate.evaluation_engine.variables
```

All replacements follow the same pattern: `quality_gate.engine.` → `quality_gate.evaluation_engine.`

- [ ] **Step 7: Run tests**

```bash
./scripts/api-test.sh --tail 5
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```
refactor: rename quality_gate/engine to evaluation_engine
```

---

### Task 3: Move `shared/` files

Move cross-cutting infrastructure files: `exceptions.py`, `params.py`, `protocols.py`, `dependencies.py`.

**Files:**
- Move: `exceptions.py` → `shared/exceptions.py`
- Move: `params.py` → `shared/params.py`
- Move: `protocols.py` → `shared/protocols.py`
- Move: `dependencies.py` → `shared/dependencies.py`
- Modify: 10 files importing `exceptions`, 13 files importing `params`, 1 file importing `protocols`, 3 files importing `dependencies`

- [ ] **Step 1: Move all four files**

```bash
git mv api/app/modules/quality_gate/exceptions.py api/app/modules/quality_gate/shared/exceptions.py
git mv api/app/modules/quality_gate/params.py api/app/modules/quality_gate/shared/params.py
git mv api/app/modules/quality_gate/protocols.py api/app/modules/quality_gate/shared/protocols.py
git mv api/app/modules/quality_gate/dependencies.py api/app/modules/quality_gate/shared/dependencies.py
```

- [ ] **Step 2: Update `exceptions` imports in production code**

All replacements: `quality_gate.exceptions` → `quality_gate.shared.exceptions`

Files to update:
- `api/app/modules/quality_gate/repository.py` (DuplicateEvaluationError)
- `api/app/modules/quality_gate/re_evaluator.py` (BaselinePinConflictError)
- `api/app/modules/quality_gate/router.py` (BaselinePinConflictError)
- `api/app/modules/quality_gate/trigger.py` (AssetNotFoundError, SLONotConfiguredError)
- `api/app/modules/quality_gate/trigger_service.py` (multiple exceptions)
- `api/app/modules/quality_gate/schemas/__init__.py` (BaselinePinConflictError)

- [ ] **Step 3: Update `exceptions` imports in test code**

Files to update:
- `api/tests/quality_gate/test_trigger.py`
- `api/tests/quality_gate/test_trigger_service.py`
- `api/tests/quality_gate/test_reeval_pin_conflict.py`
- `api/tests/quality_gate/db/test_duplicate_prevention.py`

- [ ] **Step 4: Update `params` imports in production code**

All replacements: `quality_gate.params` → `quality_gate.shared.params`

Files to update:
- `api/app/modules/quality_gate/repository.py`
- `api/app/modules/quality_gate/trigger_service.py`

- [ ] **Step 5: Update `params` imports in test code**

Files to update:
- `api/tests/quality_gate/test_params.py`
- `api/tests/quality_gate/db/test_duplicate_prevention.py`
- `api/tests/quality_gate/db/test_re_evaluation.py`
- `api/tests/quality_gate/db/test_grouped_heatmap.py`
- `api/tests/quality_gate/db/test_evaluation_repository.py`
- `api/tests/quality_gate/db/test_heatmap_query.py`
- `api/tests/quality_gate/db/test_indicator_round_trip.py`
- `api/tests/quality_gate/db/test_baseline_query.py`
- `api/tests/quality_gate/db/test_trend_query.py`
- `api/tests/quality_gate/endpoints/test_re_evaluation_endpoints.py`
- `api/tests/quality_gate/endpoints/conftest.py`

- [ ] **Step 6: Update `protocols` imports**

All replacements: `quality_gate.protocols` → `quality_gate.shared.protocols`

Files to update:
- `api/app/modules/quality_gate/trigger.py`

- [ ] **Step 7: Update `dependencies` imports**

All replacements: `quality_gate.dependencies` → `quality_gate.shared.dependencies`

Files to update:
- `api/app/modules/quality_gate/router.py`
- `api/app/modules/quality_gate/trigger_service.py`
- `api/tests/quality_gate/test_trigger_service.py`

- [ ] **Step 8: Run tests**

```bash
./scripts/api-test.sh --tail 5
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```
refactor: move quality_gate cross-cutting files to shared/
```

---

### Task 4: Move `repositories/` files

Move all 7 repository files, drop the `_repository` suffix, rename `sli_repository` → `sli_value`.

**Files:**
- Move: `repository.py` → `repositories/evaluation.py`
- Move: `evaluation_run_repository.py` → `repositories/evaluation_run.py`
- Move: `baseline_repository.py` → `repositories/baseline.py`
- Move: `annotation_repository.py` → `repositories/annotation.py`
- Move: `indicator_repository.py` → `repositories/indicator.py`
- Move: `sli_repository.py` → `repositories/sli_value.py`
- Move: `trend_repository.py` → `repositories/trend.py`
- Create: `repositories/__init__.py` with re-exports
- Modify: ~40 files with import updates

- [ ] **Step 1: Move all 7 files**

```bash
git mv api/app/modules/quality_gate/repository.py api/app/modules/quality_gate/repositories/evaluation.py
git mv api/app/modules/quality_gate/evaluation_run_repository.py api/app/modules/quality_gate/repositories/evaluation_run.py
git mv api/app/modules/quality_gate/baseline_repository.py api/app/modules/quality_gate/repositories/baseline.py
git mv api/app/modules/quality_gate/annotation_repository.py api/app/modules/quality_gate/repositories/annotation.py
git mv api/app/modules/quality_gate/indicator_repository.py api/app/modules/quality_gate/repositories/indicator.py
git mv api/app/modules/quality_gate/sli_repository.py api/app/modules/quality_gate/repositories/sli_value.py
git mv api/app/modules/quality_gate/trend_repository.py api/app/modules/quality_gate/repositories/trend.py
```

- [ ] **Step 2: Write `repositories/__init__.py` with re-exports**

This allows external consumers to import from `quality_gate.repositories` directly:

```python
"""Repository layer — pure data access for quality gate entities."""

from app.modules.quality_gate.repositories.annotation import AnnotationRepository
from app.modules.quality_gate.repositories.baseline import BaselineRepository
from app.modules.quality_gate.repositories.evaluation import EvaluationRepository
from app.modules.quality_gate.repositories.evaluation_run import EvaluationRunRepository
from app.modules.quality_gate.repositories.indicator import (
    IndicatorRepository,
    build_indicator_row_dicts,
)
from app.modules.quality_gate.repositories.sli_value import SLIValueRepository
from app.modules.quality_gate.repositories.trend import TrendRepository

__all__ = [
    'AnnotationRepository',
    'BaselineRepository',
    'EvaluationRepository',
    'EvaluationRunRepository',
    'IndicatorRepository',
    'SLIValueRepository',
    'TrendRepository',
    'build_indicator_row_dicts',
]
```

- [ ] **Step 3: Update internal imports in moved repository files**

`repositories/evaluation.py` (was `repository.py`):
```
quality_gate.evaluation_engine.constants → (already updated in Task 2)
quality_gate.shared.exceptions → (already updated in Task 3)
quality_gate.shared.params → (already updated in Task 3)
```
No changes needed — these were already updated.

- [ ] **Step 4: Update `quality_gate.repository` imports (14 files)**

All replacements: `quality_gate.repository` → `quality_gate.repositories.evaluation`

Production code:
- `api/app/queue.py`
- `api/app/modules/quality_gate/shared/dependencies.py`
- `api/app/modules/quality_gate/re_evaluator.py`
- `api/app/modules/quality_gate/worker.py`

Test code:
- `api/tests/quality_gate/db/test_duplicate_prevention.py`
- `api/tests/quality_gate/db/test_evaluation_repository.py`
- `api/tests/quality_gate/db/test_re_evaluation.py`
- `api/tests/quality_gate/db/test_grouped_heatmap.py`
- `api/tests/quality_gate/db/test_heatmap_query.py`
- `api/tests/quality_gate/db/test_indicator_round_trip.py`
- `api/tests/quality_gate/db/test_baseline_query.py`
- `api/tests/quality_gate/db/test_trend_query.py`
- `api/tests/quality_gate/endpoints/test_re_evaluation_endpoints.py`
- `api/tests/quality_gate/endpoints/conftest.py`

- [ ] **Step 5: Update `quality_gate.evaluation_run_repository` imports (4 files)**

All replacements: `quality_gate.evaluation_run_repository` → `quality_gate.repositories.evaluation_run`

- `api/app/queue.py`
- `api/app/modules/quality_gate/shared/dependencies.py`
- `api/tests/quality_gate/db/test_evaluation_run_repository.py`
- `api/tests/quality_gate/db/test_grouped_heatmap.py`

- [ ] **Step 6: Update `quality_gate.baseline_repository` imports (8 files)**

All replacements: `quality_gate.baseline_repository` → `quality_gate.repositories.baseline`

- `api/app/queue.py`
- `api/app/modules/slo_registry/service.py`
- `api/app/modules/quality_gate/shared/dependencies.py`
- `api/app/modules/quality_gate/re_evaluator.py`
- `api/app/modules/quality_gate/worker.py`
- `api/tests/quality_gate/db/test_baseline_query.py`
- `api/tests/quality_gate/db/test_re_evaluation.py`
- `api/tests/quality_gate/db/test_evaluation_repository.py`

- [ ] **Step 7: Update `quality_gate.annotation_repository` imports (3 files)**

All replacements: `quality_gate.annotation_repository` → `quality_gate.repositories.annotation`

- `api/app/modules/quality_gate/shared/dependencies.py`
- `api/app/modules/quality_gate/re_evaluator.py`
- `api/tests/quality_gate/db/test_evaluation_repository.py`

- [ ] **Step 8: Update `quality_gate.indicator_repository` imports (7 files)**

All replacements: `quality_gate.indicator_repository` → `quality_gate.repositories.indicator`

- `api/app/modules/quality_gate/worker.py`
- `api/app/modules/quality_gate/re_evaluator.py`
- `api/tests/quality_gate/db/test_re_evaluation.py`
- `api/tests/quality_gate/db/test_trend_query.py`
- `api/tests/quality_gate/db/test_indicator_repository.py`
- `api/tests/quality_gate/db/test_indicator_round_trip.py`
- `api/tests/quality_gate/endpoints/test_re_evaluation_endpoints.py`

- [ ] **Step 9: Update `quality_gate.sli_repository` imports (4 files)**

All replacements: `quality_gate.sli_repository` → `quality_gate.repositories.sli_value`

- `api/app/modules/quality_gate/shared/dependencies.py`
- `api/app/modules/quality_gate/worker.py`
- `api/tests/quality_gate/db/test_trend_query.py`
- `api/tests/quality_gate/db/test_evaluation_repository.py`

- [ ] **Step 10: Update `quality_gate.trend_repository` imports (4 files)**

All replacements: `quality_gate.trend_repository` → `quality_gate.repositories.trend`

- `api/app/modules/quality_gate/shared/dependencies.py`
- `api/tests/quality_gate/db/test_grouped_heatmap.py`
- `api/tests/quality_gate/db/test_trend_query.py`
- `api/tests/quality_gate/db/test_heatmap_query.py`

- [ ] **Step 11: Run tests**

```bash
./scripts/api-test.sh --tail 5
```

Expected: all tests pass.

- [ ] **Step 12: Commit**

```
refactor: move quality_gate repositories into repositories/ layer
```

---

### Task 5: Move `workflows/trigger/` files

**Files:**
- Move: `trigger.py` → `workflows/trigger/trigger_resolver.py`
- Move: `trigger_service.py` → `workflows/trigger/trigger_service.py`
- Modify: 5 files with import updates

- [ ] **Step 1: Move files**

```bash
git mv api/app/modules/quality_gate/trigger.py api/app/modules/quality_gate/workflows/trigger/trigger_resolver.py
git mv api/app/modules/quality_gate/trigger_service.py api/app/modules/quality_gate/workflows/trigger/trigger_service.py
```

- [ ] **Step 2: Update `quality_gate.trigger` imports (3 files)**

All replacements: `quality_gate.trigger` → `quality_gate.workflows.trigger.trigger_resolver`

- `api/app/modules/quality_gate/workflows/trigger/trigger_service.py` (imports from trigger)
- `api/tests/quality_gate/test_resolve_all_slos.py`
- `api/tests/quality_gate/test_trigger.py`

- [ ] **Step 3: Update `quality_gate.trigger_service` imports (2 files)**

All replacements: `quality_gate.trigger_service` → `quality_gate.workflows.trigger.trigger_service`

- `api/app/modules/quality_gate/router.py`
- `api/tests/quality_gate/test_trigger_service.py`

- [ ] **Step 4: Update internal imports inside moved files**

`workflows/trigger/trigger_resolver.py` — update imports that reference modules already moved:
```
quality_gate.shared.exceptions → (already correct from Task 3)
quality_gate.shared.protocols → (already correct from Task 3)
```

`workflows/trigger/trigger_service.py` — update imports:
```
quality_gate.shared.dependencies → (already correct from Task 3)
quality_gate.shared.exceptions → (already correct from Task 3)
quality_gate.shared.params → (already correct from Task 3)
```

- [ ] **Step 5: Run tests**

```bash
./scripts/api-test.sh --tail 5
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```
refactor: move trigger files into workflows/trigger/
```

---

### Task 6: Move `workflows/execution/` files

**Files:**
- Move: `worker.py` → `workflows/execution/evaluation_executor.py`
- Move: `adapter_client.py` → `workflows/execution/adapter_client.py`
- Move: `evaluation_helpers.py` → `workflows/execution/evaluation_helpers.py`
- Modify: ~10 files with import updates

- [ ] **Step 1: Move files**

```bash
git mv api/app/modules/quality_gate/worker.py api/app/modules/quality_gate/workflows/execution/evaluation_executor.py
git mv api/app/modules/quality_gate/adapter_client.py api/app/modules/quality_gate/workflows/execution/adapter_client.py
git mv api/app/modules/quality_gate/evaluation_helpers.py api/app/modules/quality_gate/workflows/execution/evaluation_helpers.py
```

- [ ] **Step 2: Update `quality_gate.worker` imports (5 files)**

All replacements: `quality_gate.worker` → `quality_gate.workflows.execution.evaluation_executor`

- `api/app/queue.py`
- `api/tests/quality_gate/test_worker_helpers.py`
- `api/tests/quality_gate/test_baselines.py`
- `api/tests/quality_gate/test_queue.py`
- `api/tests/quality_gate/test_worker_phases.py`

- [ ] **Step 3: Update `quality_gate.adapter_client` imports (3 files)**

All replacements: `quality_gate.adapter_client` → `quality_gate.workflows.execution.adapter_client`

- `api/app/queue.py`
- `api/app/modules/quality_gate/workflows/execution/evaluation_executor.py`
- `api/tests/quality_gate/test_adapter_client.py`

- [ ] **Step 4: Update `quality_gate.evaluation_helpers` imports (3 files)**

All replacements: `quality_gate.evaluation_helpers` → `quality_gate.workflows.execution.evaluation_helpers`

- `api/app/modules/quality_gate/workflows/execution/evaluation_executor.py`
- `api/app/modules/quality_gate/re_evaluator.py`
- `api/tests/quality_gate/test_evaluation_helpers.py`

- [ ] **Step 5: Run tests**

```bash
./scripts/api-test.sh --tail 5
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```
refactor: move worker and helpers into workflows/execution/
```

---

### Task 7: Move `workflows/re_evaluation/` files

**Files:**
- Move: `re_evaluator.py` → `workflows/re_evaluation/re_evaluation_service.py`
- Modify: 2 files with import updates

- [ ] **Step 1: Move file**

```bash
git mv api/app/modules/quality_gate/re_evaluator.py api/app/modules/quality_gate/workflows/re_evaluation/re_evaluation_service.py
```

- [ ] **Step 2: Update `quality_gate.re_evaluator` imports (2 files)**

All replacements: `quality_gate.re_evaluator` → `quality_gate.workflows.re_evaluation.re_evaluation_service`

- `api/app/modules/quality_gate/router.py`
- `api/tests/quality_gate/db/test_re_evaluation.py`

- [ ] **Step 3: Run tests**

```bash
./scripts/api-test.sh --tail 5
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```
refactor: move re_evaluator into workflows/re_evaluation/
```

---

### Task 8: Move `workflows/presentation/` files

**Files:**
- Move: `presenter.py` → `workflows/presentation/presenter.py`
- Move: `target_resolver.py` → `workflows/presentation/target_resolver.py`
- Modify: ~6 files with import updates

- [ ] **Step 1: Move files**

```bash
git mv api/app/modules/quality_gate/presenter.py api/app/modules/quality_gate/workflows/presentation/presenter.py
git mv api/app/modules/quality_gate/target_resolver.py api/app/modules/quality_gate/workflows/presentation/target_resolver.py
```

- [ ] **Step 2: Update `quality_gate.presenter` imports (4 files)**

All replacements: `quality_gate.presenter` → `quality_gate.workflows.presentation.presenter`

- `api/app/modules/quality_gate/router.py`
- `api/tests/quality_gate/test_presenter.py`
- `api/tests/quality_gate/test_heatmap_builder.py`
- `api/tests/quality_gate/db/test_indicator_round_trip.py`

- [ ] **Step 3: Update `quality_gate.target_resolver` imports (3 files)**

All replacements: `quality_gate.target_resolver` → `quality_gate.workflows.presentation.target_resolver`

- `api/app/modules/quality_gate/router.py`
- `api/app/modules/quality_gate/workflows/presentation/presenter.py`
- `api/tests/quality_gate/test_target_resolver.py`

- [ ] **Step 4: Run tests**

```bash
./scripts/api-test.sh --tail 5
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```
refactor: move presenter and target_resolver into workflows/presentation/
```

---

### Task 9: Move test files into mirrored structure

Now that all source files are in their final locations, move the 16 loose test files into the mirrored test directory structure.

**Files:**
- Move: 16 test files (see mapping below)
- No import changes needed — test files import from production code (already updated), not from each other

- [ ] **Step 1: Move `shared/` tests**

```bash
git mv api/tests/quality_gate/test_schemas.py api/tests/quality_gate/shared/test_schemas.py
git mv api/tests/quality_gate/test_params.py api/tests/quality_gate/shared/test_params.py
```

- [ ] **Step 2: Move `workflows/trigger/` tests**

```bash
git mv api/tests/quality_gate/test_trigger.py api/tests/quality_gate/workflows/trigger/test_trigger_resolver.py
git mv api/tests/quality_gate/test_trigger_service.py api/tests/quality_gate/workflows/trigger/test_trigger_service.py
git mv api/tests/quality_gate/test_resolve_all_slos.py api/tests/quality_gate/workflows/trigger/test_resolve_all_slos.py
```

- [ ] **Step 3: Move `workflows/execution/` tests**

```bash
git mv api/tests/quality_gate/test_worker_phases.py api/tests/quality_gate/workflows/execution/test_executor_phases.py
git mv api/tests/quality_gate/test_worker_helpers.py api/tests/quality_gate/workflows/execution/test_executor_helpers.py
git mv api/tests/quality_gate/test_baselines.py api/tests/quality_gate/workflows/execution/test_baselines.py
git mv api/tests/quality_gate/test_queue.py api/tests/quality_gate/workflows/execution/test_queue.py
git mv api/tests/quality_gate/test_adapter_client.py api/tests/quality_gate/workflows/execution/test_adapter_client.py
git mv api/tests/quality_gate/test_evaluation_helpers.py api/tests/quality_gate/workflows/execution/test_evaluation_helpers.py
```

- [ ] **Step 4: Move `workflows/re_evaluation/` tests**

```bash
git mv api/tests/quality_gate/test_re_evaluator.py api/tests/quality_gate/workflows/re_evaluation/test_re_evaluation_service.py
git mv api/tests/quality_gate/test_reeval_pin_conflict.py api/tests/quality_gate/workflows/re_evaluation/test_reeval_pin_conflict.py
```

- [ ] **Step 5: Move `workflows/presentation/` tests**

```bash
git mv api/tests/quality_gate/test_presenter.py api/tests/quality_gate/workflows/presentation/test_presenter.py
git mv api/tests/quality_gate/test_heatmap_builder.py api/tests/quality_gate/workflows/presentation/test_heatmap_builder.py
git mv api/tests/quality_gate/test_target_resolver.py api/tests/quality_gate/workflows/presentation/test_target_resolver.py
```

- [ ] **Step 6: Update any test-internal import paths**

Test files that were renamed (not just moved) need their mock/patch target paths updated:

- `test_trigger_resolver.py` (was `test_trigger.py`) — check for `@patch('app.modules.quality_gate.trigger.*')` strings and update to `quality_gate.workflows.trigger.trigger_resolver.*`
- `test_trigger_service.py` — check for `@patch('app.modules.quality_gate.trigger_service.*')` and update to `quality_gate.workflows.trigger.trigger_service.*`
- `test_executor_phases.py` (was `test_worker_phases.py`) — check for `@patch('app.modules.quality_gate.worker.*')` and update to `quality_gate.workflows.execution.evaluation_executor.*`
- `test_executor_helpers.py` (was `test_worker_helpers.py`) — same pattern
- `test_baselines.py` — check for worker-patching
- `test_queue.py` — check for worker-patching
- `test_re_evaluation_service.py` (was `test_re_evaluator.py`) — check for `@patch('app.modules.quality_gate.re_evaluator.*')` and update
- `test_adapter_client.py` — check for adapter_client patching
- `test_presenter.py` — check for presenter patching
- `test_heatmap_builder.py` — check for presenter patching

**Important:** Every `@patch()` or `patch()` call uses a string path to the module. These strings must match the new file locations or mocks will silently fail (tests pass but don't actually test anything).

- [ ] **Step 7: Run tests**

```bash
./scripts/api-test.sh --tail 5
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```
refactor: move quality_gate test files into mirrored structure
```

---

### Task 10: Clean up stale references and verify

Final verification pass — lint, typecheck, and confirm no stale imports remain.

**Files:**
- Modify: `CLAUDE.md` (update workspace layout section)
- Delete: any empty directories left behind from git mv

- [ ] **Step 1: Check for stale `quality_gate.engine.` imports**

Search the entire `api/` directory for any remaining references to the old paths:

```bash
rg "quality_gate\.engine\." api/ --type py
```

Expected: no results (all updated in Task 2).

- [ ] **Step 2: Check for stale `quality_gate.repository` imports (bare)**

```bash
rg "from app\.modules\.quality_gate\.repository " api/ --type py
```

Expected: no results. Note the trailing space — distinguishes `repository` from `repositories`.

- [ ] **Step 3: Check for stale flat-file imports**

```bash
rg "quality_gate\.(adapter_client|annotation_repository|baseline_repository|evaluation_run_repository|evaluation_helpers|exceptions|indicator_repository|params|presenter|protocols|re_evaluator|sli_repository|target_resolver|trend_repository|trigger_service|worker|dependencies)" api/ --type py
```

Expected: no results.

- [ ] **Step 4: Run lint**

```bash
uv run --directory api ruff check app/ tests/ 2>&1 | tail -20
```

Expected: no import-related errors.

- [ ] **Step 5: Run typecheck**

```bash
uv run mypy api/app 2>&1 | tail -20
```

Expected: no new errors.

- [ ] **Step 6: Run full test suite**

```bash
./scripts/api-test.sh --tail 5
```

Expected: all tests pass, same count as before restructuring.

- [ ] **Step 7: Update CLAUDE.md workspace layout**

Update the `Workspace Layout` section in `CLAUDE.md` to reflect the new structure:

```markdown
│   │   │   ├── quality_gate/     # Evaluation router + layered architecture
│   │   │   │   ├── evaluation_engine/  # Pure scoring logic (zero I/O)
│   │   │   │   ├── repositories/       # Data access layer
│   │   │   │   ├── workflows/          # Orchestration (trigger, execution, re-eval, presentation)
│   │   │   │   ├── schemas/            # API contracts
│   │   │   │   └── shared/             # Cross-cutting (exceptions, params, DI)
```

- [ ] **Step 8: Clean up empty directories**

Remove any empty directories left behind by git mv (git doesn't track empty dirs):

```bash
find api/app/modules/quality_gate -type d -empty -delete
find api/tests/quality_gate -type d -empty -delete
```

- [ ] **Step 9: Commit**

```
refactor: finalize quality_gate restructuring and update docs
```

---

## Summary

| Task | Description | Files moved | Imports updated |
|------|-------------|-------------|-----------------|
| 1 | Create directory structure | 0 | 0 |
| 2 | Rename engine → evaluation_engine | 2 dirs | ~62 |
| 3 | Move shared/ files | 4 | ~27 |
| 4 | Move repositories/ files | 7 | ~44 |
| 5 | Move workflows/trigger/ | 2 | ~5 |
| 6 | Move workflows/execution/ | 3 | ~11 |
| 7 | Move workflows/re_evaluation/ | 1 | ~2 |
| 8 | Move workflows/presentation/ | 2 | ~7 |
| 9 | Move test files | 16 | ~15 (patch strings) |
| 10 | Clean up and verify | 0 | 0 |
| **Total** | | **35 files** | **~173 imports** |
