# TROPEK AI Context

Quick-reference for LLMs working on this codebase. For full details see `docs/architecture.md`.

## Stack
Python 3.13, FastAPI, SQLAlchemy async (asyncpg), PostgreSQL + TimescaleDB, Redis (arq), uv.

## Service Topology
- **API** (:8080) — FastAPI REST, 5 routers, no middleware/auth yet
- **Worker** (×2) — arq job consumers (module not yet implemented)
- **Prometheus Adapter** (:8081) — stub, only `/health` exists
- **TimescaleDB** (:5432) — evaluations + SLI time-series
- **Redis** (:6379) — cache (db 0) + job queue (db 1)

## API Modules & Endpoints
Each module: `router.py` (endpoints) + `repository.py` (DB access) + `schemas.py` (Pydantic).

- **assets** — `/asset-types` CRUD, `/assets` CRUD+labels, `/asset-groups` hierarchy, `/{}/slo-links` bindings
- **datasource** — `/datasources` CRUD (name, adapter_type, adapter_url)
- **slo_registry** — `/slo-definitions` versioned CRUD (immutable rows, soft-delete)
- **sli_registry** — `/sli-definitions` versioned CRUD (same pattern as SLO)
- **quality_gate** — `/evaluations` list/detail/invalidate/restore, `/evaluations/{}/annotations` CRUD, `/trend` time-series

## DB Tables (13 total)
**Assets**: asset_types, assets, asset_groups, asset_group_members, asset_group_links
**Registries**: slo_definitions, sli_definitions, data_sources
**Bindings**: asset_slo_links, asset_group_slo_links
**Evaluations**: evaluations, evaluation_annotations, sli_values (hypertable), evaluation_batches

## Key Patterns
- DI: `Depends(get_session)` → `Repository(session)` per-request
- Lookups by human `name`, not UUID
- Pagination: `PagedResponse[T]` (items + total)
- Versioning: SLO/SLI auto-increment via `SELECT ... FOR UPDATE`, immutable after insert
- Evaluation lifecycle: pending → running → completed/failed/partial (check constraints)
- `sli_values` is a TimescaleDB hypertable, denormalized for Grafana (no ORM relationship)

## Engine (pure functions, zero I/O)
`api/app/modules/quality_gate/engine/` — ported from Keptn Go lighthouse-service:
- `evaluator.py` — `evaluate(slo_yaml, metrics, baselines)` → EvaluationResult
- `slo_parser.py` — parse YAML → SLO model
- `criteria.py` — parse/evaluate fixed (`<600`) and relative (`<=+10%`) criteria
- `scoring.py` — weighted per-objective scoring, key SLI veto
- `variables.py` — `$token` substitution in queries

## Config
`config.yaml` (non-secrets) + `QG_*` env vars (secrets). Loaded via pydantic_settings.

## Not Yet Built
Worker module, POST /evaluations trigger, adapter query endpoint, batch trigger API, UI.
