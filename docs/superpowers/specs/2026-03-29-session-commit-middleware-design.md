# Session Commit Middleware — Design Spec

## Problem

FastAPI's yield dependency cleanup runs **after** the HTTP response is sent. TROPEK's
`get_session()` commits in yield cleanup, so `session.commit()` executes after the client
already has the response. A client that does a write followed by an immediate read can hit
uncommitted data.

Discovered via e2e test: POST creates annotation (201), immediate GET returns empty list.
The annotation was flushed but not committed before the response left the server.

See `docs/specs/2026-03-29-session-commit-race-condition.md` for full root cause analysis.

## Solution

Replace the yield-based `get_session` dependency with a pure ASGI middleware that owns the
session lifecycle and commits **before** the response headers are sent to the client.

### Why middleware over alternatives

- **vs. commit in every repo method:** Breaks multi-step atomicity (each flush becomes an
  independent commit).
- **vs. explicit commit in router endpoints:** Requires touching ~30+ write endpoints across
  6 router files, and every future endpoint must remember to commit.
- **Middleware:** 3-4 files changed, zero router/repo changes, impossible to forget on new
  endpoints.

## Architecture

### Middleware (pure ASGI with `send` interception)

```
Request arrives
  → SessionMiddleware creates AsyncSession, stores in scope["state"]["session"]
  → FastAPI resolves dependencies (get_session reads from request.state)
  → Endpoint runs, repositories call flush() (writes to DB within transaction)
  → Response is built
  → send(http.response.start) intercepted → session.commit() runs HERE
  → Response headers + body sent to client
  → session.close() in finally block
```

The key mechanism is wrapping the ASGI `send` callable. When the response is ready to leave
(`http.response.start`), we commit first. If the commit fails, no headers have been sent yet,
so the client gets a proper 500 error.

### Middleware implementation

```python
# api/app/db/middleware.py

class SessionMiddleware:
    """ASGI middleware that manages per-request database sessions.

    Creates an AsyncSession before each HTTP request, commits before the
    response headers are sent, and rolls back on error. This eliminates the
    race condition where yield-based dependency cleanup commits after the
    response has already reached the client.
    """

    def __init__(self, app: ASGIApp, session_factory: async_sessionmaker) -> None:
        self.app = app
        self.factory = session_factory

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        session = self.factory()
        scope.setdefault("state", {})["session"] = session

        async def commit_before_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                await session.commit()
            await send(message)

        try:
            await self.app(scope, receive, commit_before_send)
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

### get_session dependency (simplified)

```python
# api/app/db/session.py — get_session becomes a plain function

async def get_session(request: Request) -> AsyncSession:
    return request.state.session
```

No yield, no commit, no rollback. The middleware owns the lifecycle entirely.
The session factory and engine creation functions remain unchanged.

### Registration

```python
# api/app/main.py — after app creation

app.add_middleware(SessionMiddleware, session_factory=get_session_factory())
```

## Files Changed

| File | Change |
|---|---|
| `api/app/db/middleware.py` | **New** — `SessionMiddleware` (~30 lines) |
| `api/app/db/session.py` | `get_session` becomes plain async function reading `request.state.session` |
| `api/app/main.py` | Register `SessionMiddleware` |
| `api/app/modules/quality_gate/annotation_repository.py` | Revert hotfix: `commit()` → `flush()` in 3 methods |

Zero changes to any other router or repository.

## Edge Cases

**Read-only requests:** `commit()` on a session with no pending changes is a no-op in
SQLAlchemy — no SQL emitted.

**Commit failure:** Happens during `http.response.start` interception, before headers are
sent. The exception propagates through the ASGI stack and FastAPI returns a 500.

**Error responses (4xx/5xx):** When an endpoint raises a domain exception, FastAPI's
exception handlers convert it to a response. That response triggers `commit_before_send`,
but since nothing was flushed, the commit is a no-op.

**Annotation hotfix revert:** `annotation_repository.py` returns to using `flush()` like
all other repositories. Consistency restored.

## Testing

- Existing integration tests (in-process ASGI transport) pass unchanged — the race doesn't
  manifest there.
- E2e tests that exposed the bug (POST then immediate GET) should pass without artificial
  delays.
- Unit tests are unaffected — they don't touch session lifecycle.

## Success Criteria

- All e2e tests pass without artificial delays
- No read-after-write races for any endpoint
- Consistent `flush()` pattern across all repositories
- Multi-step endpoint operations remain atomic (single commit at the end)
- Integration and unit tests continue to pass
- No performance regression
