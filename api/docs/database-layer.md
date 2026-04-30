# Database Layer

Async SQLAlchemy ORM with asyncpg driver, managed by Alembic migrations.

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

All models live in `api/tropek/db/models.py`. 24 model classes organized into six groups.

Key patterns:

- **UUID primary keys** generated server-side (`uuid4`)
- **Timestamps**: `created_at` (server_default) and `updated_at` (onupdate) where applicable
- **JSONB columns** for flexible data: tags, indicators, variables, job_stats, comparison
- **Check constraints** at the DB level for enums: status, result, ingestion_mode
- **Composite primary keys** for junction tables and the hypertable

### Model Index

| Model | Table | Key Relationships |
|-------|-------|-------------------|
| **Asset Inventory** | | |
| `AssetType` | `asset_types` | -- |
| `Asset` | `assets` | -> AssetType (type_name FK) |
| `AssetGroup` | `asset_groups` | -- |
| `AssetGroupMember` | `asset_group_members` | -> Asset, -> AssetGroup |
| `AssetGroupLink` | `asset_group_links` | -> AssetGroup (parent), -> AssetGroup (child) |
| **Asset Metadata** | | |
| `AssetMetaSnapshot` | `asset_meta_snapshots` | -> Asset (asset_id FK) |
| `AssetMetaValue` | `asset_meta_values` | -> AssetMetaSnapshot (snapshot_id FK) |
| `AssetMetaClosure` | `asset_meta_closures` | -> AssetMetaSnapshot (snapshot_id FK) |
| **Definition Registries** | | |
| `SLIDefinition` | `sli_definitions` | -- |
| `SLODefinition` | `slo_definitions` | -> SLOObjective[] (selectin-loaded), -> SLOGroup (optional) |
| `SLOObjective` | `slo_objectives` | -> SLODefinition (FK) |
| `DataSource` | `data_sources` | -- |
| `SLOGroup` | `slo_groups` | -> SLODefinition (template FK) |
| `SLODisplayGroup` | `slo_display_groups` | -> self (parent_id, self-referential) |
| `SLODisplayGroupMember` | `slo_display_group_members` | -> SLODisplayGroup (FK) |
| **Evaluation Binding** | | |
| `SLOAssignment` | `slo_assignments` | -> Asset or AssetGroup (XOR), -> SLODefinition, -> DataSource |
| `SLOGroupAssignment` | `slo_group_assignments` | -> Asset or AssetGroup (XOR), -> SLOGroup, -> DataSource |
| **Evaluation Results** | | |
| `EvaluationRun` | `evaluations` | -> Asset (FK) |
| `SLOEvaluation` | `slo_evaluations` | -> EvaluationRun (FK) |
| `IndicatorResultRow` | `indicator_results` | -> SLOEvaluation (FK), -> SLOObjective (FK) |
| `SLIValue` | `sli_values` | No ORM relationship (intentional — hypertable) |
| **Annotations** | | |
| `AnnotationCategory` | `annotation_categories` | -- |
| `EvaluationAnnotation` | `evaluation_annotations` | -> SLOEvaluation or EvaluationRun (XOR), -> AnnotationCategory |

### SLIValue: No ORM Relationship

The `sli_values` hypertable has no SQLAlchemy relationship to `SLOEvaluation`. This is
intentional -- it prevents accidental lazy-loading of thousands of metric rows when
fetching an evaluation. SLI values are always queried explicitly through the repository.

### Evaluation parent-child model

`EvaluationRun` is the parent -- one row per `(asset, eval_name, period)` trigger.
Each bound SLO produces one `SLOEvaluation` child row. Each SLO evaluation produces
one `IndicatorResultRow` per objective. This replaces the old flat `Evaluation` model.

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

## Key Repositories

The evaluation domain is split across multiple focused repositories:

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
