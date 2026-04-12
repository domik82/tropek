# Stream B: SLO Validate + Test Endpoints

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Read first:** `docs/superpowers/plans/2026-03-15-api-ui-alignment-overview.md`

**Goal:** Add `POST /slo-definitions/validate` and `POST /slo-definitions/test` endpoints.

**Architecture:** Both endpoints live in the `slo_registry` module. Validate is a pure-function
wrapper around the existing engine parser. Test is a multi-step orchestrator that queries an
adapter, evaluates metrics, and returns results without persisting anything.

**Tech Stack:** Python 3.13, FastAPI, httpx (adapter calls), existing evaluation engine

**Spec:** `docs/superpowers/specs/2026-03-15-api-ui-alignment-design.md` §4–5

---

## File Structure

| Action | File | Responsibility |
|---|---|---|
| Modify | `api/app/modules/slo_registry/router.py` | Add validate + test endpoints (before `/{name}` route) |
| Modify | `api/app/modules/slo_registry/schemas.py` | Request/response models for validate + test |
| Create | `api/tests/test_slo_validate.py` | Unit tests for validation endpoint logic |
| Create | `api/tests/test_slo_test_endpoint.py` | Unit tests for test endpoint logic |

---

### Task 1: Validate Schemas

**Files:**
- Modify: `api/app/modules/slo_registry/schemas.py`

- [ ] **Step 1: Add validation request/response schemas**

Append to `api/app/modules/slo_registry/schemas.py`:

```python
class SLOValidateRequest(BaseModel):
    """Request body for SLO YAML validation."""

    slo_yaml: str


class SLOValidationError(BaseModel):
    """A single validation error."""

    field: str
    message: str


class SLOValidationResult(BaseModel):
    """Response from SLO validation endpoint."""

    valid: bool
    errors: list[SLOValidationError]
    objectives: list[dict[str, Any]] | None = None
```

- [ ] **Step 2: Lint**

```bash
uv run ruff check api/app/modules/slo_registry/schemas.py
```

- [ ] **Step 3: Commit**

```bash
git add api/app/modules/slo_registry/schemas.py
git commit -m "feat: add SLO validation request/response schemas"
```

---

### Task 2: Validate Endpoint — Tests

**Files:**
- Create: `api/tests/test_slo_validate.py`

- [ ] **Step 1: Write tests for validation logic**

```python
# api/tests/test_slo_validate.py
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_validate_valid_slo(client, slo_data):
    resp = client.post(
        "/slo-definitions/validate",
        json={"slo_yaml": slo_data("minimal.yaml")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["errors"] == []
    assert body["objectives"] is not None
    assert len(body["objectives"]) > 0


def test_validate_invalid_yaml_syntax(client):
    resp = client.post(
        "/slo-definitions/validate",
        json={"slo_yaml": "{{invalid: yaml: ["},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert len(body["errors"]) > 0
    assert body["objectives"] is None


def test_validate_missing_spec_version(client):
    resp = client.post(
        "/slo-definitions/validate",
        json={"slo_yaml": "objectives:\n  - sli: cpu\n"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert any("spec_version" in e["message"] for e in body["errors"])


def test_validate_invalid_criteria_string(client):
    yaml_text = """spec_version: "1.0"
indicators:
  cpu: "query"
objectives:
  - sli: cpu
    pass:
      - criteria: [">>5"]
"""
    resp = client.post(
        "/slo-definitions/validate",
        json={"slo_yaml": yaml_text},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert len(body["errors"]) > 0


def test_validate_empty_body(client):
    resp = client.post(
        "/slo-definitions/validate",
        json={"slo_yaml": ""},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
```

- [ ] **Step 2: Run — expect failures (endpoint doesn't exist yet)**

```bash
uv run pytest api/tests/test_slo_validate.py -v -m "not integration"
```

- [ ] **Step 3: Commit**

```bash
git add api/tests/test_slo_validate.py
git commit -m "test: add failing tests for POST /slo-definitions/validate"
```

---

### Task 3: Validate Endpoint — Implementation

**Files:**
- Modify: `api/app/modules/slo_registry/router.py`

- [ ] **Step 1: Add validate endpoint BEFORE the `/{name}` GET route**

This is critical — FastAPI matches routes top-down, so `/validate` must come before `/{name}`
to prevent "validate" being interpreted as a name path parameter.

Add imports at the top of `router.py`:

```python
from app.modules.quality_gate.engine.criteria import parse_criteria_string
from app.modules.quality_gate.engine.slo_parser import parse_slo
from app.modules.quality_gate.engine.slo_models import SLOParseError
from app.modules.slo_registry.schemas import (
    SLODefinitionCreate,
    SLODefinitionRead,
    SLOValidateRequest,
    SLOValidationError as SLOValError,
    SLOValidationResult,
)
```

Add endpoint after `create_slo_definition` and before `get_slo_definition`:

```python
@router.post("/slo-definitions/validate", response_model=SLOValidationResult)
async def validate_slo(body: SLOValidateRequest) -> SLOValidationResult:
    """Validate SLO YAML structure without saving."""
    errors: list[SLOValError] = []

    if not body.slo_yaml or not body.slo_yaml.strip():
        return SLOValidationResult(
            valid=False,
            errors=[SLOValError(field="slo_yaml", message="empty slo yaml")],
        )

    try:
        slo = parse_slo(body.slo_yaml)
    except SLOParseError as e:
        return SLOValidationResult(
            valid=False,
            errors=[SLOValError(field="slo_yaml", message=str(e))],
        )
    except Exception as e:
        return SLOValidationResult(
            valid=False,
            errors=[SLOValError(field="slo_yaml", message=f"parse error: {e}")],
        )

    # Validate all criteria strings
    for i, obj in enumerate(slo.objectives):
        for block in obj.pass_threshold:
            for raw in block.criteria:
                try:
                    parse_criteria_string(raw)
                except ValueError as e:
                    errors.append(
                        SLOValError(
                            field=f"objectives[{i}].pass.criteria",
                            message=str(e),
                        )
                    )
        for block in obj.warning_threshold:
            for raw in block.criteria:
                try:
                    parse_criteria_string(raw)
                except ValueError as e:
                    errors.append(
                        SLOValError(
                            field=f"objectives[{i}].warning.criteria",
                            message=str(e),
                        )
                    )

    # Validate total_score percentages
    if not (0 <= slo.total_score.pass_threshold <= 100):
        errors.append(
            SLOValError(field="total_score.pass", message="must be 0-100")
        )
    if not (0 <= slo.total_score.warning_threshold <= 100):
        errors.append(
            SLOValError(field="total_score.warning", message="must be 0-100")
        )

    if errors:
        return SLOValidationResult(valid=False, errors=errors)

    objectives_dicts = [obj.model_dump() for obj in slo.objectives]
    return SLOValidationResult(valid=True, errors=[], objectives=objectives_dicts)
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest api/tests/test_slo_validate.py -v -m "not integration"
```

Expected: All tests pass.

- [ ] **Step 3: Run full suite + lint**

```bash
uv run pytest api/tests/ -m "not integration" -q
uv run ruff check api/app/modules/slo_registry/
uv run mypy api/app/modules/slo_registry/
```

- [ ] **Step 4: Commit**

```bash
git add api/app/modules/slo_registry/router.py
git commit -m "feat: add POST /slo-definitions/validate endpoint"
```

---

### Task 4: Test Endpoint Schemas

**Files:**
- Modify: `api/app/modules/slo_registry/schemas.py`

- [ ] **Step 1: Add test endpoint request/response schemas**

Append to `api/app/modules/slo_registry/schemas.py`:

```python
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.modules.quality_gate.schemas import IndicatorResult


class BaselineConfig(BaseModel):
    """Configuration for baseline comparison in SLO test."""

    mode: Literal["none", "asset_history", "manual"] = "none"
    limit: int = 3
    values: dict[str, float] | None = None


class SLOTestRequest(BaseModel):
    """Request body for SLO test (dry-run evaluation)."""

    slo_yaml: str
    sli_name: str
    data_source_name: str
    asset_name: str
    period_start: datetime
    period_end: datetime
    baseline: BaselineConfig | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class SLOTestResult(BaseModel):
    """Response from SLO test endpoint."""

    result: str
    score: float
    indicator_results: list[IndicatorResult]
    baseline_mode: str
    metrics_fetched: dict[str, float]
    fetch_errors: dict[str, str]
    compared_values: dict[str, float] | None
```

- [ ] **Step 2: Lint**

```bash
uv run ruff check api/app/modules/slo_registry/schemas.py
```

- [ ] **Step 3: Commit**

```bash
git add api/app/modules/slo_registry/schemas.py
git commit -m "feat: add SLO test request/response schemas"
```

---

### Task 5: Test Endpoint — Tests

**Files:**
- Create: `api/tests/test_slo_test_endpoint.py`

- [ ] **Step 1: Write tests for test endpoint validation**

The test endpoint requires DB lookups (SLI, DataSource, Asset) and HTTP calls (adapter).
For unit tests, focus on request validation only. The `get_session` dependency must be
overridden with a mock to prevent DB connection errors. Integration tests will cover the
full flow later.

```python
# api/tests/test_slo_test_endpoint.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app


@pytest.fixture
def client():
    """TestClient with mocked DB session for unit tests."""
    mock_session = AsyncMock()
    # Repository lookups return None (not found) by default
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    async def _mock_session():
        yield mock_session

    app.dependency_overrides[get_session] = _mock_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_slo_test_rejects_invalid_yaml(client):
    resp = client.post(
        "/slo-definitions/test",
        json={
            "slo_yaml": "{{invalid",
            "sli_name": "my-sli",
            "data_source_name": "prometheus",
            "asset_name": "vm-01",
            "period_start": "2026-03-01T00:00:00Z",
            "period_end": "2026-03-01T01:00:00Z",
        },
    )
    assert resp.status_code == 422
    assert "yaml" in resp.json()["detail"].lower() or "parse" in resp.json()["detail"].lower()


def test_slo_test_rejects_missing_required_fields(client):
    resp = client.post(
        "/slo-definitions/test",
        json={"slo_yaml": "spec_version: '1.0'"},
    )
    assert resp.status_code == 422


def test_slo_test_accepts_valid_request_shape(client):
    """Valid shape should not get 422 for request validation.

    It will likely get 404 for missing SLI/asset/datasource since there's no DB,
    but the request shape itself should be accepted.
    """
    resp = client.post(
        "/slo-definitions/test",
        json={
            "slo_yaml": "spec_version: '1.0'\nindicators:\n  cpu: query\nobjectives:\n  - sli: cpu\n    pass:\n      - criteria: ['<100']\ntotal_score:\n  pass: '90%'\n  warning: '75%'",
            "sli_name": "nonexistent-sli",
            "data_source_name": "nonexistent-ds",
            "asset_name": "nonexistent-asset",
            "period_start": "2026-03-01T00:00:00Z",
            "period_end": "2026-03-01T01:00:00Z",
        },
    )
    # Should be 404 (entity not found) not 422 (bad request shape)
    assert resp.status_code in (404, 502)
```

- [ ] **Step 2: Run — expect failures**

```bash
uv run pytest api/tests/test_slo_test_endpoint.py -v -m "not integration"
```

- [ ] **Step 3: Commit**

```bash
git add api/tests/test_slo_test_endpoint.py
git commit -m "test: add failing tests for POST /slo-definitions/test"
```

---

### Task 6: Test Endpoint — Implementation

**Files:**
- Modify: `api/app/modules/slo_registry/router.py`

- [ ] **Step 1: Add the test endpoint after validate**

Add imports:

```python
import httpx
from fastapi import HTTPException

from app.modules.assets.repository import AssetRepository
from app.modules.datasource.repository import DataSourceRepository
from app.modules.quality_gate.engine.evaluator import evaluate
from app.modules.quality_gate.engine.variables import build_variables, substitute_variables
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.quality_gate.schemas import IndicatorResult
from app.modules.sli_registry.repository import SLIRepository
from app.modules.slo_registry.schemas import (
    ...,
    SLOTestRequest,
    SLOTestResult,
    BaselineConfig,
)
```

Add endpoint (after `/validate`, before `/{name}`):

```python
@router.post("/slo-definitions/test", response_model=SLOTestResult)
async def test_slo(
    body: SLOTestRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> SLOTestResult:
    """Dry-run SLO evaluation — fetch metrics, evaluate, return result without persisting."""
    # 1. Validate SLO YAML
    try:
        slo = parse_slo(body.slo_yaml)
    except SLOParseError as e:
        raise HTTPException(status_code=422, detail=f"invalid slo yaml: {e}") from e

    # 2. Resolve SLI definition
    sli_repo = SLIRepository(session)
    sli_def = await sli_repo.get_latest(body.sli_name)
    if sli_def is None:
        raise_not_found("sli definition", body.sli_name)

    # 3. Resolve data source
    ds_repo = DataSourceRepository(session)
    ds = await ds_repo.get_by_name(body.data_source_name)
    if ds is None:
        raise_not_found("data source", body.data_source_name)

    # 4. Resolve asset
    asset_repo = AssetRepository(session)
    asset = await asset_repo.get_by_name(body.asset_name)
    if asset is None:
        raise_not_found("asset", body.asset_name)

    # 5. Build variables and substitute in SLI queries
    asset_labels = getattr(asset, "labels", {}) or {}
    variables = build_variables(
        metadata={**asset_labels, **body.metadata},
        asset_name=asset.name,
        start=body.period_start.isoformat(),
        end=body.period_end.isoformat(),
    )

    resolved_queries: dict[str, str] = {}
    for indicator_name, query_template in sli_def.indicators.items():
        try:
            resolved_queries[indicator_name] = substitute_variables(query_template, variables)
        except Exception as e:
            resolved_queries[indicator_name] = f"ERROR: {e}"

    # 6. Query adapter
    metrics_fetched: dict[str, float] = {}
    fetch_errors: dict[str, str] = {}

    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            adapter_resp = await http_client.post(
                f"{ds.adapter_url}/query",
                json={
                    "queries": resolved_queries,
                    "start": body.period_start.isoformat(),
                    "end": body.period_end.isoformat(),
                },
            )
            adapter_resp.raise_for_status()
            adapter_data = adapter_resp.json()
            for name, val in adapter_data.get("values", {}).items():
                if val is not None:
                    metrics_fetched[name] = float(val)
            for name, err in adapter_data.get("errors", {}).items():
                fetch_errors[name] = str(err)
    except httpx.ConnectError as e:
        raise HTTPException(
            status_code=502,
            detail=f"could not reach adapter at {ds.adapter_url}",
        ) from e
    except httpx.TimeoutException as e:
        raise HTTPException(
            status_code=504,
            detail=f"adapter query timed out after 30s",
        ) from e
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"adapter returned {e.response.status_code}",
        ) from e

    # 7. Resolve baselines
    baseline_cfg = body.baseline or BaselineConfig()
    baselines: dict[str, float | None] = {}
    compared_values: dict[str, float] | None = None

    if baseline_cfg.mode == "manual" and baseline_cfg.values:
        baselines = {k: v for k, v in baseline_cfg.values.items()}
        compared_values = dict(baseline_cfg.values)
    elif baseline_cfg.mode == "asset_history":
        eval_repo = EvaluationRepository(session)
        past_evals = await eval_repo.get_baselines(
            name=asset.name,
            scope_tags=slo.comparison.scope_tags,
            asset_snapshot={"tags": asset_labels},
            include_result_with_score=slo.comparison.include_result_with_score.value,
            limit=baseline_cfg.limit,
            sli_name=body.sli_name,
        )
        if past_evals:
            from app.modules.quality_gate.engine.criteria import aggregate_values

            compared_values = {}
            for indicator_name in sli_def.indicators:
                vals = []
                for ev in past_evals:
                    for ind in ev.indicator_results or []:
                        if ind.get("metric") == indicator_name and ind.get("value") is not None:
                            vals.append(float(ind["value"]))
                if vals:
                    agg = aggregate_values(vals, slo.comparison.aggregate_function)
                    baselines[indicator_name] = agg
                    compared_values[indicator_name] = agg
    # mode == "none": baselines stays empty — relative criteria get status "info"

    # 8. Evaluate
    eval_result = evaluate(
        body.slo_yaml,
        {k: v for k, v in metrics_fetched.items()},
        {k: v for k, v in baselines.items() if v is not None},
    )

    indicator_results_typed = [
        IndicatorResult(**ind) for ind in eval_result.indicator_results
    ]

    return SLOTestResult(
        result=eval_result.result,
        score=eval_result.score,
        indicator_results=indicator_results_typed,
        baseline_mode=baseline_cfg.mode,
        metrics_fetched=metrics_fetched,
        fetch_errors=fetch_errors,
        compared_values=compared_values,
    )
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest api/tests/test_slo_test_endpoint.py -v -m "not integration"
```

- [ ] **Step 3: Run full suite + lint**

```bash
uv run pytest api/tests/ -m "not integration" -q
uv run ruff check api/app/modules/slo_registry/
uv run mypy api/app/modules/slo_registry/
```

- [ ] **Step 4: Commit**

```bash
git add api/app/modules/slo_registry/router.py api/app/modules/slo_registry/schemas.py
git commit -m "feat: add POST /slo-definitions/test dry-run evaluation endpoint"
```
