# Python Client v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `tropek_client` with generated+cleaned Pydantic models, typed sub-resource client, structured error handling, logging, and drift tests.

**Architecture:** Generate models once from openapi-generator output, strip boilerplate, group by domain. Hand-write a thin HTTP layer with logging and error mapping. Hand-write sub-resource client classes that use the models. Drift tests validate models against `api/openapi.json`.

**Tech Stack:** Python 3.13, Pydantic v2, httpx, respx (test mocks), pytest

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `clients/python/tropek_client/models/__init__.py` | Re-export all model classes |
| Create | `clients/python/tropek_client/models/common.py` | Enums, type aliases, shared small models |
| Create | `clients/python/tropek_client/models/pagination.py` | `PagedResponse[T]` generic |
| Create | `clients/python/tropek_client/models/assets.py` | AssetCreate, AssetRead, AssetUpdate, AssetSnapshot |
| Create | `clients/python/tropek_client/models/asset_types.py` | AssetTypeCreate, AssetTypeRead, AssetTypeUpdate |
| Create | `clients/python/tropek_client/models/asset_groups.py` | AssetGroup CRUD + tree + member + subgroup models |
| Create | `clients/python/tropek_client/models/evaluations.py` | EvaluationSummary, EvaluationDetail, IndicatorResult, etc. |
| Create | `clients/python/tropek_client/models/slos.py` | SLO definition + objective + validation + test models |
| Create | `clients/python/tropek_client/models/slis.py` | SLI definition models |
| Create | `clients/python/tropek_client/models/datasources.py` | DataSource CRUD models |
| Create | `clients/python/tropek_client/models/annotations.py` | Annotation + category models |
| Create | `clients/python/tropek_client/models/heatmap.py` | Heatmap cell, metric, section, response models |
| Create | `clients/python/tropek_client/models/trend.py` | TrendPoint, TrendTargetEntry, TrendTargets |
| Create | `clients/python/tropek_client/models/timeline.py` | Timeline item, group, response models |
| Create | `clients/python/tropek_client/models/change_points.py` | ChangePoint read, marker, config models |
| Create | `clients/python/tropek_client/models/configuration.py` | ConfigurationRead, ConfigurationUpdate |
| Create | `clients/python/tropek_client/models/slo_groups.py` | SLO group CRUD models |
| Create | `clients/python/tropek_client/models/slo_assignments.py` | SLO assignment + group assignment models |
| Create | `clients/python/tropek_client/models/meta.py` | MetaSnapshot models |
| Rewrite | `clients/python/tropek_client/exceptions.py` | Structured exception hierarchy with parsed fields |
| Create | `clients/python/tropek_client/_http.py` | httpx wrapper with logging, auth, error mapping |
| Rewrite | `clients/python/tropek_client/client.py` | TropekClient with typed sub-resource groups |
| Rewrite | `clients/python/tropek_client/__init__.py` | Public API re-exports |
| Delete | `clients/python/tropek_client/models.py` | Replaced by `models/` package |
| Create | `clients/python/tropek_client/py.typed` | PEP 561 marker |
| Modify | `clients/python/pyproject.toml` | Add respx dev dependency |
| Create | `clients/python/tests/test_exceptions.py` | Error parsing tests |
| Create | `clients/python/tests/test_http.py` | HTTP layer tests |
| Rewrite | `clients/python/tests/test_client.py` | Per-method client tests with mocked HTTP |
| Create | `clients/python/tests/test_drift.py` | Contract tests: models vs openapi.json |
| Rewrite | `clients/python/tests/test_models.py` | Model round-trip tests |
| Modify | `clients/python/tropek_client/manifest.py` | Update imports to new model names |

---

### Task 1: Project setup — add dependencies and PEP 561 marker

**Files:**
- Modify: `clients/python/pyproject.toml`
- Create: `clients/python/tropek_client/py.typed`

- [ ] **Step 1: Add respx to dev dependencies and create py.typed**

In `clients/python/pyproject.toml`, add `respx` to the dev dependency group:

```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-httpx>=0.30",
    "respx>=0.22",
]
```

Create `clients/python/tropek_client/py.typed` as an empty file (PEP 561 marker for type checkers).

- [ ] **Step 2: Install dependencies**

Run: `uv sync --directory clients/python`

- [ ] **Step 3: Commit**

```
git add clients/python/pyproject.toml clients/python/tropek_client/py.typed
git commit -m "chore: add respx dev dependency and PEP 561 marker"
```

---

### Task 2: Models — common, pagination, enums

**Files:**
- Create: `clients/python/tropek_client/models/__init__.py`
- Create: `clients/python/tropek_client/models/common.py`
- Create: `clients/python/tropek_client/models/pagination.py`

Reference the generated models at `clients/python/tropek-client-openapi-gen/tropek_client_gen/models/` for field names and types. Strip all boilerplate (see spec "Cleanup from generated output" section). Use modern Python syntax: `str | None` not `Optional[str]`, `dict[str, str]` not `Dict[str, str]`, `float` not `Union[StrictFloat, StrictInt]`.

- [ ] **Step 1: Create models package with common.py**

Create `clients/python/tropek_client/models/common.py`:

```python
from enum import StrEnum

from pydantic import BaseModel


class Direction(StrEnum):
    ASC = 'asc'
    DESC = 'desc'


class AggregateFunction(StrEnum):
    AVG = 'avg'
    P50 = 'p50'
    P90 = 'p90'
    P95 = 'p95'
    P99 = 'p99'


class AggregationMethod(StrEnum):
    AVG = 'avg'
    MIN = 'min'
    MAX = 'max'
    SUM = 'sum'
    LAST = 'last'


class CategoryColor(StrEnum):
    GRAY = 'gray'
    RED = 'red'
    ORANGE = 'orange'
    YELLOW = 'yellow'
    GREEN = 'green'
    BLUE = 'blue'
    PURPLE = 'purple'


class Weight(StrEnum):
    EQUAL = 'equal'
    CUSTOM = 'custom'


class ErrorMessage(BaseModel):
    detail: str


class TagKeyCount(BaseModel):
    key: str
    count: int


class TagValueCount(BaseModel):
    key: str
    value: str
    count: int
```

Check the generated enum files (`aggregate_function.py`, `aggregation_method.py`, `direction.py`, `category_color.py`, `weight.py`) for the exact values — they come from the OpenAPI spec. Also check `tag_key_count.py` and `tag_value_count.py` for the field names.

- [ ] **Step 2: Create pagination.py**

Create `clients/python/tropek_client/models/pagination.py`:

```python
from pydantic import BaseModel


class PagedResponse[T](BaseModel):
    items: list[T]
    total: int
```

- [ ] **Step 3: Create models/__init__.py with initial re-exports**

Create `clients/python/tropek_client/models/__init__.py`:

```python
from tropek_client.models.common import (
    AggregateFunction,
    AggregationMethod,
    CategoryColor,
    Direction,
    ErrorMessage,
    TagKeyCount,
    TagValueCount,
    Weight,
)
from tropek_client.models.pagination import PagedResponse

__all__ = [
    'AggregateFunction',
    'AggregationMethod',
    'CategoryColor',
    'Direction',
    'ErrorMessage',
    'PagedResponse',
    'TagKeyCount',
    'TagValueCount',
    'Weight',
]
```

This will be extended in subsequent tasks as more model files are added.

- [ ] **Step 4: Verify imports work**

Run: `uv run --directory clients/python python -c "from tropek_client.models import PagedResponse, TagKeyCount; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```
git add clients/python/tropek_client/models/
git commit -m "feat(client): add models package with common types, enums, and pagination"
```

---

### Task 3: Models — assets, asset types, asset groups

**Files:**
- Create: `clients/python/tropek_client/models/assets.py`
- Create: `clients/python/tropek_client/models/asset_types.py`
- Create: `clients/python/tropek_client/models/asset_groups.py`
- Modify: `clients/python/tropek_client/models/__init__.py`

Reference generated files: `asset_create.py`, `asset_read.py`, `asset_update.py`, `asset_snapshot.py`, `asset_type_create.py`, `asset_type_read.py`, `asset_type_update.py`, `asset_group_create.py`, `asset_group_read.py`, `asset_group_update.py`, `asset_group_member_create.py`, `asset_group_member_read.py`, `asset_group_subgroup_create.py`, `asset_group_subgroup_read.py`, `asset_group_tree_response.py` — all under `clients/python/tropek-client-openapi-gen/tropek_client_gen/models/`.

- [ ] **Step 1: Create assets.py**

Read the generated `asset_create.py`, `asset_read.py`, `asset_update.py`, `asset_snapshot.py` for exact field names and types. Create `clients/python/tropek_client/models/assets.py` with clean Pydantic models. Example shape (verify fields against generated code):

```python
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AssetCreate(BaseModel):
    name: str
    type_name: str
    display_name: str | None = None
    tags: dict[str, str] | None = None
    variables: dict[str, str] | None = None
    color: str | None = None


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


class AssetUpdate(BaseModel):
    display_name: str | None = None
    tags: dict[str, str] | None = None
    variables: dict[str, str] | None = None
    color: str | None = None


class AssetSnapshot(BaseModel):
    asset_name: str
    asset_display_name: str | None
    asset_type_name: str
    tags: dict[str, str]
    variables: dict[str, str]
```

- [ ] **Step 2: Create asset_types.py**

Read generated `asset_type_create.py`, `asset_type_read.py`, `asset_type_update.py`. Create `clients/python/tropek_client/models/asset_types.py`.

- [ ] **Step 3: Create asset_groups.py**

Read generated `asset_group_create.py`, `asset_group_read.py`, `asset_group_update.py`, `asset_group_member_create.py`, `asset_group_member_read.py`, `asset_group_subgroup_create.py`, `asset_group_subgroup_read.py`, `asset_group_tree_response.py`. Create `clients/python/tropek_client/models/asset_groups.py`.

Also read `add_member_request.py` and `add_subgroup_request.py` — these are the request bodies for adding members/subgroups.

- [ ] **Step 4: Update models/__init__.py**

Add re-exports for all new model classes from the three files.

- [ ] **Step 5: Verify imports**

Run: `uv run --directory clients/python python -c "from tropek_client.models import AssetCreate, AssetRead, AssetGroupRead; print('OK')"`

- [ ] **Step 6: Commit**

```
git add clients/python/tropek_client/models/
git commit -m "feat(client): add asset, asset type, and asset group models"
```

---

### Task 4: Models — evaluations (summary, detail, indicator results)

**Files:**
- Create: `clients/python/tropek_client/models/evaluations.py`
- Modify: `clients/python/tropek_client/models/__init__.py`

Reference generated files: `evaluation_summary.py`, `evaluation_detail.py`, `indicator_result.py`, `failing_indicator.py`, `pass_target.py`, `evaluate_single_request.py`, `evaluate_single_response.py`, `evaluate_batch_request.py`, `evaluate_batch_response.py`, `invalidate_request.py`, `override_status_request.py`, `pin_baseline_request.py`, `re_evaluate_from_baseline_request.py`, `re_evaluate_from_date_request.py`, `re_evaluate_from_evaluation_request.py`, `re_evaluate_response.py`, `re_eval_result_item.py`, `triage_request.py`, `bulk_triage_request.py`, `batch_period.py`, `evaluation_name_entry.py`, `evaluation_column.py`, `scope.py`, `asset_scope.py`, `group_scope.py`, `slo_selector.py`, `eval_names_selector.py`, `compare_to_value.py`, `re_evaluate_from_baseline_request_selector.py`.

This is the largest model file. Key design decision: `EvaluationDetail` inherits from `EvaluationSummary` (they share 25 fields — the generator duplicated them).

- [ ] **Step 1: Create evaluations.py**

Read all the generated evaluation-related files listed above. Create `clients/python/tropek_client/models/evaluations.py` with clean models. Pay special attention to:

- `EvaluationSummary` and `EvaluationDetail` — Detail should inherit from Summary and add the extra fields (`invalidation_note`, `compared_evaluation_ids`, `annotations`, `indicator_results`, `total_score_pass_threshold`, `total_score_warning_threshold`, `sli_metadata`)
- Scope models (`AssetScope`, `GroupScope`) — used in re-evaluation requests
- Selector models — used to filter which evaluations to re-evaluate
- `PassTarget` — nested inside `IndicatorResult`

Import `AssetSnapshot` from `tropek_client.models.assets` and `AnnotationRead` from `tropek_client.models.annotations`. Since annotations haven't been created yet, use `from __future__ import annotations` and a `TYPE_CHECKING` guard, or create a stub and fill it in during Task 6.

**Practical approach:** Create the evaluations.py file first with forward references for `AnnotationRead`. When Task 6 creates the annotations module, the imports will resolve.

- [ ] **Step 2: Update models/__init__.py**

Add re-exports for all evaluation model classes.

- [ ] **Step 3: Verify imports**

Run: `uv run --directory clients/python python -c "from tropek_client.models import EvaluationSummary, EvaluationDetail, IndicatorResult; print('OK')"`

- [ ] **Step 4: Commit**

```
git add clients/python/tropek_client/models/
git commit -m "feat(client): add evaluation models (summary, detail, indicator results, requests)"
```

---

### Task 5: Models — SLOs, SLIs, datasources

**Files:**
- Create: `clients/python/tropek_client/models/slos.py`
- Create: `clients/python/tropek_client/models/slis.py`
- Create: `clients/python/tropek_client/models/datasources.py`
- Modify: `clients/python/tropek_client/models/__init__.py`

Reference generated files: `slo_definition_create.py`, `slo_definition_read.py`, `slo_objective_in.py`, `slo_objective_read.py`, `slo_validate_request.py`, `slo_validation_result.py`, `slo_validation_error.py`, `slo_test_request.py`, `slo_test_result.py`, `baseline_config.py`, `comparison_config.py`, `comparison_config_read.py`, `comparison_rule.py`, `method_criteria_override.py`, `method_criteria_override_read.py`, `change_point_config_input.py`, `change_point_config_read.py`, `sli_definition_create.py`, `sli_definition_read.py`, `sli_metadata.py`, `data_source_create.py`, `data_source_read.py`, `data_source_update.py`.

- [ ] **Step 1: Create slos.py**

Read all generated SLO-related files. Create `clients/python/tropek_client/models/slos.py`.

- [ ] **Step 2: Create slis.py**

Read generated SLI files. Create `clients/python/tropek_client/models/slis.py`.

- [ ] **Step 3: Create datasources.py**

Read generated datasource files. Create `clients/python/tropek_client/models/datasources.py`.

- [ ] **Step 4: Update models/__init__.py and verify**

- [ ] **Step 5: Commit**

```
git add clients/python/tropek_client/models/
git commit -m "feat(client): add SLO, SLI, and datasource models"
```

---

### Task 6: Models — annotations, heatmap, trend, timeline, change points, configuration, SLO groups, SLO assignments, meta

**Files:**
- Create: `clients/python/tropek_client/models/annotations.py`
- Create: `clients/python/tropek_client/models/heatmap.py`
- Create: `clients/python/tropek_client/models/trend.py`
- Create: `clients/python/tropek_client/models/timeline.py`
- Create: `clients/python/tropek_client/models/change_points.py`
- Create: `clients/python/tropek_client/models/configuration.py`
- Create: `clients/python/tropek_client/models/slo_groups.py`
- Create: `clients/python/tropek_client/models/slo_assignments.py`
- Create: `clients/python/tropek_client/models/meta.py`
- Modify: `clients/python/tropek_client/models/__init__.py`

Reference generated files for each domain. This task covers the remaining model files.

- [ ] **Step 1: Create annotations.py**

Reference: `annotation_create.py`, `annotation_read.py`, `annotation_update.py`, `annotation_hide.py`, `annotation_category_create.py`, `annotation_category_read.py`, `annotation_category_update.py`.

- [ ] **Step 2: Create heatmap.py**

Reference: `heatmap_cell.py`, `heatmap_cell_grouped.py`, `heatmap_metric.py`, `heatmap_summary_cell.py`, `heatmap_slo_group_section.py`, `grouped_metric_heatmap_response.py`, `metric_heatmap_response.py`, `evaluation_column.py`.

Import `SliMetadata` from `tropek_client.models.slis`, `PassTarget` and `ChangePointMarker` from their respective modules.

- [ ] **Step 3: Create trend.py**

Reference: `trend_point.py`, `trend_target_entry.py`, `trend_targets.py`.

- [ ] **Step 4: Create timeline.py**

Reference: `timeline_item.py`, `timeline_group.py`, `timeline_response.py`, `timeline_summary_response.py`.

- [ ] **Step 5: Create change_points.py**

Reference: `change_point_read.py`, `change_point_marker.py`, `change_point_config_read.py`, `change_point_config_input.py`.

- [ ] **Step 6: Create configuration.py**

Reference: `configuration_read.py`, `configuration_update.py`.

- [ ] **Step 7: Create slo_groups.py**

Reference: `slo_group_create.py`, `slo_group_read.py`, `slo_group_update.py`, `slo_group_assignment_read.py`, `slo_group_assignment_upsert.py`, `extract_request.py`, `display_group_create.py`, `display_group_read.py`, `display_group_member_add.py`.

- [ ] **Step 8: Create slo_assignments.py**

Reference: `slo_assignment_read.py`, `slo_assignment_upsert.py`, `slo_assignment_upgrade.py`.

- [ ] **Step 9: Create meta.py**

Reference: `meta_snapshot_create.py`, `meta_snapshot_created.py`, `meta_value_input.py`, `meta_closure_input.py`.

- [ ] **Step 10: Update models/__init__.py with all remaining re-exports**

Finalize the `__init__.py` with re-exports from every model file. This is the last models update — after this, `from tropek_client.models import X` works for every model class.

- [ ] **Step 11: Verify all imports**

Run: `uv run --directory clients/python python -c "from tropek_client.models import AnnotationRead, GroupedMetricHeatmapResponse, TrendTargets, TimelineResponse, ChangePointRead, ConfigurationRead, SLOGroupRead, SLOAssignmentRead, MetaSnapshotCreate; print('OK')"`

- [ ] **Step 12: Commit**

```
git add clients/python/tropek_client/models/
git commit -m "feat(client): add remaining models (annotations, heatmap, trend, timeline, etc.)"
```

---

### Task 7: Model review via subagents

Before proceeding to the client layer, the generated-and-cleaned models need a thorough review.

- [ ] **Step 1: Review all model files against generated source**

For each model file in `clients/python/tropek_client/models/`, compare field names, types, and required/optional status against the corresponding generated file in `clients/python/tropek-client-openapi-gen/tropek_client_gen/models/`. Verify:

- No fields were accidentally dropped
- Type simplifications are correct (`Union[StrictFloat, StrictInt]` → `float`, not `int`)
- Optional vs required matches the generated code
- Default values are preserved
- Nested model references use the correct cleaned class names

- [ ] **Step 2: Run a quick import smoke test**

Run: `uv run --directory clients/python python -c "from tropek_client.models import *; print('All models imported successfully')"`

- [ ] **Step 3: Fix any issues found and commit**

```
git add clients/python/tropek_client/models/
git commit -m "fix(client): model review corrections"
```

---

### Task 8: Exceptions — structured error hierarchy

**Files:**
- Rewrite: `clients/python/tropek_client/exceptions.py`
- Create: `clients/python/tests/test_exceptions.py`

- [ ] **Step 1: Write tests for exception hierarchy**

Create `clients/python/tests/test_exceptions.py`:

```python
import pytest

from tropek_client.exceptions import (
    TropekAPIError,
    TropekConflictError,
    TropekConnectionError,
    TropekNotFoundError,
    TropekServerError,
    TropekValidationError,
    ValidationDetail,
    parse_error_response,
)


class TestExceptionHierarchy:
    def test_all_exceptions_inherit_from_base(self):
        for exc_class in [TropekNotFoundError, TropekConflictError, TropekValidationError, TropekServerError, TropekConnectionError]:
            assert issubclass(exc_class, TropekAPIError)

    def test_not_found_has_entity_and_name(self):
        exc = TropekNotFoundError(status_code=404, detail="asset 'my-svc' not found", entity='asset', name='my-svc')
        assert exc.entity == 'asset'
        assert exc.name == 'my-svc'
        assert exc.status_code == 404

    def test_conflict_has_entity_name_reason(self):
        exc = TropekConflictError(status_code=409, detail="asset 'my-svc': already exists", entity='asset', name='my-svc', reason='already exists')
        assert exc.reason == 'already exists'

    def test_validation_has_errors_list(self):
        errors = [ValidationDetail(loc=['body', 'name'], msg='field required', type='missing')]
        exc = TropekValidationError(status_code=422, detail='validation failed', errors=errors)
        assert len(exc.errors) == 1
        assert exc.errors[0].loc == ['body', 'name']


class TestParseErrorResponse:
    def test_parse_404(self):
        exc = parse_error_response(404, {'detail': "asset 'my-svc' not found"})
        assert isinstance(exc, TropekNotFoundError)
        assert exc.entity == 'asset'
        assert exc.name == 'my-svc'

    def test_parse_409(self):
        exc = parse_error_response(409, {'detail': "asset 'my-svc': already exists"})
        assert isinstance(exc, TropekConflictError)
        assert exc.entity == 'asset'
        assert exc.name == 'my-svc'
        assert exc.reason == 'already exists'

    def test_parse_422_with_detail_list(self):
        body = {'detail': [{'loc': ['body', 'name'], 'msg': 'field required', 'type': 'missing'}]}
        exc = parse_error_response(422, body)
        assert isinstance(exc, TropekValidationError)
        assert len(exc.errors) == 1

    def test_parse_422_with_string_detail(self):
        body = {'detail': 'some validation error'}
        exc = parse_error_response(422, body)
        assert isinstance(exc, TropekValidationError)

    def test_parse_500(self):
        exc = parse_error_response(500, {'detail': 'internal server error'})
        assert isinstance(exc, TropekServerError)

    def test_parse_unknown_status(self):
        exc = parse_error_response(503, {'detail': 'service unavailable'})
        assert isinstance(exc, TropekAPIError)

    def test_parse_404_unparseable_detail(self):
        exc = parse_error_response(404, {'detail': 'not found'})
        assert isinstance(exc, TropekNotFoundError)
        assert exc.entity is None
        assert exc.name is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory clients/python pytest tests/test_exceptions.py -v`
Expected: FAIL — `parse_error_response` doesn't exist yet, exception constructors have wrong signatures.

- [ ] **Step 3: Implement exceptions.py**

Rewrite `clients/python/tropek_client/exceptions.py`:

```python
from __future__ import annotations

import re

from pydantic import BaseModel


class ValidationDetail(BaseModel):
    loc: list[str]
    msg: str
    type: str


class TropekAPIError(Exception):
    def __init__(self, status_code: int, detail: str, *, request_id: str | None = None) -> None:
        self.status_code = status_code
        self.detail = detail
        self.request_id = request_id
        super().__init__(f'HTTP {status_code}: {detail}')


class TropekNotFoundError(TropekAPIError):
    def __init__(
        self,
        status_code: int = 404,
        detail: str = '',
        *,
        entity: str | None = None,
        name: str | None = None,
        request_id: str | None = None,
    ) -> None:
        self.entity = entity
        self.name = name
        super().__init__(status_code, detail, request_id=request_id)


class TropekConflictError(TropekAPIError):
    def __init__(
        self,
        status_code: int = 409,
        detail: str = '',
        *,
        entity: str | None = None,
        name: str | None = None,
        reason: str | None = None,
        request_id: str | None = None,
    ) -> None:
        self.entity = entity
        self.name = name
        self.reason = reason
        super().__init__(status_code, detail, request_id=request_id)


class TropekValidationError(TropekAPIError):
    def __init__(
        self,
        status_code: int = 422,
        detail: str = '',
        *,
        errors: list[ValidationDetail] | None = None,
        request_id: str | None = None,
    ) -> None:
        self.errors = errors or []
        super().__init__(status_code, detail, request_id=request_id)


class TropekServerError(TropekAPIError):
    pass


class TropekConnectionError(TropekAPIError):
    def __init__(self, detail: str, *, request_id: str | None = None) -> None:
        super().__init__(0, detail, request_id=request_id)


_NOT_FOUND_PATTERN = re.compile(r"^(\w[\w\s]*?)\s+'([^']+)'\s+not found$")
_CONFLICT_PATTERN = re.compile(r"^(\w[\w\s]*?)\s+'([^']+)':\s+(.+)$")


def parse_error_response(status_code: int, body: dict) -> TropekAPIError:
    detail_raw = body.get('detail', '')

    if status_code == 404:
        detail_str = str(detail_raw)
        entity, name = None, None
        match = _NOT_FOUND_PATTERN.match(detail_str)
        if match:
            entity, name = match.group(1), match.group(2)
        return TropekNotFoundError(detail=detail_str, entity=entity, name=name)

    if status_code == 409:
        detail_str = str(detail_raw)
        entity, name, reason = None, None, None
        match = _CONFLICT_PATTERN.match(detail_str)
        if match:
            entity, name, reason = match.group(1), match.group(2), match.group(3)
        return TropekConflictError(detail=detail_str, entity=entity, name=name, reason=reason)

    if status_code == 422:
        errors: list[ValidationDetail] = []
        if isinstance(detail_raw, list):
            for item in detail_raw:
                loc = [str(part) for part in item.get('loc', [])]
                errors.append(ValidationDetail(loc=loc, msg=item.get('msg', ''), type=item.get('type', '')))
        detail_str = str(detail_raw) if not errors else 'validation failed'
        return TropekValidationError(detail=detail_str, errors=errors)

    if status_code >= 500:
        return TropekServerError(status_code, str(detail_raw))

    return TropekAPIError(status_code, str(detail_raw))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory clients/python pytest tests/test_exceptions.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```
git add clients/python/tropek_client/exceptions.py clients/python/tests/test_exceptions.py
git commit -m "feat(client): structured exception hierarchy with error response parsing"
```

---

### Task 9: HTTP layer — _http.py with logging and error mapping

**Files:**
- Create: `clients/python/tropek_client/_http.py`
- Create: `clients/python/tests/test_http.py`

- [ ] **Step 1: Write tests for HTTP layer**

Create `clients/python/tests/test_http.py`:

```python
import httpx
import pytest
import respx

from tropek_client._http import HttpSession
from tropek_client.exceptions import (
    TropekConflictError,
    TropekConnectionError,
    TropekNotFoundError,
    TropekServerError,
    TropekValidationError,
)


@pytest.fixture
def session():
    return HttpSession(base_url='http://test-api:8080')


class TestHttpSession:
    @respx.mock
    def test_get_success(self, session):
        respx.get('http://test-api:8080/assets').mock(
            return_value=httpx.Response(200, json={'items': [], 'total': 0})
        )
        response = session.get('/assets')
        assert response.status_code == 200
        assert response.json() == {'items': [], 'total': 0}

    @respx.mock
    def test_post_sends_json_body(self, session):
        route = respx.post('http://test-api:8080/assets').mock(
            return_value=httpx.Response(201, json={'id': '123', 'name': 'test'})
        )
        session.post('/assets', json={'name': 'test', 'type_name': 'vm'})
        assert route.calls[0].request.content == b'{"name": "test", "type_name": "vm"}'

    @respx.mock
    def test_404_raises_not_found(self, session):
        respx.get('http://test-api:8080/assets/missing').mock(
            return_value=httpx.Response(404, json={'detail': "asset 'missing' not found"})
        )
        with pytest.raises(TropekNotFoundError) as exc_info:
            session.get('/assets/missing')
        assert exc_info.value.entity == 'asset'
        assert exc_info.value.name == 'missing'

    @respx.mock
    def test_409_raises_conflict(self, session):
        respx.post('http://test-api:8080/assets').mock(
            return_value=httpx.Response(409, json={'detail': "asset 'dup': already exists"})
        )
        with pytest.raises(TropekConflictError):
            session.post('/assets', json={'name': 'dup'})

    @respx.mock
    def test_422_raises_validation(self, session):
        respx.post('http://test-api:8080/assets').mock(
            return_value=httpx.Response(422, json={'detail': [{'loc': ['body', 'name'], 'msg': 'field required', 'type': 'missing'}]})
        )
        with pytest.raises(TropekValidationError) as exc_info:
            session.post('/assets', json={})
        assert len(exc_info.value.errors) == 1

    @respx.mock
    def test_500_raises_server_error(self, session):
        respx.get('http://test-api:8080/health').mock(
            return_value=httpx.Response(500, json={'detail': 'internal error'})
        )
        with pytest.raises(TropekServerError):
            session.get('/health')

    @respx.mock
    def test_connection_error(self, session):
        respx.get('http://test-api:8080/health').mock(side_effect=httpx.ConnectError('connection refused'))
        with pytest.raises(TropekConnectionError):
            session.get('/health')

    @respx.mock
    def test_timeout_error(self, session):
        respx.get('http://test-api:8080/health').mock(side_effect=httpx.TimeoutException('timed out'))
        with pytest.raises(TropekConnectionError):
            session.get('/health')

    def test_api_key_sets_header(self):
        session = HttpSession(base_url='http://test-api:8080', api_key='secret-key')
        assert session._client.headers.get('x-api-key') == 'secret-key'

    def test_custom_headers(self):
        session = HttpSession(base_url='http://test-api:8080', headers={'X-Custom': 'value'})
        assert session._client.headers.get('x-custom') == 'value'

    def test_context_manager(self):
        with HttpSession(base_url='http://test-api:8080') as session:
            assert session._client is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory clients/python pytest tests/test_http.py -v`
Expected: FAIL — `_http` module doesn't exist

- [ ] **Step 3: Implement _http.py**

Create `clients/python/tropek_client/_http.py`:

```python
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from tropek_client.exceptions import TropekConnectionError, parse_error_response

logger = logging.getLogger('tropek_client')


class HttpSession:
    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
        verify: bool = True,
    ) -> None:
        request_headers: dict[str, str] = {}
        if api_key:
            request_headers['X-API-Key'] = api_key
        if headers:
            request_headers.update(headers)
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers=request_headers,
            verify=verify,
        )
        self._slow_threshold = 5.0

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> httpx.Response:
        return self._request('GET', path, params=params)

    def post(self, path: str, *, json: Any = None, params: dict[str, Any] | None = None) -> httpx.Response:
        return self._request('POST', path, json=json, params=params)

    def put(self, path: str, *, json: Any = None) -> httpx.Response:
        return self._request('PUT', path, json=json)

    def patch(self, path: str, *, json: Any = None) -> httpx.Response:
        return self._request('PATCH', path, json=json)

    def delete(self, path: str) -> httpx.Response:
        return self._request('DELETE', path)

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        start = time.monotonic()
        try:
            response = self._client.request(method, path, **kwargs)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error('%s %s failed after %.0fms: %s', method, path, duration_ms, exc)
            raise TropekConnectionError(str(exc)) from exc

        duration_ms = (time.monotonic() - start) * 1000

        if response.is_success:
            logger.info('%s %s %d (%.0fms)', method, path, response.status_code, duration_ms)
            if duration_ms > self._slow_threshold * 1000:
                logger.warning('%s %s took %.0fms (slow)', method, path, duration_ms)
        else:
            self._raise_for_status(response, duration_ms)

        logger.debug(
            '%s %s -> %d body=%s',
            method,
            path,
            response.status_code,
            response.text[:500] if response.text else '(empty)',
        )

        return response

    def _raise_for_status(self, response: httpx.Response, duration_ms: float) -> None:
        try:
            body = response.json()
        except (ValueError, TypeError):
            body = {'detail': response.text}

        if not isinstance(body, dict):
            body = {'detail': str(body)}

        request_id = response.headers.get('x-request-id')
        error = parse_error_response(response.status_code, body)
        error.request_id = request_id

        logger.error(
            '%s %s %d (%.0fms): %s',
            response.request.method,
            response.request.url.path,
            response.status_code,
            duration_ms,
            error.detail,
        )
        raise error

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpSession:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
```

- [ ] **Step 4: Run tests**

Run: `uv run --directory clients/python pytest tests/test_http.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```
git add clients/python/tropek_client/_http.py clients/python/tests/test_http.py
git commit -m "feat(client): HTTP layer with logging, auth, and error mapping"
```

---

### Task 10: Client — TropekClient with all sub-resource groups

**Files:**
- Rewrite: `clients/python/tropek_client/client.py`
- Rewrite: `clients/python/tropek_client/__init__.py`
- Delete: `clients/python/tropek_client/models.py`

This is the largest task. The client has ~12 sub-resource groups. Each group is a class with typed methods that call `self._http.get/post/put/patch/delete` and deserialize responses into models.

- [ ] **Step 1: Rewrite client.py**

Reference the existing `clients/python/tropek_client/client.py` for URL patterns and the design spec for method signatures. The existing client already has the right URL patterns — the rewrite preserves those while:

- Replacing `httpx.Client` with `HttpSession` from `_http.py`
- Replacing `_raise_for_status()` calls (now handled by `HttpSession`)
- Using Pydantic model bodies instead of `**kwargs` and `dict[str, Any]`
- Returning typed models from all methods (no more `dict[str, Any]` returns)
- Importing models from `tropek_client.models` package

The file will contain: `_AssetTypes`, `_Assets`, `_AssetGroups`, `_DataSources`, `_SLIDefinitions`, `_SLODefinitions`, `_Evaluations`, `_Annotations`, `_Trend`, `_SLOAssignments`, `_SLOGroups`, `_SLOGroupAssignments`, `_Configuration`, `_Meta`, and `TropekClient`.

Key changes from existing client:

- `client.assets.create(AssetCreate(...))` instead of `client.assets.create(name, type_name, ...)`
- `client.assets.update(name, AssetUpdate(...))` instead of `client.assets.update(name, **kwargs)`
- `client.assets.tag_keys()` returns `list[TagKeyCount]` instead of `list[dict]`
- `client.evaluations.evaluate()` → `client.evaluations.trigger()` with `EvaluateSingleRequest` body
- `client.evaluations.evaluate_batch()` → `client.evaluations.trigger_batch()` with `EvaluateBatchRequest` body
- All re-evaluate methods take typed request bodies
- `TropekClient.__init__` takes `base_url, api_key, timeout, headers, verify` and creates an `HttpSession`
- `TropekClient` is a context manager (delegates to `HttpSession`)
- Sub-resource property names: keep `sli_definitions` → `slis`, `slo_definitions` → `slos` for shorter DX, but keep `asset_types`, `asset_groups`, `datasources` etc.

For each sub-resource class method:
1. Build query params dict from method arguments (for GET/list methods)
2. Call `self._http.get/post/put/patch/delete`
3. Deserialize `response.json()` into the correct model via `Model.model_validate()`
4. Return the typed model

For methods returning `None` (deletes, some actions): just call the HTTP method — `HttpSession` raises on errors.

For methods sending a Pydantic model body: use `body.model_dump(exclude_none=True)` to serialize. This drops unset optional fields from the request.

- [ ] **Step 2: Delete old models.py**

Remove `clients/python/tropek_client/models.py` — replaced by `models/` package.

- [ ] **Step 3: Update __init__.py**

Rewrite `clients/python/tropek_client/__init__.py`:

```python
from tropek_client.client import TropekClient
from tropek_client.exceptions import (
    TropekAPIError,
    TropekConflictError,
    TropekConnectionError,
    TropekNotFoundError,
    TropekServerError,
    TropekValidationError,
    ValidationDetail,
)

__all__ = [
    'TropekAPIError',
    'TropekClient',
    'TropekConflictError',
    'TropekConnectionError',
    'TropekNotFoundError',
    'TropekServerError',
    'TropekValidationError',
    'ValidationDetail',
]
```

- [ ] **Step 4: Verify client instantiation works**

Run: `uv run --directory clients/python python -c "from tropek_client import TropekClient; c = TropekClient(base_url='http://localhost:8080'); print(type(c.assets)); print(type(c.evaluations)); print('OK')"`

- [ ] **Step 5: Commit**

```
git add clients/python/tropek_client/client.py clients/python/tropek_client/__init__.py
git rm clients/python/tropek_client/models.py
git commit -m "feat(client): rewrite client with typed sub-resource groups and HttpSession"
```

---

### Task 11: Client unit tests with respx mocks

**Files:**
- Rewrite: `clients/python/tests/test_client.py`
- Rewrite: `clients/python/tests/test_models.py`

- [ ] **Step 1: Write test_models.py — model round-trip tests**

Rewrite `clients/python/tests/test_models.py` to test that every major model can be constructed with sample data, serialized to dict, and deserialized back. Group tests by model file. At minimum cover:

- `AssetRead`, `AssetCreate` — basic fields, nullable fields
- `EvaluationSummary`, `EvaluationDetail` — nested models (AssetSnapshot, FailingIndicator, AnnotationRead)
- `IndicatorResult` — nested PassTarget list
- `GroupedMetricHeatmapResponse` — deeply nested (columns, groups, cells, summary)
- `SLODefinitionRead` — nested objectives list
- `PagedResponse[AssetRead]` — generic pagination

Each test constructs the model from a dict, dumps it back, and asserts the round-trip matches.

- [ ] **Step 2: Write test_client.py — per-method tests with mocked HTTP**

Rewrite `clients/python/tests/test_client.py`. Use `respx` to mock HTTP responses. Structure:

```python
import httpx
import pytest
import respx

from tropek_client import TropekClient
from tropek_client.models import AssetCreate, AssetRead, AssetUpdate


BASE_URL = 'http://test-api:8080'


@pytest.fixture
def client():
    return TropekClient(base_url=BASE_URL)


class TestAssets:
    @respx.mock
    def test_list(self, client):
        respx.get(f'{BASE_URL}/assets').mock(
            return_value=httpx.Response(200, json={
                'items': [{'id': '...', 'name': 'svc', ...}],
                'total': 1,
            })
        )
        result = client.assets.list()
        assert result.total == 1
        assert isinstance(result.items[0], AssetRead)

    @respx.mock
    def test_create(self, client):
        # ... mock POST /assets, verify body sent, verify response type

    @respx.mock
    def test_get(self, client):
        # ... mock GET /assets/{name}, verify response type

    # ... update, delete, tag_keys, tag_values


class TestEvaluations:
    # ... list, get, trigger, trigger_batch, invalidate, etc.
```

Cover at minimum: one test per sub-resource group per HTTP method used. The tests verify:
1. Correct URL was called
2. Correct HTTP method was used
3. Request body matches what the Pydantic model serializes to (for POST/PUT/PATCH)
4. Query parameters are passed correctly (for list/filter methods)
5. Response is deserialized into the correct model type

- [ ] **Step 3: Run all tests**

Run: `uv run --directory clients/python pytest tests/test_models.py tests/test_client.py -v`
Expected: all PASS

- [ ] **Step 4: Commit**

```
git add clients/python/tests/test_client.py clients/python/tests/test_models.py
git commit -m "test(client): model round-trips and per-method client tests with respx mocks"
```

---

### Task 12: Drift tests — models vs openapi.json

**Files:**
- Create: `clients/python/tests/test_drift.py`

- [ ] **Step 1: Write drift test**

Create `clients/python/tests/test_drift.py`. This test parses `api/openapi.json` and validates every client model:

```python
import json
from pathlib import Path
from typing import Any, get_args, get_origin

import pytest

import tropek_client.models as client_models

OPENAPI_PATH = Path(__file__).resolve().parents[3] / 'api' / 'openapi.json'

OPENAPI_TO_PYTHON = {
    ('string', None): str,
    ('string', 'uuid'): 'UUID',
    ('string', 'date-time'): 'datetime',
    ('integer', None): int,
    ('number', None): float,
    ('boolean', None): bool,
}

# Map OpenAPI schema names to client model classes
# This is the registry — add new models here when they're created
SCHEMA_MODEL_MAP: dict[str, type] = {}

def _register_models():
    """Build map from OpenAPI schema name to Pydantic model class."""
    # Iterate over all exported model classes
    for name in dir(client_models):
        obj = getattr(client_models, name)
        if isinstance(obj, type) and hasattr(obj, 'model_fields'):
            SCHEMA_MODEL_MAP[name] = obj

_register_models()


@pytest.fixture(scope='module')
def openapi_schemas() -> dict[str, Any]:
    with open(OPENAPI_PATH) as f:
        spec = json.load(f)
    return spec['components']['schemas']


def _resolve_ref(ref: str, schemas: dict) -> dict:
    name = ref.split('/')[-1]
    return schemas[name]


class TestModelDrift:
    def test_openapi_file_exists(self):
        assert OPENAPI_PATH.exists(), f'OpenAPI spec not found at {OPENAPI_PATH}'

    def test_all_response_schemas_have_models(self, openapi_schemas):
        """Every schema used in a response should have a client model."""
        missing = []
        skip_prefixes = ('HTTPValidationError', 'ValidationError', 'LocationInner', 'Response')
        for schema_name in openapi_schemas:
            if schema_name.startswith(skip_prefixes):
                continue
            if schema_name.startswith('PagedResponse'):
                continue
            if schema_name not in SCHEMA_MODEL_MAP:
                missing.append(schema_name)
        if missing:
            pytest.fail(f'Missing client models for OpenAPI schemas: {sorted(missing)}')

    @pytest.mark.parametrize('schema_name', sorted(SCHEMA_MODEL_MAP.keys()))
    def test_fields_match(self, schema_name, openapi_schemas):
        """Model fields match the OpenAPI schema fields."""
        if schema_name not in openapi_schemas:
            pytest.skip(f'{schema_name} not in OpenAPI spec (may be a base class)')
        schema = openapi_schemas[schema_name]
        model = SCHEMA_MODEL_MAP[schema_name]
        schema_props = schema.get('properties', {})
        required_fields = set(schema.get('required', []))
        model_field_names = set(model.model_fields.keys())

        # Check no schema fields are missing from model
        schema_field_names = set(schema_props.keys())
        missing_in_model = schema_field_names - model_field_names
        assert not missing_in_model, f'{schema_name}: fields in OpenAPI but not in model: {missing_in_model}'

        # Check no extra fields in model
        extra_in_model = model_field_names - schema_field_names
        assert not extra_in_model, f'{schema_name}: fields in model but not in OpenAPI: {extra_in_model}'
```

This covers field presence and extra field detection. Type checking can be added later as an enhancement — field presence is the critical drift signal.

- [ ] **Step 2: Run drift tests**

Run: `uv run --directory clients/python pytest tests/test_drift.py -v`

If tests fail, they'll show exactly which models have field mismatches. Fix any issues in the model files.

- [ ] **Step 3: Commit**

```
git add clients/python/tests/test_drift.py
git commit -m "test(client): add drift tests validating models against openapi.json"
```

---

### Task 13: Update manifest.py imports

**Files:**
- Modify: `clients/python/tropek_client/manifest.py`

- [ ] **Step 1: Update imports in manifest.py**

The manifest imports models from `tropek_client.models`. The old model names need to map to new ones:

| Old name | New name |
|----------|----------|
| `Asset` | `AssetRead` |
| `AssetType` | `AssetTypeRead` |
| `AssetGroup` | `AssetGroupRead` |
| `DataSource` | `DataSourceRead` |
| `SLIDefinition` | `SLIDefinitionRead` |
| `SLODefinition` | `SLODefinitionRead` |
| `SLOAssignment` | `SLOAssignmentRead` |
| `SLOGroup` | `SLOGroupRead` |
| `SLOGroupAssignment` | `SLOGroupAssignmentRead` |

Read `clients/python/tropek_client/manifest.py` fully. Update all imports and type references. The manifest mostly uses the models for type hints and `model_validate()` — the field access patterns should be compatible since the new models have the same field names.

Also update any client method calls that changed signature:
- `client.assets.create(name, type_name)` → `client.assets.create(AssetCreate(name=..., type_name=...))`
- `client.datasources.create(name, adapter_type, adapter_url)` → `client.datasources.create(DataSourceCreate(...))`
- `client.slo_definitions.create(...)` → `client.slos.create(SLODefinitionCreate(...))`
- `client.sli_definitions.create(...)` → `client.slis.create(SLIDefinitionCreate(...))`
- Sub-resource renames: `slo_definitions` → `slos`, `sli_definitions` → `slis`
- `**kwargs` calls on `.update()` → explicit model bodies

- [ ] **Step 2: Run existing manifest tests**

Run: `uv run --directory clients/python pytest tests/test_manifest.py -v`

Fix any failures caused by the import changes.

- [ ] **Step 3: Commit**

```
git add clients/python/tropek_client/manifest.py
git commit -m "refactor(client): update manifest imports to new model names"
```

---

### Task 14: Update __init__.py imports in tests

**Files:**
- Modify: `clients/python/tests/__init__.py`
- Modify: `clients/python/tests/test_cli.py`
- Modify: `clients/python/tests/test_manifest.py` (if not already fixed in Task 13)

- [ ] **Step 1: Fix any remaining import errors across test files**

Run: `uv run --directory clients/python pytest tests/ -v`

Fix any import errors in test files that reference old model names or old exception signatures.

- [ ] **Step 2: Commit**

```
git add clients/python/tests/
git commit -m "fix(client): update remaining test imports for v2 models"
```

---

### Task 15: Clean up spike directories

**Files:**
- Delete: `clients/python/tropek-client-generated/`
- Delete: `clients/python/tropek-client-openapi-gen/`
- Delete: `clients/python/tropek-client-clientele/`

- [ ] **Step 1: Remove the three generator spike directories**

These were evaluation artifacts. The useful output (field names and types) has been incorporated into the owned models.

```
rm -rf clients/python/tropek-client-generated
rm -rf clients/python/tropek-client-openapi-gen
rm -rf clients/python/tropek-client-clientele
```

- [ ] **Step 2: Commit**

```
git add -A clients/python/tropek-client-generated clients/python/tropek-client-openapi-gen clients/python/tropek-client-clientele
git commit -m "chore: remove generator spike directories"
```

---

### Task 16: Final verification

- [ ] **Step 1: Run all client tests**

Run: `uv run --directory clients/python pytest tests/ -v`
Expected: all PASS

- [ ] **Step 2: Verify drift tests pass**

Run: `uv run --directory clients/python pytest tests/test_drift.py -v`
Expected: all PASS — models match openapi.json

- [ ] **Step 3: Verify imports work end-to-end**

Run:
```python
uv run --directory clients/python python -c "
from tropek_client import TropekClient
from tropek_client.models import (
    AssetCreate, AssetRead, EvaluationSummary, EvaluationDetail,
    GroupedMetricHeatmapResponse, SLODefinitionCreate, TrendTargets,
    PagedResponse, TagKeyCount, AnnotationRead, ConfigurationRead,
)
print(f'Models: {len(dir())} names imported')
c = TropekClient(base_url='http://localhost:8080')
print(f'Sub-resources: assets={type(c.assets).__name__}, evals={type(c.evaluations).__name__}')
print('All OK')
"
```

- [ ] **Step 4: Final commit if any fixes needed**

```
git add -A clients/python/
git commit -m "fix(client): final verification fixes"
```
