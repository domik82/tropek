# Stream E: Python Client SDK

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Read first:** `docs/superpowers/plans/2026-03-15-api-ui-alignment-overview.md`

**Goal:** Create `tropek-client` Python package with typed client, Pydantic models, YAML
manifest loader, desired-state reconciler, and CLI.

**Architecture:** Standalone package in `clients/python/` added to the uv workspace.
Uses `httpx` for HTTP, Pydantic v2 for models, `click` for CLI, `pyyaml` for manifests.
Models mirror API schemas. Reconciler compares declared state vs API state and produces
create/update/skip actions.

**Tech Stack:** Python 3.13, httpx, Pydantic v2, click, PyYAML, pytest

**Spec:** `docs/superpowers/specs/2026-03-15-api-ui-alignment-design.md` §10

---

## File Structure

| Action | File | Responsibility |
|---|---|---|
| Create | `clients/python/pyproject.toml` | Package config, dependencies |
| Create | `clients/python/tropek_client/__init__.py` | Public exports |
| Create | `clients/python/tropek_client/models.py` | Pydantic models mirroring API schemas |
| Create | `clients/python/tropek_client/exceptions.py` | Typed exception hierarchy |
| Create | `clients/python/tropek_client/client.py` | TropekClient + resource classes |
| Create | `clients/python/tropek_client/manifest.py` | YAML loader + reconciler |
| Create | `clients/python/tropek_client/cli.py` | Click CLI (`tropek apply`, `tropek validate`) |
| Create | `clients/python/tests/test_models.py` | Model validation tests |
| Create | `clients/python/tests/test_manifest.py` | Manifest loading + reconciliation tests |
| Create | `clients/python/tests/test_client.py` | Client resource class tests |
| Create | `clients/python/tests/test_cli.py` | CLI validation + apply tests |
| Modify | `pyproject.toml` (workspace root) | Add `clients/python` to workspace members |

---

### Task 1: Package Scaffold

**Files:**
- Create: `clients/python/pyproject.toml`
- Create: `clients/python/tropek_client/__init__.py`
- Modify: `pyproject.toml` (workspace root)

- [ ] **Step 1: Create package config**

```toml
# clients/python/pyproject.toml
[project]
name = "tropek-client"
version = "0.1.0"
description = "Typed Python client for the TROPEK quality gate API"
requires-python = ">=3.13"
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.7",
    "pyyaml>=6.0",
    "click>=8.1",
]

[project.scripts]
tropek = "tropek_client.cli:cli"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-httpx>=0.30",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["tropek_client"]
```

- [ ] **Step 2: Create `__init__.py` with public exports**

```python
# clients/python/tropek_client/__init__.py
"""TROPEK Python client — typed API client with declarative YAML setup."""

from tropek_client.client import TropekClient
from tropek_client.exceptions import (
    TropekAPIError,
    TropekConflictError,
    TropekNotFoundError,
    TropekValidationError,
)

__all__ = [
    "TropekClient",
    "TropekAPIError",
    "TropekConflictError",
    "TropekNotFoundError",
    "TropekValidationError",
]
```

- [ ] **Step 3: Add to workspace**

In root `pyproject.toml`, add `"clients/python"` to `[tool.uv.workspace] members`:

```toml
[tool.uv.workspace]
members = [
    "api",
    "adapters/prometheus",
    "clients/python",
]
```

**Do NOT add `clients/python/tests` to root `testpaths`** — SDK tests should run in
isolation via `uv run pytest clients/python/tests/` to avoid polluting the root test
suite. Only add `"clients/python"` to `pythonpath` so imports resolve:

In `[tool.pytest.ini_options]`, add to `pythonpath` only:
```toml
pythonpath = ["api", "adapters/prometheus", "clients/python"]
```

- [ ] **Step 4: Commit**

```bash
git add clients/python/pyproject.toml clients/python/tropek_client/__init__.py pyproject.toml
git commit -m "feat: scaffold tropek-client package in workspace"
```

---

### Task 2: Exceptions

**Files:**
- Create: `clients/python/tropek_client/exceptions.py`

- [ ] **Step 1: Create exception hierarchy**

```python
# clients/python/tropek_client/exceptions.py
"""Typed exceptions for TROPEK API errors."""

from __future__ import annotations


class TropekAPIError(Exception):
    """Base exception for all TROPEK API errors."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


class TropekNotFoundError(TropekAPIError):
    """Raised when a resource is not found (404)."""

    def __init__(self, detail: str) -> None:
        super().__init__(404, detail)


class TropekConflictError(TropekAPIError):
    """Raised when a resource conflict occurs (409)."""

    def __init__(self, detail: str) -> None:
        super().__init__(409, detail)


class TropekValidationError(TropekAPIError):
    """Raised when request validation fails (422)."""

    def __init__(self, detail: str) -> None:
        super().__init__(422, detail)
```

- [ ] **Step 2: Commit**

```bash
git add clients/python/tropek_client/exceptions.py
git commit -m "feat: add tropek-client exception hierarchy"
```

---

### Task 3: Pydantic Models

**Files:**
- Create: `clients/python/tropek_client/models.py`
- Create: `clients/python/tests/test_models.py`

- [ ] **Step 1: Write failing test for model validation**

```python
# clients/python/tests/test_models.py
from __future__ import annotations

from tropek_client.models import Asset, AssetType, SLODefinition, SLOTestRequest


def test_asset_type_from_dict():
    at = AssetType.model_validate({"id": "abc-123", "name": "vm", "is_default": True})
    assert at.name == "vm"
    assert at.is_default is True


def test_asset_from_dict():
    a = Asset.model_validate({
        "id": "abc-123",
        "name": "vm-01",
        "display_name": "VM 01",
        "type_name": "vm",
        "labels": {"os": "linux"},
        "created_at": "2026-03-01T00:00:00Z",
    })
    assert a.name == "vm-01"
    assert a.labels["os"] == "linux"


def test_slo_definition_from_dict():
    slo = SLODefinition.model_validate({
        "id": "abc-123",
        "name": "my-slo",
        "display_name": None,
        "version": 1,
        "slo_yaml": "spec_version: '1.0'",
        "notes": None,
        "author": None,
        "meta": {},
        "active": True,
        "created_at": "2026-03-01T00:00:00Z",
    })
    assert slo.version == 1


def test_slo_test_request_from_dict():
    req = SLOTestRequest.model_validate({
        "slo_yaml": "spec_version: '1.0'",
        "sli_name": "my-sli",
        "data_source_name": "prom",
        "asset_name": "vm-01",
        "period_start": "2026-03-01T00:00:00Z",
        "period_end": "2026-03-01T01:00:00Z",
    })
    assert req.sli_name == "my-sli"
    assert req.baseline is None
```

- [ ] **Step 2: Create models**

```python
# clients/python/tropek_client/models.py
"""Pydantic models mirroring TROPEK API response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class PagedResponse[T](BaseModel):
    """Generic paginated response."""

    items: list[T]
    total: int


class AssetType(BaseModel):
    """Asset type."""

    id: uuid.UUID
    name: str
    is_default: bool

    model_config = ConfigDict(from_attributes=True)


class Asset(BaseModel):
    """Asset."""

    id: uuid.UUID
    name: str
    display_name: str | None
    type_name: str
    labels: dict[str, str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssetGroupMember(BaseModel):
    """Member of an asset group."""

    asset_id: uuid.UUID
    asset_name: str
    weight: float


class AssetGroupSubgroup(BaseModel):
    """Subgroup reference."""

    group_id: uuid.UUID
    weight: float


class AssetGroup(BaseModel):
    """Asset group with members and subgroups."""

    id: uuid.UUID
    name: str
    display_name: str | None
    members: list[AssetGroupMember]
    subgroups: list[AssetGroupSubgroup]


class AssetGroupTree(BaseModel):
    """Tree of asset groups.

    NOTE: Verify field names against actual GET /asset-groups/tree response.
    If the API returns different field names, update to match.
    """

    top_level: list[AssetGroup]
    all_groups: list[AssetGroup]


class DataSource(BaseModel):
    """Data source registration."""

    id: uuid.UUID
    name: str
    display_name: str | None
    adapter_type: str
    adapter_url: str
    labels: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class SLIDefinition(BaseModel):
    """SLI definition."""

    id: uuid.UUID
    name: str
    display_name: str | None
    version: int
    indicators: dict[str, str]
    notes: str | None
    author: str | None
    meta: dict[str, Any]
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SLODefinition(BaseModel):
    """SLO definition."""

    id: uuid.UUID
    name: str
    display_name: str | None
    version: int
    slo_yaml: str
    notes: str | None
    author: str | None
    meta: dict[str, Any]
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SLOValidationError(BaseModel):
    """Single validation error."""

    field: str
    message: str


class SLOValidationResult(BaseModel):
    """Result from SLO validation."""

    valid: bool
    errors: list[SLOValidationError]
    objectives: list[dict[str, Any]] | None = None


class BaselineConfig(BaseModel):
    """Baseline configuration for SLO testing."""

    mode: Literal["none", "asset_history", "manual"]
    values: dict[str, float] | None = None


class SLOTestRequest(BaseModel):
    """Request body for POST /slo-definitions/test."""

    slo_yaml: str
    sli_name: str
    data_source_name: str
    asset_name: str
    period_start: datetime
    period_end: datetime
    baseline: BaselineConfig | None = None


class SLOTestResult(BaseModel):
    """Result from SLO test/dry-run."""

    result: str
    score: float
    indicator_results: list[IndicatorResult]
    warning_count: int
    fail_count: int


class FailingIndicator(BaseModel):
    """A failing SLI indicator summary."""

    metric: str
    display_name: str
    value: float
    threshold: str


class Annotation(BaseModel):
    """Evaluation annotation."""

    id: uuid.UUID
    content: str
    author: str | None
    category: str | None
    meta: dict[str, Any]
    created_at: datetime
    updated_at: datetime | None


class EvaluationSummary(BaseModel):
    """Compact evaluation for list views."""

    id: uuid.UUID
    name: str
    status: str
    result: str | None
    score: float | None
    period_start: datetime
    period_end: datetime
    slo_name: str | None
    slo_version: int | None
    sli_name: str | None
    sli_version: int | None
    data_source_name: str | None
    ingestion_mode: str
    adapter_used: str | None
    invalidated: bool
    asset_snapshot: dict[str, Any]
    evaluation_metadata: dict[str, Any]
    annotation_count: int
    latest_annotation: Annotation | None
    top_failures: list[FailingIndicator]
    created_at: datetime


class IndicatorResult(BaseModel):
    """Per-SLI evaluation result."""

    metric: str
    display_name: str
    value: float
    compared_value: float | None
    change_absolute: float | None
    change_relative_pct: float | None
    status: str
    score: float
    weight: float
    key_sli: bool
    pass_targets: list[dict[str, Any]] | None
    warning_targets: list[dict[str, Any]] | None


class EvaluationDetail(EvaluationSummary):
    """Full evaluation with annotations and indicator results."""

    invalidation_note: str | None
    compared_evaluation_ids: list[uuid.UUID]
    annotations: list[Annotation]
    indicator_results: list[IndicatorResult]


class TrendPoint(BaseModel):
    """Single trend data point."""

    timestamp: datetime
    value: float
    eval_id: uuid.UUID
    result: str
    baseline: float | None


class AssetSLOLink(BaseModel):
    """Asset-SLO binding."""

    id: uuid.UUID
    link_name: str
    asset_id: uuid.UUID
    slo_name: str
    sli_name: str
    data_source_name: str


class AssetGroupSLOLink(BaseModel):
    """Asset group-SLO binding."""

    id: uuid.UUID
    link_name: str
    group_id: uuid.UUID
    slo_name: str
    sli_name: str
    data_source_name: str
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest clients/python/tests/test_models.py -v
```

- [ ] **Step 4: Commit**

```bash
git add clients/python/tropek_client/models.py clients/python/tests/test_models.py
git commit -m "feat: add tropek-client Pydantic models"
```

---

### Task 4: HTTP Client

**Files:**
- Create: `clients/python/tropek_client/client.py`

- [ ] **Step 1: Create the client with resource classes**

```python
# clients/python/tropek_client/client.py
"""Typed HTTP client for the TROPEK API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import httpx

from tropek_client.exceptions import (
    TropekAPIError,
    TropekConflictError,
    TropekNotFoundError,
    TropekValidationError,
)
from tropek_client.models import (
    Annotation,
    Asset,
    AssetGroup,
    AssetGroupSLOLink,
    AssetGroupTree,
    AssetSLOLink,
    AssetType,
    DataSource,
    EvaluationDetail,
    EvaluationSummary,
    PagedResponse,
    SLIDefinition,
    SLODefinition,
    SLOTestResult,
    SLOValidationResult,
    TrendPoint,
)


def _raise_for_status(resp: httpx.Response) -> None:
    """Raise typed exception for non-2xx responses."""
    if resp.is_success:
        return
    detail = resp.text
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:
        pass
    match resp.status_code:
        case 404:
            raise TropekNotFoundError(detail)
        case 409:
            raise TropekConflictError(detail)
        case 422:
            raise TropekValidationError(detail)
        case _:
            raise TropekAPIError(resp.status_code, detail)


class _AssetTypes:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list(self) -> list[AssetType]:
        resp = self._http.get("/asset-types")
        _raise_for_status(resp)
        return [AssetType.model_validate(i) for i in resp.json()]

    def create(self, name: str, *, is_default: bool = False) -> AssetType:
        resp = self._http.post("/asset-types", json={"name": name, "is_default": is_default})
        _raise_for_status(resp)
        return AssetType.model_validate(resp.json())

    def set_default(self, name: str) -> AssetType:
        resp = self._http.patch(f"/asset-types/{name}/set-default")
        _raise_for_status(resp)
        return AssetType.model_validate(resp.json())

    def delete(self, name: str) -> None:
        resp = self._http.delete(f"/asset-types/{name}")
        _raise_for_status(resp)


class _Assets:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list(
        self,
        *,
        type_name: str | None = None,
        label_key: str | None = None,
        label_val: str | None = None,
    ) -> PagedResponse[Asset]:
        params: dict[str, str] = {}
        if type_name:
            params["type_name"] = type_name
        if label_key:
            params["label_key"] = label_key
        if label_val:
            params["label_val"] = label_val
        resp = self._http.get("/assets", params=params)
        _raise_for_status(resp)
        data = resp.json()
        return PagedResponse(
            items=[Asset.model_validate(i) for i in data["items"]],
            total=data["total"],
        )

    def create(
        self,
        name: str,
        type_name: str = "vm",
        *,
        display_name: str | None = None,
        labels: dict[str, str] | None = None,
    ) -> Asset:
        body: dict[str, Any] = {"name": name, "type_name": type_name}
        if display_name:
            body["display_name"] = display_name
        if labels:
            body["labels"] = labels
        resp = self._http.post("/assets", json=body)
        _raise_for_status(resp)
        return Asset.model_validate(resp.json())

    def get(self, name: str) -> Asset:
        resp = self._http.get(f"/assets/{name}")
        _raise_for_status(resp)
        return Asset.model_validate(resp.json())

    def update(self, name: str, **kwargs: Any) -> Asset:
        resp = self._http.patch(f"/assets/{name}", json=kwargs)
        _raise_for_status(resp)
        return Asset.model_validate(resp.json())


class _AssetGroups:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list(self) -> PagedResponse[AssetGroup]:
        resp = self._http.get("/asset-groups")
        _raise_for_status(resp)
        data = resp.json()
        return PagedResponse(
            items=[AssetGroup.model_validate(i) for i in data["items"]],
            total=data["total"],
        )

    def tree(self) -> AssetGroupTree:
        resp = self._http.get("/asset-groups/tree")
        _raise_for_status(resp)
        return AssetGroupTree.model_validate(resp.json())

    def create(
        self, name: str, *, members: list[dict[str, Any]] | None = None,
        subgroups: list[dict[str, Any]] | None = None,
    ) -> AssetGroup:
        body: dict[str, Any] = {"name": name}
        if members:
            body["members"] = members
        if subgroups:
            body["subgroups"] = subgroups
        resp = self._http.post("/asset-groups", json=body)
        _raise_for_status(resp)
        return AssetGroup.model_validate(resp.json())

    def get(self, name: str) -> AssetGroup:
        resp = self._http.get(f"/asset-groups/{name}")
        _raise_for_status(resp)
        return AssetGroup.model_validate(resp.json())

    def add_member(self, group_name: str, asset_id: str, weight: float = 1.0) -> AssetGroup:
        resp = self._http.post(
            f"/asset-groups/{group_name}/members",
            json={"asset_id": asset_id, "weight": weight},
        )
        _raise_for_status(resp)
        return AssetGroup.model_validate(resp.json())

    def remove_member(self, group_name: str, asset_id: str) -> None:
        resp = self._http.delete(f"/asset-groups/{group_name}/members/{asset_id}")
        _raise_for_status(resp)

    def add_subgroup(
        self, group_name: str, child_group_id: str, weight: float = 1.0
    ) -> AssetGroup:
        resp = self._http.post(
            f"/asset-groups/{group_name}/subgroups",
            json={"child_group_id": child_group_id, "weight": weight},
        )
        _raise_for_status(resp)
        return AssetGroup.model_validate(resp.json())

    def remove_subgroup(self, group_name: str, child_group_id: str) -> None:
        resp = self._http.delete(f"/asset-groups/{group_name}/subgroups/{child_group_id}")
        _raise_for_status(resp)


class _SLOLinks[T: BaseModel]:
    def __init__(self, http: httpx.Client, prefix: str, model: type[T]) -> None:
        self._http = http
        self._prefix = prefix
        self._model = model

    def list(self, parent_name: str) -> list[T]:
        resp = self._http.get(f"/{self._prefix}/{parent_name}/slo-links")
        _raise_for_status(resp)
        return [self._model.model_validate(i) for i in resp.json()]

    def create(
        self, parent_name: str, link_name: str,
        slo_name: str, sli_name: str, data_source_name: str,
    ) -> T:
        resp = self._http.post(
            f"/{self._prefix}/{parent_name}/slo-links",
            json={
                "link_name": link_name,
                "slo_name": slo_name,
                "sli_name": sli_name,
                "data_source_name": data_source_name,
            },
        )
        _raise_for_status(resp)
        return self._model.model_validate(resp.json())

    def delete(self, parent_name: str, link_name: str) -> None:
        resp = self._http.delete(f"/{self._prefix}/{parent_name}/slo-links/{link_name}")
        _raise_for_status(resp)


class _DataSources:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list(self, *, adapter_type: str | None = None) -> PagedResponse[DataSource]:
        params: dict[str, str] = {}
        if adapter_type:
            params["adapter_type"] = adapter_type
        resp = self._http.get("/datasources", params=params)
        _raise_for_status(resp)
        data = resp.json()
        return PagedResponse(
            items=[DataSource.model_validate(i) for i in data["items"]],
            total=data["total"],
        )

    def create(
        self, name: str, adapter_type: str, adapter_url: str, **kwargs: Any
    ) -> DataSource:
        body = {"name": name, "adapter_type": adapter_type, "adapter_url": adapter_url, **kwargs}
        resp = self._http.post("/datasources", json=body)
        _raise_for_status(resp)
        return DataSource.model_validate(resp.json())

    def get(self, name: str) -> DataSource:
        resp = self._http.get(f"/datasources/{name}")
        _raise_for_status(resp)
        return DataSource.model_validate(resp.json())

    def update(self, name: str, **kwargs: Any) -> DataSource:
        resp = self._http.patch(f"/datasources/{name}", json=kwargs)
        _raise_for_status(resp)
        return DataSource.model_validate(resp.json())


class _SLIDefinitions:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list(self) -> PagedResponse[SLIDefinition]:
        resp = self._http.get("/sli-definitions")
        _raise_for_status(resp)
        data = resp.json()
        return PagedResponse(
            items=[SLIDefinition.model_validate(i) for i in data["items"]],
            total=data["total"],
        )

    def create(self, name: str, indicators: dict[str, str], **kwargs: Any) -> SLIDefinition:
        body = {"name": name, "indicators": indicators, **kwargs}
        resp = self._http.post("/sli-definitions", json=body)
        _raise_for_status(resp)
        return SLIDefinition.model_validate(resp.json())

    def get(self, name: str) -> SLIDefinition:
        resp = self._http.get(f"/sli-definitions/{name}")
        _raise_for_status(resp)
        return SLIDefinition.model_validate(resp.json())

    def versions(self, name: str) -> list[SLIDefinition]:
        resp = self._http.get(f"/sli-definitions/{name}/versions")
        _raise_for_status(resp)
        return [SLIDefinition.model_validate(v) for v in resp.json()]

    def delete(self, name: str) -> None:
        resp = self._http.delete(f"/sli-definitions/{name}")
        _raise_for_status(resp)


class _SLODefinitions:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list(self) -> PagedResponse[SLODefinition]:
        resp = self._http.get("/slo-definitions")
        _raise_for_status(resp)
        data = resp.json()
        return PagedResponse(
            items=[SLODefinition.model_validate(i) for i in data["items"]],
            total=data["total"],
        )

    def create(self, name: str, slo_yaml: str, **kwargs: Any) -> SLODefinition:
        body = {"name": name, "slo_yaml": slo_yaml, **kwargs}
        resp = self._http.post("/slo-definitions", json=body)
        _raise_for_status(resp)
        return SLODefinition.model_validate(resp.json())

    def get(self, name: str) -> SLODefinition:
        resp = self._http.get(f"/slo-definitions/{name}")
        _raise_for_status(resp)
        return SLODefinition.model_validate(resp.json())

    def versions(self, name: str) -> list[SLODefinition]:
        resp = self._http.get(f"/slo-definitions/{name}/versions")
        _raise_for_status(resp)
        return [SLODefinition.model_validate(v) for v in resp.json()]

    def delete(self, name: str) -> None:
        resp = self._http.delete(f"/slo-definitions/{name}")
        _raise_for_status(resp)

    def validate(self, slo_yaml: str) -> SLOValidationResult:
        resp = self._http.post("/slo-definitions/validate", json={"slo_yaml": slo_yaml})
        _raise_for_status(resp)
        return SLOValidationResult.model_validate(resp.json())

    def test(self, request: dict[str, Any]) -> SLOTestResult:
        resp = self._http.post("/slo-definitions/test", json=request)
        _raise_for_status(resp)
        return SLOTestResult.model_validate(resp.json())


class _Evaluations:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list(
        self,
        *,
        asset_name: str | None = None,
        slo_name: str | None = None,
        result: str | None = None,
        date: str | None = None,
        group_name: str | None = None,
        from_: str | None = None,
        to: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PagedResponse[EvaluationSummary]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if asset_name:
            params["asset_name"] = asset_name
        if slo_name:
            params["slo_name"] = slo_name
        if result:
            params["result"] = result
        if date:
            params["date"] = date
        if group_name:
            params["group_name"] = group_name
        if from_:
            params["from"] = from_
        if to:
            params["to"] = to
        resp = self._http.get("/evaluations", params=params)
        _raise_for_status(resp)
        data = resp.json()
        return PagedResponse(
            items=[EvaluationSummary.model_validate(i) for i in data["items"]],
            total=data["total"],
        )

    def get(self, eval_id: str) -> EvaluationDetail:
        resp = self._http.get(f"/evaluations/{eval_id}")
        _raise_for_status(resp)
        return EvaluationDetail.model_validate(resp.json())

    def invalidate(self, eval_id: str, note: str) -> EvaluationSummary:
        resp = self._http.patch(
            f"/evaluations/{eval_id}/invalidate",
            json={"invalidation_note": note},
        )
        _raise_for_status(resp)
        return EvaluationSummary.model_validate(resp.json())

    def restore(self, eval_id: str) -> EvaluationSummary:
        resp = self._http.patch(f"/evaluations/{eval_id}/restore")
        _raise_for_status(resp)
        return EvaluationSummary.model_validate(resp.json())


class _Annotations:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def list(self, eval_id: str) -> list[Annotation]:
        resp = self._http.get(f"/evaluations/{eval_id}/annotations")
        _raise_for_status(resp)
        return [Annotation.model_validate(a) for a in resp.json()]

    def create(self, eval_id: str, content: str, **kwargs: Any) -> Annotation:
        body = {"content": content, **kwargs}
        resp = self._http.post(f"/evaluations/{eval_id}/annotations", json=body)
        _raise_for_status(resp)
        return Annotation.model_validate(resp.json())

    def update(self, eval_id: str, ann_id: str, **kwargs: Any) -> Annotation:
        resp = self._http.patch(f"/evaluations/{eval_id}/annotations/{ann_id}", json=kwargs)
        _raise_for_status(resp)
        return Annotation.model_validate(resp.json())

    def delete(self, eval_id: str, ann_id: str) -> None:
        resp = self._http.delete(f"/evaluations/{eval_id}/annotations/{ann_id}")
        _raise_for_status(resp)


class _Trend:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def by_eval(self, eval_id: str, metric: str, limit: int = 50) -> list[TrendPoint]:
        resp = self._http.get(
            "/trend", params={"eval_id": eval_id, "metric": metric, "limit": limit}
        )
        _raise_for_status(resp)
        return [TrendPoint.model_validate(p) for p in resp.json()]

    def by_asset(
        self, asset_name: str, slo_name: str, metric: str, limit: int = 50
    ) -> list[TrendPoint]:
        resp = self._http.get(
            "/trend",
            params={
                "asset_name": asset_name,
                "slo_name": slo_name,
                "metric": metric,
                "limit": limit,
            },
        )
        _raise_for_status(resp)
        return [TrendPoint.model_validate(p) for p in resp.json()]


class TropekClient:
    """Typed Python client for the TROPEK API."""

    def __init__(self, base_url: str, *, api_key: str | None = None) -> None:
        self._http = httpx.Client(base_url=base_url, timeout=30.0)
        if api_key:
            self._http.headers["Authorization"] = f"Bearer {api_key}"
        self.asset_types = _AssetTypes(self._http)
        self.assets = _Assets(self._http)
        self.asset_groups = _AssetGroups(self._http)
        self.asset_slo_links = _SLOLinks(self._http, "assets", AssetSLOLink)
        self.group_slo_links = _SLOLinks(self._http, "asset-groups", AssetGroupSLOLink)
        self.datasources = _DataSources(self._http)
        self.sli_definitions = _SLIDefinitions(self._http)
        self.slo_definitions = _SLODefinitions(self._http)
        self.evaluations = _Evaluations(self._http)
        self.annotations = _Annotations(self._http)
        self.trend = _Trend(self._http)

    def health(self) -> dict[str, str]:
        """Check API health."""
        resp = self._http.get("/health")
        _raise_for_status(resp)
        return resp.json()

    def close(self) -> None:
        """Close the HTTP client."""
        self._http.close()

    def __enter__(self) -> TropekClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
```

- [ ] **Step 2: Write client tests**

```python
# clients/python/tests/test_client.py
from __future__ import annotations

import pytest
import httpx
from pytest_httpx import HTTPXMock

from tropek_client.client import TropekClient


def test_asset_types_list(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://test/asset-types",
        json=[{"id": "abc-123", "name": "vm", "is_default": True}],
    )
    with TropekClient("http://test") as client:
        types = client.asset_types.list()
    assert len(types) == 1
    assert types[0].name == "vm"


def test_not_found_raises(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://test/assets/missing",
        status_code=404,
        json={"detail": "asset 'missing' not found"},
    )
    with TropekClient("http://test") as client:
        from tropek_client.exceptions import TropekNotFoundError
        with pytest.raises(TropekNotFoundError):
            client.assets.get("missing")


def test_slo_validate(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://test/slo-definitions/validate",
        json={"valid": False, "errors": [{"field": "spec_version", "message": "missing"}]},
    )
    with TropekClient("http://test") as client:
        result = client.slo_definitions.validate("bad yaml")
    assert result.valid is False
    assert len(result.errors) == 1
```

- [ ] **Step 3: Run lint + tests**

```bash
uv run ruff check clients/python/tropek_client/client.py
uv run mypy clients/python/tropek_client/client.py
uv run pytest clients/python/tests/test_client.py -v
```

- [ ] **Step 4: Commit**

```bash
git add clients/python/tropek_client/client.py clients/python/tests/test_client.py
git commit -m "feat: add TropekClient with all resource classes"
```

---

### Task 5: Manifest Loader + Reconciler

**Files:**
- Create: `clients/python/tropek_client/manifest.py`
- Create: `clients/python/tests/test_manifest.py`

- [ ] **Step 1: Write failing tests for manifest loading**

```python
# clients/python/tests/test_manifest.py
from __future__ import annotations

from tropek_client.manifest import load_manifests, ManifestDocument


def test_load_single_document(tmp_path):
    f = tmp_path / "test.yaml"
    f.write_text("""
api_version: tropek/v1
kind: AssetType
metadata:
  name: vm
spec:
  is_default: true
""")
    docs = load_manifests(str(f))
    assert len(docs) == 1
    assert docs[0].kind == "AssetType"
    assert docs[0].metadata["name"] == "vm"
    assert docs[0].spec["is_default"] is True


def test_load_multi_document(tmp_path):
    f = tmp_path / "test.yaml"
    f.write_text("""
api_version: tropek/v1
kind: AssetType
metadata:
  name: vm
spec:
  is_default: true
---
api_version: tropek/v1
kind: Asset
metadata:
  name: vm-01
spec:
  type_name: vm
""")
    docs = load_manifests(str(f))
    assert len(docs) == 2
    assert docs[0].kind == "AssetType"
    assert docs[1].kind == "Asset"


def test_load_directory(tmp_path):
    (tmp_path / "a.yaml").write_text("""
api_version: tropek/v1
kind: AssetType
metadata:
  name: vm
spec:
  is_default: true
""")
    (tmp_path / "b.yaml").write_text("""
api_version: tropek/v1
kind: Asset
metadata:
  name: vm-01
spec:
  type_name: vm
""")
    docs = load_manifests(str(tmp_path))
    assert len(docs) == 2


def test_topological_sort(tmp_path):
    f = tmp_path / "test.yaml"
    f.write_text("""
api_version: tropek/v1
kind: Asset
metadata:
  name: vm-01
spec:
  type_name: vm
---
api_version: tropek/v1
kind: AssetType
metadata:
  name: vm
spec:
  is_default: true
""")
    docs = load_manifests(str(f))
    kinds = [d.kind for d in docs]
    assert kinds.index("AssetType") < kinds.index("Asset")


def test_rejects_missing_api_version(tmp_path):
    f = tmp_path / "test.yaml"
    f.write_text("""
kind: AssetType
metadata:
  name: vm
spec:
  is_default: true
""")
    import pytest
    with pytest.raises(ValueError, match="api_version"):
        load_manifests(str(f))


def test_validate_cross_references(tmp_path):
    """Cross-reference warnings are returned for missing refs within manifest."""
    f = tmp_path / "test.yaml"
    f.write_text("""
api_version: tropek/v1
kind: AssetSLOLink
metadata:
  link_name: my-link
spec:
  asset_name: vm-01
  slo_name: missing-slo
  sli_name: missing-sli
  data_source_name: missing-ds
""")
    errors = validate_manifests(str(f))
    assert len(errors) == 3
    assert all("WARNING" in e for e in errors)


def test_dry_run_creates_plan():
    """dry_run produces CREATE actions for missing entities."""
    from unittest.mock import MagicMock
    from tropek_client.manifest import dry_run, ManifestDocument
    from tropek_client.exceptions import TropekNotFoundError

    client = MagicMock()
    client.asset_types.list.return_value = []  # no existing types

    docs = [
        ManifestDocument(
            api_version="tropek/v1",
            kind="AssetType",
            metadata={"name": "vm"},
            spec={"is_default": True},
        )
    ]
    plan = dry_run(client, docs)
    assert len(plan.actions) == 1
    assert plan.actions[0].operation == "CREATE"
    assert plan.actions[0].name == "vm"


def test_apply_creates_entity():
    """apply calls create on the client for CREATE actions."""
    from unittest.mock import MagicMock
    from tropek_client.manifest import apply as do_apply, ManifestDocument

    client = MagicMock()
    client.asset_types.list.return_value = []  # triggers CREATE

    docs = [
        ManifestDocument(
            api_version="tropek/v1",
            kind="AssetType",
            metadata={"name": "vm"},
            spec={"is_default": True},
        )
    ]
    result = do_apply(client, docs)
    assert result.created == 1
    assert result.failed == 0
    client.asset_types.create.assert_called_once_with("vm", is_default=True)
```

- [ ] **Step 2: Create manifest module**

```python
# clients/python/tropek_client/manifest.py
"""YAML manifest loader and desired-state reconciler."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# Processing order — dependencies must come first
_KIND_ORDER = [
    "AssetType",
    "DataSource",
    "Asset",
    "SLI",
    "SLO",
    "AssetGroup",
    "AssetSLOLink",
    "AssetGroupSLOLink",
]


@dataclass
class ManifestDocument:
    """A single parsed manifest document."""

    api_version: str
    kind: str
    metadata: dict[str, Any]
    spec: dict[str, Any]


@dataclass
class PlanAction:
    """A single action in a reconciliation plan."""

    operation: str  # CREATE | UPDATE | SKIP
    kind: str
    name: str
    reason: str


@dataclass
class ApplyPlan:
    """Result of dry_run — list of planned actions."""

    actions: list[PlanAction] = field(default_factory=list)


@dataclass
class ApplyError:
    """A single error during apply."""

    kind: str
    name: str
    error: str


@dataclass
class ApplyResult:
    """Result of apply — counts and errors."""

    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[ApplyError] = field(default_factory=list)


def load_manifests(path: str) -> list[ManifestDocument]:
    """Load and topologically sort manifests from a file or directory."""
    p = Path(path)
    raw_docs: list[dict[str, Any]] = []

    if p.is_dir():
        for f in sorted(p.glob("*.yaml")):
            raw_docs.extend(_load_file(f))
        for f in sorted(p.glob("*.yml")):
            raw_docs.extend(_load_file(f))
    else:
        raw_docs.extend(_load_file(p))

    docs = [_parse_document(d) for d in raw_docs]
    return _topological_sort(docs)


def _load_file(path: Path) -> list[dict[str, Any]]:
    """Load all YAML documents from a single file."""
    text = path.read_text(encoding="utf-8")
    docs = []
    for doc in yaml.safe_load_all(text):
        if doc:
            docs.append(doc)
    return docs


def _parse_document(raw: dict[str, Any]) -> ManifestDocument:
    """Validate and parse a raw YAML document into a ManifestDocument."""
    if "api_version" not in raw:
        raise ValueError(f"manifest document missing required field: api_version")
    if "kind" not in raw:
        raise ValueError(f"manifest document missing required field: kind")
    if "metadata" not in raw:
        raise ValueError(f"manifest document missing required field: metadata")
    if raw["kind"] not in _KIND_ORDER:
        raise ValueError(f"unknown kind: {raw['kind']}. valid: {_KIND_ORDER}")

    return ManifestDocument(
        api_version=raw["api_version"],
        kind=raw["kind"],
        metadata=raw["metadata"],
        spec=raw.get("spec", {}),
    )


def _topological_sort(docs: list[ManifestDocument]) -> list[ManifestDocument]:
    """Sort documents by kind dependency order, preserving file order within a kind."""

    def sort_key(doc: ManifestDocument) -> int:
        try:
            return _KIND_ORDER.index(doc.kind)
        except ValueError:
            return len(_KIND_ORDER)

    return sorted(docs, key=sort_key)


def validate_manifests(path: str) -> list[str]:
    """Validate manifest files without making API calls. Returns list of errors."""
    errors: list[str] = []
    try:
        docs = load_manifests(path)
    except ValueError as e:
        errors.append(str(e))
        return errors

    # Cross-reference validation (warnings, not errors — refs may exist in API)
    names_by_kind: dict[str, set[str]] = {}
    for doc in docs:
        names_by_kind.setdefault(doc.kind, set()).add(doc.metadata["name"])

    for doc in docs:
        if doc.kind == "Asset":
            type_name = doc.spec.get("type_name")
            if type_name and type_name not in names_by_kind.get("AssetType", set()):
                errors.append(
                    f"WARNING: Asset '{doc.metadata['name']}' references AssetType "
                    f"'{type_name}' not found in manifest (may exist in API)"
                )
        elif doc.kind in ("AssetSLOLink", "AssetGroupSLOLink"):
            for ref_field, ref_kind in [
                ("slo_name", "SLO"), ("sli_name", "SLI"), ("data_source_name", "DataSource"),
            ]:
                ref_val = doc.spec.get(ref_field)
                if ref_val and ref_val not in names_by_kind.get(ref_kind, set()):
                    errors.append(
                        f"WARNING: {doc.kind} '{doc.metadata['name']}' references {ref_kind} "
                        f"'{ref_val}' not found in manifest (may exist in API)"
                    )

    return errors


def dry_run(client: Any, manifests: list[ManifestDocument]) -> ApplyPlan:
    """Compare manifests against API state and return planned actions."""
    plan = ApplyPlan()
    for doc in manifests:
        name = doc.metadata.get("name", "unknown")
        try:
            existing = _lookup(client, doc)
            if existing is None:
                plan.actions.append(
                    PlanAction("CREATE", doc.kind, name, "not found in current state")
                )
            elif _has_diff(doc, existing):
                reason = _diff_reason(doc, existing)
                plan.actions.append(PlanAction("UPDATE", doc.kind, name, reason))
            else:
                plan.actions.append(
                    PlanAction("SKIP", doc.kind, name, "already exists, no changes")
                )
        except Exception as e:
            plan.actions.append(PlanAction("CREATE", doc.kind, name, f"lookup failed: {e}"))
    return plan


def apply(client: Any, manifests: list[ManifestDocument]) -> ApplyResult:
    """Apply manifests using desired-state reconciliation."""
    plan = dry_run(client, manifests)
    result = ApplyResult()
    blocked_kinds: set[str] = set()

    for action, doc in zip(plan.actions, manifests):
        name = doc.metadata.get("name", "unknown")
        if action.operation == "SKIP":
            result.skipped += 1
            continue
        if doc.kind in blocked_kinds:
            result.failed += 1
            result.errors.append(ApplyError(doc.kind, name, "blocked by prior error"))
            continue
        try:
            if action.operation == "CREATE":
                _create(client, doc)
                result.created += 1
            elif action.operation == "UPDATE":
                _update(client, doc)
                result.updated += 1
        except Exception as e:
            result.failed += 1
            result.errors.append(ApplyError(doc.kind, name, str(e)))
            # Block only kinds that depend on the failed kind
            for dep_kind in _dependents_of(doc.kind):
                blocked_kinds.add(dep_kind)

    return result


_KIND_DEPS: dict[str, set[str]] = {
    "AssetType": {"Asset"},
    "DataSource": {"AssetSLOLink", "AssetGroupSLOLink"},
    "Asset": {"AssetGroup", "AssetSLOLink"},
    "SLI": {"AssetSLOLink", "AssetGroupSLOLink"},
    "SLO": {"AssetSLOLink", "AssetGroupSLOLink"},
    "AssetGroup": {"AssetGroupSLOLink"},
}


def _dependents_of(kind: str) -> set[str]:
    """Return the set of kinds that depend on the given kind (transitively)."""
    result: set[str] = set()
    stack = [kind]
    while stack:
        k = stack.pop()
        for dep in _KIND_DEPS.get(k, set()):
            if dep not in result:
                result.add(dep)
                stack.append(dep)
    return result


def _lookup(client: Any, doc: ManifestDocument) -> Any | None:
    """Look up an existing entity by name via the client."""
    name = doc.metadata["name"]
    try:
        match doc.kind:
            case "AssetType":
                types = client.asset_types.list()
                return next((t for t in types if t.name == name), None)
            case "Asset":
                return client.assets.get(name)
            case "AssetGroup":
                return client.asset_groups.get(name)
            case "DataSource":
                return client.datasources.get(name)
            case "SLI":
                return client.sli_definitions.get(name)
            case "SLO":
                return client.slo_definitions.get(name)
            case "AssetSLOLink":
                asset_name = doc.spec.get("asset_name", "")
                links = client.asset_slo_links.list(asset_name)
                return next((l for l in links if l.link_name == name), None)
            case "AssetGroupSLOLink":
                group_name = doc.spec.get("group_name", "")
                links = client.group_slo_links.list(group_name)
                return next((l for l in links if l.link_name == name), None)
            case _:
                return None
    except Exception:
        return None


def _has_diff(doc: ManifestDocument, existing: Any) -> bool:
    """Check if the manifest differs from the existing entity."""
    match doc.kind:
        case "AssetType":
            return doc.spec.get("is_default") != getattr(existing, "is_default", None)
        case "Asset":
            return (
                doc.metadata.get("display_name") != getattr(existing, "display_name", None)
                or doc.metadata.get("labels", {}) != getattr(existing, "labels", {})
            )
        case "AssetGroup":
            # Groups are complex — always update to sync members/subgroups
            return True
        case "DataSource":
            return (
                doc.metadata.get("display_name") != getattr(existing, "display_name", None)
                or doc.spec.get("adapter_url") != getattr(existing, "adapter_url", None)
                or doc.metadata.get("labels", {}) != getattr(existing, "labels", {})
            )
        case "SLI":
            return doc.spec.get("indicators") != getattr(existing, "indicators", {})
        case "SLO":
            return doc.spec.get("slo_yaml") != getattr(existing, "slo_yaml", "")
        case "AssetSLOLink" | "AssetGroupSLOLink":
            return (
                doc.spec.get("slo_name") != getattr(existing, "slo_name", None)
                or doc.spec.get("sli_name") != getattr(existing, "sli_name", None)
                or doc.spec.get("data_source_name") != getattr(existing, "data_source_name", None)
            )
        case _:
            return False


def _diff_reason(doc: ManifestDocument, existing: Any) -> str:
    """Generate a human-readable diff reason."""
    match doc.kind:
        case "SLI":
            return "indicators differ (new version will be created)"
        case "SLO":
            return "slo_yaml differs (new version will be created)"
        case _:
            return "fields differ"


def _create(client: Any, doc: ManifestDocument) -> None:
    """Create a new entity via the client."""
    name = doc.metadata["name"]
    match doc.kind:
        case "AssetType":
            client.asset_types.create(name, is_default=doc.spec.get("is_default", False))
        case "Asset":
            client.assets.create(
                name,
                type_name=doc.spec.get("type_name", "vm"),
                display_name=doc.metadata.get("display_name"),
                labels=doc.metadata.get("labels"),
            )
        case "AssetGroup":
            client.asset_groups.create(name)
        case "DataSource":
            client.datasources.create(
                name,
                adapter_type=doc.spec["adapter_type"],
                adapter_url=doc.spec["adapter_url"],
                display_name=doc.metadata.get("display_name"),
                labels=doc.metadata.get("labels"),
            )
        case "SLI":
            client.sli_definitions.create(
                name,
                indicators=doc.spec["indicators"],
                display_name=doc.metadata.get("display_name"),
                notes=doc.metadata.get("notes"),
                author=doc.metadata.get("author"),
            )
        case "SLO":
            client.slo_definitions.create(
                name,
                slo_yaml=doc.spec["slo_yaml"],
                display_name=doc.metadata.get("display_name"),
                notes=doc.metadata.get("notes"),
                author=doc.metadata.get("author"),
            )
        case "AssetSLOLink":
            asset_name = doc.spec["asset_name"]
            client.asset_slo_links.create(
                asset_name, name,
                doc.spec["slo_name"], doc.spec["sli_name"], doc.spec["data_source_name"],
            )
        case "AssetGroupSLOLink":
            group_name = doc.spec["group_name"]
            client.group_slo_links.create(
                group_name, name,
                doc.spec["slo_name"], doc.spec["sli_name"], doc.spec["data_source_name"],
            )


def _update(client: Any, doc: ManifestDocument) -> None:
    """Update an existing entity via the client."""
    name = doc.metadata["name"]
    match doc.kind:
        case "AssetType":
            client.asset_types.set_default(name) if doc.spec.get("is_default") else None
        case "Asset":
            client.assets.update(
                name,
                display_name=doc.metadata.get("display_name"),
                labels=doc.metadata.get("labels"),
            )
        case "AssetGroup":
            # TODO: sync members/subgroups — requires add/remove member API calls
            # For v1, log that group exists but member sync is not yet implemented
            pass
        case "DataSource":
            client.datasources.update(
                name,
                display_name=doc.metadata.get("display_name"),
                adapter_url=doc.spec.get("adapter_url"),
                labels=doc.metadata.get("labels"),
            )
        case "SLI":
            # Creates new version
            client.sli_definitions.create(
                name,
                indicators=doc.spec["indicators"],
                display_name=doc.metadata.get("display_name"),
                notes=doc.metadata.get("notes"),
                author=doc.metadata.get("author"),
            )
        case "SLO":
            # Creates new version
            client.slo_definitions.create(
                name,
                slo_yaml=doc.spec["slo_yaml"],
                display_name=doc.metadata.get("display_name"),
                notes=doc.metadata.get("notes"),
                author=doc.metadata.get("author"),
            )
        case "AssetSLOLink":
            # Delete + recreate
            asset_name = doc.spec["asset_name"]
            client.asset_slo_links.delete(asset_name, name)
            client.asset_slo_links.create(
                asset_name, name,
                doc.spec["slo_name"], doc.spec["sli_name"], doc.spec["data_source_name"],
            )
        case "AssetGroupSLOLink":
            # Delete + recreate
            group_name = doc.spec["group_name"]
            client.group_slo_links.delete(group_name, name)
            client.group_slo_links.create(
                group_name, name,
                doc.spec["slo_name"], doc.spec["sli_name"], doc.spec["data_source_name"],
            )
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest clients/python/tests/test_manifest.py -v
```

- [ ] **Step 4: Commit**

```bash
git add clients/python/tropek_client/manifest.py clients/python/tests/test_manifest.py
git commit -m "feat: add manifest loader and desired-state reconciler"
```

---

### Task 6: CLI

**Files:**
- Create: `clients/python/tropek_client/cli.py`
- Create: `clients/python/tests/test_cli.py`

- [ ] **Step 1: Write failing CLI test**

```python
# clients/python/tests/test_cli.py
from __future__ import annotations

from click.testing import CliRunner

from tropek_client.cli import cli


def test_validate_valid_manifest(tmp_path):
    f = tmp_path / "test.yaml"
    f.write_text("""
api_version: tropek/v1
kind: AssetType
metadata:
  name: vm
spec:
  is_default: true
""")
    runner = CliRunner()
    result = runner.invoke(cli, ["validate", "-f", str(f)])
    assert result.exit_code == 0
    assert "valid" in result.output.lower()


def test_validate_invalid_manifest(tmp_path):
    f = tmp_path / "test.yaml"
    f.write_text("""
kind: AssetType
metadata:
  name: vm
""")
    runner = CliRunner()
    result = runner.invoke(cli, ["validate", "-f", str(f)])
    assert result.exit_code != 0


def test_apply_dry_run(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    from tropek_client.manifest import ApplyPlan, PlanAction

    f = tmp_path / "test.yaml"
    f.write_text("""
api_version: tropek/v1
kind: AssetType
metadata:
  name: vm
spec:
  is_default: true
""")
    mock_client = MagicMock()
    mock_plan = ApplyPlan(actions=[
        PlanAction("CREATE", "AssetType", "vm", "not found in current state"),
    ])

    import tropek_client.cli as cli_mod
    monkeypatch.setattr(cli_mod, "TropekClient", lambda **kw: mock_client)

    from tropek_client.manifest import dry_run as orig_dry_run
    monkeypatch.setattr(
        "tropek_client.manifest.dry_run", lambda c, d: mock_plan
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["apply", "--dry-run", "-f", str(f)])
    assert result.exit_code == 0
    assert "CREATE" in result.output
    assert "AssetType/vm" in result.output
```

- [ ] **Step 2: Create CLI**

```python
# clients/python/tropek_client/cli.py
"""CLI entrypoint for tropek client."""

from __future__ import annotations

import sys

import click

from tropek_client.manifest import load_manifests, validate_manifests


@click.group()
def cli() -> None:
    """TROPEK client CLI."""


@cli.command()
@click.option("-f", "--file", "path", required=True, help="YAML file or directory")
def validate(path: str) -> None:
    """Validate manifest syntax without making API calls."""
    errors = validate_manifests(path)
    if errors:
        for e in errors:
            click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)
    docs = load_manifests(path)
    click.echo(f"Valid: {len(docs)} document(s)")


@cli.command()
@click.option("-f", "--file", "path", required=True, help="YAML file or directory")
@click.option("--base-url", default="http://localhost:8080", help="TROPEK API URL")
@click.option("--dry-run", is_flag=True, help="Show what would change without applying")
@click.option("--api-key", default=None, help="API key for authentication")
def apply(path: str, base_url: str, dry_run: bool, api_key: str | None) -> None:
    """Apply manifests to a TROPEK instance."""
    from tropek_client.client import TropekClient
    from tropek_client.manifest import apply as do_apply
    from tropek_client.manifest import dry_run as do_dry_run

    docs = load_manifests(path)
    client = TropekClient(base_url=base_url, api_key=api_key)

    if dry_run:
        plan = do_dry_run(client, docs)
        for action in plan.actions:
            click.echo(f"{action.operation:6s}  {action.kind}/{action.name}  {action.reason}")
        return

    result = do_apply(client, docs)
    click.echo(
        f"{result.created} created, {result.updated} updated, "
        f"{result.skipped} skipped, {result.failed} failed"
    )
    if result.errors:
        for err in result.errors:
            click.echo(f"  ERROR: {err.kind}/{err.name}: {err.error}", err=True)
        sys.exit(1)
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest clients/python/tests/test_cli.py -v
```

- [ ] **Step 4: Run full SDK test suite + lint**

```bash
uv run pytest clients/python/tests/ -v
uv run ruff check clients/python/
uv run mypy clients/python/tropek_client/
```

- [ ] **Step 5: Commit**

```bash
git add clients/python/tropek_client/cli.py clients/python/tests/test_cli.py
git commit -m "feat: add tropek CLI with validate and apply commands"
```
