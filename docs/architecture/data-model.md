# Data Model

TROPEK uses PostgreSQL 16 with the TimescaleDB extension. 14 tables organized into
four groups.

## Entity Relationship Diagram

```mermaid
erDiagram
    asset_types ||--o{ assets : "type_name"
    assets ||--o{ evaluations : "asset_id"
    assets ||--o{ asset_group_members : "asset_id"
    assets ||--o{ asset_slo_links : "asset_id"

    asset_groups ||--o{ asset_group_members : "group_id"
    asset_groups ||--o{ asset_group_links : "parent"
    asset_groups ||--o{ asset_group_links : "child"
    asset_groups ||--o{ asset_group_slo_links : "group_id"

    evaluations ||--o{ evaluation_annotations : "evaluation_id"
    evaluations ||--o{ sli_values : "eval_id"
    evaluation_batches ||--|| evaluations : "evaluation_ids (JSONB)"

    asset_slo_links }o..o{ slo_definitions : "slo_name"
    asset_slo_links }o..o{ sli_definitions : "sli_name"
    asset_slo_links }o..o{ data_sources : "data_source_name"

    asset_group_slo_links }o..o{ slo_definitions : "slo_name"
    asset_group_slo_links }o..o{ sli_definitions : "sli_name"
    asset_group_slo_links }o..o{ data_sources : "data_source_name"

    asset_types { uuid id PK; text name UK; bool is_default }
    assets { uuid id PK; text name UK; text type_name FK; jsonb labels }
    asset_groups { uuid id PK; text name UK; text display_name; text description }
    asset_group_members { uuid group_id PK_FK; uuid asset_id PK_FK; float weight }
    asset_group_links { uuid parent_group_id PK_FK; uuid child_group_id PK_FK; float weight }
    data_sources { uuid id PK; text name UK; text adapter_type; text adapter_url; jsonb labels }
    slo_definitions { uuid id PK; text name; int version; text slo_yaml; bool active }
    sli_definitions { uuid id PK; text name; int version; jsonb indicators; bool active }
    evaluations { uuid id PK; text status; text result; float score; jsonb indicator_results }
    evaluation_annotations { uuid id PK; uuid evaluation_id FK; text content; text author }
    sli_values { uuid eval_id PK_FK; timestamptz eval_start PK; text metric_name PK; float value }
    asset_slo_links { uuid id PK; uuid asset_id FK; text slo_name; text sli_name; text data_source_name }
    asset_group_slo_links { uuid id PK; uuid group_id FK; text slo_name; text sli_name; text data_source_name }
    evaluation_batches { uuid id PK; text status; jsonb evaluation_ids }
```

## Table Groups

### Asset Inventory

Entities under test and how they are organized.

| Table | Purpose |
|-------|---------|
| `asset_types` | Extensible vocabulary of asset kinds (vm, service, container, database, endpoint). One row is marked `is_default`. |
| `assets` | Named entities with a type, key-value labels (JSONB), and timestamps. Unique by `name`. |
| `asset_groups` | Named collections. Can contain assets (flat) or other groups (hierarchical). |
| `asset_group_members` | Asset-to-group junction with a `weight` column for weighted group scoring. |
| `asset_group_links` | Group-to-group junction (parent/child) with weight. Enables nested hierarchies. |

### Definition Registries

Versioned, immutable-after-insert definitions.

| Table | Purpose |
|-------|---------|
| `slo_definitions` | SLO YAML stored as text. Versioned by `(name, version)`. Soft-delete via `active` flag. Each version captures: objectives, pass/warning thresholds, comparison config, author, notes, metadata. |
| `sli_definitions` | Indicator query maps (metric name -> query string) stored as JSONB. Same versioning scheme as SLOs. |
| `data_sources` | Named pointers to adapter instances (adapter_type, adapter_url, labels). Mutable -- URL can be updated. |

### Evaluation Binding

Connects assets and groups to their evaluation configuration.

| Table | Purpose |
|-------|---------|
| `asset_slo_links` | Binds one asset to an (SLO, SLI, DataSource) triple. Named and unique per `(asset_id, link_name)`. |
| `asset_group_slo_links` | Same for groups. Group triggers fan out evaluations across all members. Unique per `(group_id, link_name)` and `(group_id, slo_name)`. |

### Evaluation Results

The core output of the platform.

| Table | Purpose |
|-------|---------|
| `evaluations` | One row per evaluation run. Tracks full lifecycle (pending -> running -> completed/failed/partial). Key JSONB columns: `asset_snapshot` (denormalized asset state at trigger time), `indicator_results` (per-SLI breakdown), `evaluation_metadata` (caller context), `job_stats` (worker info). |
| `evaluation_annotations` | Append-only contextual notes on evaluations (content, author, category, metadata). |
| `sli_values` | **TimescaleDB hypertable** partitioned by `eval_start`. One metric value per evaluation per metric. Denormalized columns (`asset_name`, `test_name`, `os_tag`) avoid joins in Grafana dashboards. |
| `evaluation_batches` | Groups evaluations spawned by one trigger call. Tracks batch-level status via JSONB `evaluation_ids`. |

## Key Design Decisions

### Versioning strategy

SLO and SLI definitions are **immutable after insert**. Creating a new version with an
existing name auto-increments the version using `SELECT ... FOR UPDATE` to prevent race
conditions. `DELETE` soft-deactivates all versions (sets `active = false`). Evaluations
record which version they used, so historical results are always reproducible.

### TimescaleDB hypertable

`sli_values` is partitioned by `eval_start` for efficient time-range queries. The composite
PK `(eval_id, eval_start, metric_name, aggregation)` is required because TimescaleDB needs
the partition key in the primary key. No ORM relationship to `Evaluation` is defined --
this prevents accidental lazy-loading of thousands of metric rows.

### Asset snapshot denormalization

`evaluations.asset_snapshot` captures the asset state at trigger time as JSONB. Evaluation
results remain historically accurate even if the asset is later renamed or relabeled.

### JSONB for flexible data

`indicator_results`, `evaluation_metadata`, `job_stats`, `labels`, and `meta` are all JSONB.
Schema-flexible without migration overhead. Avoids the need for new columns as metadata
requirements evolve.

### Check constraints

`status` (pending/running/completed/failed/partial), `result` (pass/warning/fail/error),
and `ingestion_mode` (push/pull/file) are enforced at the database level via CHECK
constraints, not just application-level validation.

## Migrations

Managed by Alembic (async mode). Two migrations exist:

1. **001_initial_schema** -- All tables, indexes, constraints, foreign keys
2. **002_timescaledb_hypertable** -- Creates the `sli_values` hypertable and seeds default asset types

Migrations are autogenerated against the test database:

```bash
ENV_FILE=.env.test uv run --directory api alembic revision --autogenerate -m "description"
```
