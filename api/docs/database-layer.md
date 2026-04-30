# Database Layer

Async SQLAlchemy ORM with asyncpg driver, managed by Alembic migrations.

For the full data model (table descriptions, ER diagrams, design decisions):
[`docs/architecture/data-model.md`](../../docs/architecture/data-model.md)

## Session Management

`api/tropek/db/session.py` provides:

- `_get_engine()` -- shared `AsyncEngine` (created once, reused)
- `get_session_factory()` -- shared `async_sessionmaker`
- `get_session()` -- FastAPI dependency (returns session from middleware)

Session lifecycle is managed by `SessionMiddleware` (`api/tropek/db/middleware.py`),
not by the `get_session()` dependency itself. The middleware creates a session per
HTTP request, commits on 2xx responses, rolls back on 4xx/5xx or raised exceptions,
and closes the session in a `finally` block.

```python
async def get_session(request: Request) -> AsyncSession:
    session: AsyncSession = request.state.session
    return session
```

## ORM Models

All 24 model classes live in `api/tropek/db/models.py`.

Key patterns:

- **UUID primary keys** generated server-side (`uuid4`)
- **Timestamps**: `created_at` (server_default) and `updated_at` (onupdate) where applicable
- **JSONB columns** for flexible data: tags, indicators, variables, job_stats, comparison
- **Check constraints** at the DB level for enums: status, result, ingestion_mode
- **Composite primary keys** for junction tables and the hypertable
- **No ORM relationship** on the `sli_values` hypertable — prevents accidental lazy-loading
  of thousands of metric rows. SLI values are always queried explicitly via repository.

## Migrations

Alembic runs in async mode. Configuration in `api/alembic/env.py`:

- Loads `ENV_FILE` via `python-dotenv` (defaults to `.env`, override with `ENV_FILE=.env.test`)
- Builds the async database URL from `DatabaseSettings`
- Runs migrations within an async engine context

### Existing Migrations

1. **001_initial_schema** -- All tables, indexes, constraints, foreign keys
2. **002_timescaledb_hypertable** -- Creates the `sli_values` hypertable and seeds default asset types

### Creating New Migrations

Never hand-write migration files. Use the regeneration script:

```bash
./scripts/db-regen-migrations.sh
```

This drops and recreates the test database, then regenerates migrations from ORM models.

## Repositories

### EvaluationRepository (SLOEvaluation)

The largest repository, handling per-SLO evaluation lifecycle:

- `create_pending()` -- Create SLO evaluation in pending status
- `mark_running()` -- Set running, record worker_id
- `mark_completed()` -- Write result, score, indicator results
- `mark_failed()` / `mark_partial()` -- Set failure/partial status
- `get_by_id()` / `list_evaluations()` -- Query methods
- `list_with_counts()` -- List with annotation counts
- `find_stuck()` -- Running evaluations past stuck threshold
- `invalidate()` / `restore()` -- Mark as invalid or clear invalidation
- `pin_baseline()` / `unpin_baseline()` -- Baseline pin management
- `override_status()` / `restore_override()` -- Manual status override

### EvaluationRunRepository

Parent evaluation run lifecycle:

- `create()` -- Create parent run for an asset
- `mark_completed()` -- Aggregate child SLO evaluation results
- `finalize_if_all_done()` -- Check if all children completed, finalize

### Other Repositories

- `BaselineRepository` -- Fetch previous evaluations for relative comparison
- `IndicatorRepository` -- Per-SLI result row CRUD
- `SLIValueRepository` -- Bulk insert/query on the hypertable
- `TrendRepository` -- Time-series queries by asset+SLO or evaluation ID
- `AnnotationRepository` -- Annotation CRUD
- `AnnotationCategoryRepository` -- Category taxonomy management
- `AssignmentRepository` -- SLO and SLO group assignment CRUD
- `AssetTypeRepository` / `AssetRepository` / `AssetGroupRepository` -- Asset inventory
- `DataSourceRepository` -- Adapter registry
- `SLORepository` / `SLIRepository` -- Definition registries
- `SLOGroupRepository` -- SLO group template management
- `DisplayGroupRepository` -- UI display group hierarchy
- `AssetMetaRepository` -- Metadata snapshot ingestion and timeline queries
