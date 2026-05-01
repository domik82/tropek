#!/usr/bin/env bash
# db-migrate-docker.sh
#
# Applies DB migrations against the FULL DOCKER COMPOSE stack.
#
# Assumptions:
#   - docker compose up has already been run (or will be started here).
#   - TimescaleDB port 5432 is mapped to localhost:5432 by docker-compose.yml.
#   - Secrets live in .env at the repo root (docker compose picks them up too).
#
# Usage:
#   ./scripts/db-migrate-docker.sh              # start infra + migrate
#   ./scripts/db-migrate-docker.sh --no-start   # skip docker compose up (infra already running)
#   ./scripts/db-migrate-docker.sh --check      # show pending migrations only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"

# ── Load secrets ─────────────────────────────────────────────────────────────
if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: ${ENV_FILE} not found. Copy .env.example and fill in values." >&2
    exit 1
fi
set -a
# shellcheck source=/dev/null
source "${ENV_FILE}"
set +a

# ── Flags ─────────────────────────────────────────────────────────────────────
START_INFRA=true
CHECK_ONLY=false

for arg in "$@"; do
    case "${arg}" in
        --no-start) START_INFRA=false ;;
        --check)    CHECK_ONLY=true ;;
    esac
done

# ── Start infrastructure ──────────────────────────────────────────────────────
# To fully reset the database (wipe all data), use docker volumes:
#   docker compose down -v && ./scripts/db-migrate-docker.sh
# Do NOT use DROP SCHEMA on a running timescaledb container — the background
# worker will immediately re-initialize the extension.

if [[ "${START_INFRA}" == "true" ]]; then
    echo "==> Starting Docker Compose services (timescaledb + redis) ..."
    docker compose --project-directory "${REPO_ROOT}" up timescaledb redis -d

    echo "==> Waiting for timescaledb to be healthy ..."
    for i in $(seq 1 30); do
        STATUS=$(docker compose --project-directory "${REPO_ROOT}" ps timescaledb --format '{{.Health}}' 2>/dev/null || true)
        if [[ "${STATUS}" == "healthy" ]]; then
            echo "    healthy after ${i}s"
            break
        fi
        if [[ "${i}" -eq 30 ]]; then
            echo "ERROR: timescaledb did not become healthy in 30s" >&2
            docker compose --project-directory "${REPO_ROOT}" logs timescaledb | tail -20 >&2
            exit 1
        fi
        sleep 1
    done
fi

# ── Override DB host: docker-compose maps 5432 → localhost ───────────────────
# Migrations run from the HOST (via uv), so the DB host is localhost even
# when the DB is inside a container.
export TK_DB_HOST=localhost

# ── Check mode ────────────────────────────────────────────────────────────────
if [[ "${CHECK_ONLY}" == "true" ]]; then
    echo "==> Pending migrations:"
    uv run --directory "${REPO_ROOT}/api" alembic history --indicate-current
    exit 0
fi

# ── Apply migrations ──────────────────────────────────────────────────────────
echo ""
echo "==> Applying migrations to localhost:5432/tropek ..."
uv run --directory "${REPO_ROOT}/api" alembic upgrade head

echo "==> Current revision:"
uv run --directory "${REPO_ROOT}/api" alembic current

# ── Validate seed data ────────────────────────────────────────────────────────
echo ""
echo "==> Validating seed data ..."

DB_URL="postgresql://${TK_DB_USER}:${TK_DB_PASSWORD}@localhost:5432/tropek"

PASS=true

# 1. asset_types seeded
echo ""
echo "  asset_types:"
ASSET_TYPE_COUNT=$(uv run --directory "${REPO_ROOT}" python3 -c "
import asyncio, asyncpg
async def q():
    conn = await asyncpg.connect('${DB_URL}')
    r = await conn.fetchval('SELECT count(*) FROM asset_types')
    await conn.close()
    return r
print(asyncio.run(q()))
")

if [[ "${ASSET_TYPE_COUNT}" -ge 5 ]]; then
    echo "    OK — ${ASSET_TYPE_COUNT} types seeded"
    uv run --directory "${REPO_ROOT}" python3 -c "
import asyncio, asyncpg
async def q():
    conn = await asyncpg.connect('${DB_URL}')
    rows = await conn.fetch('SELECT name, is_default FROM asset_types ORDER BY name')
    await conn.close()
    for r in rows:
        mark = '* (default)' if r['is_default'] else ''
        print(f'      {r[\"name\"]} {mark}')
asyncio.run(q())
"
else
    echo "    FAIL — expected >= 5 types, got ${ASSET_TYPE_COUNT}" >&2
    PASS=false
fi

# 2. sli_values is a hypertable
echo ""
echo "  sli_values hypertable:"
IS_HYPERTABLE=$(uv run --directory "${REPO_ROOT}" python3 -c "
import asyncio, asyncpg
async def q():
    conn = await asyncpg.connect('${DB_URL}')
    r = await conn.fetchval(
        \"SELECT count(*) FROM timescaledb_information.hypertables \
          WHERE hypertable_name = 'sli_values'\"
    )
    await conn.close()
    return r
print(asyncio.run(q()))
")

if [[ "${IS_HYPERTABLE}" -eq 1 ]]; then
    echo "    OK — sli_values is a hypertable"
else
    echo "    FAIL — sli_values is not a hypertable" >&2
    PASS=false
fi

# 3. alembic at head
echo ""
echo "  alembic version:"
ALEMBIC_HEAD=$(uv run --directory "${REPO_ROOT}/api" alembic current 2>/dev/null | grep "(head)" || true)
if [[ -n "${ALEMBIC_HEAD}" ]]; then
    echo "    OK — ${ALEMBIC_HEAD}"
else
    echo "    FAIL — not at head" >&2
    PASS=false
fi

echo ""
if [[ "${PASS}" == "true" ]]; then
    echo "==> All checks passed."
else
    echo "==> One or more checks FAILED." >&2
    exit 1
fi
