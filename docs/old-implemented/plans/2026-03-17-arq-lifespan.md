# arq Pool Lifespan Management — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move arq connection pool management into FastAPI's `lifespan` context manager so the pool is created at startup (fail-fast), closed on shutdown, and injected into endpoints as a proper dependency.

**Architecture:** `main.py` owns the pool lifecycle via `lifespan`; `queue.py` exposes a `get_arq_pool(request)` dependency that reads `app.state.arq_pool`; endpoints inject the pool via `Depends(get_arq_pool)`. The module-level global pool and lazy-init helpers are removed.

**Tech Stack:** FastAPI lifespan, arq `create_pool` / `ArqRedis`, `Request.app.state`, `unittest.mock.patch`

---

## Chunk 1: Refactor queue, wire lifespan, fix tests and script

### File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `api/app/queue.py` | Remove `_pool` global, `get_arq_pool()`, `enqueue_evaluation()`; add `get_arq_pool(request)` dependency |
| Modify | `api/app/main.py` | Add `lifespan` context manager; import `create_pool`, `_redis_settings` |
| Modify | `api/app/modules/quality_gate/router.py` | Inject `arq_pool` via `Depends(get_arq_pool)`; enqueue directly; remove `enqueue_evaluation` import |
| Modify | `api/tests/test_qg_router.py` | Patch `create_pool` in fixture; override `get_arq_pool` dependency |
| Modify | `scripts/integration-test.sh` | Add `PYTHONPATH=.` before arq worker launch |

---

### Task 1: Refactor `queue.py`

**Files:**
- Modify: `api/app/queue.py`

- [ ] **Step 1: Replace the file contents**

The new `queue.py` removes the module-level `_pool` global, `get_arq_pool()` pool factory, and
`enqueue_evaluation()` helper. It adds a `get_arq_pool` FastAPI dependency that reads from
`request.app.state`.

```python
"""arq job queue — worker settings and pool dependency."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from arq import create_pool  # noqa: F401 — re-exported for main.py import
from arq.connections import ArqRedis, RedisSettings
from fastapi import Request

from app.config import get_settings
from app.db.session import get_session_factory
from app.modules.quality_gate.worker import run_evaluation


def _redis_settings() -> RedisSettings:
    """Build arq RedisSettings from application config."""
    settings = get_settings()
    pw = settings.cache.password.get_secret_value()
    return RedisSettings(
        host=settings.cache.host,
        port=settings.cache.port,
        password=pw or None,
        database=settings.queue.db_index,
    )


def get_arq_pool(request: Request) -> ArqRedis:
    """FastAPI dependency — returns the arq pool stored on app.state at startup."""
    return request.app.state.arq_pool  # type: ignore[no-any-return]


async def run_evaluation_job(ctx: dict[str, Any], eval_id_str: str) -> None:
    """Arq job function — wraps run_evaluation with a DB session."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            await run_evaluation(session, uuid.UUID(eval_id_str))
            await session.commit()
        except Exception:
            await session.rollback()
            raise


class WorkerSettings:
    """arq worker configuration — discovered by `arq app.queue.WorkerSettings`."""

    functions: ClassVar[list[Any]] = [run_evaluation_job]
    redis_settings = _redis_settings()
```

- [ ] **Step 2: Run linter**

```bash
uv run --directory /mnt/d/DEV/keptn_rewrite/tropek/.worktrees/end-to-end-wiring ruff check api/app/queue.py
```

Expected: `All checks passed!`

- [ ] **Step 3: Run mypy**

```bash
uv run --directory /mnt/d/DEV/keptn_rewrite/tropek/.worktrees/end-to-end-wiring mypy api/app/queue.py
```

Expected: `Success: no issues found`

---

### Task 2: Add lifespan to `main.py`

**Files:**
- Modify: `api/app/main.py`

- [ ] **Step 1: Replace the file contents**

```python
"""TROPEK API — FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.modules.assets.router import router as assets_router
from app.modules.datasource.router import router as datasource_router
from app.modules.quality_gate.router import router as quality_gate_router
from app.modules.sli_registry.router import router as sli_router
from app.modules.slo_registry.router import router as slo_router
from app.queue import _redis_settings, create_pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Open the arq pool at startup; close it on shutdown."""
    app.state.arq_pool = await create_pool(_redis_settings())
    yield
    await app.state.arq_pool.close()


app = FastAPI(title="TROPEK API", version="0.2.0", lifespan=lifespan)

# No prefix= — every router defines full absolute paths
app.include_router(assets_router)
app.include_router(datasource_router)
app.include_router(sli_router)
app.include_router(slo_router)
app.include_router(quality_gate_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok"}
```

- [ ] **Step 2: Run linter + mypy**

```bash
uv run --directory /mnt/d/DEV/keptn_rewrite/tropek/.worktrees/end-to-end-wiring ruff check api/app/main.py
uv run --directory /mnt/d/DEV/keptn_rewrite/tropek/.worktrees/end-to-end-wiring mypy api/app/main.py
```

Expected: both clean.

---

### Task 3: Update `router.py` — inject pool via Depends

**Files:**
- Modify: `api/app/modules/quality_gate/router.py`

- [ ] **Step 1: Replace the `enqueue_evaluation` import with `get_arq_pool` and `ArqRedis`**

Remove this line:
```python
from app.queue import enqueue_evaluation
```

Replace with:
```python
from arq.connections import ArqRedis

from app.queue import get_arq_pool
```

- [ ] **Step 2: Add `arq_pool` parameter to `trigger_evaluation`**

Change the function signature from:
```python
async def trigger_evaluation(
    body: TriggerRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> TriggerResponse:
```

To:
```python
async def trigger_evaluation(
    body: TriggerRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    arq_pool: ArqRedis = Depends(get_arq_pool),  # noqa: B008
) -> TriggerResponse:
```

- [ ] **Step 3: Replace the manual commit + enqueue in `trigger_evaluation`**

Change:
```python
    await session.commit()
    await enqueue_evaluation(ev.id)
    return TriggerResponse(id=ev.id, status="pending")
```

To:
```python
    await session.commit()
    await arq_pool.enqueue_job("run_evaluation_job", str(ev.id))
    return TriggerResponse(id=ev.id, status="pending")
```

- [ ] **Step 4: Add `arq_pool` parameter to `trigger_batch`**

Change the function signature from:
```python
async def trigger_batch(
    body: BatchTriggerRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> BatchTriggerResponse:
```

To:
```python
async def trigger_batch(
    body: BatchTriggerRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    arq_pool: ArqRedis = Depends(get_arq_pool),  # noqa: B008
) -> BatchTriggerResponse:
```

- [ ] **Step 5: Replace the manual commit + enqueue loop in `trigger_batch`**

Change:
```python
    session.add(batch)
    await session.commit()

    for eid in evaluation_ids:
        await enqueue_evaluation(eid)
```

To:
```python
    session.add(batch)
    await session.commit()

    for eid in evaluation_ids:
        await arq_pool.enqueue_job("run_evaluation_job", str(eid))
```

- [ ] **Step 6: Lint + mypy**

```bash
uv run --directory /mnt/d/DEV/keptn_rewrite/tropek/.worktrees/end-to-end-wiring ruff check api/app/modules/quality_gate/router.py
uv run --directory /mnt/d/DEV/keptn_rewrite/tropek/.worktrees/end-to-end-wiring mypy api/app/modules/quality_gate/router.py
```

Expected: both clean.

---

### Task 4: Fix the test fixture

Adding `lifespan` to `main.py` means `TestClient(app)` will try to connect to Redis when running
tests. The fixture must patch `create_pool` to return a mock and override the `get_arq_pool`
dependency to avoid a real Redis connection.

**Files:**
- Modify: `api/tests/test_qg_router.py`

- [ ] **Step 1: Add imports at the top of the file**

Add these imports (keep them grouped with existing ones):
```python
from unittest.mock import AsyncMock, MagicMock, patch

from app.queue import get_arq_pool
```

The file already imports `AsyncMock` and `MagicMock` — just add `patch` to that line and add the
`get_arq_pool` import.

- [ ] **Step 2: Update the `client` fixture**

Replace:
```python
@pytest.fixture
def client():
    app.dependency_overrides[get_session] = _mock_session
    yield TestClient(app)
    app.dependency_overrides.clear()
```

With:
```python
@pytest.fixture
def client():
    mock_pool = AsyncMock()
    app.dependency_overrides[get_session] = _mock_session
    app.dependency_overrides[get_arq_pool] = lambda: mock_pool
    with patch("app.main.create_pool", return_value=mock_pool):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()
```

The `patch` stops lifespan from attempting a real Redis connection. The `dependency_overrides`
entry for `get_arq_pool` ensures any endpoint that calls `Depends(get_arq_pool)` gets the mock
without touching `app.state`.

- [ ] **Step 3: Run existing unit tests — all must pass**

```bash
uv run --directory /mnt/d/DEV/keptn_rewrite/tropek/.worktrees/end-to-end-wiring pytest api/tests/ -m "not integration" -q
```

Expected: 97 passed (same count as before).

---

### Task 5: Fix the E2E script

**Files:**
- Modify: `scripts/integration-test.sh`

- [ ] **Step 1: Add `PYTHONPATH=.` to the arq worker launch line**

Change:
```bash
uv run --directory api arq app.queue.WorkerSettings &
```

To:
```bash
PYTHONPATH=. uv run --directory api arq app.queue.WorkerSettings &
```

`uv run --directory api` sets the working directory to `api/`. `PYTHONPATH=.` adds `api/` to
Python's module search path, making `app.queue` importable.

---

### Task 6: Commit

- [ ] **Step 1: Lint the full changeset**

```bash
uv run --directory /mnt/d/DEV/keptn_rewrite/tropek/.worktrees/end-to-end-wiring ruff check api/app/ api/tests/
```

Expected: `All checks passed!`

- [ ] **Step 2: Run unit tests one final time**

```bash
uv run --directory /mnt/d/DEV/keptn_rewrite/tropek/.worktrees/end-to-end-wiring pytest api/tests/ -m "not integration" -q
```

Expected: all pass.

- [ ] **Step 3: Stage and commit**

```bash
git -C /mnt/d/DEV/keptn_rewrite/tropek/.worktrees/end-to-end-wiring add api/app/queue.py api/app/main.py api/app/modules/quality_gate/router.py api/tests/test_qg_router.py scripts/integration-test.sh
```

```bash
git -C /mnt/d/DEV/keptn_rewrite/tropek/.worktrees/end-to-end-wiring commit -m "refactor: manage arq pool via FastAPI lifespan and Depends injection"
```
