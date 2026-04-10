# Quality Gate Module Restructuring

**Date:** 2026-04-11
**Status:** Draft
**Scope:** Source and test restructuring of `api/app/modules/quality_gate/` — file moves, renames, and import updates. No logic changes.

## Problem

The `quality_gate` module has 21 files at its root plus two subfolders (`engine/`, `schemas/`). It is 3x larger than any other module in the project, but uses a flat layout that works for smaller modules (4-6 files). The result:

- **No visible layers.** A data access file (`baseline_repository.py`) sits next to an orchestrator (`re_evaluator.py`) sits next to a pure utility (`evaluation_helpers.py`). You must open each file to know what layer you're in.
- **Ambiguous names.** `repository.py` (which entity?), `trigger.py` (it resolves, not triggers), `worker.py` (named after infrastructure, not purpose), `evaluation_helpers.py` (vague "helpers"), `engine/` (too generic).
- **Inconsistent conventions.** `re_evaluator.py` is module-level functions; `trigger_service.py` is a class. `sli_repository.py` manages SLI values, not definitions — confusing against `sli_registry/`.

## Design Principles

1. **Layered architecture.** Code is organized into clear layers with strict dependency direction: `router` → `workflows` → `repositories` / `evaluation_engine`. Each layer has one job.
2. **Filenames are globally unique.** Workflow files use a domain prefix (`trigger_service.py`, `trigger_resolver.py`) so `@`-search in editors and LLMs returns one hit, not many `service.py` matches.
3. **Repository suffix dropped.** Inside `repositories/`, the folder provides context — `repositories/baseline.py` is self-explanatory.
4. **No logic changes.** Class names, function signatures, and behavior are unchanged. This is purely structural.

## Target Structure

### Source: `api/app/modules/quality_gate/`

```
quality_gate/
├── __init__.py
├── router.py                              # HTTP entry point (unchanged location)
│
├── shared/                                # module-wide infrastructure
│   ├── __init__.py
│   ├── dependencies.py                    # FastAPI DI container (QualityGateRepos)
│   ├── exceptions.py                      # domain-specific errors
│   ├── protocols.py                       # interface types for trigger resolution
│   └── params.py                          # EvalCreateParams
│
├── schemas/                               # API contracts (unchanged location)
│   ├── __init__.py
│   ├── annotations.py
│   ├── baseline.py
│   ├── evaluations.py
│   ├── heatmap.py
│   ├── re_evaluation.py
│   └── trigger.py
│
├── evaluation_engine/                     # pure scoring math, zero I/O (renamed from engine/)
│   ├── __init__.py
│   ├── constants.py
│   ├── criteria.py
│   ├── evaluator.py
│   ├── result_models.py
│   ├── scoring.py
│   ├── slo_models.py
│   ├── slo_parser.py
│   └── variables.py
│
├── repositories/                          # pure data access layer
│   ├── __init__.py                        # re-exports all repository classes
│   ├── evaluation.py                      # was repository.py — SLOEvaluation CRUD
│   ├── evaluation_run.py                  # was evaluation_run_repository.py
│   ├── baseline.py                        # was baseline_repository.py
│   ├── annotation.py                      # was annotation_repository.py
│   ├── indicator.py                       # was indicator_repository.py
│   ├── sli_value.py                       # was sli_repository.py — renamed for clarity
│   └── trend.py                           # was trend_repository.py
│
└── workflows/                             # orchestration layer
    ├── __init__.py
    ├── trigger/                           # kick off evaluations
    │   ├── __init__.py
    │   ├── trigger_resolver.py            # was trigger.py (resolve_single_trigger, etc.)
    │   └── trigger_service.py             # was trigger_service.py (TriggerService class)
    ├── execution/                         # run evaluations (arq worker jobs)
    │   ├── __init__.py
    │   ├── evaluation_executor.py         # was worker.py
    │   ├── adapter_client.py              # was adapter_client.py (HTTP SLI fetching)
    │   └── evaluation_helpers.py          # was evaluation_helpers.py (shared with re_evaluation)
    ├── re_evaluation/                     # re-score historical evaluations
    │   ├── __init__.py
    │   └── re_evaluation_service.py       # was re_evaluator.py
    └── presentation/                      # format results for API responses
        ├── __init__.py
        ├── presenter.py                   # was presenter.py (build_summary, build_detail, etc.)
        └── target_resolver.py             # was target_resolver.py (pass/warning targets)
```

### File move map (source)

| Current path | New path |
|---|---|
| `repository.py` | `repositories/evaluation.py` |
| `evaluation_run_repository.py` | `repositories/evaluation_run.py` |
| `baseline_repository.py` | `repositories/baseline.py` |
| `annotation_repository.py` | `repositories/annotation.py` |
| `indicator_repository.py` | `repositories/indicator.py` |
| `sli_repository.py` | `repositories/sli_value.py` |
| `trend_repository.py` | `repositories/trend.py` |
| `trigger.py` | `workflows/trigger/trigger_resolver.py` |
| `trigger_service.py` | `workflows/trigger/trigger_service.py` |
| `worker.py` | `workflows/execution/evaluation_executor.py` |
| `adapter_client.py` | `workflows/execution/adapter_client.py` |
| `evaluation_helpers.py` | `workflows/execution/evaluation_helpers.py` |
| `re_evaluator.py` | `workflows/re_evaluation/re_evaluation_service.py` |
| `presenter.py` | `workflows/presentation/presenter.py` |
| `target_resolver.py` | `workflows/presentation/target_resolver.py` |
| `dependencies.py` | `shared/dependencies.py` |
| `exceptions.py` | `shared/exceptions.py` |
| `protocols.py` | `shared/protocols.py` |
| `params.py` | `shared/params.py` |
| `engine/` | `evaluation_engine/` (rename directory) |

### Tests: `api/tests/quality_gate/`

Tests mirror the source structure. Already-organized subfolders stay as-is.

```
tests/quality_gate/
├── test_router.py                         # stays at root
│
├── shared/
│   ├── test_schemas.py                    # was test_schemas.py
│   └── test_params.py                     # was test_params.py
│
├── evaluation_engine/                     # renamed from engine/
│   └── (all existing files, unchanged)
│
├── endpoints/                             # unchanged
│   └── (all existing files)
│
├── db/                                    # unchanged
│   └── (all existing files)
│
└── workflows/
    ├── trigger/
    │   ├── test_trigger_resolver.py       # was test_trigger.py
    │   ├── test_trigger_service.py        # was test_trigger_service.py
    │   └── test_resolve_all_slos.py       # was test_resolve_all_slos.py
    ├── execution/
    │   ├── test_executor_phases.py        # was test_worker_phases.py
    │   ├── test_executor_helpers.py       # was test_worker_helpers.py
    │   ├── test_baselines.py             # was test_baselines.py
    │   ├── test_queue.py                  # was test_queue.py
    │   ├── test_adapter_client.py         # was test_adapter_client.py
    │   └── test_evaluation_helpers.py     # was test_evaluation_helpers.py
    ├── re_evaluation/
    │   ├── test_re_evaluation_service.py  # was test_re_evaluator.py
    │   └── test_reeval_pin_conflict.py    # was test_reeval_pin_conflict.py
    └── presentation/
        ├── test_presenter.py             # was test_presenter.py
        ├── test_heatmap_builder.py        # was test_heatmap_builder.py
        └── test_target_resolver.py        # was test_target_resolver.py
```

## External consumers requiring import updates

| File | Current imports from | New imports from |
|---|---|---|
| `api/app/main.py` | `quality_gate.router` | No change |
| `api/app/queue.py` | `quality_gate.adapter_client`, `quality_gate.baseline_repository`, `quality_gate.evaluation_run_repository`, `quality_gate.repository`, `quality_gate.worker` | `quality_gate.workflows.execution.adapter_client`, `quality_gate.repositories`, `quality_gate.workflows.execution.evaluation_executor` |
| `api/app/modules/slo_registry/router.py` | `quality_gate.engine.*` | `quality_gate.evaluation_engine.*` |
| `api/app/modules/slo_registry/service.py` | `quality_gate.baseline_repository`, `quality_gate.engine.*`, `quality_gate.schemas` | `quality_gate.repositories.baseline`, `quality_gate.evaluation_engine.*`, `quality_gate.schemas` |
| `api/app/modules/slo_registry/schemas.py` | `quality_gate.schemas` | No change |

## Cross-workflow import

`workflows/re_evaluation/re_evaluation_service.py` imports `evaluation_helpers` from `workflows/execution/evaluation_helpers.py`. This cross-workflow dependency is accepted — the helpers (`build_slo_model`, `compute_baselines`, `build_eval_variables`) are evaluation-pipeline-specific, not generic infrastructure. If this becomes a pain point, the helpers can move to `shared/` later.

## Out of scope

- Class or function renames (names stay the same, only file locations change)
- Logic changes or refactoring
- Database model changes
- Restructuring other modules (`assets/`, `datasource/`, `sli_registry/`, `slo_registry/`)
- Changes to `db/` or `endpoints/` test subfolders (already well-organized)
