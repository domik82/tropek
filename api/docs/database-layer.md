# Database Layer

Async SQLAlchemy ORM with asyncpg driver, managed by Alembic migrations.

For ER diagrams and table-level design decisions:
[`docs/architecture/data-model.md`](../../docs/architecture/data-model.md)

## Session Management

Source: `api/tropek/db/session.py`, `api/tropek/db/middleware.py`.

### Shared Singletons

| Function | Returns | Notes |
|----------|---------|-------|
| `_get_engine()` | `AsyncEngine` | Lazy singleton. Pool size from config. `echo=False`. |
| `get_session_factory()` | `async_sessionmaker` | Lazy singleton. `expire_on_commit=False` to prevent post-commit attribute errors. |

### API Session Strategy (Middleware-Managed)

`SessionMiddleware` creates one `AsyncSession` per HTTP request:

1. Creates session, stores in `scope['state']['session']`
2. Wraps the ASGI `send` to intercept `http.response.start`
3. 2xx status: `session.commit()`
4. 4xx/5xx status: `session.rollback()`
5. On exception: `session.rollback()`
6. Always: `session.close()` in `finally`

**Endpoints never call `commit()`** -- the middleware handles it. Non-HTTP scopes
(WebSocket, lifespan) pass through untouched.

### Worker Session Strategy (Manual)

Worker jobs use `async with session_factory() as session:` blocks. Each phase gets
a fresh session and explicitly calls `session.commit()`. This isolates failures --
a phase 3 commit failure does not roll back phase 1's snapshot.

See [workflows.md](workflows.md) for the three-phase execution model.

### FastAPI Dependencies

```python
get_session(request)  # extracts session from request.state (set by middleware)
get_cache(request)    # returns RedisCache from app.state.cache, or None
```

## ORM Models

All models live in `api/tropek/db/models.py` (single file, ~710 lines).
Base class: `Base(DeclarativeBase)`.

### Model Inventory (21 models)

| Model | Table | Key Columns | Notes |
|-------|-------|-------------|-------|
| `AssetType` | `asset_types` | `name` (unique), `is_default` | Partial unique index on `is_default` |
| `Asset` | `assets` | `name` (unique), `type_name` (FK), `tags` (JSONB), `variables` (JSONB) | `heatmap_config` (JSONB), `color` |
| `AssetMetaSnapshot` | `asset_meta_snapshots` | `asset_id` (FK), `source`, `observed_at` | |
| `AssetMetaValue` | `asset_meta_values` | `snapshot_id` (FK), `path` (TEXT[]), `value` | BigInteger PK |
| `AssetMetaClosure` | `asset_meta_closures` | `snapshot_id` (FK), `path` (TEXT[]) | BigInteger PK |
| `AssetGroup` | `asset_groups` | `name` (unique), `display_name`, `color` | |
| `AssetGroupMember` | `asset_group_members` | Composite PK: `asset_group_id` + `asset_id`, `weight` | |
| `AssetGroupLink` | `asset_group_links` | Composite PK: `parent_asset_group_id` + `child_asset_group_id` | |
| `DataSource` | `data_sources` | `name` (unique), `adapter_type`, `adapter_url`, `token` | `tags` (JSONB) |
| `SLIDefinition` | `sli_definitions` | `name` + `version` (unique), `adapter_type`, `indicators` (JSONB) | `mode`, `active` |
| `SLOObjective` | `slo_objectives` | `slo_definition_id` (FK), `sli`, `weight`, `key_sli` | `pass_threshold` (TEXT[]), `warning_threshold` (TEXT[]) |
| `SLODefinition` | `slo_definitions` | `name` + `version` (unique), `sli_definition_id` (FK), `kind`, `active` | `comparison` (JSONB), eager-loads `objectives` and `sli_definition` |
| `AnnotationCategory` | `annotation_categories` | `name` (unique), `label`, `color`, `is_system` | |
| `EvaluationAnnotation` | `evaluation_annotations` | XOR: `slo_evaluation_id` or `evaluation_run_id` | Soft-delete: `hidden_at`, `hidden_by`, `hidden_reason` |
| `SLIValue` | `sli_values` | Composite PK: `slo_evaluation_id` + `eval_start` + `metric_name` + `aggregation` | TimescaleDB hypertable. Denormalized `asset_name`, `evaluation_name`. |
| `SLOGroup` | `slo_groups` | `name`, `template_slo_definition_id` (FK), `gen_variables` (JSONB) | Partial unique on name where active |
| `SLOAssignment` | `slo_assignments` | XOR: `asset_id` or `asset_group_id`, `slo_definition_id` (FK) | `slo_name`, `data_source_id` (FK) |
| `SLOGroupAssignment` | `slo_group_assignments` | XOR: `asset_id` or `asset_group_id`, `slo_group_id` (FK) | |
| `SLODisplayGroup` | `slo_display_groups` | `name` (unique), `parent_id` (self-FK), `sort_order` | |
| `SLODisplayGroupMember` | `slo_display_group_members` | Composite PK: `group_id` + `slo_name` | |
| `SLOEvaluation` | `slo_evaluations` | `evaluation_id` (FK), `asset_id`, `slo_name`, `status`, `result`, `score` | Baseline pin fields, override fields, `invalidated` |
| `EvaluationRun` | `evaluations` | `asset_id`, `eval_name`, `status`, `result` | Parent of `SLOEvaluation` rows |

### Relationship Loading Strategies

| Strategy | Usage | Why |
|----------|-------|-----|
| `lazy='joined'` | `SLODefinition -> SLIDefinition`, `IndicatorResultRow -> SLOObjective` | Single query, always needed |
| `lazy='selectin'` | `SLODefinition -> objectives`, `SLOEvaluation -> indicator_rows` | Separate `SELECT IN`, cleaner top-level query |
| `lazy='raise'` | `SLOAssignment -> slo_definition`, `SLOAssignment -> data_source` | Prevent accidental lazy loads |
| No relationship | `SLIValue -> SLOEvaluation` | Intentional: prevents loading thousands of hypertable rows |

### Index Strategy

| Purpose | Index | Notes |
|---------|-------|-------|
| Baseline lookup | `(asset_id, slo_name, period_start DESC)` WHERE `status='completed' AND invalidated=false` | Partial composite index |
| Stuck job detection | `(status, started_at)` WHERE `status='running'` | Partial index |
| Duplicate prevention | Partial unique on identity tuple excluding failed | Prevents duplicate in-flight evals |
| Latest version queries | Version DESC indexes on SLO/SLI definitions | |

### Conventions

- All IDs are UUID v4
- Timestamps use `DateTime(timezone=True)` with `server_default=func.now()`
- `created_at` + `updated_at` pattern (updated_at uses `onupdate=func.now()`)
- Soft delete via `hidden_at`/`hidden_by`/`hidden_reason` (annotations only)
- `active` boolean for logical deletion (SLO/SLI definitions, SLO groups)
- Check constraints enforce enums at DB level: status, result, ingestion_mode
- XOR constraints ensure polymorphic FK correctness (annotations, assignments)

## Migrations

Alembic runs in async mode. Config: `api/alembic/env.py`.

### Two-File Approach

| File | Type | Content |
|------|------|---------|
| `001_initial_schema.py` | Autogenerated | All `CREATE TABLE` statements from ORM models |
| `002_timescaledb_hypertable_and_seed_data.py` | Manual | TimescaleDB hypertable conversion for `sli_values`, seed data for asset types and annotation categories |

### Migration Workflow

Never hand-write migration files. Use the regeneration script:

```bash
./scripts/db-regen-migrations.sh
```

This script:
1. Tears down the test DB
2. Clears the versions directory (preserving manual 002)
3. Autogenerates fresh 001 from current ORM models
4. Restores 002
5. Verifies both apply cleanly

This is a rapid-prototyping-phase workflow -- no incremental migrations.

### Seed Data (002)

- **Asset types**: `vm`, `service`, `database`, `container`, `endpoint`, `load-test`
- **Annotation categories**: `failure`, `info`, `investigation`, `re-evaluation`
- All operations are idempotent (`ON CONFLICT DO NOTHING`, `if_not_exists`)

## Repository Pattern

All repositories follow consistent conventions:

- Constructor takes `AsyncSession` as first argument
- Optional `RedisCache` for cache-enabled repositories
- Repositories never commit -- callers manage transaction boundaries
- Methods use `await self._session.flush()` after writes to surface DB errors immediately
- Repositories are instantiated per-request in endpoint functions

### Repository Index

| Repository | Module | Tables | Cache |
|------------|--------|--------|-------|
| `AssetTypeRepository` | assets | `asset_types` | No |
| `AssetRepository` | assets | `assets` | Yes (Redis) |
| `AssetGroupRepository` | assets | `asset_groups`, `asset_group_members`, `asset_group_links` | No |
| `AssignmentRepository` | assignments | `slo_assignments`, `slo_group_assignments` | No |
| `DataSourceRepository` | datasource | `data_sources` | No |
| `SLORepository` | slo_registry | `slo_definitions`, `slo_objectives` | Yes (Redis) |
| `SLIRepository` | sli_registry | `sli_definitions` | Yes (Redis) |
| `SLOGroupRepository` | slo_groups | `slo_groups` | No |
| `DisplayGroupRepository` | display_groups | `slo_display_groups`, `slo_display_group_members` | No |
| `EvaluationRepository` | quality_gate | `slo_evaluations` | Yes (Redis + heatmap) |
| `EvaluationRunRepository` | quality_gate | `evaluations` | No |
| `BaselineRepository` | quality_gate | `slo_evaluations` (read-only) | Yes (Redis) |
| `IndicatorRepository` | quality_gate | `indicator_results` | No |
| `SLIValueRepository` | quality_gate | `sli_values` | No |
| `TrendRepository` | quality_gate | `sli_values`, `slo_evaluations` (read-only) | No |
| `AnnotationRepository` | quality_gate | `evaluation_annotations` | Yes (Redis) |
| `AnnotationCategoryRepository` | quality_gate | `annotation_categories` | No |
| `AssetMetaRepository` | asset_meta | `asset_meta_snapshots`, `asset_meta_values`, `asset_meta_closures` | No |

For quality gate repository internals, see [repositories.md](repositories.md).

### Versioned Registry Pattern (SLO + SLI)

Both SLO and SLI registries use identical versioning:

1. Name-based identity with auto-incrementing version via `SELECT ... FOR UPDATE`
2. `comparable_from_version` tracks baseline compatibility
3. Soft-delete: `active=False` on all versions of a name
4. `DISTINCT ON (name)` for latest-version queries (PostgreSQL-specific)
5. Redis cache invalidation on `{entity}:{name}:latest`

See [`docs/modules/registries.md`](../../docs/modules/registries.md).

### Tag Query Mixin

`TagQueryMixin` (`modules/common/tag_mixin.py`) provides `get_tag_keys()` and
`get_tag_values(key)` via PostgreSQL `jsonb_object_keys()`. Used by:
`SLORepository`, `SLIRepository`, `DataSourceRepository`, `AssetRepository`.

## Redis Cache

`api/tropek/cache/redis_cache.py` -- minimal read-through cache:

- `get_or_load(key, loader, ttl_seconds)` -- check cache, call async loader on miss
- `invalidate(key)` -- delete a key
- Does not cache `None` values
- No serialization layer -- callers handle JSON encoding

### TTL Defaults

| Cache Target | TTL | Key Pattern |
|-------------|-----|-------------|
| Trend | 60s | -- |
| Evaluation list | 30s | -- |
| Evaluation detail | 300s | -- |
| SLO definition | 600s | `slo:{name}:latest` |
| Heatmap column | 7 days | `heatmap:col:v1:{run_id}` |
| Baseline | -- | `baseline:{asset_id}:{slo_name}` |
| Annotation count | -- | `annot_count:{slo_eval_id}` |
