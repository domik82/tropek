# Python Client v2 — Design Spec

## Problem

The current `tropek_client` has several issues:

- **~50% API coverage** — missing models for heatmap, timeline, change points, configuration, display groups, meta snapshots
- **Weak typing** — `**kwargs` on update methods kills intellisense; `dict[str, Any]` return types on tag endpoints
- **Hand-maintained models** — drift from API undetected; no contract tests
- **No structured error handling** — callers get raw HTTP status codes, not business-level detail
- **No logging** — no visibility into request/response lifecycle

## Decision: Generate Once, Own Forever

After evaluating three OpenAPI generators (openapi-python-client, openapi-generator, clientele) against the TROPEK spec, we chose **Approach A: generated models + hand-written client**.

**Why not fully generated?** No generator produces the `client.assets.get()` sub-resource DX. All generate flat function calls. The existing hand-written client has better DX than any generator output.

**Why not fully hand-written?** The current hand-maintained models already drifted to ~50% coverage. Generated models guarantee field-level accuracy at the starting point, and drift tests prevent future divergence.

**Flow:** Generate Pydantic models once via openapi-generator → strip boilerplate → own the clean models from that point forward → drift tests validate against `openapi.json` on every CI run.

## Package Structure

```
clients/python/
├── tropek_client/
│   ├── __init__.py              # Public API: TropekClient + top-level re-exports
│   ├── client.py                # TropekClient with sub-resource groups
│   ├── _http.py                 # httpx wrapper, auth, logging, error mapping
│   ├── exceptions.py            # Structured exception hierarchy
│   ├── models/
│   │   ├── __init__.py          # Re-exports all model classes
│   │   ├── assets.py            # AssetCreate, AssetRead, AssetUpdate, AssetSnapshot
│   │   ├── asset_types.py       # AssetTypeCreate, AssetTypeRead, AssetTypeUpdate
│   │   ├── asset_groups.py      # AssetGroupCreate, AssetGroupRead, tree, members, subgroups
│   │   ├── evaluations.py       # EvaluationSummary, EvaluationDetail, IndicatorResult, FailingIndicator, PassTarget
│   │   ├── slos.py              # SLODefinitionCreate, SLODefinitionRead, SLOObjectiveIn/Read, validation, test
│   │   ├── slis.py              # SLIDefinitionCreate, SLIDefinitionRead, SLIMetadata
│   │   ├── datasources.py       # DataSourceCreate, DataSourceRead, DataSourceUpdate
│   │   ├── annotations.py       # AnnotationCreate, AnnotationRead, AnnotationUpdate, categories
│   │   ├── heatmap.py           # HeatmapCell, HeatmapCellGrouped, HeatmapMetric, HeatmapSummaryCell, sections, responses
│   │   ├── trend.py             # TrendPoint, TrendTargetEntry, TrendTargets
│   │   ├── timeline.py          # TimelineItem, TimelineGroup, TimelineResponse, TimelineSummaryResponse
│   │   ├── change_points.py     # ChangePointRead, ChangePointMarker, ChangePointConfigRead/Input
│   │   ├── configuration.py     # ConfigurationRead, ConfigurationUpdate
│   │   ├── slo_groups.py        # SLOGroupCreate, SLOGroupRead, assignments
│   │   ├── slo_assignments.py   # SLOAssignmentRead, SLOAssignmentUpsert, SLOAssignmentUpgrade
│   │   ├── meta.py              # MetaSnapshotCreate, MetaSnapshotCreated, MetaValueInput, MetaClosureInput
│   │   ├── pagination.py        # PagedResponse generic
│   │   └── common.py            # Enums (Direction, AggregateFunction, ...), ErrorMessage, type aliases
│   ├── manifest.py              # YAML desired-state reconciler (existing, updated to use new models)
│   ├── cli.py                   # Click CLI (existing, unchanged)
│   └── py.typed                 # PEP 561 marker
├── tests/
│   ├── test_models.py           # Model serialization/deserialization tests
│   ├── test_client.py           # Client method tests (mocked HTTP)
│   ├── test_drift.py            # Contract tests: models vs openapi.json
│   ├── test_manifest.py         # Manifest reconciler tests
│   └── test_cli.py              # CLI tests
└── pyproject.toml
```

### Model file grouping rationale

Models are grouped by **domain**, not by CRUD action. `assets.py` contains Create + Read + Update together because they are always used together. Each file contains 2-8 tightly related models that reference each other.

## Model Design

### Cleanup from generated output

The openapi-generator produces ~120-line files per model. After cleanup each model is ~10-30 lines:

**Strip:**
- `to_str()`, `to_json()`, `from_json()`, `to_dict()`, `from_dict()` — Pydantic v2 handles all of this natively via `model_dump()`, `model_validate()`, `model_dump_json()`
- `__properties` class var — redundant with `model_fields`
- `ConfigDict` block — not needed for plain response models
- `# noqa` comments, unused imports, duplicate imports
- Generator docstrings and header comments

**Simplify types:**
- `StrictStr` → `str`
- `StrictInt` → `int`
- `StrictBool` → `bool`
- `StrictFloat` → `float`
- `Union[StrictFloat, StrictInt]` → `float`
- `Optional[X]` → `X | None`
- `Dict[str, X]` → `dict[str, X]`
- `List[X]` → `list[X]`

**Improve where possible:**
- `EvaluationDetail` inherits from `EvaluationSummary` (25 shared fields, generator duplicated them)
- Field validators for `SafeStr` pattern (`^[^\x00]*$`) consolidated into a reusable validator

### Example: cleaned model

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AssetRead(BaseModel):
    id: UUID
    name: str
    display_name: str | None
    type_name: str
    tags: dict[str, str]
    variables: dict[str, str]
    heatmap_config: dict[str, Any] | None = None
    color: str | None = None
    created_at: datetime
    updated_at: datetime
```

## Client Layer

### TropekClient

```python
from tropek_client import TropekClient

client = TropekClient(
    base_url="http://localhost:8080",
    api_key="my-key",
    timeout=30.0,
)
```

Constructor parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str` | required | API base URL |
| `api_key` | `str \| None` | `None` | Sets `X-API-Key` header |
| `timeout` | `float` | `30.0` | Request timeout in seconds |
| `headers` | `dict[str, str]` | `{}` | Additional headers |
| `verify` | `bool` | `True` | TLS certificate verification |

### Sub-resource groups

Each group maps to one API router. Every method has explicit typed parameters and typed return values.

**Assets:**
```python
client.assets.list(type_name=..., tags=..., page=..., page_size=...) -> PagedResponse[AssetRead]
client.assets.get(name: str)                          -> AssetRead
client.assets.create(body: AssetCreate)               -> AssetRead
client.assets.update(name: str, body: AssetUpdate)    -> AssetRead
client.assets.delete(name: str)                       -> None
client.assets.tag_keys(type_name=...)                 -> list[TagKeyCount]
client.assets.tag_values(type_name=..., key=...)      -> list[TagValueCount]
```

**Asset Types:**
```python
client.asset_types.list(...)            -> PagedResponse[AssetTypeRead]
client.asset_types.get(name: str)       -> AssetTypeRead
client.asset_types.create(body)         -> AssetTypeRead
client.asset_types.update(name, body)   -> AssetTypeRead
client.asset_types.delete(name)         -> None
```

**Asset Groups:**
```python
client.asset_groups.list(...)               -> PagedResponse[AssetGroupRead]
client.asset_groups.get(name: str)          -> AssetGroupRead
client.asset_groups.create(body)            -> AssetGroupRead
client.asset_groups.update(name, body)      -> AssetGroupRead
client.asset_groups.delete(name)            -> None
client.asset_groups.tree()                  -> AssetGroupTreeResponse
client.asset_groups.add_member(name, body)  -> AssetGroupMemberRead
client.asset_groups.remove_member(name, member_name) -> None
client.asset_groups.add_subgroup(name, body) -> AssetGroupSubgroupRead
client.asset_groups.remove_subgroup(name, subgroup_name) -> None
```

**Evaluations:**
```python
client.evaluations.list(asset_name=..., evaluation_name=..., ...) -> PagedResponse[EvaluationSummary]
client.evaluations.get(evaluation_id: UUID)         -> EvaluationDetail
client.evaluations.trigger(body: EvaluateSingleRequest)     -> EvaluateSingleResponse
client.evaluations.trigger_batch(body: EvaluateBatchRequest) -> EvaluateBatchResponse
client.evaluations.invalidate(evaluation_id, body: InvalidateRequest) -> None
client.evaluations.override_status(evaluation_id, body)     -> EvaluationDetail
client.evaluations.pin_baseline(evaluation_id, body)        -> None
client.evaluations.unpin_baseline(evaluation_id)             -> None
client.evaluations.re_evaluate_from_baseline(body)           -> ReEvaluateResponse
client.evaluations.re_evaluate_from_date(body)               -> ReEvaluateResponse
client.evaluations.re_evaluate_from_evaluation(body)         -> ReEvaluateResponse
client.evaluations.triage(evaluation_id, body: TriageRequest) -> None
client.evaluations.bulk_triage(body: BulkTriageRequest)       -> None
```

**Heatmap & Trend:**
```python
client.evaluations.heatmap(asset_name, evaluation_name=..., limit=...) -> GroupedMetricHeatmapResponse
client.evaluations.trend(asset_name, targets=..., ...)                 -> TrendTargets
client.evaluations.timeline(asset_name, ...)                           -> TimelineResponse
client.evaluations.timeline_summary(asset_name, ...)                   -> TimelineSummaryResponse
```

**SLOs:**
```python
client.slos.list(...)                     -> PagedResponse[SLODefinitionRead]
client.slos.get(name, version=...)        -> SLODefinitionRead
client.slos.create(body)                  -> SLODefinitionRead
client.slos.delete(name)                  -> None
client.slos.validate(body)               -> SLOValidationResult
client.slos.test(body)                   -> SLOTestResult
```

**SLIs:**
```python
client.slis.list(...)                     -> PagedResponse[SLIDefinitionRead]
client.slis.get(name, version=...)        -> SLIDefinitionRead
client.slis.create(body)                  -> SLIDefinitionRead
client.slis.delete(name)                  -> None
```

**Data Sources:**
```python
client.datasources.list(...)              -> PagedResponse[DataSourceRead]
client.datasources.get(name)              -> DataSourceRead
client.datasources.create(body)           -> DataSourceRead
client.datasources.update(name, body)     -> DataSourceRead
client.datasources.delete(name)           -> None
```

**Annotations:**
```python
client.annotations.list(evaluation_id=...)         -> list[AnnotationRead]
client.annotations.create(body: AnnotationCreate)  -> AnnotationRead
client.annotations.update(annotation_id, body)     -> AnnotationRead
client.annotations.delete(annotation_id)           -> None
client.annotations.hide(annotation_id)             -> None
client.annotations.categories.list()               -> list[AnnotationCategoryRead]
client.annotations.categories.create(body)         -> AnnotationCategoryRead
client.annotations.categories.update(id, body)     -> AnnotationCategoryRead
client.annotations.categories.delete(id)           -> None
```

**SLO Groups:**
```python
client.slo_groups.list(...)                         -> PagedResponse[SLOGroupRead]
client.slo_groups.get(name)                         -> SLOGroupRead
client.slo_groups.create(body)                      -> SLOGroupRead
client.slo_groups.update(name, body)                -> SLOGroupRead
client.slo_groups.delete(name)                      -> None
```

**SLO Assignments:**
```python
client.slo_assignments.list(asset_name)             -> list[SLOAssignmentRead]
client.slo_assignments.upsert(body)                 -> SLOAssignmentRead
client.slo_assignments.delete(asset_name, slo_name) -> None
client.slo_assignments.upgrade(body)                -> SLOAssignmentRead
```

**Configuration:**
```python
client.config.get()                      -> ConfigurationRead
client.config.update(body)               -> ConfigurationRead
```

**Meta Snapshots:**
```python
client.meta.create_snapshot(body: MetaSnapshotCreate) -> MetaSnapshotCreated
client.meta.extract(body: ExtractRequest)             -> ...
```

### Internal structure

```python
# _http.py — the ONLY file that imports httpx

class HttpSession:
    """Thin httpx wrapper. Auth, logging, error mapping."""

    def get(self, path, *, params=None) -> httpx.Response
    def post(self, path, *, json=None, params=None) -> httpx.Response
    def put(self, path, *, json=None) -> httpx.Response
    def delete(self, path) -> httpx.Response
```

Each sub-resource class receives the session:

```python
class _Assets:
    def __init__(self, http: HttpSession) -> None: ...

class TropekClient:
    def __init__(self, base_url, api_key=None, ...):
        self._http = HttpSession(base_url, api_key, ...)
        self.assets = _Assets(self._http)
        self.evaluations = _Evaluations(self._http)
        ...
```

## Error Handling

### Exception hierarchy

```python
class TropekAPIError(Exception):
    status_code: int
    detail: str
    request_id: str | None

class TropekNotFoundError(TropekAPIError):       # 404
    entity: str | None
    name: str | None

class TropekConflictError(TropekAPIError):       # 409
    entity: str | None
    name: str | None
    reason: str | None

class TropekValidationError(TropekAPIError):     # 422
    errors: list[ValidationDetail]

class ValidationDetail(BaseModel):
    loc: list[str]
    msg: str
    type: str

class TropekServerError(TropekAPIError):         # 500+
    pass

class TropekConnectionError(TropekAPIError):     # network/timeout
    pass
```

### Error mapping

The API returns structured JSON error bodies:

- **404:** `{"detail": "asset 'foo' not found"}` → `TropekNotFoundError(entity="asset", name="foo")`
- **409:** `{"detail": "asset 'foo': already exists"}` → `TropekConflictError(entity="asset", name="foo", reason="already exists")`
- **422:** `{"detail": [{"loc": ["body", "name"], "msg": "field required", "type": "missing"}]}` → `TropekValidationError(errors=[...])`
- **500+:** `{"detail": "..."}` → `TropekServerError`
- **Connection/timeout:** `TropekConnectionError`

The `HttpSession._raise_for_status()` method parses the response body and raises the appropriate exception. Entity/name are parsed from the detail string using the known API error message patterns.

### Usage

```python
try:
    client.assets.create(AssetCreate(name="my-svc", type_name="service"))
except TropekConflictError as exc:
    print(f"{exc.entity} '{exc.name}': {exc.reason}")
except TropekValidationError as exc:
    for err in exc.errors:
        print(f"  {'.'.join(err.loc)}: {err.msg}")
```

## Logging

Standard `logging` module under the `tropek_client` logger name.

| Level | What gets logged |
|-------|-----------------|
| `DEBUG` | Full request/response: method, URL, headers (API key masked), body, status, timing |
| `INFO` | Request summary: `POST /assets 201 (42ms)` |
| `WARNING` | Slow responses (>5s), unexpected status codes |
| `ERROR` | Failed requests with parsed error detail |

```python
import logging
logging.getLogger("tropek_client").setLevel(logging.DEBUG)
```

## Drift Tests

### What they validate

A test suite (`test_drift.py`) that parses `api/openapi.json` and validates every client model against it:

1. **Field presence** — every required field in the OpenAPI schema has a corresponding field in the Pydantic model
2. **Field types** — OpenAPI `string`/`format: uuid` maps to `UUID`, `string`/`format: date-time` maps to `datetime`, etc.
3. **Nullable/optional** — fields marked `nullable: true` in OpenAPI must be `X | None` in the model
4. **Missing models** — every schema in `components/schemas` that is used in a response body has a corresponding Pydantic model
5. **Extra fields** — model fields not present in the OpenAPI schema are flagged (catches stale fields after API changes)

### How they run

```bash
# Part of the standard test suite
just test-client          # runs all client tests including drift
./scripts/client-test.sh  # agent-friendly wrapper
```

Drift tests read `api/openapi.json` from the repo root — the spec is committed and regenerated as part of the API dev workflow. No running API server needed.

### What they do NOT do

- They do not auto-fix models. A failing drift test tells you which fields diverged; you update the model manually.
- They do not validate client method signatures against API paths. That is a future enhancement.

## Migration Plan

### What changes

- `tropek_client/models.py` (single file) → `tropek_client/models/` (domain-grouped package)
- `tropek_client/client.py` — rewritten with typed parameters, typed returns, no `**kwargs`
- `tropek_client/exceptions.py` — expanded with structured error parsing
- New: `tropek_client/_http.py` — extracted HTTP layer with logging
- New: `tests/test_drift.py` — contract tests

### What stays the same

- `tropek_client/manifest.py` — updated to use new models, same public API
- `tropek_client/cli.py` — unchanged
- Package name and install path: `tropek-client`, `from tropek_client import TropekClient`

### Breaking changes

- Import paths for models change: `from tropek_client.models import AssetRead` (was `from tropek_client.models import Asset`)
- Some model class names change to match API schema names (e.g., `Asset` → `AssetRead`, `AssetInput` → `AssetCreate`)
- Update methods take explicit `body` parameter instead of `**kwargs`
- Tag endpoints return `list[TagKeyCount]` instead of `dict`

This is a v2 / breaking release. The manifest layer absorbs the changes internally.

## Out of Scope

- Async client (`AsyncTropekClient`) — future enhancement, same pattern with `httpx.AsyncClient`
- Retry/backoff logic — callers can use tenacity or similar
- CLI changes — existing CLI works, cosmetic improvements are separate
- OpenAPI spec improvements beyond the existing `_deduplicate_inline_schemas()` fix
