# Testing Guide

Contributor-facing documentation for TROPEK's API test infrastructure,
patterns, and coverage.

---

## Test Infrastructure

### Running Tests

```bash
# Unit tests (no infra required)
just test                    # or: uv run --directory api pytest tests/ -m "not integration" -q

# Integration tests (requires test database)
just test-env                # start test TimescaleDB on port 5433
just test-int                # run integration tests
just test-env-down           # tear down

# Specific file
just test-one quality_gate/evaluation_engine/test_evaluator.py

# Agent-friendly (summary only)
./scripts/api-test.sh --tail 5
./scripts/api-test.sh --tail 20 tests/db/test_baseline_query.py -v
```

### Test Database

Integration tests use a dedicated TimescaleDB instance on port 5433, completely
separate from the dev database on port 5432. The `.env.test` file is committed
with local defaults and loaded automatically by `pytest-dotenv`.

**Ephemeral database per session.** The `db_engine` fixture
(`api/tests/db/conftest.py:48-104`) creates a fresh database named
`tropek_test_<uuid>` on every pytest session. The schema is built from
SQLAlchemy models via `Base.metadata.create_all` (not Alembic migrations),
then dropped on teardown. This means parallel sessions on different
branches/worktrees never collide.

**Seed data.** Because `create_all` does not run data migrations, the
`db_engine` fixture seeds four default annotation categories (failure, info,
investigation, re-evaluation) that migration 002 would normally insert
(`api/tests/db/conftest.py:78-95`).

### Pytest Configuration

Key settings from `pyproject.toml`:

- `asyncio_mode = auto` -- all async test functions run without explicit
  `@pytest.mark.asyncio`
- Integration tests are marked with `@pytest.mark.integration` (or module-level
  `pytestmark = pytest.mark.integration`)
- The default test run (`just test`) excludes integration tests via `-m "not integration"`

---

## Conftest Hierarchy

### Root conftest (`api/tests/conftest.py`)

Provides two fixtures available to all tests:

- **`slo_fixture`** -- callable fixture that loads YAML from
  `api/tests/data/slo/`, parses with `yaml.safe_load`, and constructs a
  validated `SLO` model via `build_slo()`. Usage:
  `result = evaluate(slo_fixture('full_evaluation.yaml'), metrics, baselines={})`

- **`result_data`** -- callable fixture that loads raw text from
  `api/tests/data/results/` by filename.

### Database conftest (`api/tests/db/conftest.py`)

Session-scoped fixtures for integration tests:

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `db_url` | session | Reads `TEST_DATABASE_URL` from env; skips if not set |
| `db_engine` | session | Creates ephemeral database, runs `create_all`, seeds categories |
| `db_session` | function | Per-test session with savepoint rollback -- no data leaks between tests |
| `redis_client` | function | `fakeredis.aioredis.FakeRedis` instance, flushed on teardown |
| `info_category_id` | function | Returns the UUID of the seeded "info" annotation category |

**Savepoint rollback pattern** (`api/tests/db/conftest.py:132-151`): each test
gets a session bound to a connection with an open transaction. The session uses
`join_transaction_mode='create_savepoint'` so it joins the outer transaction
rather than starting its own (required for asyncpg compatibility with
`SELECT ... FOR UPDATE`). On teardown, the connection rolls back, undoing all
test writes.

### Quality gate DB conftest (`api/tests/quality_gate/db/conftest.py`)

Extends the base DB fixtures with:

- **`api_client`** -- `httpx.AsyncClient` bound to the FastAPI `app` via
  `ASGITransport`. Overrides `get_session` to inject the test session and
  `get_heatmap_column_cache` to inject fakeredis. Cleared on teardown via
  `app.dependency_overrides.clear()`.

- **`seed_asset_with_indicators`** -- factory fixture that creates an asset
  type, asset, and N completed `EvaluationRun`/`SLOEvaluation` pairs. Returns
  a `SeededAsset(id, name)` dataclass. Used heavily by heatmap and cache tests.

### Asset meta DB conftest (`api/tests/asset_meta/db/conftest.py`)

Same `api_client` pattern as quality gate. Adds `test_asset_id` fixture that
creates a throwaway asset type + asset and returns the asset UUID.

---

## Test File Organization

```
api/tests/
├── conftest.py                           # Root: slo_fixture, result_data
├── data/
│   ├── slo/                              # YAML fixtures for engine tests
│   │   ├── full_evaluation.yaml          #   3 objectives, fixed+relative, key_sli
│   │   ├── minimal.yaml                  #   Single objective, fixed <600
│   │   ├── multi_objective_weighted.yaml  #   Weighted, informational
│   │   └── relative_comparison.yaml      #   Relative-only with scope_tags
│   └── results/                          # Result file fixtures
├── db/
│   ├── conftest.py                       # Core DB fixtures (engine, session, redis)
│   ├── test_annotation_category_repository.py  # 7 tests
│   └── test_note_category_router.py            # 7 tests
├── quality_gate/
│   ├── db/
│   │   ├── conftest.py                   # api_client, seed_asset_with_indicators
│   │   ├── test_baseline_query.py        # 2 tests
│   │   ├── test_column_annotations.py    # 5 tests
│   │   ├── test_duplicate_prevention.py  # 6 tests
│   │   ├── test_evaluation_names.py      # 2 tests
│   │   ├── test_evaluation_repository.py # 13 tests
│   │   ├── test_evaluation_run_repository.py # 8 tests
│   │   ├── test_finalize_sweeper.py      # 5 tests
│   │   ├── test_grouped_heatmap.py       # 4 tests
│   │   ├── test_grouped_heatmap_has_notes.py # 3 tests
│   │   ├── test_heatmap_cache.py         # 14 tests (incl. property test)
│   │   ├── test_heatmap_query.py         # 2 tests
│   │   ├── test_indicator_repository.py  # 3 tests
│   │   ├── test_indicator_round_trip.py  # 3 tests
│   │   ├── test_re_evaluation.py         # 5 tests
│   │   ├── test_trend_query.py           # 3 tests
│   │   └── test_trigger_evaluate.py      # 3 tests
│   ├── endpoints/                        # Router-level unit tests (mocked deps)
│   │   ├── test_annotation_endpoints.py
│   │   ├── test_baseline_pin_endpoints.py
│   │   ├── test_heatmap_endpoints.py
│   │   ├── test_invalidation_endpoints.py
│   │   ├── test_override_endpoints.py
│   │   ├── test_re_evaluation_endpoints.py
│   │   └── test_smoke.py
│   ├── evaluation_engine/                # Pure unit tests (zero I/O)
│   │   ├── test_criteria.py              # 203 lines
│   │   ├── test_criteria_edge_cases.py   # 86 lines
│   │   ├── test_evaluator.py             # 98 lines
│   │   ├── test_evaluator_failures.py    # 147 lines
│   │   ├── test_scoring.py               # 155 lines
│   │   ├── test_scoring_edge_cases.py    # 138 lines
│   │   ├── test_variables.py             # 99 lines
│   │   ├── test_variables_edge_cases.py  # 77 lines
│   │   ├── test_comparison_rules.py      # Tests assets.comparison_rules (misplaced)
│   │   ├── test_generator.py             # Tests slo_groups.generator (misplaced)
│   │   ├── test_regeneration.py          # Tests slo_groups.regeneration (misplaced)
│   │   └── test_slo_builder.py           # 66 lines
│   ├── shared/
│   │   ├── test_params.py
│   │   └── test_schemas.py
│   └── workflows/
│       ├── execution/
│       │   ├── test_adapter_client.py
│       │   ├── test_baselines.py
│       │   ├── test_evaluation_helpers.py
│       │   ├── test_executor_helpers.py
│       │   ├── test_executor_phases.py
│       │   └── test_queue.py
│       ├── presentation/
│       │   ├── test_heatmap_builder.py
│       │   ├── test_presenter.py
│       │   ├── test_presenter_fragment_builder.py
│       │   └── test_target_resolver.py
│       └── trigger/
│           ├── test_resolve_all_slos.py
│           ├── test_trigger_resolver.py
│           └── test_trigger_service.py
├── asset_meta/
│   ├── test_schemas.py                   # Pydantic validation rules
│   ├── test_service.py                   # Service with FakeRepository
│   ├── db/                               # Integration tests
│   │   ├── test_ingest_endpoint.py
│   │   ├── test_read_endpoint.py
│   │   ├── test_repository.py
│   │   └── test_summary_endpoint.py
│   └── timeline/                         # Pure pipeline unit tests
│       ├── test_clipping.py              # 12-case parametrize matrix
│       ├── test_conflict_resolution.py
│       ├── test_derivation.py
│       ├── test_item_emitter.py
│       ├── test_orchestrator.py          # 19 end-to-end scenarios
│       ├── test_summary.py
│       ├── test_tree_builder.py
│       └── test_types.py
├── assets/db/test_asset_repositories.py
├── assignments/db/
│   ├── test_assignments.py
│   └── test_binding_resolution.py
├── cache/test_redis_cache.py
├── common/
│   ├── db/test_tag_mixin.py
│   ├── test_exceptions.py
│   ├── test_input_types.py
│   └── test_openapi_postprocessor.py
├── datasource/db/test_datasource_repository.py
├── display_groups/db/test_display_groups.py
├── schemathesis/
│   ├── test_schema.py
│   └── test_stateful.py
├── sli_registry/
│   ├── db/test_comparable_from_version.py
│   ├── db/test_sli_repository.py
│   ├── test_params.py
│   └── test_schemas.py
├── slo_groups/db/test_slo_groups.py
├── slo_registry/
│   ├── db/test_slo_repository.py
│   ├── test_params.py
│   ├── test_service.py
│   └── test_validate.py
├── test_config.py
├── test_db_imports.py
├── test_schema_contracts.py
└── test_session_middleware.py
```

---

## Unit Test Patterns

### Pure Engine Tests (zero I/O)

Tests in `api/tests/quality_gate/evaluation_engine/` exercise the scoring
engine without any database, network, or filesystem access. All data arrives
via function arguments or the `slo_fixture` callable.

**Pattern:**

```python
def test_all_pass_no_baseline(slo_fixture) -> None:
    metrics = {'response_time': 450.0, 'error_rate': 0.5, 'throughput': 200.0}
    result = evaluate(slo_fixture('full_evaluation.yaml'), metrics, baselines={})
    assert result.result == EvaluationOutcome.PASS
```

**Key conventions:**
- Tests import production code at the top of the file (never inside test bodies)
- YAML fixtures live in `api/tests/data/slo/`, loaded via `slo_fixture`
- No mocking -- the engine is pure functions, so tests pass real data
- Edge cases get separate files (e.g., `test_criteria_edge_cases.py`)

### Pipeline Tests (asset meta timeline)

The timeline pipeline follows the same zero-I/O pattern. Each pipeline stage
has its own test file with targeted unit tests. The orchestrator test
(`test_orchestrator.py`) runs 19 numbered end-to-end scenarios through the
full five-stage pipeline.

**Clipping tests** use an exhaustive 2x3x2=12 parametrize matrix covering all
combinations of start position (before/within window), end position
(before/within/after window), and span state (open/closed).

### Service Tests with Fakes

`api/tests/asset_meta/test_service.py` demonstrates testing the service layer
without a database by using a `FakeRepository` dataclass and `AsyncMock`
session. This pattern tests orchestration logic (existence checks, write
ordering, response construction) without touching infrastructure.

### Workflow Tests

Tests in `api/tests/quality_gate/workflows/` test the trigger, execution, and
presentation layers. These use protocol stubs and mocks for repository
dependencies, testing orchestration logic without a database.

---

## Integration Test Patterns

### Database Tests

All integration test files use the module-level marker:

```python
pytestmark = pytest.mark.integration
```

**Key patterns:**

1. **Savepoint isolation** -- each test runs inside a rolled-back transaction.
   No cleanup code needed; the `db_session` fixture handles it.

2. **Randomized names** -- tests create assets and types with UUID-suffixed
   names (`f'cache-test-{uuid.uuid4().hex[:8]}'`) to avoid collisions even
   if savepoint rollback fails.

3. **Factory fixtures** -- complex setup is encapsulated in factory fixtures
   like `seed_asset_with_indicators` that create a full entity graph
   (type + asset + runs + evaluations).

4. **Direct repository testing** -- tests instantiate repositories with the
   test session and call methods directly, asserting on returned ORM objects.

5. **HTTP round-trip testing** -- tests use the `api_client` fixture
   (`httpx.AsyncClient` bound to the app) to test full request/response cycles
   including serialization, routing, and status codes.

### Cache Tests

`api/tests/quality_gate/db/test_heatmap_cache.py` is the most sophisticated
integration test file (14 tests). It includes a **property test**
(`test_cache_equals_uncached_after_mutation`) that parametrizes over 9 mutation
types and asserts that the `cache=true` heatmap response is byte-identical to
the `cache=false` response after each mutation. This catches missing cache
invalidation sites.

### Schemathesis Tests

`api/tests/schemathesis/` contains contract tests that fuzz the API against
its OpenAPI schema. These drove many of the defensive input validation types
(`SafeStr`, `StrictQueryBool`, `IntNotBool`, etc.).

---

## Coverage Assessment

### Strong Coverage

| Area | Tests | Notes |
|------|-------|-------|
| Criteria parsing & evaluation | ~290 lines | All operators, relative/fixed, whitespace, edge cases |
| Scoring logic | ~290 lines | Pass/warn/fail/info/error, key SLI veto, weighted scoring |
| Variable substitution | ~176 lines | Shadowing, special chars, bare `$`, empty values |
| Evaluation CRUD | 13 tests | Full lifecycle, double override, tag merge, constraint violation |
| Baseline queries | 8+ tests | Version ranges, tag filters, ID restriction, pin awareness |
| Heatmap (grouped + flat) | 23+ tests | Cache roundtrip, warm/cold paths, mutation invalidation, has_notes |
| Annotation categories | 14 tests | Repository + router, system protection, delete-reassign |
| Timeline pipeline | 19 orchestrator scenarios + per-stage unit tests | Exhaustive clipping matrix |
| EvaluationRun finalization | 8 tests | Sweeper, worst-case result, limit+order |

### Coverage Gaps

| Gap | Location | Severity |
|-----|----------|----------|
| `_compare()` unknown operator branch | `evaluation_engine/criteria.py:119-132` | Low -- defensive fallback, unlikely to hit |
| `>` operator fixed criteria has no fail case | `test_criteria.py` | Low -- only one pass test for `>` |
| `>=` operator has no boundary/fail case | `test_criteria.py` | Low |
| `=` with floating-point precision | Not tested | Medium -- could cause subtle mismatches |
| `relative_comparison.yaml` fixture unused | `tests/data/slo/` | Low -- defined but never loaded by any test |
| `build_variables` start/end in actual substitution | `test_variables.py` | Low -- presence tested but not round-tripped |
| Metric heatmap endpoint (by-metric) | No cache, no dedicated perf test | Medium |
| Timeline pagination/limits | No test for large snapshot counts | Medium -- no limit on snapshots loaded |
| SLO group router orchestration | No isolated unit tests | Medium -- ~200 lines of helper logic in router |

### Misplaced Test Files

Three test files in `api/tests/quality_gate/evaluation_engine/` test code
outside the evaluation engine:

| File | Actually tests |
|------|---------------|
| `test_comparison_rules.py` | `tropek.modules.assets.comparison_rules` |
| `test_generator.py` | `tropek.modules.slo_groups.generator` |
| `test_regeneration.py` | `tropek.modules.slo_groups.regeneration` |

These should be moved to `tests/assets/` and `tests/slo_groups/` respectively.
