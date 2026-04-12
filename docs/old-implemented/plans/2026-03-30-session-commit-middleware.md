# Session Commit Middleware Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the read-after-write race condition by moving session commit before the HTTP response via ASGI middleware.

**Architecture:** Pure ASGI middleware intercepts the `send` callback, committing the session before response headers leave the server. `get_session` becomes a plain function that reads from `request.state`. All repositories continue using `flush()`.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2 async, Starlette ASGI types

**Spec:** `docs/superpowers/specs/2026-03-29-session-commit-middleware-design.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `api/app/db/middleware.py` | Create | ASGI middleware — session lifecycle (create, commit, rollback, close) |
| `api/app/db/session.py` | Modify | `get_session` becomes plain function reading `request.state.session` |
| `api/app/main.py` | Modify | Register `SessionMiddleware` |
| `api/app/modules/quality_gate/annotation_repository.py` | Modify | Revert hotfix: `commit()` → `flush()` |
| `api/tests/test_session_middleware.py` | Create | Unit tests for middleware behavior |

---

### Task 1: Create SessionMiddleware with tests

**Files:**
- Create: `api/tests/test_session_middleware.py`
- Create: `api/app/db/middleware.py`

- [ ] **Step 1: Write failing tests for the middleware**

Create `api/tests/test_session_middleware.py`:

```python
"""Tests for the session commit middleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, call

import pytest

from app.db.middleware import SessionMiddleware


def _make_mock_session():
    """Build a mock AsyncSession with commit/rollback/close."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


def _make_mock_factory(session):
    """Return a callable that returns the mock session."""
    return lambda: session


async def _make_asgi_app(*, raise_error: Exception | None = None):
    """Build a trivial ASGI app that sends a complete HTTP response.

    If raise_error is set, the app raises that exception instead of responding.
    """

    async def app(scope, receive, send):
        if raise_error is not None:
            raise raise_error
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'ok'})

    return app


@pytest.mark.asyncio
async def test_commit_called_before_response_headers():
    """Session is committed before http.response.start reaches the client."""
    session = _make_mock_session()
    inner_app = await _make_asgi_app()
    middleware = SessionMiddleware(inner_app, session_factory=_make_mock_factory(session))

    sent_messages: list[dict] = []

    async def mock_send(message):
        sent_messages.append(message)

    scope = {'type': 'http', 'state': {}}
    await middleware(scope, AsyncMock(), mock_send)

    session.commit.assert_awaited_once()
    session.close.assert_awaited_once()
    session.rollback.assert_not_awaited()
    assert len(sent_messages) == 2
    assert sent_messages[0]['type'] == 'http.response.start'


@pytest.mark.asyncio
async def test_rollback_on_endpoint_error():
    """Session is rolled back when the inner app raises an exception."""
    session = _make_mock_session()
    inner_app = await _make_asgi_app(raise_error=ValueError('boom'))
    middleware = SessionMiddleware(inner_app, session_factory=_make_mock_factory(session))

    scope = {'type': 'http', 'state': {}}
    with pytest.raises(ValueError, match='boom'):
        await middleware(scope, AsyncMock(), AsyncMock())

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_session_stored_in_scope_state():
    """Middleware stores the session in scope['state']['session']."""
    session = _make_mock_session()
    captured_scope: dict = {}

    async def capturing_app(scope, receive, send):
        captured_scope.update(scope)
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})

    middleware = SessionMiddleware(capturing_app, session_factory=_make_mock_factory(session))
    scope = {'type': 'http', 'state': {}}
    await middleware(scope, AsyncMock(), AsyncMock())

    assert captured_scope['state']['session'] is session


@pytest.mark.asyncio
async def test_non_http_requests_pass_through():
    """Non-HTTP scopes (websocket, lifespan) skip session creation entirely."""
    session = _make_mock_session()
    inner_called = False

    async def inner_app(scope, receive, send):
        nonlocal inner_called
        inner_called = True

    middleware = SessionMiddleware(inner_app, session_factory=_make_mock_factory(session))
    scope = {'type': 'lifespan'}
    await middleware(scope, AsyncMock(), AsyncMock())

    assert inner_called
    session.commit.assert_not_awaited()
    session.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_session_closed_even_on_commit_failure():
    """Session is always closed, even if commit raises."""
    session = _make_mock_session()
    session.commit = AsyncMock(side_effect=RuntimeError('db gone'))

    async def app(scope, receive, send):
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})

    middleware = SessionMiddleware(app, session_factory=_make_mock_factory(session))
    scope = {'type': 'http', 'state': {}}

    with pytest.raises(RuntimeError, match='db gone'):
        await middleware(scope, AsyncMock(), AsyncMock())

    session.close.assert_awaited_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/api-test.sh --tail 10 tests/test_session_middleware.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.db.middleware'`

- [ ] **Step 3: Implement the middleware**

Create `api/app/db/middleware.py`:

```python
"""ASGI middleware for per-request database session lifecycle."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class SessionMiddleware:
    """Create a DB session per HTTP request, commit before the response is sent.

    Wraps the ASGI ``send`` callable so that ``session.commit()`` runs before
    ``http.response.start`` reaches the client.  On error the session is rolled
    back instead.  The session is always closed in a ``finally`` block.

    Non-HTTP scopes (WebSocket, lifespan) pass through untouched.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.app = app
        self.factory = session_factory

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        session: AsyncSession = self.factory()
        scope.setdefault('state', {})['session'] = session

        async def _commit_then_send(message: Message) -> None:
            if message['type'] == 'http.response.start':
                await session.commit()
            await send(message)

        try:
            await self.app(scope, receive, _commit_then_send)
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/api-test.sh --tail 10 tests/test_session_middleware.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add api/app/db/middleware.py api/tests/test_session_middleware.py
git commit -m "feat: add ASGI session middleware with commit-before-response"
```

---

### Task 2: Update get_session to read from request.state

**Files:**
- Modify: `api/app/db/session.py:1-59`

- [ ] **Step 1: Update get_session**

Replace the entire `get_session` function (lines 42–58) in `api/app/db/session.py`. Also update imports — remove `AsyncGenerator`, add `Request`:

Full file after changes:

```python
"""Async SQLAlchemy session factory and FastAPI session dependency."""

from __future__ import annotations

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine:
    """Return the shared async engine, creating it on first call."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database.async_url,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            echo=False,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the shared session factory, creating it on first call."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            _get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _session_factory


async def get_session(request: Request) -> AsyncSession:
    """Return the per-request session created by SessionMiddleware."""
    return request.state.session
```

- [ ] **Step 2: Run existing unit tests to check for regressions**

Run: `./scripts/api-test.sh --tail 10 tests/test_session_middleware.py tests/test_qg_router.py tests/test_db_imports.py -v`
Expected: all pass. The `dependency_overrides[get_session]` in test files replaces the callable entirely, so the new signature doesn't affect test overrides.

- [ ] **Step 3: Commit**

```bash
git add api/app/db/session.py
git commit -m "refactor: simplify get_session to read from request.state"
```

---

### Task 3: Register middleware in main.py

**Files:**
- Modify: `api/app/main.py:1-75`

- [ ] **Step 1: Add middleware registration**

Add two imports and one registration line to `api/app/main.py`.

Add to imports (after the existing `from app.db.session` line or among the `app.*` imports):

```python
from app.db.middleware import SessionMiddleware
from app.db.session import get_session_factory
```

Add after the `app = FastAPI(...)` line (line 46), before the exception handlers:

```python
app.add_middleware(SessionMiddleware, session_factory=get_session_factory())
```

Note: Starlette's `add_middleware` passes `session_factory` as a keyword argument to `SessionMiddleware.__init__`, and injects `app` as the first positional argument automatically.

- [ ] **Step 2: Run unit and integration tests**

Run: `./scripts/api-test.sh --tail 10 -v`
Expected: all unit tests pass.

Run integration tests if the test environment is available:
```bash
./scripts/api-test.sh --tail 10 -m integration -v
```

- [ ] **Step 3: Commit**

```bash
git add api/app/main.py
git commit -m "feat: register SessionMiddleware for commit-before-response"
```

---

### Task 4: Revert annotation repository hotfix

**Files:**
- Modify: `api/app/modules/quality_gate/annotation_repository.py:52,88,117`

- [ ] **Step 1: Change commit() back to flush() in three methods**

In `api/app/modules/quality_gate/annotation_repository.py`, make these three changes:

Line 52 — `add_annotation`:
```python
# before:
        await self._session.commit()
# after:
        await self._session.flush()
```

Line 88 — `update_annotation`:
```python
# before:
            await self._session.commit()
# after:
            await self._session.flush()
```

Line 117 — `hide_annotation`:
```python
# before:
        await self._session.commit()
# after:
        await self._session.flush()
```

- [ ] **Step 2: Verify no commit() calls remain in any repository**

Run: `grep -rn "session.commit()" api/app/modules/`
Expected: zero results. All repositories now use `flush()` only.

- [ ] **Step 3: Run full test suite**

Run: `./scripts/api-test.sh --tail 10 -v`
Expected: all pass.

If integration test environment is available:
```bash
./scripts/api-test.sh --tail 10 -m integration -v
```

- [ ] **Step 4: Commit**

```bash
git add api/app/modules/quality_gate/annotation_repository.py
git commit -m "fix: revert annotation hotfix — middleware handles commit"
```

---

### Task 5: Run lint and typecheck

**Files:** none (verification only)

- [ ] **Step 1: Run ruff linter**

Run: `uv run ruff check api/app/db/middleware.py api/app/db/session.py api/app/main.py api/app/modules/quality_gate/annotation_repository.py api/tests/test_session_middleware.py`
Expected: no errors. Fix any issues before proceeding.

- [ ] **Step 2: Run mypy**

Run: `uv run mypy api/app/db/middleware.py api/app/db/session.py api/app/main.py`
Expected: no errors.

- [ ] **Step 3: Run full check suite**

Run: `just check`
Expected: all pass.

- [ ] **Step 4: Commit any lint/type fixes if needed**

```bash
git add -u
git commit -m "style: fix lint and type issues from middleware changes"
```
