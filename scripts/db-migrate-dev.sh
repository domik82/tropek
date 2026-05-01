#!/usr/bin/env bash
# db-migrate-dev.sh
#
# Applies DB migrations for LOCAL DEVELOPMENT.
#
# Assumptions:
#   - TimescaleDB runs in Docker (docker compose up timescaledb -d) and is
#     reachable at localhost:5432 (port-mapped from the container).
#   - You are running alembic/Python directly via uv, NOT inside Docker.
#   - Secrets live in .env at the repo root.
#
# Usage:
#   ./scripts/db-migrate-dev.sh
#   ./scripts/db-migrate-dev.sh --check     # dry-run: show pending migrations only

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

# ── Override service hostnames for local dev ──────────────────────────────────
# config.yaml uses Docker hostnames (timescaledb, redis). When running outside
# Docker these resolve to nothing. TK_DB_HOST overrides the value from config.yaml.
export TK_DB_HOST=localhost
export TK_REDIS_HOST=localhost

# ── Optional: check mode ─────────────────────────────────────────────────────
if [[ "${1:-}" == "--check" ]]; then
    echo "==> Pending migrations:"
    uv run --directory "${REPO_ROOT}/api" alembic history --indicate-current
    exit 0
fi

# ── Apply migrations ──────────────────────────────────────────────────────────
echo "==> Applying migrations to localhost:5432/tropek ..."
uv run --directory "${REPO_ROOT}/api" alembic upgrade head

echo "==> Current revision:"
uv run --directory "${REPO_ROOT}/api" alembic current

# ── Validate seed data ────────────────────────────────────────────────────────
echo ""
echo "==> Validating seed data ..."

DB_URL="postgresql://${TK_DB_USER}:${TK_DB_PASSWORD}@localhost:5432/tropek"

run_sql() {
    uv run --directory "${REPO_ROOT}" python3 -c "
import asyncio, asyncpg, sys

async def query(sql):
    conn = await asyncpg.connect('${DB_URL}')
    try:
        return await conn.fetch(sql)
    finally:
        await conn.close()

rows = asyncio.run(query(\"\"\"$1\"\"\"))
for r in rows:
    print(dict(r))
sys.exit(0 if rows else 1)
"
}

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
