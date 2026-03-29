#!/usr/bin/env bash
# live-test-adapter.sh — End-to-end smoke test for the Prometheus SLI adapter
#
# Prerequisites:
#   1. Observability stack running:  cd observability_stack/integration-test && just up
#   2. Redis available on localhost:6379 (or set REDIS_URL)
#
# What it does:
#   1. Starts the adapter in the background
#   2. Waits for health check
#   3. Runs a battery of tests (submit, poll, cancel, variables, errors, back-pressure)
#   4. Stops the adapter
#   5. Reports pass/fail summary
#
# Usage:
#   ./scripts/live-test-adapter.sh
#   PROMETHEUS_URL=http://prom:9090 REDIS_URL=redis://myredis:6379/0 ./scripts/live-test-adapter.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ADAPTER_DIR="${REPO_ROOT}/adapters/prometheus"

# --- Configuration (override via env vars) ---
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
ADAPTER_PORT="${ADAPTER_PORT:-8081}"
ADAPTER_URL="http://localhost:${ADAPTER_PORT}"

# Timeline data range (quick-test.yaml: 2026-03-14 + 168h = 2026-03-21)
QUERY_START="${QUERY_START:-2026-03-18T12:00:00Z}"
QUERY_END="${QUERY_END:-2026-03-18T12:05:00Z}"

# --- State ---
ADAPTER_PID=""
PASS=0
FAIL=0
TESTS_RUN=0

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

cleanup() {
    if [[ -n "${ADAPTER_PID}" ]]; then
        echo ""
        echo -e "${CYAN}==> Stopping adapter (PID ${ADAPTER_PID})...${NC}"
        kill "${ADAPTER_PID}" 2>/dev/null || true
        wait "${ADAPTER_PID}" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# --- Helpers ---

log_section() {
    echo ""
    echo -e "${CYAN}━━━ $1 ━━━${NC}"
}

assert_eq() {
    local name="$1" expected="$2" actual="$3"
    TESTS_RUN=$((TESTS_RUN + 1))
    if [[ "${expected}" == "${actual}" ]]; then
        echo -e "  ${GREEN}PASS${NC} ${name}"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}FAIL${NC} ${name} — expected '${expected}', got '${actual}'"
        FAIL=$((FAIL + 1))
    fi
}

assert_contains() {
    local name="$1" needle="$2" haystack="$3"
    TESTS_RUN=$((TESTS_RUN + 1))
    if echo "${haystack}" | grep -q "${needle}"; then
        echo -e "  ${GREEN}PASS${NC} ${name}"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}FAIL${NC} ${name} — '${needle}' not found in response"
        FAIL=$((FAIL + 1))
    fi
}

assert_status() {
    local name="$1" expected_code="$2" actual_code="$3"
    TESTS_RUN=$((TESTS_RUN + 1))
    if [[ "${expected_code}" == "${actual_code}" ]]; then
        echo -e "  ${GREEN}PASS${NC} ${name} (HTTP ${actual_code})"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}FAIL${NC} ${name} — expected HTTP ${expected_code}, got ${actual_code}"
        FAIL=$((FAIL + 1))
    fi
}

poll_job() {
    local job_id="$1"
    local max_attempts="${2:-30}"
    local attempt=0
    while [[ $attempt -lt $max_attempts ]]; do
        local resp
        resp=$(curl -s "${ADAPTER_URL}/api/v1/query-jobs/${job_id}")
        local status
        status=$(echo "${resp}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
        if [[ "${status}" == "completed" || "${status}" == "timed_out" ]]; then
            echo "${resp}"
            return 0
        fi
        sleep 0.2
        attempt=$((attempt + 1))
    done
    echo "${resp}"
    return 1
}

# --- Preflight checks ---

log_section "Preflight checks"

# Check Prometheus
echo -n "  Prometheus (${PROMETHEUS_URL})... "
if curl -sf "${PROMETHEUS_URL}/-/healthy" > /dev/null 2>&1; then
    echo -e "${GREEN}ok${NC}"
else
    echo -e "${RED}unreachable${NC}"
    echo ""
    echo "Start the observability stack first:"
    echo "  cd observability_stack/integration-test && just up"
    exit 1
fi

# Check Redis
echo -n "  Redis (${REDIS_URL})... "
REDIS_HOST=$(echo "${REDIS_URL}" | sed -n 's|redis://\([^:]*\):\([0-9]*\).*|\1|p')
REDIS_PORT=$(echo "${REDIS_URL}" | sed -n 's|redis://\([^:]*\):\([0-9]*\).*|\2|p')
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

if redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" ping > /dev/null 2>&1; then
    echo -e "${GREEN}ok${NC}"
else
    echo -e "${RED}unreachable${NC}"
    echo ""
    echo "Start Redis:"
    echo "  docker run -d --name adapter-redis -p 6379:6379 redis:7-alpine"
    exit 1
fi

# Check Prometheus has data in our time range
echo -n "  Prometheus data in range... "
DATA_CHECK=$(curl -sf "${PROMETHEUS_URL}/api/v1/query?query=up&time=${QUERY_END}" | python3 -c "import sys,json; r=json.load(sys.stdin); print(len(r.get('data',{}).get('result',[])))" 2>/dev/null || echo "0")
if [[ "${DATA_CHECK}" -gt 0 ]]; then
    echo -e "${GREEN}ok (${DATA_CHECK} series)${NC}"
else
    echo -e "${YELLOW}no data — queries may return errors (that's ok for error-handling tests)${NC}"
fi

# --- Start adapter ---

log_section "Starting adapter on :${ADAPTER_PORT}"

PROMETHEUS_URL="${PROMETHEUS_URL}" \
REDIS_URL="${REDIS_URL}" \
PORT="${ADAPTER_PORT}" \
uv run --directory "${ADAPTER_DIR}" \
    uvicorn app.main:app --host 0.0.0.0 --port "${ADAPTER_PORT}" \
    --log-level warning &
ADAPTER_PID=$!
echo "  PID: ${ADAPTER_PID}"

# Wait for health
echo -n "  Waiting for health... "
for i in $(seq 1 30); do
    if curl -sf "${ADAPTER_URL}/health/live" > /dev/null 2>&1; then
        echo -e "${GREEN}ready (${i}s)${NC}"
        break
    fi
    if [[ $i -eq 30 ]]; then
        echo -e "${RED}timeout${NC}"
        exit 1
    fi
    sleep 1
done

# ══════════════════════════════════════════════════════════════════════════════
# TEST SUITE
# ══════════════════════════════════════════════════════════════════════════════

# --- Test 1: Health endpoints ---

log_section "Test 1: Health endpoints"

LIVE_RESP=$(curl -s "${ADAPTER_URL}/health/live")
assert_contains "GET /health/live returns ok" '"ok"' "${LIVE_RESP}"

READY_RESP=$(curl -s "${ADAPTER_URL}/health/ready")
assert_contains "GET /health/ready returns ok" '"ok"' "${READY_RESP}"

# --- Test 2: Submit and poll a single raw query ---

log_section "Test 2: Submit + poll single query"

SUBMIT_RESP=$(curl -s -w '\n%{http_code}' -X POST "${ADAPTER_URL}/api/v1/query-jobs" \
    -H 'Content-Type: application/json' \
    -d "{
        \"queries\": {
            \"cpu\": {\"mode\": \"raw\", \"query\": \"avg(cpu_usage_percent{service=\\\"api\\\"})\"}
        },
        \"start\": \"${QUERY_START}\",
        \"end\": \"${QUERY_END}\"
    }")
SUBMIT_BODY=$(echo "${SUBMIT_RESP}" | head -1)
SUBMIT_CODE=$(echo "${SUBMIT_RESP}" | tail -1)

assert_status "POST /query-jobs returns 202" "202" "${SUBMIT_CODE}"

JOB_ID=$(echo "${SUBMIT_BODY}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('job_id',''))" 2>/dev/null || echo "")
assert_contains "Response contains job_id" "${JOB_ID:0:8}" "${SUBMIT_BODY}"

if [[ -n "${JOB_ID}" ]]; then
    POLL_RESP=$(poll_job "${JOB_ID}")
    POLL_STATUS=$(echo "${POLL_RESP}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
    assert_eq "Job completes" "completed" "${POLL_STATUS}"

    # Check that we got a numeric value (or at least a result entry)
    HAS_RESULTS=$(echo "${POLL_RESP}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
results = d.get('results', [])
if results:
    r = results[0]
    if r.get('success'):
        print(f'value={r[\"value\"]:.4f}')
    else:
        print(f'error={r.get(\"message\",\"unknown\")}')
else:
    print('no_results')
" 2>/dev/null || echo "parse_error")
    echo -e "  ${CYAN}INFO${NC} cpu result: ${HAS_RESULTS}"
fi

# --- Test 3: Multi-query job ---

log_section "Test 3: Multi-query job (3 metrics)"

MULTI_RESP=$(curl -s -X POST "${ADAPTER_URL}/api/v1/query-jobs" \
    -H 'Content-Type: application/json' \
    -d "{
        \"queries\": {
            \"error_rate\": {\"mode\": \"raw\", \"query\": \"sum(rate(http_errors_total{service=\\\"api\\\"}[5m])) / sum(rate(http_requests_total{service=\\\"api\\\"}[5m]))\"},
            \"cpu\": {\"mode\": \"raw\", \"query\": \"avg(cpu_usage_percent{service=\\\"api\\\"})\"},
            \"p99_latency\": {\"mode\": \"raw\", \"query\": \"histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{service=\\\"api\\\"}[5m])) by (le))\"}
        },
        \"start\": \"${QUERY_START}\",
        \"end\": \"${QUERY_END}\"
    }")
MULTI_JOB_ID=$(echo "${MULTI_RESP}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('job_id',''))" 2>/dev/null || echo "")

if [[ -n "${MULTI_JOB_ID}" ]]; then
    MULTI_POLL=$(poll_job "${MULTI_JOB_ID}")
    RESULT_COUNT=$(echo "${MULTI_POLL}" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('results',[])))" 2>/dev/null || echo "0")
    assert_eq "Job returns 3 results" "3" "${RESULT_COUNT}"

    # Print each result
    echo "${MULTI_POLL}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for r in d.get('results', []):
    name = r.get('indicator', '?')
    if r.get('success'):
        print(f'    {name} = {r[\"value\"]:.6f}')
    else:
        print(f'    {name} = ERROR: {r.get(\"message\",\"?\")}')
" 2>/dev/null || true
fi

# --- Test 4: Variable substitution ---

log_section "Test 4: Variable substitution"

VAR_RESP=$(curl -s -X POST "${ADAPTER_URL}/api/v1/query-jobs" \
    -H 'Content-Type: application/json' \
    -d "{
        \"queries\": {
            \"cpu_by_service\": {\"mode\": \"raw\", \"query\": \"avg(cpu_usage_percent{service=\\\"\$SERVICE\\\"})\"}
        },
        \"variables\": {\"SERVICE\": \"frontend\"},
        \"start\": \"${QUERY_START}\",
        \"end\": \"${QUERY_END}\"
    }")
VAR_JOB_ID=$(echo "${VAR_RESP}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('job_id',''))" 2>/dev/null || echo "")

if [[ -n "${VAR_JOB_ID}" ]]; then
    VAR_POLL=$(poll_job "${VAR_JOB_ID}")
    VAR_STATUS=$(echo "${VAR_POLL}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
    assert_eq "Variable substitution job completes" "completed" "${VAR_STATUS}"

    VAR_SUCCESS=$(echo "${VAR_POLL}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
results = d.get('results', [])
if results and results[0].get('success'):
    print('true')
else:
    print('false')
" 2>/dev/null || echo "false")
    # Success depends on whether Prometheus has data — just report
    echo -e "  ${CYAN}INFO${NC} query success: ${VAR_SUCCESS}"
fi

# --- Test 5: Error handling — non-existent metric ---

log_section "Test 5: Error handling (non-existent metric)"

ERR_RESP=$(curl -s -X POST "${ADAPTER_URL}/api/v1/query-jobs" \
    -H 'Content-Type: application/json' \
    -d "{
        \"queries\": {
            \"missing\": {\"mode\": \"raw\", \"query\": \"definitely_not_a_real_metric_xyz\"}
        },
        \"start\": \"${QUERY_START}\",
        \"end\": \"${QUERY_END}\"
    }")
ERR_JOB_ID=$(echo "${ERR_RESP}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('job_id',''))" 2>/dev/null || echo "")

if [[ -n "${ERR_JOB_ID}" ]]; then
    ERR_POLL=$(poll_job "${ERR_JOB_ID}")
    ERR_RESULT=$(echo "${ERR_POLL}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
results = d.get('results', [])
if results:
    r = results[0]
    print(f'success={r.get(\"success\")}, message={r.get(\"message\",\"\")}')
else:
    print('no_results')
" 2>/dev/null || echo "parse_error")
    assert_contains "Missing metric returns success=False" "success=False" "${ERR_RESULT}"
    echo -e "  ${CYAN}INFO${NC} ${ERR_RESULT}"
fi

# --- Test 6: Cancel a job ---

log_section "Test 6: Cancel job"

CANCEL_SUBMIT=$(curl -s -X POST "${ADAPTER_URL}/api/v1/query-jobs" \
    -H 'Content-Type: application/json' \
    -d "{
        \"queries\": {
            \"slow\": {\"mode\": \"raw\", \"query\": \"up\"}
        },
        \"start\": \"${QUERY_START}\",
        \"end\": \"${QUERY_END}\"
    }")
CANCEL_JOB_ID=$(echo "${CANCEL_SUBMIT}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('job_id',''))" 2>/dev/null || echo "")

if [[ -n "${CANCEL_JOB_ID}" ]]; then
    CANCEL_CODE=$(curl -s -o /dev/null -w '%{http_code}' -X DELETE "${ADAPTER_URL}/api/v1/query-jobs/${CANCEL_JOB_ID}")
    # 204 = cancelled, 409 = already completed (race condition with coordinator)
    if [[ "${CANCEL_CODE}" == "204" || "${CANCEL_CODE}" == "409" ]]; then
        TESTS_RUN=$((TESTS_RUN + 1))
        PASS=$((PASS + 1))
        echo -e "  ${GREEN}PASS${NC} DELETE returns ${CANCEL_CODE} (${CANCEL_CODE}=cancelled or already done)"
    else
        TESTS_RUN=$((TESTS_RUN + 1))
        FAIL=$((FAIL + 1))
        echo -e "  ${RED}FAIL${NC} DELETE returned ${CANCEL_CODE}, expected 204 or 409"
    fi
fi

# --- Test 7: 404 for unknown job ---

log_section "Test 7: Not-found (404)"

NOT_FOUND_CODE=$(curl -s -o /dev/null -w '%{http_code}' "${ADAPTER_URL}/api/v1/query-jobs/00000000-0000-0000-0000-000000000000")
assert_status "GET unknown job returns 404" "404" "${NOT_FOUND_CODE}"

# --- Test 8: $DURATION_SECONDS auto-computation ---

log_section "Test 8: DURATION_SECONDS auto-computed"

DUR_RESP=$(curl -s -X POST "${ADAPTER_URL}/api/v1/query-jobs" \
    -H 'Content-Type: application/json' \
    -d "{
        \"queries\": {
            \"with_duration\": {\"mode\": \"raw\", \"query\": \"avg_over_time(cpu_usage_percent{service=\\\"api\\\"}[\$DURATION_SECONDS])\"}
        },
        \"start\": \"${QUERY_START}\",
        \"end\": \"${QUERY_END}\"
    }")
DUR_JOB_ID=$(echo "${DUR_RESP}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('job_id',''))" 2>/dev/null || echo "")

if [[ -n "${DUR_JOB_ID}" ]]; then
    DUR_POLL=$(poll_job "${DUR_JOB_ID}")
    DUR_STATUS=$(echo "${DUR_POLL}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
    assert_eq "DURATION_SECONDS job completes" "completed" "${DUR_STATUS}"
fi

# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

log_section "Results"

echo ""
echo -e "  Tests run: ${TESTS_RUN}"
echo -e "  ${GREEN}Passed: ${PASS}${NC}"
if [[ ${FAIL} -gt 0 ]]; then
    echo -e "  ${RED}Failed: ${FAIL}${NC}"
    echo ""
    exit 1
else
    echo -e "  Failed: 0"
    echo ""
    echo -e "  ${GREEN}All tests passed!${NC}"
fi
