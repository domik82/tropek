# arq Pool Lifespan Management

**Date:** 2026-03-17
**Status:** Approved

## Problem

The current implementation lazily initialises the arq connection pool as a module-level global in
`api/app/queue.py`. This has three defects:

1. Redis misconfiguration surfaces at the first POST, not at startup (no fail-fast).
2. The pool is never explicitly closed, leaving connections dangling on shutdown.
3. The global mutable state is hard to override in tests.

The `arq` CLI worker also fails to start because `app.queue` is not on `sys.path` when launched via
`uv run --directory api arq app.queue.WorkerSettings`.

## Design

### Lifespan — `api/app/main.py`

A FastAPI `lifespan` async context manager replaces the lazy init pattern. It creates the arq pool
at startup using `_redis_settings()` (imported from `queue.py`), stores it on `app.state.arq_pool`,
and explicitly closes it on shutdown.

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.arq_pool = await create_pool(_redis_settings())
    yield
    await app.state.arq_pool.close()

app = FastAPI(..., lifespan=lifespan)
```

### Dependency — `api/app/queue.py`

The module-level `_pool` global, `get_arq_pool()`, and `enqueue_evaluation()` helpers are removed.
`queue.py` retains only: `_redis_settings()`, `run_evaluation_job()`, and `WorkerSettings`.

A new dependency function is added:

```python
def get_arq_pool(request: Request) -> ArqRedis:
    return request.app.state.arq_pool
```

### Router — `api/app/modules/quality_gate/router.py`

Both `trigger_evaluation` and `trigger_batch` gain a new parameter:

```python
arq_pool: ArqRedis = Depends(get_arq_pool)
```

They enqueue directly:

```python
await arq_pool.enqueue_job("run_evaluation_job", str(ev.id))
```

The `enqueue_evaluation` import is removed.

### E2E Script — `scripts/integration-test.sh`

The worker launch command gains `PYTHONPATH=.` so `app.queue` is importable:

```bash
PYTHONPATH=. uv run --directory api arq app.queue.WorkerSettings &
```

## Files Changed

| File | Change |
|---|---|
| `api/app/main.py` | Add lifespan; import `create_pool`, `_redis_settings` from `queue` |
| `api/app/queue.py` | Remove global pool / lazy helpers; add `get_arq_pool` dependency |
| `api/app/modules/quality_gate/router.py` | Inject `arq_pool` via `Depends(get_arq_pool)`; enqueue directly |
| `scripts/integration-test.sh` | Prefix worker launch with `PYTHONPATH=.` |

## Implementation Notes

**`WorkerSettings.redis_settings` runs at import time.** The class-body assignment
`redis_settings = _redis_settings()` is intentionally left unchanged — it executes when `queue.py`
is first imported by the arq worker process. This is existing behaviour; the environment variables
(`QG_REDIS_*`) must be set before the worker starts (the E2E script exports them before launching
the worker).

**Test override pattern.** Any future router test that exercises the trigger endpoints should
override the pool dependency rather than rely on a live Redis connection:
```python
app.dependency_overrides[get_arq_pool] = lambda: mock_pool
```

## Testing

Unit tests are unaffected (they don't touch the router or queue module). The E2E script
(`scripts/integration-test.sh`) is the acceptance test — a successful run through all steps
(single eval completes, batch completes, pin/override/restore pass) confirms the change works.
