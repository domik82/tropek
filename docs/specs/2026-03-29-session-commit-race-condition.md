# Session Commit Race Condition — Specification

## Problem Statement

FastAPI's yield dependency cleanup runs **after** the HTTP response is sent to the client. This means `session.commit()` in `get_session()` executes after the client already has the response. When a client does a write (POST/PATCH) followed by an immediate read (GET), the read may arrive before the write's session has committed, returning stale data.

This is a **systemic issue** affecting every write endpoint in TROPEK, not just annotations.

## Discovery

Found during e2e test `test_annotations` (Step 13): POST creates annotation (201), GET immediately lists annotations — annotation not found. The annotation was flushed to the DB within the transaction but not committed before the response was sent.

## Root Cause Analysis

### FastAPI/Starlette Lifecycle (Starlette 0.52.1, FastAPI 0.135.1)

The critical code is in `fastapi.routing` (the `request_response` wrapper):

```python
# fastapi/routing.py — simplified from actual source
async def app(scope, receive, send):
    async with AsyncExitStack() as request_stack:          # yield deps register HERE
        scope["fastapi_inner_astack"] = request_stack
        async with AsyncExitStack() as function_stack:
            scope["fastapi_function_astack"] = function_stack
            response = await f(request)                    # endpoint runs, builds Response
        await response(scope, receive, send)               # RESPONSE SENT TO CLIENT
    # request_stack.__aexit__() runs HERE — session.commit() happens NOW
```

Sequence:
1. `function_stack` enters → endpoint resolves dependencies (including `get_session` yield)
2. Endpoint runs → repository calls `session.flush()` (writes to DB within transaction, uncommitted)
3. `function_stack` exits (no yield deps registered here)
4. **Response is sent to client** via `await response(scope, receive, send)`
5. `request_stack` exits → `get_session` generator resumes → **`session.commit()` runs here**

The gap between steps 4 and 5 is the race window.

### Current Session Pattern

```python
# api/app/db/session.py
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session              # FastAPI registers on request_stack
            await session.commit()     # Runs AFTER response is sent
        except Exception:
            await session.rollback()
            raise
```

Session factory config: `expire_on_commit=False` (objects remain usable after commit).

### Repository Pattern

Every repository in the codebase uses `flush()`, never `commit()`:

```python
# Every repo does this:
self._session.add(entity)
await self._session.flush()   # Writes to DB within transaction, but does NOT commit
return entity
```

This pattern relies on `get_session` to commit after the endpoint returns. But since commit happens after the response is sent, any immediate read-after-write from a client hits uncommitted data.

### Why It's Usually Not Visible

Most API patterns return the created/updated object directly from the same request (POST returns the created resource). The client doesn't need to do a separate GET. The annotation e2e test exposed it because it does:
1. `POST /evaluations/{id}/annotations` → returns created annotation
2. `GET /evaluations/{id}/annotations` → expects to find it in the list

Other potential exposure points (not yet failing but vulnerable):
- Any UI optimistic update that falls back to a refetch
- Webhook/callback systems that read back after a write notification
- Any sequential API calls in scripts or integrations

## Affected Code

### All repositories using `flush()` (comprehensive list)

| File | Methods using `flush()` |
|------|------------------------|
| `api/app/modules/quality_gate/repository.py` | `create_pending`, `store_result`, `update_result`, `update_slo_version`, `set_period` |
| `api/app/modules/quality_gate/indicator_repository.py` | `upsert_rows`, `bulk_upsert` |
| `api/app/modules/assets/repository.py` | `create_asset`, `create_asset_type`, `create_group`, `add_group_member`, `create_slo_binding`, `create_asset_slo_link`, `create_group_slo_link`, and more (~10 methods) |
| `api/app/modules/slo_registry/repository.py` | `create`, `create_version` |
| `api/app/modules/datasource/repository.py` | `create` |
| `api/app/modules/sli_registry/repository.py` | `create` |

### Hotfix already applied

`annotation_repository.py` — changed `flush()` → `commit()` in `add_annotation`, `update_annotation`, `hide_annotation`. This fixes the immediate e2e failure but is inconsistent with the rest of the codebase.

## Constraints

- **Python 3.13, FastAPI 0.135.1, Starlette 0.52.1, SQLAlchemy 2.x async (asyncpg)**
- **`expire_on_commit=False`** is set — objects remain valid after commit
- **No middleware** currently installed (only exception handlers and lifespan)
- **Redis cache invalidation** happens in some repositories after flush — must still work correctly
- **Worker processes** (arq) have their own sessions — not affected by this issue
- **Integration tests** use `httpx.AsyncClient` with ASGI transport (in-process) — they share the event loop so the race doesn't manifest
- **e2e tests** use real HTTP (separate process) — where the race manifests

## Session/Dependency Wiring

```
get_session()                          → yields AsyncSession
    ↓
get_qg_repos(session)                  → QualityGateRepos dataclass
get_asset_repos(session)               → AssetRepos dataclass
get_slo_repos(session)                 → SLORepos dataclass
get_sli_repos(session)                 → SLIRepos dataclass
get_ds_repos(session)                  → DataSourceRepos dataclass
    ↓
Router endpoints receive repo bundles via Depends()
```

All repo bundles share the same session instance per request. The session is the single `Depends(get_session)` at the root.

## Key Files

| File | Role |
|------|------|
| `api/app/db/session.py` | Session factory + `get_session` dependency |
| `api/app/main.py` | FastAPI app setup (no middleware currently) |
| `api/app/modules/quality_gate/dependencies.py` | `QualityGateRepos` wiring |
| `api/app/modules/assets/dependencies.py` | `AssetRepos` wiring |
| `api/app/modules/slo_registry/dependencies.py` | SLO repos wiring |
| `api/app/modules/quality_gate/annotation_repository.py` | Hotfixed (commit instead of flush) |

## Possible Solution Directions

These are starting points for brainstorming, not final decisions:

### A. Middleware-based session management
Replace the yield dependency with ASGI middleware that creates the session, stores it in `request.state`, commits before `await call_next(request)` returns, and rolls back on error. This guarantees commit before response.

### B. Commit in all repository write methods
Change every `flush()` to `commit()` across all repositories. Simple but changes transactional semantics — if an endpoint does multiple writes, each becomes independently committed (no atomic rollback of the whole request).

### C. Commit in router endpoints before returning
Add `await repos.session.commit()` at the end of every mutating endpoint. Preserves the flush-only pattern in repositories (allowing multi-step transactions) while ensuring commit before response.

### D. Custom dependency that commits on function_stack
Create a dependency that registers its cleanup on `fastapi_function_astack` (which exits before the response is sent) instead of `fastapi_inner_astack`. This would require reaching into FastAPI internals.

### E. Accept the race and handle it in clients
Add retry/polling logic in clients that need read-after-write consistency. Not recommended — pushes complexity to every consumer.

## Success Criteria

- All e2e tests pass without artificial delays
- No read-after-write races for any endpoint
- Consistent pattern across all repositories (no special-casing)
- Transactional integrity preserved (multi-step endpoint operations still atomic)
- Integration tests continue to pass
- No performance regression (unnecessary commits or extra round-trips)
