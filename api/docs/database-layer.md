# Database Layer

Async SQLAlchemy ORM with asyncpg driver, managed by Alembic migrations.

## Session Management

`api/tropek/db/session.py` provides:

- `_get_engine()` -- shared `AsyncEngine` (created once, reused)
- `get_session_factory()` -- shared `async_sessionmaker`
- `get_session()` -- FastAPI dependency (async generator)

```python
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

Sessions auto-commit on success, rollback on exception. One session per request.

## ORM Models

All models live in `api/tropek/db/models.py`. Key patterns:

- **UUID primary keys** generated server-side (`uuid4`)
- **Timestamps**: `created_at` (server_default) and `updated_at` (onupdate) where applicable
- **JSONB columns** for flexible data: labels, indicators, metadata, job_stats
- **Check constraints** at the DB level for enums: status, result, ingestion_mode
- **Composite primary keys** for junction tables and the hypertable

### Model Index

| Model | Table | Key Relationships |
|-------|-------|-------------------|
| `AssetType` | `asset_types` | -- |
| `Asset` | `assets` | -> AssetType (type_name FK) |
| `AssetGroup` | `asset_groups` | -- |
| `AssetGroupMember` | `asset_group_members` | -> Asset, -> AssetGroup |
| `AssetGroupLink` | `asset_group_links` | -> AssetGroup (parent), -> AssetGroup (child) |
| `DataSource` | `data_sources` | -- |
| `SLIDefinition` | `sli_definitions` | -- |
| `SLODefinition` | `slo_definitions` | -> SLOObjective[] (selectin-loaded) |
| `SLOObjective` | `slo_objectives` | -> SLODefinition (FK) |
| `Evaluation` | `evaluations` | -> Asset (FK), -> EvaluationAnnotation[] (cascade) |
| `EvaluationAnnotation` | `evaluation_annotations` | -> Evaluation (FK) |
| `SLIValue` | `sli_values` | No ORM relationship (intentional) |
| `AssetSLOLink` | `asset_slo_links` | -> Asset (FK) |
| `AssetGroupSLOLink` | `asset_group_slo_links` | -> AssetGroup (FK) |
| `EvaluationBatch` | `evaluation_batches` | References evaluations via JSONB |

### SLIValue: No ORM Relationship

The `sli_values` hypertable has no SQLAlchemy relationship to `Evaluation`. This is
intentional -- it prevents accidental lazy-loading of thousands of metric rows when
fetching an evaluation. SLI values are always queried explicitly through the repository.

## Migrations

Alembic runs in async mode. Configuration in `api/alembic/env.py`:

- Loads `ENV_FILE` via `python-dotenv` (defaults to `.env`, override with `ENV_FILE=.env.test`)
- Builds the async database URL from `DatabaseSettings`
- Runs migrations within an async engine context

### Existing Migrations

1. **001_initial_schema** -- Creates all 14 tables with indexes, constraints, and foreign keys
2. **002_timescaledb_hypertable** -- Converts `sli_values` to a hypertable and seeds default asset types

### Creating New Migrations

Always autogenerate against the test database:

```bash
ENV_FILE=.env.test uv run --directory api alembic revision --autogenerate -m "description"
```

Never hand-write migration files.

## EvaluationRepository

The largest repository, organized by concern:

### Lifecycle Methods
- `create_pending()` -- Create evaluation in pending status
- `mark_running()` -- Set running, record worker_id and started_at
- `mark_completed()` -- Write result, score, indicator_results; set completed
- `mark_failed()` -- Set failed with error details
- `mark_partial()` -- Mark partial (worker crash mid-execution)

### Query Methods
- `get_by_id()` -- Fetch with annotations eagerly loaded
- `list_evaluations()` -- Filtered, paginated list
- `list_with_counts()` -- List with annotation counts
- `get_baselines()` -- Previous evaluations for relative comparison
- `find_stuck()` -- Running evaluations past the stuck threshold

### Annotation Methods
- `add_annotation()`, `get_annotation_by_id()`
- `update_annotation()`, `delete_annotation()`

### SLI Value Methods
- `write_sli_values()` -- Bulk insert into hypertable
- `delete_sli_values()` -- Remove by eval_id
- `get_sli_values_for_eval()` -- Fetch for one evaluation

### Trend Methods
- `get_trend()` -- Time-series for one metric
- `get_trend_by_domain()` -- Query by asset_name + slo_name

### Invalidation
- `invalidate()` -- Set invalidated flag + note
- `restore()` -- Clear invalidation
