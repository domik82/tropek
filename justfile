# TROPEK development task runner
# Run `just` to see all available recipes.

# Default: list available recipes
default:
    @just --list

# ─── Testing ───────────────────────────────────────────────────────────

# Run API unit tests (no infrastructure required)
test *args='-q':
    uv run --directory api pytest tests/ -m "not integration" {{args}}

# Run API integration tests (requires test-env)
test-int *args='-v':
    uv run --directory api pytest tests/ -m integration {{args}}

# Run a specific API test file or test
test-one path *args='-v':
    uv run --directory api pytest tests/{{path}} {{args}}

# Run UI component tests
test-ui *args:
    cd ui && pnpm exec vitest run {{args}}

# Run all tests (unit + integration + UI)
test-all: test test-int test-ui

# ─── Test Infrastructure ───────────────────────────────────────────────

# Start test database (port 5433) and apply migrations
test-env:
    ./scripts/start-test-infra.sh

# Stop test database and remove volumes
test-env-down:
    ./scripts/stop-test-infra.sh

# ─── Linting & Type Checking ──────────────────────────────────────────

# Run ruff linter (Python)
lint:
    uv run ruff check api/ adapters/

# Run eslint (UI — React hooks, compiler)
lint-ui:
    cd ui && pnpm exec eslint src/

# Run ruff formatter (check only)
fmt-check:
    uv run ruff format --check api/ adapters/

# Run ruff formatter (apply fixes)
fmt:
    uv run ruff format api/ adapters/

# Run mypy type checker
typecheck:
    uv run mypy api/app adapters/prometheus/app

# Run all checks (lint + format check + typecheck)
check: lint fmt-check typecheck

# ─── Development ──────────────────────────────────────────────────────

# Start full dev environment (Ctrl+C to stop)
dev:
    ./scripts/dev-start.sh

# Install all dependencies
install:
    uv sync
    cd ui && pnpm install

# Apply database migrations (dev)
migrate:
    uv run --directory api alembic upgrade head

# Apply database migrations (test DB)
migrate-test:
    ENV_FILE=.env.test uv run --directory api alembic upgrade head

# Regenerate alembic migrations (squash to single file)
migrate-regen:
    ./scripts/db-regen-migrations.sh

# Start infrastructure only (DB + Redis)
infra:
    docker compose up timescaledb redis -d

# Start all services via docker compose
up:
    docker compose up --build

# Run e2e integration test suite
e2e:
    ./scripts/integration-test.sh
