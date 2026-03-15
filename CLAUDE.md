# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**TROPEK** = Trend Reporting and Objective Evaluation toolKit — a standalone quality gate and performance test evaluation platform. It is a Python rewrite/extraction of Keptn's `lighthouse-service`, deployable without Kubernetes via Docker Compose.

Stack: Python 3.13, FastAPI, PostgreSQL + TimescaleDB, Redis (arq job queue), uv (package manager).

## Common Commands

```bash
# Dependencies
uv sync                                               # Install all workspace dependencies

# Run unit tests (no infrastructure required)
uv run pytest api/tests/ -m "not integration" -q

# Run a single test
uv run pytest api/tests/engine/test_evaluator.py::TestName -v

# Lint and format
uv run ruff check api/ adapters/
uv run ruff format api/ adapters/
uv run mypy api/app adapters/prometheus/app

# Start infrastructure only (dev)
docker compose up timescaledb redis -d

# Apply DB migrations (dev)
uv run --directory api alembic upgrade head

# Apply DB migrations (test DB — single command, no chaining needed)
ENV_FILE=.env.test uv run --directory api alembic upgrade head

# Start all services
docker compose up --build
```

## Integration Tests — REQUIRED STEPS

Integration tests require a **dedicated test database** on port 5433 — completely separate from the
dev database (port 5432). **Never run integration tests against the dev database.**

### First-time setup

```bash
cp .env.test.example .env.test   # fill in values (defaults match the test container)
```

### Running integration tests

Each step is a separate command — do NOT chain them or prefix env vars inline:

```bash
# Step 1: Start test infrastructure (idempotent — safe to re-run)
./start_test_infra.sh

# Step 2: Run integration tests (.env.test is loaded automatically by pytest-dotenv)
uv run pytest api/tests/ -m integration -v

# Step 3: Tear down when done (removes container + volume)
./stop_test_infra.sh
```

`api/tests/db/conftest.py` loads `.env.test` via `python-dotenv` when the DB fixtures are imported —
scoped to integration tests only, so unit tests are not affected. **Never** pass
`TEST_DATABASE_URL` or `QG_*` vars as shell prefixes or inline exports.

### Re-running migrations only (container already running)

If the container is already up and you only need to re-apply migrations:

```bash
ENV_FILE=.env.test uv run --directory api alembic upgrade head
```

This is a single command — `alembic/env.py` uses `python-dotenv` to load `ENV_FILE` internally.
Never use `set -a && source .env.test && set +a` or any bash chaining for this purpose.

## Architecture

### Service Topology (Docker Compose)

| Service | Port | Role |
|---|---|---|
| `api` | 8080 | FastAPI REST API |
| `worker` | — | arq job workers (×2) for async evaluation |
| `adapter-prometheus` | 8081 | Prometheus query adapter |
| `timescaledb` | 5432 | PostgreSQL + TimescaleDB (metrics, evaluations, SLOs) |
| `redis` | 6379 | Job queue + response cache |
| `ui` | 3000 | React SPA (Phase 1, in progress) |

### Evaluation Flow

1. Client POSTs to `/evaluations`
2. API validates SLO, enqueues job to Redis
3. Worker dequeues, queries adapter (e.g., Prometheus) for SLI values
4. Core engine evaluates SLI values against SLO criteria — pure function, no I/O
5. Results written to TimescaleDB, cached in Redis
6. Client fetches result via GET

### Core Evaluation Engine (`api/app/modules/quality_gate/engine/`)

Zero-I/O pure Python logic ported from Keptn's Go lighthouse-service. All unit-testable without database or network:

- `evaluator.py` — Top-level `evaluate()` entry point
- `slo_parser.py` — Parse and validate SLO YAML
- `criteria.py` — Parse criteria strings, evaluate pass/warning/fail conditions
- `scoring.py` — Per-objective scoring and total score calculation
- `variables.py` — Template variable substitution in SLI queries

### Workspace Layout

```
tropek/
├── api/                          # FastAPI app, worker, DB models, repositories
│   ├── app/
│   │   ├── modules/
│   │   │   ├── quality_gate/     # Evaluation router + engine
│   │   │   └── slo_registry/     # Versioned SLO CRUD
│   │   └── ...
│   ├── tests/
│   │   ├── engine/               # Pure unit tests
│   │   ├── db/                   # Integration tests (mark: integration)
│   │   └── data/slo/             # YAML fixtures for engine tests
│   └── pyproject.toml
├── adapters/prometheus/          # Standalone Prometheus query adapter (separate package)
├── config.yaml                   # Non-secret runtime config template
├── .env.example                  # Secrets template (DB, Redis, API key)
└── pyproject.toml                # UV workspace root + ruff/mypy/pytest config
```

### SLO File Format

TROPEK's SLO format is a superset of Keptn 1.0: **SLI queries are embedded** in the SLO YAML under an `indicators` block (no separate SLI file). Criteria support fixed thresholds (`<600`), relative percent (`<=+10%`), and relative absolute (`<=+50`) comparisons against a configurable baseline.

### Repository/Database Layer

SQLAlchemy async ORM (asyncpg driver) with Alembic migrations. Repositories in `api/app/modules/*/repositories.py` wrap DB access. Integration tests hit a real database — no mocks for DB layer.

## Code Conventions

- Python 3.13, strict MyPy, ruff with rules: E, W, F, I, N, UP, B, SIM, D, S, DTZ, RUF, PT, C90, PERF, TRY
- Line length: 100 chars
- Pytest: `asyncio_mode = auto`, mark infra-requiring tests with `@pytest.mark.integration`
- Error messages: lowercase, no trailing period, prefer `"could not ..."` phrasing
- Pre-commit runs ruff (lint + format) and mypy automatically

## Configuration

- Non-secret config: `config.yaml` (server, DB pool, cache TTLs, queue settings, adapter URLs, logging)
- Secrets: environment variables prefixed `QG_` (e.g., `QG_DB_PASSWORD`, `QG_REDIS_PASSWORD`, `QG_SECRET_KEY`)

## Git commands

When working with git in worktrees, always issue git add and git commit as 
separate bash calls, never chained with &&.

Never use `cd <path> && git <command>` patterns. Always use `git -C <path> <command>` instead.

✗ cd /mnt/d/DEV/keptn_rewrite/tropek/.worktrees/theme-system && git add ui/src/index.css
✓ git -C /mnt/d/DEV/keptn_rewrite/tropek/.worktrees/theme-system add ui/src/index.css

✗ cd .worktrees/theme-system && git add . && git commit -m "..."
✓ git -C .worktrees/theme-system add . && git -C .worktrees/theme-system commit -m "..."

## Python execution

Never use `python` or `python3` directly. Always use `uv run` to execute 
Python code and scripts — this ensures the project virtualenv is used, 
not the system Python.

✗ python script.py
✗ python3 -m pytest
✓ uv run python script.py
✓ uv run pytest
✓ uv run -m pytest