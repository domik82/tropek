# API Refactor Design — SOLID, Lint Hygiene, Parameter Reduction

**Date:** 2026-03-29
**Approach:** Parallel tracks — C (lint/formatting) ships independently, B+D (architecture + params) per-module
**Priority order:** B/C/D (no A — `test_slo()` decomposition deferred)

---

## Track C: Ruff Config & Formatting

Zero behavior change. Ships as its own PR.

### Ruff config changes (`pyproject.toml`)

Add to `select`:
- `PLC` — pylint convention (catches PLC0415 import placement)
- `PLR` — pylint refactor (catches too-many-args/branches/statements)
- `BLE` — blind-except
- `Q` — quote enforcement

Add sections:
```toml
[tool.ruff.format]
quote-style = "single"

[tool.ruff.lint.pylint]
max-args = 8
```

Add per-file ignore:
```toml
"**/router.py" = ["B008"]  # FastAPI Depends() convention
```

### Formatting pass

- Run `ruff format` to normalize all quotes to single
- Run `ruff check --fix` to auto-fix what's possible

### Import fixes

Move in-function imports to top of file in:
- `tests/test_config.py` (6 violations)
- `tests/services/test_worker_helpers.py` (1)
- `tests/services/test_trigger_service.py` (1)

### PLR0913 noqa

Add targeted `# noqa: PLR0913` only on FastAPI router functions where query params make reduction impossible (e.g., `list_evaluations` with 8+ query params). These are inherent to FastAPI's DI pattern.

---

## Track B: Domain Exceptions & Separation of Concerns

### B1. Shared exception hierarchy — `api/app/modules/common/exceptions.py`

```python
class DomainError(Exception):
    """Base for all domain errors."""

class NotFoundError(DomainError):
    def __init__(self, entity: str, name: str) -> None:
        self.entity = entity
        self.name = name
        super().__init__(f'{entity} {name!r} not found')

class ConflictError(DomainError):
    def __init__(self, entity: str, name: str, reason: str) -> None:
        self.entity = entity
        self.name = name
        self.reason = reason
        super().__init__(f'{entity} {name!r}: {reason}')

class DomainValidationError(DomainError):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)
```

### B2. Consolidate existing quality_gate exceptions

The 5 existing exceptions in `quality_gate/exceptions.py` become thin subclasses or are replaced:
- `AssetNotFoundError` → `NotFoundError('asset', name)` (replace — no unique behavior)
- `SLONotConfiguredError` → `NotFoundError('slo', name)` or keep if the 422 status code matters (it maps to "not configured" not "not found")
- `DataSourceNotFoundError` → `NotFoundError('data source', name)` (replace)
- `DuplicateEvaluationError` → `ConflictError('evaluation', name, 'duplicate')` (replace)
- `EvaluationNotFoundError` → `NotFoundError('evaluation', name)` (replace)

Decision: keep `SLONotConfiguredError` as a subclass of `DomainValidationError` since it maps to 422, not 404. The rest become `NotFoundError`/`ConflictError` instances.

### B3. Centralized exception handlers

Extend `main.py` handler registration:
- `NotFoundError` → 404 JSONResponse
- `ConflictError` → 409 JSONResponse
- `DomainValidationError` → 422 JSONResponse

Remove the 5 individual quality_gate handlers once consolidated. The response format stays the same: `{"detail": str(exc)}`.

### B4. Replace HTTPException in repositories

**`assets/repository.py`** — 7 raises:
- `AssetTypeRepository.delete()`: `HTTPException(409)` → `ConflictError('asset type', name, 'in use by N assets')`
- `AssetTypeRepository.rename()`: `HTTPException(409)` → `ConflictError('asset type', new_name, 'already exists')`
- `AssetRepository.update()`: `HTTPException(404)` → `NotFoundError('asset', name)`
- `AssetGroupRepository.add_member()`: `HTTPException(404)` → `NotFoundError('asset group', group_name)`
- `AssetGroupRepository.remove_member()`: `HTTPException(404)` → `NotFoundError('asset group', group_name)`
- `AssetGroupRepository.add_subgroup()`: `HTTPException(404)` → `NotFoundError('asset group', group_name)`
- `AssetGroupRepository.remove_subgroup()`: `HTTPException(404)` → `NotFoundError('asset group', group_name)`

### B5. Remove `common/errors.py`

`raise_not_found()` and `raise_conflict()` helpers become unnecessary. Repositories raise domain exceptions; routers let them propagate. Delete the file and update all call sites in routers to either:
- Let the repo raise (if the repo already checks), or
- Raise `NotFoundError`/`ConflictError` directly in the router

### B6. Service layer extraction

Following the existing `TriggerService` pattern (constructor takes repos, methods encapsulate business logic, raises domain exceptions).

**`slo_registry/service.py` — `SLOTestService`**

Extracts the orchestration logic from `test_slo()` router handler:
- `run_test(body: SLOTestRequest, session: AsyncSession) -> SLOTestResult`
- Internally calls shared helpers for: variable building, adapter querying, baseline resolution
- Reuses `_build_eval_variables()` logic from worker (extracted to a shared location)
- Uses `HttpAdapterClient` instead of raw httpx (eliminates adapter call duplication)

The router becomes:
```python
@router.post('/test')
async def test_slo(body: SLOTestRequest, session: AsyncSession = Depends(get_session)):
    service = SLOTestService(session)
    return await service.run_test(body)
```

**`assets/service.py` — `AssetService`**

Extracts asset/group resolution logic that `list_evaluations()` in quality_gate/router.py does inline:
- `resolve_asset_ids(asset_name, group_name) -> list[UUID] | None`

**Shared helpers** (new file: `api/app/modules/quality_gate/evaluation_helpers.py` or similar):
- `build_eval_variables(asset, slo_variables, eval_variables)` — extracted from worker's `_build_eval_variables`, reused by `SLOTestService`
- `resolve_baselines(baseline_repo, slo, ...)` — extracted from worker's `_resolve_baselines`, reused by `SLOTestService`

The worker's private functions become thin wrappers around these shared helpers, or call them directly.

---

## Track D: Pydantic Input Models & Deduplication

### D1. Repository input models

New file per module: `params.py` containing Pydantic models consumed by repository `.create()` methods.

**`slo_registry/params.py`:**
```python
class SLOObjectiveParams(BaseModel):
    sli: str
    display_name: str | None = None
    weight: int = 1
    key_sli: bool = False
    pass_criteria: list[str] = []
    warning_criteria: list[str] = []

class SLOCreateParams(BaseModel):
    name: str
    objectives: list[SLOObjectiveParams]
    total_score_pass_pct: float = 90.0
    total_score_warning_pct: float = 75.0
    comparison: ComparisonParams | None = None
    display_name: str | None = None
    notes: str | None = None
    author: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    variables: dict[str, str] = Field(default_factory=dict)
    comparable_from_version: int | None = None
    kind: str = 'standard'
    sli_name: str | None = None
    sli_version: int | None = None
```

**`quality_gate/params.py`:**
```python
class EvalCreateParams(BaseModel):
    evaluation_name: str
    period_start: datetime
    period_end: datetime
    ingestion_mode: str
    asset_snapshot: dict
    variables: dict[str, str] = Field(default_factory=dict)
    asset_id: UUID
    slo_name: str
    slo_version: int | None = None
    adapter_used: str | None = None
    sli_name: str | None = None
    sli_version: int | None = None
    data_source_name: str | None = None

class RescoreContext(BaseModel):
    """Context object for _rescore_single(), replacing 11 params."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    ev: Evaluation  # ORM model from quality_gate/models.py
    slo_model: SLO
    slo_def: SLODefinition
    slo_version: int
    eligible_ids: list[UUID]
    asset_id: UUID
    slo_name: str
    default_sli_version_range: tuple[int, int] | None
    baseline_repo: BaselineRepository
    sli_repo: SLIRepository
    dry_run: bool

class ReEvalUpdateParams(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    eval_id: UUID
    new_result: str
    new_score: float
    new_engine_results: dict | None = None
    slo_objectives: list | None = None
    old_result: str | None = None
    old_score: float | None = None
    slo_version: int | None = None
```

**Same pattern for:** `SLICreateParams`, `ReEvalBaselineQuery`.

### D2. Repository method signatures

Before:
```python
async def create(self, name, objectives, total_score_pass_pct=90.0, ...14 params...):
```

After:
```python
async def create(self, params: SLOCreateParams) -> SLODefinition:
```

Internal implementation accesses `params.name`, `params.objectives`, etc. Call sites construct the Pydantic model, getting validation for free.

### D3. Tag query deduplication — `TagQueryMixin`

New file: `api/app/modules/common/tag_mixin.py`

```python
class TagQueryMixin:
    _tag_table: str  # set by subclass

    async def get_tag_keys(self) -> dict[str, int]:
        result = await self._session.execute(
            text(
                f'SELECT key, COUNT(*) as cnt '
                f'FROM {self._tag_table}, jsonb_object_keys(tags) AS key '
                f'GROUP BY key ORDER BY cnt DESC'
            )
        )
        return {row[0]: row[1] for row in result}

    async def get_tag_values(self, key: str) -> dict[str, int]:
        result = await self._session.execute(
            text(
                f'SELECT tags->>:key AS val, COUNT(*) as cnt '
                f'FROM {self._tag_table} '
                f'WHERE tags ? :key '
                f'GROUP BY val ORDER BY cnt DESC'
            ),
            {'key': key},
        )
        return {row[0]: row[1] for row in result}
```

Repositories inherit:
```python
class AssetRepository(TagQueryMixin):
    _tag_table = 'assets'
```

Eliminates 8 copy-pasted methods (2 per repo × 4 repos) → 2 methods in mixin.

### D4. Fix `Any` annotations in worker.py

- `ds: Any` → `ds: DataSource`
- `slo_def: Any` → `slo_def: SLODefinition`

---

## Module execution order for B+D

Each module gets a single PR with both architectural fixes and param reduction:

1. **`common/`** — Create `exceptions.py`, `tag_mixin.py`. Update `main.py` handlers. Remove `errors.py`.
2. **`assets/`** — Replace HTTPException with domain exceptions. Create `service.py`. Inherit `TagQueryMixin`.
3. **`quality_gate/`** — Consolidate exceptions. Create `params.py` for `EvalCreateParams`, `RescoreContext`, `ReEvalUpdateParams`. Extract shared evaluation helpers. Fix `Any` types.
4. **`slo_registry/`** — Create `params.py` for `SLOCreateParams`. Create `service.py` for test_slo orchestration. Inherit `TagQueryMixin`.
5. **`sli_registry/`** — Create `SLICreateParams`. Inherit `TagQueryMixin`.
6. **`datasource/`** — Inherit `TagQueryMixin`.

---

## Out of scope

- `test_slo()` full decomposition into <30-line functions (deferred — Track A)
- Test cleanup (duplicated helpers, shared fixtures) — separate effort
- Settings property caching optimization — minor perf, separate effort
- Heatmap nested ternary cleanup — cosmetic, separate effort
