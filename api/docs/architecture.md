# API Architecture

Concise overview of the TROPEK API backend. For domain-specific detail, see the
linked documents.

## Application Bootstrap

Entry point: `api/tropek/main.py`.

The FastAPI app is created at module level (`app = FastAPI(title='TROPEK API', version='0.2.0')`).
A `lifespan()` async context manager runs at startup:

1. Validates required secrets via `settings.validate_required()` (checks `QG_DB_PASSWORD`,
   `QG_REDIS_PASSWORD`, `QG_SECRET_KEY`)
2. Configures structlog via `configure_logging()`
3. Creates the arq Redis pool (`app.state.arq_pool`)
4. Creates the cache Redis connection wrapped in `RedisCache` (`app.state.cache`)

On shutdown, both Redis connections are closed.

## Middleware Stack

Applied in reverse order (outermost runs first):

| Order | Middleware | File | Purpose |
|-------|-----------|------|---------|
| 1 | `MethodNotAllowedMiddleware` | `modules/common/method_not_allowed.py` | Returns 405 for known paths hit with unsupported methods. Solves Starlette's greedy parameterised route matching. |
| 2 | `SessionMiddleware` | `db/middleware.py` | Creates per-request `AsyncSession`, auto-commits on 2xx, auto-rollbacks on 4xx/5xx or exception, closes in `finally`. |

## Exception Handlers

| Exception | HTTP Status | Source |
|-----------|-------------|--------|
| `NotFoundError` | 404 | `modules/common/exceptions.py` |
| `ConflictError` | 409 | `modules/common/exceptions.py` |
| `DomainValidationError` | 422 | `modules/common/exceptions.py` |
| `IntegrityError` (SQLAlchemy) | 409 | Safety net for uncaught DB constraint violations |

All domain exceptions follow structured formatting: `NotFoundError(entity, name)`,
`ConflictError(entity, name, reason)`. Messages are lowercase, no trailing period.

## Configuration System

Two-tier config: YAML for non-secrets, environment variables for secrets.

- `config.yaml` loaded at module import time into `_yaml` dict
- Secrets use `QG_` prefix (e.g., `QG_DB_PASSWORD`)
- `get_settings()` returns a `@lru_cache` singleton

| Settings Class | Env Prefix | Key Properties |
|----------------|-----------|----------------|
| `DatabaseSettings` | `QG_DB_` | `host`, `port`, `name`, `pool_size`, `max_overflow`, `async_url` |
| `CacheSettings` | `QG_REDIS_` | `backend`, `host`, `port`, `url`, `ttl` (per-endpoint TTLs) |
| `QueueSettings` | -- | `max_jobs`, `max_retries`, `job_timeout_seconds`, sweeper config |
| `ReliabilitySettings` | -- | `adapter_timeout_seconds`, `adapter_retry_attempts`, `stuck_job_threshold_seconds` |
| `AdaptersSettings` | -- | `max_concurrent_queries_per_adapter`, `prometheus` instance |
| `EvaluationSettings` | -- | `async_threshold_metrics` |
| `UISettings` | -- | `max_evaluations`, `page_size`, `data_start_date` |

Full configuration reference: [`docs/architecture/configuration.md`](../../docs/architecture/configuration.md)

## Service Topology

| Service | Port | Role |
|---------|------|------|
| `api` | 8080 | FastAPI REST API |
| `worker` | -- | arq job workers (x4) for async evaluation |
| `adapter-prometheus` | 8081 | Prometheus query adapter |
| `timescaledb` | 5432 | PostgreSQL + TimescaleDB |
| `redis` | 6379 | Job queue + response cache |
| `ui` | 5173 | React SPA (Vite dev server) |

System overview: [`docs/architecture/system-overview.md`](../../docs/architecture/system-overview.md)

## Module Layout

Every domain module follows a consistent structure:

```
modules/{domain}/
  router.py       -- FastAPI endpoint handlers
  repository.py   -- Database access (async SQLAlchemy)
  schemas.py      -- Pydantic request/response models
  params.py       -- Inter-layer Pydantic param objects (optional)
  service.py      -- Cross-entity orchestration (optional)
```

| Module | URL Prefix | Detail Doc |
|--------|------------|------------|
| `assets` | `/asset-types`, `/assets`, `/asset-groups` | [`docs/modules/assets.md`](../../docs/modules/assets.md) |
| `assignments` | `/assets/{name}/slo-assignments`, `/asset-groups/{name}/slo-*-assignments` | [`docs/modules/evaluations.md`](../../docs/modules/evaluations.md) |
| `datasource` | `/datasources` | [`docs/modules/datasources.md`](../../docs/modules/datasources.md) |
| `sli_registry` | `/sli-definitions` | [`docs/modules/registries.md`](../../docs/modules/registries.md) |
| `slo_registry` | `/slo-definitions` | [`docs/modules/registries.md`](../../docs/modules/registries.md) |
| `slo_groups` | `/slo-groups` | [`docs/modules/slo-groups.md`](../../docs/modules/slo-groups.md) |
| `display_groups` | `/slo-display-groups` | -- |
| `quality_gate` | `/evaluations`, `/evaluation/{id}`, `/note-categories` | [workflows.md](workflows.md), [repositories.md](repositories.md), [schemas.md](schemas.md) |
| `asset_meta` | `/assets/{id}/meta/*` | -- |
| `common` | -- | Shared exceptions, `PagedResponse[T]`, `StrictInput`, null-byte validators |

Routers are mounted with no URL prefix -- each router defines absolute paths.

## Dependency Injection

Repositories are instantiated per-request in endpoint functions:

```python
repo = SLORepository(session, cache=cache)
```

- `get_session(request)` -- extracts session from `request.state` (set by middleware)
- `get_cache(request)` -- returns `RedisCache` from `app.state.cache`
- `get_arq_pool(request)` -- returns arq pool from `app.state.arq_pool`

The `quality_gate` module bundles 14 repositories into a single `QualityGateRepos`
dataclass via `Depends(get_qg_repos)`. See [workflows.md](workflows.md) for details.

Worker jobs receive dependencies via `ctx` dict (arq pattern), not FastAPI `Depends()`.

## Logging

`api/tropek/logging_config.py` -- structlog routed through stdlib logging:

- Stderr handler at INFO (console or JSON renderer)
- Optional rotating file handler via `LOG_DIR` env var (10 MB x 100 files, DEBUG level)
- Idempotent: safe to call multiple times

## Related Documentation

- **Database layer**: [database-layer.md](database-layer.md) -- models, sessions, migrations
- **Workflows**: [workflows.md](workflows.md) -- trigger, execution, re-evaluation, presentation
- **Repositories**: [repositories.md](repositories.md) -- quality gate data access patterns
- **Schemas**: [schemas.md](schemas.md) -- API request/response contracts
- **Evaluation engine**: [`docs/modules/evaluation-internals.md`](../../docs/modules/evaluation-internals.md) -- pure scoring logic
- **Data model**: [`docs/architecture/data-model.md`](../../docs/architecture/data-model.md) -- ER diagrams and table descriptions
- **Evaluation lifecycle**: [`docs/architecture/evaluation-lifecycle.md`](../../docs/architecture/evaluation-lifecycle.md)
