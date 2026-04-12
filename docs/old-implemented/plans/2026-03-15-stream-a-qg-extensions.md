# Stream A: Quality Gate Extensions

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Read first:** `docs/superpowers/plans/2026-03-15-api-ui-alignment-overview.md`

**Goal:** Add `eval_id` lookup to `GET /trend` and `from`/`to` time-range filters to `GET /evaluations`.

**Architecture:** Two additive changes to existing `quality_gate` module. No new files needed beyond tests. No schema migrations.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, pytest

**Spec:** `docs/superpowers/specs/2026-03-15-api-ui-alignment-design.md` §2–3

---

## File Structure

| Action | File | Responsibility |
|---|---|---|
| Modify | `api/app/modules/quality_gate/router.py` | New params on `get_trend` + `list_evaluations` |
| Modify | `api/app/modules/quality_gate/repository.py` | Add `from_ts`/`to_ts` to `list_with_counts()` |
| Create | `api/tests/test_qg_router.py` | Parameter validation tests via TestClient |

**Note:** Tests in this stream cover parameter validation only (422 responses). Happy-path
tests (eval_id found but no asset_id, eval_id not found → 404, successful trend data)
require DB fixtures and are deferred to integration tests.

---

### Task 1: Trend by eval_id — Tests

**Files:**
- Create: `api/tests/test_qg_router.py`

- [ ] **Step 1: Write failing tests for trend parameter validation**

```python
# api/tests/test_qg_router.py
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_trend_rejects_both_eval_id_and_asset_name(client):
    resp = client.get(
        "/trend",
        params={
            "eval_id": str(uuid.uuid4()),
            "asset_name": "vm-01",
            "slo_name": "my-slo",
            "metric": "cpu",
        },
    )
    assert resp.status_code == 422


def test_trend_rejects_neither_eval_id_nor_asset_name(client):
    resp = client.get("/trend", params={"metric": "cpu"})
    assert resp.status_code == 422


def test_trend_rejects_eval_id_with_partial_asset(client):
    resp = client.get(
        "/trend",
        params={
            "eval_id": str(uuid.uuid4()),
            "asset_name": "vm-01",
            "metric": "cpu",
        },
    )
    assert resp.status_code == 422


def test_trend_rejects_asset_name_without_slo_name(client):
    resp = client.get(
        "/trend",
        params={"asset_name": "vm-01", "metric": "cpu"},
    )
    assert resp.status_code == 422
```

- [ ] **Step 2: Run tests — expect failures**

```bash
uv run pytest api/tests/test_qg_router.py -v -m "not integration"
```

- [ ] **Step 3: Commit failing tests**

```bash
git add api/tests/test_qg_router.py
git commit -m "test: add failing tests for trend-by-eval-id parameter validation"
```

---

### Task 2: Trend by eval_id — Implementation

**Files:**
- Modify: `api/app/modules/quality_gate/router.py`

- [ ] **Step 1: Update `get_trend` endpoint**

Update the import line at the top of the file:

```python
# Change this:
from fastapi import APIRouter, Depends, Query
# To this:
from fastapi import APIRouter, Depends, HTTPException, Query
```

Then replace the `get_trend` function (lines 233–253) with this version that accepts
optional `eval_id` as an alternative to `asset_name + slo_name`:

```python
@router.get("/trend", response_model=list[TrendPoint])
async def get_trend(
    metric: str,
    eval_id: uuid.UUID | None = None,
    asset_name: str | None = None,
    slo_name: str | None = None,
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[TrendPoint]:
    """Return time-series trend data for a specific metric.

    Exactly one of eval_id or (asset_name + slo_name) must be provided.
    """
    has_eval = eval_id is not None
    has_asset = asset_name is not None or slo_name is not None

    if has_eval and has_asset:
        raise HTTPException(
            status_code=422,
            detail="provide either eval_id or (asset_name + slo_name), not both",
        )
    if not has_eval and not has_asset:
        raise HTTPException(
            status_code=422,
            detail="provide either eval_id or (asset_name + slo_name)",
        )
    if has_asset and (asset_name is None or slo_name is None):
        raise HTTPException(
            status_code=422,
            detail="both asset_name and slo_name are required when not using eval_id",
        )

    eval_repo = EvaluationRepository(session)

    if eval_id is not None:
        ev = await eval_repo.get_by_id(eval_id)
        if ev is None:
            raise_not_found("evaluation", str(eval_id))
        if ev.asset_id is None:
            raise HTTPException(status_code=422, detail="evaluation has no associated asset")
        if ev.slo_name is None:
            raise HTTPException(status_code=422, detail="evaluation has no associated slo")
        resolved_asset_id = ev.asset_id
        resolved_slo_name = ev.slo_name
    else:
        asset_repo = AssetRepository(session)
        asset = await asset_repo.get_by_name(asset_name)  # type: ignore[arg-type]
        if asset is None:
            raise_not_found("asset", asset_name)  # type: ignore[arg-type]
        resolved_asset_id = asset.id
        resolved_slo_name = slo_name  # type: ignore[assignment]

    points = await eval_repo.get_trend_by_domain(
        asset_id=resolved_asset_id,
        slo_name=resolved_slo_name,
        metric_name=metric,
        limit=limit,
    )
    return [TrendPoint(**p) for p in points]
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest api/tests/test_qg_router.py -v -m "not integration"
```

Expected: All 4 validation tests PASS.

- [ ] **Step 3: Run full suite + lint**

```bash
uv run pytest api/tests/ -m "not integration" -q
uv run ruff check api/app/modules/quality_gate/router.py
uv run mypy api/app/modules/quality_gate/router.py
```

- [ ] **Step 4: Commit**

```bash
git add api/app/modules/quality_gate/router.py
git commit -m "feat: extend GET /trend to accept eval_id as alternative lookup"
```

---

### Task 3: Time-range filters — Tests

**Files:**
- Modify: `api/tests/test_qg_router.py`

- [ ] **Step 1: Append failing tests for from/to validation**

Add to `api/tests/test_qg_router.py`:

```python
def test_evaluations_rejects_date_with_from(client):
    resp = client.get(
        "/evaluations",
        params={"date": "2026-03-01", "from": "2026-03-01T00:00:00Z"},
    )
    assert resp.status_code == 422


def test_evaluations_rejects_date_with_to(client):
    resp = client.get(
        "/evaluations",
        params={"date": "2026-03-01", "to": "2026-03-01T23:59:59Z"},
    )
    assert resp.status_code == 422


def test_evaluations_accepts_from_to_without_date(client):
    resp = client.get(
        "/evaluations",
        params={"from": "2026-03-01T00:00:00Z", "to": "2026-03-01T23:59:59Z"},
    )
    # Should be 200 (empty results) — NOT 422 (validation error)
    assert resp.status_code == 200
```

- [ ] **Step 2: Run — expect failures**

```bash
uv run pytest api/tests/test_qg_router.py::test_evaluations_rejects_date_with_from -v
```

- [ ] **Step 3: Commit**

```bash
git add api/tests/test_qg_router.py
git commit -m "test: add failing tests for evaluation time-range filter validation"
```

---

### Task 4: Time-range filters — Implementation

**Files:**
- Modify: `api/app/modules/quality_gate/router.py`
- Modify: `api/app/modules/quality_gate/repository.py`

- [ ] **Step 1: Add from/to params to `list_evaluations` in router.py**

Add `datetime` import at the top of the file:

```python
from datetime import datetime
```

Update `list_evaluations` signature to add two params after `group_name`:

```python
    from_ts: datetime | None = Query(default=None, alias="from"),
    to_ts: datetime | None = Query(default=None, alias="to"),
```

Add mutual-exclusion check at top of function body (before `eval_repo` creation):

```python
    if date and (from_ts or to_ts):
        raise HTTPException(
            status_code=422,
            detail="date and from/to filters are mutually exclusive",
        )
```

Pass `from_ts` and `to_ts` through to `list_with_counts`:

```python
    evals, total, count_map = await eval_repo.list_with_counts(
        ...,
        from_ts=from_ts,
        to_ts=to_ts,
        ...
    )
```

- [ ] **Step 2: Add from_ts/to_ts to `list_with_counts` in repository.py**

Add two new keyword args to the method signature:

```python
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
```

Add filter clauses after the `asset_ids` check (before `count_q`):

```python
        if from_ts:
            q = q.where(Evaluation.period_start >= from_ts)
        if to_ts:
            q = q.where(Evaluation.period_start <= to_ts)
```

- [ ] **Step 3: Run all tests**

```bash
uv run pytest api/tests/ -m "not integration" -q
```

- [ ] **Step 4: Lint + type check**

```bash
uv run ruff check api/app/modules/quality_gate/
uv run mypy api/app/modules/quality_gate/
```

- [ ] **Step 5: Commit**

```bash
git add api/app/modules/quality_gate/router.py api/app/modules/quality_gate/repository.py
git commit -m "feat: add from/to time-range filters to GET /evaluations"
```
