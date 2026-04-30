# TROPEK API

FastAPI REST service providing the evaluation engine, registries, and trend queries.

## What It Does

- Exposes REST endpoints for evaluations, SLO/SLI registries, assets, groups, and data sources
- Triggers async evaluations via Redis job queue (arq)
- Runs the pure-function evaluation engine (ported from Keptn's lighthouse-service)
- Persists results to TimescaleDB with time-series SLI values

## Running

### Development (host-based)

```bash
# Start infrastructure
docker compose up timescaledb redis -d

# Apply migrations
uv run --directory api alembic upgrade head

# Start the API
uv run --directory api uvicorn tropek.main:app --reload --port 8080
```

### Docker

```bash
docker compose up api --build
```

### Health check

```bash
curl http://localhost:8080/health
# {"status": "ok"}
```

## Testing

```bash
# Unit tests (no infrastructure needed)
uv run --directory api pytest tests/ -m "not integration" -q

# Single test
uv run --directory api pytest tests/engine/test_evaluator.py::TestName -v

# Integration tests (requires test DB)
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
# Dev database
uv run --directory api alembic upgrade head

# Test database
ENV_FILE=.env.test uv run --directory api alembic upgrade head

# Regenerate migrations from models (drops and recreates test DB)
./scripts/db-regen-migrations.sh
```

## Architecture

See [docs/architecture.md](docs/architecture.md) for API layer architecture,
[docs/evaluation-engine.md](docs/evaluation-engine.md) for the scoring engine, and
[docs/database-layer.md](docs/database-layer.md) for the database schema and repository pattern.

For module documentation see [`docs/modules/`](../docs/modules/).
For architecture see [`docs/architecture/`](../docs/architecture/).
