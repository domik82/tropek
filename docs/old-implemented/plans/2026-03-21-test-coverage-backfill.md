# Test Coverage Backfill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backfill test coverage for endpoint mutations, repository round-trips, presenter edge cases, and heatmap behavior — creating a safety net before the DB normalization migration.

**Architecture:** All backend integration tests use the existing `db_session` fixture from `api/tests/db/conftest.py` (real test DB, rolled-back transactions). Endpoint tests use FastAPI `AsyncClient` (httpx) with dependency overrides for the DB session. UI tests use Vitest + React Testing Library with mocked hooks.

**Tech Stack:** Python 3.13, pytest (asyncio_mode=auto), FastAPI AsyncClient (httpx), SQLAlchemy async, Vitest, React Testing Library

**Spec:** `docs/superpowers/specs/2026-03-21-test-coverage-backfill-design.md`

**Commands:**
- Run backend integration tests: `uv run --directory api pytest api/tests/ -m integration -v`
- Run backend unit tests: `uv run --directory api pytest api/tests/ -m "not integration" -v`
- Run single test: `uv run --directory api pytest api/tests/path/test_file.py::test_name -v`
- Run UI tests: `cd ui && npx vitest run`
- Run single UI test: `cd ui && npx vitest run src/path/Component.test.tsx`
- Start test infra: `./start_test_infra.sh`
- Lint: `uv run ruff check api/`
- Type check: `uv run mypy api/app`

---

### Task 1: Fix override double-apply bug

**Files:**
- Modify: `api/app/modules/quality_gate/repository.py:447-470`
- Test: `api/tests/db/test_evaluation_repository.py`

The `override_status()` method unconditionally sets `original_result=ev.result`. On a second override, this loses the true original. Fix: only set `original_result` and `original_score` if they are currently NULL.

- [ ] **Step 1: Write failing test for double-apply**

Add to `api/tests/db/test_evaluation_repository.py`:

```python
@pytest.mark.integration
async def test_override_double_apply_preserves_original(db_session: AsyncSession) -> None:
    """Second override must NOT overwrite original_result from the first eval."""
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        evaluation_name="override-test",
        period_start=_START,
        period_end=_END,
        ingestion_mode="push",
        asset_snapshot=_make_snapshot(),
        metadata={},
        asset_id=asset_id,
        slo_name="test-slo",
    )
    await repo.mark_completed(ev.id, result="fail", score=30.0, indicator_results=[], slo_name="test-slo")

    # First override: fail → pass
    await repo.override_status(ev.id, new_result="pass", reason="false alarm", author="alice")
    ev1 = await repo.get_by_id(ev.id)
    assert ev1.original_result == "fail"
    assert ev1.result == "pass"

    # Second override: pass → warning — original must still be "fail"
    await repo.override_status(ev.id, new_result="warning", reason="adjusted", author="bob")
    ev2 = await repo.get_by_id(ev.id)
    assert ev2.original_result == "fail"  # NOT "pass"
    assert ev2.result == "warning"
    assert ev2.override_author == "bob"
```

- [ ] **Step 2: Run test — verify it fails**

Run: `uv run --directory api pytest api/tests/db/test_evaluation_repository.py::test_override_double_apply_preserves_original -v`

Expected: FAIL — `assert ev2.original_result == "fail"` fails because it gets `"pass"`

- [ ] **Step 3: Fix the bug**

In `api/app/modules/quality_gate/repository.py`, change `override_status()`:

```python
async def override_status(
    self,
    eval_id: uuid.UUID,
    *,
    new_result: str,
    reason: str,
    author: str,
) -> Evaluation | None:
    """Override the evaluation result, preserving the original."""
    ev = await self.get_by_id(eval_id)
    if ev is None:
        return None
    values: dict[str, Any] = {
        "result": new_result,
        "override_reason": reason,
        "override_author": author,
    }
    # Only set original on first override — preserve the true original
    if ev.original_result is None:
        values["original_result"] = ev.result
    await self._session.execute(
        update(Evaluation).where(Evaluation.id == eval_id).values(**values)
    )
    await self._session.flush()
    return await self.get_by_id(eval_id)
```

Note: add `from typing import Any` to imports if not already present.

- [ ] **Step 4: Run test — verify it passes**

Run: `uv run --directory api pytest api/tests/db/test_evaluation_repository.py::test_override_double_apply_preserves_original -v`

Expected: PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `uv run --directory api pytest api/tests/ -m integration -v`

Expected: All tests pass

- [ ] **Step 6: Lint and type check**

Run: `uv run ruff check api/app/modules/quality_gate/repository.py`
Run: `uv run mypy api/app`

- [ ] **Step 7: Commit**

```
git add api/app/modules/quality_gate/repository.py api/tests/db/test_evaluation_repository.py
git commit -m "fix: preserve original_result on double override"
```

---

### Task 2: Endpoint test infrastructure

**Files:**
- Create: `api/tests/endpoints/__init__.py`
- Create: `api/tests/endpoints/conftest.py`

Set up shared fixtures for endpoint integration tests that use a real DB (not mocked sessions). These tests call the FastAPI app via `AsyncClient` with the DB session overridden to use the test database.

- [ ] **Step 1: Create the endpoint test directory and conftest**

Create `api/tests/endpoints/__init__.py` (empty file).

Create `api/tests/endpoints/conftest.py`:

```python
"""Shared fixtures for endpoint integration tests.

These tests use a real test database (via db_session from conftest.py)
with FastAPI AsyncClient (httpx). The DB session dependency is overridden
to use the test session, so all changes are rolled back after each test.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from app.db.models import Asset, AssetType
from app.db.session import get_session
from app.main import app
from app.modules.quality_gate.repository import EvaluationRepository
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

_START = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
_END = datetime(2026, 3, 15, 10, 30, 0, tzinfo=UTC)


def _make_snapshot(
    name: str = "vm-test-01", os: str = "windows-11", arch: str = "x64"
) -> dict:
    return {"name": name, "tags": {"os": os, "arch": arch}}


async def _create_asset(session: AsyncSession, name: str | None = None) -> uuid.UUID:
    type_name = f"vm-{uuid.uuid4().hex[:8]}"
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    asset_name = name or f"asset-{asset_id.hex[:8]}"
    session.add(Asset(id=asset_id, name=asset_name, type_name=type_name))
    await session.flush()
    return asset_id


async def _create_completed_eval(
    session: AsyncSession,
    asset_id: uuid.UUID,
    *,
    result: str = "pass",
    score: float = 90.0,
    indicator_results: list | None = None,
    slo_name: str = "test-slo",
    evaluation_name: str = "compile-test",
    period_start: datetime = _START,
    period_end: datetime = _END,
) -> uuid.UUID:
    repo = EvaluationRepository(session)
    ev = await repo.create_pending(
        evaluation_name=evaluation_name,
        period_start=period_start,
        period_end=period_end,
        ingestion_mode="push",
        asset_snapshot=_make_snapshot(),
        metadata={},
        asset_id=asset_id,
        slo_name=slo_name,
    )
    await repo.mark_completed(
        ev.id,
        result=result,
        score=score,
        indicator_results=indicator_results or [],
        slo_name=slo_name,
    )
    return ev.id


@pytest_asyncio.fixture()
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Yield an httpx AsyncClient bound to the FastAPI app with test DB session."""

    async def _override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Verify the fixture works with a smoke test**

Create a minimal test in `api/tests/endpoints/test_smoke.py`:

```python
"""Smoke test to verify endpoint test infrastructure."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_health_endpoint(async_client: AsyncClient) -> None:
    resp = await async_client.get("/health")
    assert resp.status_code == 200
```

- [ ] **Step 3: Run smoke test**

Run: `uv run --directory api pytest api/tests/endpoints/test_smoke.py -v`

Expected: PASS (may need to adjust the dependency override path — the router imports `get_session` from `app.db.session`, and the conftest overrides that same function object.)

- [ ] **Step 4: Commit**

```
git add api/tests/endpoints/
git commit -m "test: add endpoint integration test infrastructure"
```

---

### Task 3: Annotation endpoint tests

**Files:**
- Create: `api/tests/endpoints/test_annotation_endpoints.py`

- [ ] **Step 1: Write annotation endpoint tests**

```python
"""Endpoint tests for annotation CRUD operations."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import _create_asset, _create_completed_eval


@pytest.mark.integration
async def test_create_annotation(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    resp = await async_client.post(
        f"/evaluations/{eval_id}/annotations",
        json={"content": "Looks like a network blip", "author": "alice", "category": "observation"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["content"] == "Looks like a network blip"
    assert body["author"] == "alice"
    assert body["category"] == "observation"
    assert body["hidden_at"] is None


@pytest.mark.integration
async def test_annotation_appears_in_eval_detail(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    await async_client.post(
        f"/evaluations/{eval_id}/annotations",
        json={"content": "Note one", "author": "alice"},
    )
    await async_client.post(
        f"/evaluations/{eval_id}/annotations",
        json={"content": "Note two", "author": "bob"},
    )

    resp = await async_client.get(f"/evaluations/{eval_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["annotation_count"] == 2
    contents = [a["content"] for a in detail["annotations"]]
    assert "Note one" in contents
    assert "Note two" in contents


@pytest.mark.integration
async def test_list_annotations(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    await async_client.post(
        f"/evaluations/{eval_id}/annotations",
        json={"content": "Visible note", "author": "alice"},
    )

    resp = await async_client.get(f"/evaluations/{eval_id}/annotations")
    assert resp.status_code == 200
    annotations = resp.json()
    assert len(annotations) == 1
    assert annotations[0]["content"] == "Visible note"


@pytest.mark.integration
async def test_update_annotation(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    create_resp = await async_client.post(
        f"/evaluations/{eval_id}/annotations",
        json={"content": "Original", "author": "alice"},
    )
    ann_id = create_resp.json()["id"]

    resp = await async_client.patch(
        f"/evaluations/{eval_id}/annotations/{ann_id}",
        json={"content": "Updated content"},
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "Updated content"


@pytest.mark.integration
async def test_hide_annotation_excludes_from_detail(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    create_resp = await async_client.post(
        f"/evaluations/{eval_id}/annotations",
        json={"content": "Will be hidden", "author": "alice"},
    )
    ann_id = create_resp.json()["id"]

    hide_resp = await async_client.post(
        f"/evaluations/{eval_id}/annotations/{ann_id}/hide",
        json={"reason": "Duplicate", "author": "bob"},
    )
    assert hide_resp.status_code == 200
    assert hide_resp.json()["hidden_at"] is not None

    detail_resp = await async_client.get(f"/evaluations/{eval_id}")
    detail = detail_resp.json()
    assert detail["annotation_count"] == 0
    assert len(detail["annotations"]) == 0


@pytest.mark.integration
async def test_create_annotation_on_missing_eval(async_client: AsyncClient) -> None:
    fake_id = uuid.uuid4()
    resp = await async_client.post(
        f"/evaluations/{fake_id}/annotations",
        json={"content": "Orphan note", "author": "alice"},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests**

Run: `uv run --directory api pytest api/tests/endpoints/test_annotation_endpoints.py -v`

Expected: All PASS. If any endpoint paths don't match, check `api/app/modules/quality_gate/router.py` for the exact paths and adjust.

- [ ] **Step 3: Commit**

```
git add api/tests/endpoints/test_annotation_endpoints.py
git commit -m "test: add annotation endpoint integration tests"
```

---

### Task 4: Invalidation endpoint tests

**Files:**
- Create: `api/tests/endpoints/test_invalidation_endpoints.py`

- [ ] **Step 1: Write invalidation endpoint tests**

```python
"""Endpoint tests for evaluation invalidation and restore."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import _create_asset, _create_completed_eval


@pytest.mark.integration
async def test_invalidate_evaluation(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id, result="pass", score=90.0)

    resp = await async_client.patch(
        f"/evaluations/{eval_id}/invalidate",
        json={"invalidation_note": "Wrong time window"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["invalidated"] is True


@pytest.mark.integration
async def test_restore_invalidated_evaluation(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    await async_client.patch(
        f"/evaluations/{eval_id}/invalidate",
        json={"invalidation_note": "Mistake"},
    )

    resp = await async_client.patch(f"/evaluations/{eval_id}/restore")
    assert resp.status_code == 200
    body = resp.json()
    assert body["invalidated"] is False


@pytest.mark.integration
async def test_invalidate_restore_cycle(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Full cycle: valid → invalidated → restored to valid."""
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id, result="pass", score=85.0)

    # Invalidate
    await async_client.patch(
        f"/evaluations/{eval_id}/invalidate",
        json={"invalidation_note": "Under review"},
    )

    # Verify invalidated in detail
    detail_resp = await async_client.get(f"/evaluations/{eval_id}")
    assert detail_resp.json()["invalidated"] is True
    assert detail_resp.json()["invalidation_note"] == "Under review"

    # Restore
    await async_client.patch(f"/evaluations/{eval_id}/restore")

    # Verify restored
    detail_resp2 = await async_client.get(f"/evaluations/{eval_id}")
    assert detail_resp2.json()["invalidated"] is False
    assert detail_resp2.json()["result"] == "pass"
    assert detail_resp2.json()["score"] == 85.0
```

- [ ] **Step 2: Run tests**

Run: `uv run --directory api pytest api/tests/endpoints/test_invalidation_endpoints.py -v`

Expected: All PASS

- [ ] **Step 3: Commit**

```
git add api/tests/endpoints/test_invalidation_endpoints.py
git commit -m "test: add invalidation endpoint integration tests"
```

---

### Task 5: Override endpoint tests

**Files:**
- Create: `api/tests/endpoints/test_override_endpoints.py`

- [ ] **Step 1: Write override endpoint tests**

```python
"""Endpoint tests for evaluation result override and restore."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import _create_asset, _create_completed_eval


@pytest.mark.integration
async def test_override_status(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id, result="fail", score=30.0)

    resp = await async_client.patch(
        f"/evaluations/{eval_id}/override-status",
        json={"new_result": "pass", "reason": "False alarm", "author": "alice"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"] == "pass"
    assert body["original_result"] == "fail"
    assert body["override_reason"] == "False alarm"
    assert body["override_author"] == "alice"


@pytest.mark.integration
async def test_restore_override(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id, result="fail", score=30.0)

    await async_client.patch(
        f"/evaluations/{eval_id}/override-status",
        json={"new_result": "pass", "reason": "Override", "author": "alice"},
    )

    resp = await async_client.patch(f"/evaluations/{eval_id}/restore-override")
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"] == "fail"
    assert body["original_result"] is None
    assert body["override_reason"] is None


@pytest.mark.integration
async def test_double_override_preserves_true_original(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Overriding an already-overridden eval must keep the FIRST original."""
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id, result="fail", score=30.0)

    # First override: fail → pass
    await async_client.patch(
        f"/evaluations/{eval_id}/override-status",
        json={"new_result": "pass", "reason": "v1", "author": "alice"},
    )

    # Second override: pass → warning
    resp = await async_client.patch(
        f"/evaluations/{eval_id}/override-status",
        json={"new_result": "warning", "reason": "v2", "author": "bob"},
    )
    body = resp.json()
    assert body["result"] == "warning"
    assert body["original_result"] == "fail"  # True original preserved
    assert body["override_author"] == "bob"
```

- [ ] **Step 2: Run tests**

Run: `uv run --directory api pytest api/tests/endpoints/test_override_endpoints.py -v`

Expected: All PASS (depends on Task 1 bug fix)

- [ ] **Step 3: Commit**

```
git add api/tests/endpoints/test_override_endpoints.py
git commit -m "test: add override endpoint integration tests"
```

---

### Task 6: Baseline pin/unpin endpoint tests

**Files:**
- Create: `api/tests/endpoints/test_baseline_pin_endpoints.py`

- [ ] **Step 1: Write pin/unpin endpoint tests**

```python
"""Endpoint tests for baseline pin and unpin operations."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import _create_asset, _create_completed_eval


@pytest.mark.integration
async def test_pin_baseline(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    resp = await async_client.patch(
        f"/evaluations/{eval_id}/pin-baseline",
        json={"reason": "Golden run", "author": "alice"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["baseline_pinned_at"] is not None
    assert body["baseline_pin_reason"] == "Golden run"
    assert body["baseline_pin_author"] == "alice"


@pytest.mark.integration
async def test_unpin_baseline(async_client: AsyncClient, db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    eval_id = await _create_completed_eval(db_session, asset_id)

    await async_client.patch(
        f"/evaluations/{eval_id}/pin-baseline",
        json={"reason": "Golden run", "author": "alice"},
    )

    resp = await async_client.patch(f"/evaluations/{eval_id}/unpin-baseline")
    assert resp.status_code == 200
    body = resp.json()
    assert body["baseline_unpinned_at"] is not None


@pytest.mark.integration
async def test_pin_new_unpins_previous(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Pinning eval B for the same asset+SLO must atomically unpin eval A."""
    asset_id = await _create_asset(db_session)
    eval_a = await _create_completed_eval(
        db_session, asset_id, evaluation_name="run-a",
    )
    eval_b = await _create_completed_eval(
        db_session, asset_id, evaluation_name="run-b",
    )

    # Pin A
    await async_client.patch(
        f"/evaluations/{eval_a}/pin-baseline",
        json={"reason": "First pin", "author": "alice"},
    )

    # Pin B — should unpin A
    await async_client.patch(
        f"/evaluations/{eval_b}/pin-baseline",
        json={"reason": "Better run", "author": "bob"},
    )

    # Verify A is unpinned
    resp_a = await async_client.get(f"/evaluations/{eval_a}")
    assert resp_a.json()["baseline_unpinned_at"] is not None

    # Verify B is pinned
    resp_b = await async_client.get(f"/evaluations/{eval_b}")
    assert resp_b.json()["baseline_pinned_at"] is not None
    assert resp_b.json()["baseline_unpinned_at"] is None
```

- [ ] **Step 2: Run tests**

Run: `uv run --directory api pytest api/tests/endpoints/test_baseline_pin_endpoints.py -v`

Expected: All PASS

- [ ] **Step 3: Commit**

```
git add api/tests/endpoints/test_baseline_pin_endpoints.py
git commit -m "test: add baseline pin/unpin endpoint integration tests"
```

---

### Task 7: Re-evaluation endpoint tests

**Files:**
- Create: `api/tests/endpoints/test_re_evaluation_endpoints.py`

The re-evaluate endpoint (`POST /evaluations/re-evaluate`) triggers re-evaluation of completed evaluations from stored SLI values. Tests must verify original_result/original_score preservation across re-evaluations.

- [ ] **Step 1: Read re-evaluation request schema**

Read `api/app/modules/quality_gate/re_evaluation_schemas.py` to understand `ReEvaluateRequest` and `ReEvaluateResponse` shapes. Also read `api/app/modules/quality_gate/re_evaluator.py` to understand what setup is needed (SLO definition, SLI values must exist).

- [ ] **Step 2: Write re-evaluation endpoint tests**

Create `api/tests/endpoints/test_re_evaluation_endpoints.py`. The exact test bodies depend on what `ReEvaluateRequest` requires. Structure:

```python
"""Endpoint tests for re-evaluation."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import _create_asset, _create_completed_eval


@pytest.mark.integration
async def test_re_evaluate_sets_original_result(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """First re-evaluation must set original_result and original_score."""
    # Setup: create asset, seed SLO definition, create completed eval,
    # seed SLI values for the eval (required for re-eval to have data to score).
    # Then POST /evaluations/re-evaluate and verify original_result is set.
    # Read re_evaluator.py and re_evaluation_schemas.py for exact setup.
    ...


@pytest.mark.integration
async def test_re_evaluate_preserves_original_on_second_reeval(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Second re-evaluation must NOT overwrite original_result."""
    ...
```

Note: The re-evaluator requires a full SLO definition + SLI values in the DB. The test setup is more complex than other endpoint tests. Read `api/tests/db/test_re_evaluation.py` for the existing pattern — it uses `BaselineRepository` and seeds SLO definitions. Follow that pattern.

- [ ] **Step 3: Run tests**

Run: `uv run --directory api pytest api/tests/endpoints/test_re_evaluation_endpoints.py -v`

Expected: All PASS

- [ ] **Step 4: Commit**

```
git add api/tests/endpoints/test_re_evaluation_endpoints.py
git commit -m "test: add re-evaluation endpoint integration tests"
```

---

### Task 8: Indicator results round-trip test

**Files:**
- Create: `api/tests/db/test_indicator_round_trip.py`

Tests that data written via `mark_completed()` survives the full read path through the presenter and produces the correct API schema output.

- [ ] **Step 1: Write round-trip tests**

```python
"""Round-trip tests: write indicator_results → read via presenter → assert field equality.

These lock down the exact transformation from DB storage to API response,
creating a safety net for the DB normalization migration.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.db.models import Asset, AssetType
from app.modules.quality_gate.presenter import build_detail, build_summary
from app.modules.quality_gate.repository import EvaluationRepository
from sqlalchemy.ext.asyncio import AsyncSession

_START = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
_END = datetime(2026, 3, 15, 10, 30, 0, tzinfo=UTC)

_INDICATOR_PASS = {
    "metric": "response_time_p95",
    "display_name": "Response Time P95",
    "tab_group": "latency",
    "value": 580.0,
    "compared_value": 500.0,
    "change_absolute": 80.0,
    "change_relative_pct": 16.0,
    "aggregation": "p95",
    "status": "pass",
    "score": 1.0,
    "weight": 1,
    "key_sli": True,
    "pass_targets": [{"criteria": "<600", "target_value": 600, "violated": False}],
    "warning_targets": None,
}

_INDICATOR_FAIL = {
    "metric": "error_rate",
    "display_name": "Error Rate",
    "tab_group": None,
    "value": 5.2,
    "compared_value": 1.0,
    "change_absolute": 4.2,
    "change_relative_pct": 420.0,
    "aggregation": "avg",
    "status": "fail",
    "score": 0.0,
    "weight": 2,
    "key_sli": False,
    "pass_targets": [{"criteria": "<2", "target_value": 2, "violated": True}],
    "warning_targets": [{"criteria": "<5", "target_value": 5, "violated": True}],
}

_INDICATOR_NULL_VALUE = {
    "metric": "cpu_usage",
    "display_name": "CPU Usage",
    "tab_group": None,
    "value": None,
    "compared_value": None,
    "change_absolute": None,
    "change_relative_pct": None,
    "aggregation": None,
    "status": "fail",
    "score": 0.0,
    "weight": 1,
    "key_sli": False,
    "pass_targets": [{"criteria": "<80", "target_value": 80, "violated": True}],
    "warning_targets": None,
}

_INDICATOR_INFO = {
    "metric": "build_duration",
    "display_name": "Build Duration",
    "tab_group": None,
    "value": 120.0,
    "compared_value": None,
    "change_absolute": None,
    "change_relative_pct": None,
    "aggregation": "avg",
    "status": "info",
    "score": 0.0,
    "weight": 0,
    "key_sli": False,
    "pass_targets": None,
    "warning_targets": None,
}


async def _create_asset(session: AsyncSession) -> uuid.UUID:
    type_name = f"vm-{uuid.uuid4().hex[:8]}"
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(Asset(id=asset_id, name=f"asset-{asset_id.hex[:8]}", type_name=type_name))
    await session.flush()
    return asset_id


@pytest.mark.integration
async def test_detail_round_trip_all_fields(db_session: AsyncSession) -> None:
    """Write indicators with all field types, read back via presenter, assert equality."""
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        evaluation_name="round-trip-test",
        period_start=_START,
        period_end=_END,
        ingestion_mode="push",
        asset_snapshot={"name": "vm-test-01", "tags": {}},
        metadata={},
        asset_id=asset_id,
        slo_name="test-slo",
    )
    indicators = [_INDICATOR_PASS, _INDICATOR_FAIL, _INDICATOR_NULL_VALUE, _INDICATOR_INFO]
    await repo.mark_completed(ev.id, result="fail", score=25.0, indicator_results=indicators, slo_name="test-slo")

    fetched = await repo.get_by_id(ev.id)
    detail = build_detail(fetched)

    assert len(detail.indicator_results) == 4

    # Assert pass indicator
    ir_pass = next(ir for ir in detail.indicator_results if ir.metric == "response_time_p95")
    assert ir_pass.value == 580.0
    assert ir_pass.compared_value == 500.0
    assert ir_pass.status == "pass"
    assert ir_pass.key_sli is True
    assert ir_pass.tab_group == "latency"
    assert ir_pass.pass_targets == [{"criteria": "<600", "target_value": 600, "violated": False}]

    # Assert fail indicator
    ir_fail = next(ir for ir in detail.indicator_results if ir.metric == "error_rate")
    assert ir_fail.status == "fail"
    assert ir_fail.weight == 2
    assert ir_fail.warning_targets is not None
    assert len(ir_fail.warning_targets) == 1

    # Assert null-value indicator
    ir_null = next(ir for ir in detail.indicator_results if ir.metric == "cpu_usage")
    assert ir_null.value is None
    assert ir_null.compared_value is None
    assert ir_null.change_absolute is None

    # Assert info indicator
    ir_info = next(ir for ir in detail.indicator_results if ir.metric == "build_duration")
    assert ir_info.status == "info"
    assert ir_info.score == 0.0
    assert ir_info.pass_targets is None


@pytest.mark.integration
async def test_summary_top_failures(db_session: AsyncSession) -> None:
    """Summary extracts only failing indicators into top_failures."""
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        evaluation_name="failures-test",
        period_start=_START,
        period_end=_END,
        ingestion_mode="push",
        asset_snapshot={"name": "vm-test-01", "tags": {}},
        metadata={},
        asset_id=asset_id,
        slo_name="test-slo",
    )
    await repo.mark_completed(
        ev.id,
        result="fail",
        score=25.0,
        indicator_results=[_INDICATOR_PASS, _INDICATOR_FAIL],
        slo_name="test-slo",
    )

    fetched = await repo.get_by_id(ev.id)
    summary = build_summary(fetched, annotation_count=0, latest_ann=None)

    assert len(summary.top_failures) == 1
    assert summary.top_failures[0].metric == "error_rate"
    assert summary.top_failures[0].threshold == "<2"


@pytest.mark.integration
async def test_empty_indicator_results(db_session: AsyncSession) -> None:
    """Evaluation with no indicators produces empty lists."""
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        evaluation_name="empty-test",
        period_start=_START,
        period_end=_END,
        ingestion_mode="push",
        asset_snapshot={"name": "vm-test-01", "tags": {}},
        metadata={},
        asset_id=asset_id,
        slo_name="test-slo",
    )
    await repo.mark_completed(ev.id, result="pass", score=100.0, indicator_results=[], slo_name="test-slo")

    fetched = await repo.get_by_id(ev.id)
    detail = build_detail(fetched)
    summary = build_summary(fetched, annotation_count=0, latest_ann=None)

    assert detail.indicator_results == []
    assert summary.top_failures == []
```

- [ ] **Step 2: Run tests**

Run: `uv run --directory api pytest api/tests/db/test_indicator_round_trip.py -v`

Expected: All PASS

- [ ] **Step 3: Commit**

```
git add api/tests/db/test_indicator_round_trip.py
git commit -m "test: add indicator results round-trip tests"
```

---

### Task 9: Heatmap and trend query tests

**Files:**
- Create: `api/tests/db/test_heatmap_query.py`
- Create: `api/tests/db/test_trend_query.py`

- [ ] **Step 1: Write heatmap query tests**

```python
"""Integration tests for metric heatmap query."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.db.models import Asset, AssetType
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.quality_gate.trend_repository import TrendRepository
from sqlalchemy.ext.asyncio import AsyncSession

_BASE = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)

_INDICATORS = [
    {
        "metric": "cpu_usage",
        "display_name": "CPU Usage",
        "value": 72.0,
        "compared_value": None,
        "change_absolute": None,
        "change_relative_pct": None,
        "status": "pass",
        "score": 1.0,
        "weight": 1,
        "key_sli": False,
        "pass_targets": [{"criteria": "<80", "target_value": 80, "violated": False}],
        "warning_targets": None,
    },
]


async def _create_asset(session: AsyncSession, name: str) -> uuid.UUID:
    type_name = f"vm-{uuid.uuid4().hex[:8]}"
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(Asset(id=asset_id, name=name, type_name=type_name))
    await session.flush()
    return asset_id


@pytest.mark.integration
async def test_heatmap_returns_completed_evals(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session, "heatmap-asset")
    eval_repo = EvaluationRepository(db_session)
    trend_repo = TrendRepository(db_session)

    for i in range(3):
        start = _BASE + timedelta(hours=i)
        ev = await eval_repo.create_pending(
            evaluation_name="hm-test",
            period_start=start,
            period_end=start + timedelta(minutes=30),
            ingestion_mode="push",
            asset_snapshot={"name": "heatmap-asset", "tags": {}},
            metadata={},
            asset_id=asset_id,
            slo_name="test-slo",
        )
        await eval_repo.mark_completed(
            ev.id, result="pass", score=90.0, indicator_results=_INDICATORS, slo_name="test-slo"
        )

    evals = await trend_repo.get_metric_heatmap(asset_id=asset_id, limit=10)
    assert len(evals) == 3


@pytest.mark.integration
async def test_heatmap_includes_invalidated_completed(db_session: AsyncSession) -> None:
    """The repository query returns invalidated evals (router handles display)."""
    asset_id = await _create_asset(db_session, "hm-inv-asset")
    eval_repo = EvaluationRepository(db_session)
    trend_repo = TrendRepository(db_session)

    ev = await eval_repo.create_pending(
        evaluation_name="hm-inv",
        period_start=_BASE,
        period_end=_BASE + timedelta(minutes=30),
        ingestion_mode="push",
        asset_snapshot={"name": "hm-inv-asset", "tags": {}},
        metadata={},
        asset_id=asset_id,
        slo_name="test-slo",
    )
    await eval_repo.mark_completed(
        ev.id, result="pass", score=90.0, indicator_results=_INDICATORS, slo_name="test-slo"
    )
    await eval_repo.invalidate(ev.id, note="bad data")

    evals = await trend_repo.get_metric_heatmap(asset_id=asset_id, limit=10)
    # Repository returns it — router transforms result to "invalidated"
    assert len(evals) == 1
```

- [ ] **Step 2: Write trend query tests**

```python
"""Integration tests for trend query (joins Evaluation + SLIValue)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.db.models import Asset, AssetType
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.quality_gate.sli_repository import SLIValueRepository
from app.modules.quality_gate.trend_repository import TrendRepository
from sqlalchemy.ext.asyncio import AsyncSession

_BASE = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)

_INDICATORS = [
    {
        "metric": "response_time",
        "display_name": "Response Time",
        "value": 250.0,
        "compared_value": 200.0,
        "change_absolute": 50.0,
        "change_relative_pct": 25.0,
        "status": "pass",
        "score": 1.0,
        "weight": 1,
        "key_sli": False,
        "pass_targets": [{"criteria": "<600", "target_value": 600, "violated": False}],
        "warning_targets": None,
    },
]


async def _create_asset(session: AsyncSession, name: str) -> uuid.UUID:
    type_name = f"vm-{uuid.uuid4().hex[:8]}"
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(Asset(id=asset_id, name=name, type_name=type_name))
    await session.flush()
    return asset_id


@pytest.mark.integration
async def test_trend_returns_points_with_baseline(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session, "trend-asset")
    repo = EvaluationRepository(db_session)
    sli_repo = SLIValueRepository(db_session)
    trend_repo = TrendRepository(db_session)

    ev = await repo.create_pending(
        evaluation_name="trend-test",
        period_start=_BASE,
        period_end=_BASE + timedelta(minutes=30),
        ingestion_mode="push",
        asset_snapshot={"name": "trend-asset", "tags": {}},
        metadata={},
        asset_id=asset_id,
        slo_name="test-slo",
    )
    await repo.mark_completed(
        ev.id, result="pass", score=90.0, indicator_results=_INDICATORS, slo_name="test-slo"
    )

    # Seed SLI value for the join
    await sli_repo.write_sli_values([{
        "eval_id": ev.id,
        "eval_start": _BASE,
        "metric_name": "response_time",
        "aggregation": "avg",
        "value": 250.0,
        "asset_name": "trend-asset",
        "evaluation_name": "trend-test",
        "os_tag": None,
    }])

    points = await trend_repo.get_trend_by_domain(
        asset_id=asset_id, slo_name="test-slo", metric_name="response_time", limit=50
    )
    assert len(points) == 1
    assert points[0]["value"] == 250.0
    assert points[0]["baseline"] == 200.0  # from indicator_results compared_value


@pytest.mark.integration
async def test_trend_excludes_invalidated(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session, "trend-inv-asset")
    repo = EvaluationRepository(db_session)
    sli_repo = SLIValueRepository(db_session)
    trend_repo = TrendRepository(db_session)

    ev = await repo.create_pending(
        evaluation_name="trend-inv",
        period_start=_BASE,
        period_end=_BASE + timedelta(minutes=30),
        ingestion_mode="push",
        asset_snapshot={"name": "trend-inv-asset", "tags": {}},
        metadata={},
        asset_id=asset_id,
        slo_name="test-slo",
    )
    await repo.mark_completed(
        ev.id, result="pass", score=90.0, indicator_results=_INDICATORS, slo_name="test-slo"
    )
    await sli_repo.write_sli_values([{
        "eval_id": ev.id,
        "eval_start": _BASE,
        "metric_name": "response_time",
        "aggregation": "avg",
        "value": 250.0,
        "asset_name": "trend-inv-asset",
        "evaluation_name": "trend-inv",
        "os_tag": None,
    }])

    await repo.invalidate(ev.id, note="bad")

    points = await trend_repo.get_trend_by_domain(
        asset_id=asset_id, slo_name="test-slo", metric_name="response_time", limit=50
    )
    assert len(points) == 0
```

- [ ] **Step 3: Run tests**

Run: `uv run --directory api pytest api/tests/db/test_heatmap_query.py api/tests/db/test_trend_query.py -v`

Expected: All PASS. If `TrendRepository` import path differs, check `api/app/modules/quality_gate/trend_repository.py` for the class name.

- [ ] **Step 4: Commit**

```
git add api/tests/db/test_heatmap_query.py api/tests/db/test_trend_query.py
git commit -m "test: add heatmap and trend query integration tests"
```

---

### Task 10: Baseline query round-trip tests

**Files:**
- Create: `api/tests/db/test_baseline_query.py`

Tests the `BaselineRepository.get_evaluation_baselines()` method to verify it returns only eligible evaluations, excludes invalidated ones, and uses overridden results.

- [ ] **Step 1: Write baseline query tests**

```python
"""Integration tests for baseline query — verifies which evaluations are eligible as baselines."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.db.models import Asset, AssetType
from app.modules.quality_gate.baseline_repository import BaselineRepository
from app.modules.quality_gate.repository import EvaluationRepository
from sqlalchemy.ext.asyncio import AsyncSession

_BASE = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)


async def _create_asset(session: AsyncSession, name: str) -> uuid.UUID:
    type_name = f"vm-{uuid.uuid4().hex[:8]}"
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(Asset(id=asset_id, name=name, type_name=type_name))
    await session.flush()
    return asset_id


async def _create_eval(
    session: AsyncSession,
    repo: EvaluationRepository,
    asset_id: uuid.UUID,
    *,
    result: str = "pass",
    score: float = 90.0,
    offset_hours: int = 0,
) -> uuid.UUID:
    start = _BASE + timedelta(hours=offset_hours)
    ev = await repo.create_pending(
        evaluation_name="baseline-test",
        period_start=start,
        period_end=start + timedelta(minutes=30),
        ingestion_mode="push",
        asset_snapshot={"name": "baseline-asset", "tags": {}},
        metadata={},
        asset_id=asset_id,
        slo_name="test-slo",
    )
    await repo.mark_completed(ev.id, result=result, score=score, indicator_results=[], slo_name="test-slo")
    return ev.id


@pytest.mark.integration
async def test_baselines_exclude_invalidated(db_session: AsyncSession) -> None:
    """Invalidated evaluations must not appear in baseline results."""
    asset_id = await _create_asset(db_session, "bl-inv")
    repo = EvaluationRepository(db_session)
    bl_repo = BaselineRepository(db_session)

    ev1 = await _create_eval(db_session, repo, asset_id, result="pass", offset_hours=0)
    ev2 = await _create_eval(db_session, repo, asset_id, result="pass", offset_hours=1)
    await repo.invalidate(ev1, note="bad data")

    baselines = await bl_repo.get_evaluation_baselines(
        asset_id=asset_id,
        slo_name="test-slo",
        period_start_before=_BASE + timedelta(hours=3),
        include_result_with_score="all",
        limit=10,
    )
    baseline_ids = [b.id for b in baselines]
    assert ev1 not in baseline_ids
    assert ev2 in baseline_ids


@pytest.mark.integration
async def test_baselines_return_pass_only(db_session: AsyncSession) -> None:
    """When include_result_with_score='pass', only passing evals returned."""
    asset_id = await _create_asset(db_session, "bl-pass")
    repo = EvaluationRepository(db_session)
    bl_repo = BaselineRepository(db_session)

    await _create_eval(db_session, repo, asset_id, result="pass", offset_hours=0)
    await _create_eval(db_session, repo, asset_id, result="fail", offset_hours=1)
    await _create_eval(db_session, repo, asset_id, result="warning", offset_hours=2)

    baselines = await bl_repo.get_evaluation_baselines(
        asset_id=asset_id,
        slo_name="test-slo",
        period_start_before=_BASE + timedelta(hours=4),
        include_result_with_score="pass",
        limit=10,
    )
    assert all(b.result == "pass" for b in baselines)
    assert len(baselines) == 1
```

- [ ] **Step 2: Run tests**

Run: `uv run --directory api pytest api/tests/db/test_baseline_query.py -v`

Expected: All PASS

- [ ] **Step 3: Commit**

```
git add api/tests/db/test_baseline_query.py
git commit -m "test: add baseline query round-trip tests"
```

---

### Task 11: Heatmap router-level transformation tests

**Files:**
- Create: `api/tests/endpoints/test_heatmap_endpoints.py`

Tests that the router correctly transforms invalidated and overridden evaluations in the heatmap response. The repository returns raw data; the router (lines 155-163) transforms `result` to `"invalidated"` for display.

- [ ] **Step 1: Write heatmap endpoint tests**

```python
"""Endpoint tests for heatmap result transformation (router-level)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import _create_asset, _create_completed_eval, _START

_INDICATORS = [
    {
        "metric": "cpu_usage",
        "display_name": "CPU Usage",
        "value": 72.0,
        "compared_value": None,
        "change_absolute": None,
        "change_relative_pct": None,
        "status": "pass",
        "score": 1.0,
        "weight": 1,
        "key_sli": False,
        "pass_targets": [{"criteria": "<80", "target_value": 80, "violated": False}],
        "warning_targets": None,
    },
]


@pytest.mark.integration
async def test_heatmap_invalidated_eval_shows_invalidated_result(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Router transforms invalidated completed eval cells to result='invalidated'."""
    asset_id = await _create_asset(db_session, name="hm-router-inv")
    eval_id = await _create_completed_eval(
        db_session, asset_id,
        result="pass", score=90.0,
        indicator_results=_INDICATORS,
    )

    # Invalidate via endpoint
    await async_client.patch(
        f"/evaluations/{eval_id}/invalidate",
        json={"invalidation_note": "bad data"},
    )

    # Fetch heatmap — the router should show "invalidated" not "pass"
    resp = await async_client.get(
        "/evaluations/metric-heatmap",
        params={"asset_name": "hm-router-inv"},
    )
    assert resp.status_code == 200
    cells = resp.json()["cells"]
    assert len(cells) >= 1
    assert all(c["result"] == "invalidated" for c in cells)


@pytest.mark.integration
async def test_heatmap_overridden_eval_shows_overridden_result(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Overridden evaluation cells show the overridden result in heatmap."""
    asset_id = await _create_asset(db_session, name="hm-router-ovr")
    eval_id = await _create_completed_eval(
        db_session, asset_id,
        result="fail", score=30.0,
        indicator_results=_INDICATORS,
    )

    # Override via endpoint: fail → pass
    await async_client.patch(
        f"/evaluations/{eval_id}/override-status",
        json={"new_result": "pass", "reason": "false alarm", "author": "alice"},
    )

    resp = await async_client.get(
        "/evaluations/metric-heatmap",
        params={"asset_name": "hm-router-ovr"},
    )
    assert resp.status_code == 200
    cells = resp.json()["cells"]
    # Router uses ev.result (overridden) when ev.original_result is not None
    assert len(cells) >= 1
    assert all(c["result"] == "pass" for c in cells)
```

- [ ] **Step 2: Run tests**

Run: `uv run --directory api pytest api/tests/endpoints/test_heatmap_endpoints.py -v`

Expected: All PASS

- [ ] **Step 3: Commit**

```
git add api/tests/endpoints/test_heatmap_endpoints.py
git commit -m "test: add heatmap router transformation endpoint tests"
```

---

### Task 12: Presenter edge case tests

**Files:**
- Modify: `api/tests/services/test_presenter.py`

Add edge case tests to the existing file using its existing `_make_evaluation` and `_make_annotation` helpers.

- [ ] **Step 1: Read existing helpers**

Read `api/tests/services/test_presenter.py` to understand the exact signature of `_make_evaluation` and `_make_annotation`. Verify the helper signatures match what the tests below expect.

Key facts about `_make_evaluation`:
- Accepts: `result`, `score`, `invalidated`, `original_result`, `indicator_results`, `job_stats`, `annotations`
- Does NOT accept: `override_reason`, `override_author` (these are hardcoded to `None` in the SimpleNamespace)
- `job_stats=None` is normalized to `{}` by the helper (`job_stats=job_stats or {}`)

- [ ] **Step 2: Add edge case tests**

Add `timedelta` to the existing `datetime` import at the top of the file (line 6: `from datetime import UTC, datetime` → `from datetime import UTC, datetime, timedelta`).

Append to `api/tests/services/test_presenter.py`:

```python
def test_build_detail_empty_indicator_results():
    ev = _make_evaluation(indicator_results=[])
    detail = build_detail(ev)
    assert detail.indicator_results == []
    assert detail.top_failures == []


def test_build_summary_no_pass_targets_in_failure():
    """Failing indicator without pass_targets → threshold defaults to empty string."""
    ev = _make_evaluation(indicator_results=[
        {"metric": "cpu", "display_name": "CPU", "value": 99.0, "compared_value": None,
         "change_absolute": None, "change_relative_pct": None, "status": "fail",
         "score": 0.0, "weight": 1, "key_sli": False,
         "pass_targets": None, "warning_targets": None},
    ])
    summary = build_summary(ev, annotation_count=0, latest_ann=None)
    assert len(summary.top_failures) == 1
    assert summary.top_failures[0].threshold == ""


def test_build_detail_null_job_stats():
    """When job_stats is None, original_score is None and compared_evaluation_ids is empty."""
    ev = _make_evaluation()
    ev.job_stats = None  # bypass helper normalization to test true None path
    detail = build_detail(ev)
    assert detail.original_score is None
    assert detail.compared_evaluation_ids == []


def test_build_detail_combined_invalidated_and_overridden():
    """Both invalidated and override fields can coexist."""
    ev = _make_evaluation(
        invalidated=True,
        original_result="fail",
        result="pass",
    )
    # Set override fields directly — helper doesn't accept these as kwargs
    ev.override_reason = "Overridden before invalidation"
    ev.override_author = "alice"
    detail = build_detail(ev)
    assert detail.invalidated is True
    assert detail.original_result == "fail"
    assert detail.result == "pass"
    assert detail.override_author == "alice"


def test_build_detail_annotations_sorted_by_created_at():
    """Annotations in detail response must be sorted by created_at ascending."""
    ann_old = _make_annotation("First", "general")
    ann_old.created_at = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
    ann_new = _make_annotation("Second", "general")
    ann_new.created_at = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)
    ann_mid = _make_annotation("Middle", "general")
    ann_mid.created_at = datetime(2026, 3, 15, 11, 0, 0, tzinfo=UTC)

    ev = _make_evaluation(annotations=[ann_new, ann_old, ann_mid])
    detail = build_detail(ev)
    assert [a.content for a in detail.annotations] == ["First", "Middle", "Second"]


def test_build_detail_latest_annotation_is_most_recent():
    """latest_annotation in detail should be the most recent visible annotation."""
    ann_old = _make_annotation("Old", "general")
    ann_old.created_at = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
    ann_new = _make_annotation("New", "general")
    ann_new.created_at = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)

    ev = _make_evaluation(annotations=[ann_old, ann_new])
    detail = build_detail(ev)
    assert detail.latest_annotation is not None
    assert detail.latest_annotation.content == "New"
```

- [ ] **Step 3: Run tests**

Run: `uv run --directory api pytest api/tests/services/test_presenter.py -v`

Expected: All PASS (including existing tests)

- [ ] **Step 4: Commit**

```
git add api/tests/services/test_presenter.py
git commit -m "test: add presenter edge case tests"
```

---

### Task 13: UI mutation flow tests

**Files:**
- Modify: `ui/src/features/evaluations/components/EvaluationActions.test.tsx`
- Modify: `ui/src/features/evaluations/components/AnnotationForm.test.tsx`

Add tests that verify mutation submission (not just form rendering). The existing tests mock hooks to return `vi.fn()` mutators — the new tests verify that submitting the form calls the mutate function with correct arguments.

- [ ] **Step 1: Read existing test files**

Read `ui/src/features/evaluations/components/EvaluationActions.test.tsx` and `ui/src/features/evaluations/components/AnnotationForm.test.tsx` to understand the current mock patterns and component props.

Also read the actual components:
- `ui/src/features/evaluations/components/EvaluationActions.tsx` — for form field names and submit behavior
- `ui/src/features/evaluations/hooks.ts` — for mutation function signatures

- [ ] **Step 2: Add mutation submission tests to EvaluationActions.test.tsx**

Append tests to the existing `describe('EvaluationActionForm', ...)` block:

```typescript
  it('calls invalidate mutation on form submit', async () => {
    const mutateFn = vi.fn()
    vi.mocked(useInvalidateEvaluation).mockReturnValue({ mutate: mutateFn, isPending: false } as any)

    renderWithQuery(
      <EvaluationActionForm
        evalId="e1"
        currentResult="pass"
        activeAction="invalidate"
        onClose={vi.fn()}
      />,
    )
    fireEvent.change(screen.getByPlaceholderText('Reason…'), { target: { value: 'Bad data' } })
    fireEvent.click(screen.getByRole('button', { name: /invalidate/i }))
    expect(mutateFn).toHaveBeenCalled()
  })

  it('calls override mutation on form submit', async () => {
    const mutateFn = vi.fn()
    vi.mocked(useOverrideStatus).mockReturnValue({ mutate: mutateFn, isPending: false } as any)

    renderWithQuery(
      <EvaluationActionForm
        evalId="e1"
        currentResult="pass"
        activeAction="override"
        onClose={vi.fn()}
      />,
    )
    fireEvent.change(screen.getByPlaceholderText('Reason…'), { target: { value: 'Override reason' } })
    fireEvent.click(screen.getByRole('button', { name: /mark as failure/i }))
    expect(mutateFn).toHaveBeenCalled()
  })
```

Note: The exact button text and mock import depends on the component implementation. Read the component source first (Step 1) and adjust selector text and mock setup accordingly.

- [ ] **Step 3: Add annotation submit test to AnnotationForm.test.tsx**

Append a test that fills in the annotation form and submits:

```typescript
  it('calls addAnnotation mutation on form submit', async () => {
    const mutateFn = vi.fn()
    vi.mocked(useAddAnnotation).mockReturnValue({ mutate: mutateFn, isPending: false } as any)

    renderWithQuery(<AnnotationSection evalId="e1" annotations={[]} />)

    // Open form
    fireEvent.click(screen.getByText('+ Note'))
    // Fill content
    fireEvent.change(screen.getByPlaceholderText('Note content...'), {
      target: { value: 'Test annotation' },
    })
    // Submit
    fireEvent.click(screen.getByText('Add Note'))
    expect(mutateFn).toHaveBeenCalled()
  })
```

Note: Adjust selectors based on actual component implementation found in Step 1.

- [ ] **Step 4: Run UI tests**

Run: `cd ui && npx vitest run src/features/evaluations/components/EvaluationActions.test.tsx src/features/evaluations/components/AnnotationForm.test.tsx`

Expected: All PASS

- [ ] **Step 5: Commit**

```
git add ui/src/features/evaluations/components/EvaluationActions.test.tsx
git add ui/src/features/evaluations/components/AnnotationForm.test.tsx
git commit -m "test: add UI mutation flow tests for eval actions and annotations"
```

---

### Task 14: AssetHeatmap component tests

**Files:**
- Create: `ui/src/features/navigator/components/AssetHeatmap.test.tsx`

New test file for the `AssetHeatmap` component. Tests cover invalidated cell display, overridden evaluation result color, and empty indicator results.

- [ ] **Step 1: Read component dependencies**

Read:
- `ui/src/features/navigator/components/AssetHeatmap.tsx` — component props and rendering logic
- `ui/src/features/navigator/utils.ts` — `buildAssetHeatmapData` function
- `ui/src/features/navigator/types.ts` — `MetricHeatmapResponse`, `HeatmapCell` types
- `ui/src/components/charts/HeatmapChart.tsx` — underlying chart component

- [ ] **Step 2: Write AssetHeatmap tests**

Create `ui/src/features/navigator/components/AssetHeatmap.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AssetHeatmap } from './AssetHeatmap'
import type { MetricHeatmapResponse } from '../types'

// Mock theme context
vi.mock('@/lib/theme-context', () => ({
  useTheme: () => ({ theme: 'forest' }),
}))

// Mock the chart component to inspect what data AssetHeatmap passes to it
vi.mock('@/components/charts/HeatmapChart', () => ({
  HeatmapChart: (props: any) => (
    <div data-testid="heatmap-chart">
      {JSON.stringify(props.cells)}
    </div>
  ),
}))

vi.mock('@/components/charts/NoteIndicatorRow', () => ({
  NoteIndicatorRow: () => null,
}))

const baseMockData: MetricHeatmapResponse = {
  asset_name: 'test-asset',
  slots: ['2026-03-15T10:00:00Z'],
  metrics: [{ name: 'cpu_usage', display_name: 'CPU Usage' }],
  cells: [
    {
      slot: '2026-03-15T10:00:00Z',
      metric: 'cpu_usage',
      display_name: 'CPU Usage',
      result: 'pass',
      score: 1.0,
      eval_id: 'e1',
    },
  ],
}

describe('AssetHeatmap', () => {
  it('renders heatmap chart with provided data', () => {
    render(<AssetHeatmap data={baseMockData} />)
    expect(screen.getByTestId('heatmap-chart')).toBeInTheDocument()
  })

  it('passes invalidated result through to chart', () => {
    const data: MetricHeatmapResponse = {
      ...baseMockData,
      cells: [{ ...baseMockData.cells[0], result: 'invalidated' }],
    }
    render(<AssetHeatmap data={data} />)
    const chart = screen.getByTestId('heatmap-chart')
    expect(chart.textContent).toContain('invalidated')
  })

  it('handles empty cells array', () => {
    const data: MetricHeatmapResponse = {
      ...baseMockData,
      cells: [],
      slots: [],
      metrics: [],
    }
    render(<AssetHeatmap data={data} />)
    expect(screen.getByTestId('heatmap-chart')).toBeInTheDocument()
  })
})
```

Note: Adjust mock patterns based on what Step 1 reveals about the component's dependencies.

- [ ] **Step 3: Run test**

Run: `cd ui && npx vitest run src/features/navigator/components/AssetHeatmap.test.tsx`

Expected: PASS

- [ ] **Step 4: Commit**

```
git add ui/src/features/navigator/components/AssetHeatmap.test.tsx
git commit -m "test: add AssetHeatmap component tests"
```

---

### Task 15: Run full suite and verify

This is a verification task — no new code.

- [ ] **Step 1: Run all backend unit tests**

Run: `uv run --directory api pytest api/tests/ -m "not integration" -v`

Expected: All unit tests pass

- [ ] **Step 2: Run all backend integration tests**

Run: `uv run --directory api pytest api/tests/ -m integration -v`

Expected: All integration tests pass (requires test infra running via `./start_test_infra.sh`)

- [ ] **Step 3: Run UI tests**

Run: `cd ui && npx vitest run`

Expected: All UI tests pass

- [ ] **Step 4: Lint and type check**

Run: `uv run ruff check api/`
Run: `uv run mypy api/app`

Expected: Clean
