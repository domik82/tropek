# TROPEK API

FastAPI REST service providing the evaluation engine, registries, and trend queries.

## What It Does

- Exposes REST endpoints for evaluations, SLO/SLI registries, assets, groups, and data sources
- Triggers async evaluations via Redis job queue (arq)
- Runs the pure-function evaluation engine (ported from Keptn's lighthouse-service)
- Persists results to TimescaleDB with time-series SLI values

## Documentation

### API internals (`api/docs/`)

- [Architecture overview](docs/architecture.md) -- app bootstrap, middleware, config, and module layout
- [Database layer](docs/database-layer.md) -- ORM models, session lifecycle, and migrations
- [Evaluation workflows](docs/workflows.md) -- trigger, execution, re-evaluation, and presentation
- [Repository patterns](docs/repositories.md) -- data access layer and query patterns
- [API contracts](docs/schemas.md) -- Pydantic schemas and request/response shapes
- [Test patterns](docs/testing.md) -- unit and integration test conventions
- [Known issues](docs/known-issues.md) -- technical debt and open questions

### Module guides (`docs/modules/`)

- [Evaluation internals](../docs/modules/evaluation-internals.md) -- scoring engine algorithm (criteria, scoring, variables)
- [Evaluations](../docs/modules/evaluations.md) -- evaluation module from trigger to result
- [SLO/SLI registries](../docs/modules/registries.md) -- versioned SLO and SLI definition CRUD
- [Datasources](../docs/modules/datasources.md) -- datasource (adapter) management
- [Assets](../docs/modules/assets.md) -- asset and asset group management
- [SLO groups](../docs/modules/slo-groups.md) -- SLO grouping and bulk operations
- [Timeline](../docs/modules/timeline.md) -- timeline pipeline for trend views

## Quick Start

### Development (host-based)

```bash
docker compose up timescaledb redis -d
uv run --directory api alembic upgrade head
uv run --directory api uvicorn tropek.main:app --reload --port 8080
```

### Docker

```bash
docker compose up api --build
```

### Health check

```bash
curl http://localhost:8080/health
```

## Testing

```bash
# Unit tests (no infrastructure needed)
uv run --directory api pytest tests/ -m "not integration" -q

# Integration tests (requires test DB on port 5433)
just test-env
uv run --directory api pytest tests/ -m integration -v
just test-env-down
```

## Linting

```bash
uv run ruff check api/
uv run ruff format api/
uv run mypy api/tropek
```

## Migrations

```bash
uv run --directory api alembic upgrade head                        # dev database
ENV_FILE=.env.test uv run --directory api alembic upgrade head     # test database
./scripts/db-regen-migrations.sh                                   # regenerate from models
```
