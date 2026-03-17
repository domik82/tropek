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
uv run --directory api uvicorn app.main:app --reload --port 8080
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
uv run pytest api/tests/ -m "not integration" -q

# Single test
uv run pytest api/tests/engine/test_evaluator.py::TestName -v

# Integration tests (requires test DB)
./start_test_infra.sh
uv run pytest api/tests/ -m integration -v
./stop_test_infra.sh
```

## Linting

```bash
uv run ruff check api/
uv run ruff format api/
uv run mypy api/app
```

## Migrations

```bash
# Dev database
uv run --directory api alembic upgrade head

# Test database
ENV_FILE=.env.test uv run --directory api alembic upgrade head

# Autogenerate new migration (against test DB)
ENV_FILE=.env.test uv run --directory api alembic revision --autogenerate -m "description"
```

## Architecture

See [docs/architecture.md](docs/architecture.md) for API layer architecture,
[docs/evaluation-engine.md](docs/evaluation-engine.md) for the scoring engine, and
[docs/database-layer.md](docs/database-layer.md) for the database schema and repository pattern.
