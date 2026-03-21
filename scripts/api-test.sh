#!/usr/bin/env bash
# Run API tests (pytest). Handles working directory so it works from repo root.
#
# Usage:
#   ./scripts/api-test.sh                                  # all non-integration tests
#   ./scripts/api-test.sh -m integration                   # integration tests only
#   ./scripts/api-test.sh tests/db/test_baseline_query.py  # specific file
#   ./scripts/api-test.sh --tail 20                        # show only last 20 lines
#   ./scripts/api-test.sh --tail 10 -m integration -v      # combine flags

set -euo pipefail

TAIL_LINES=0
ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tail)
      TAIL_LINES="$2"
      shift 2
      ;;
    *)
      ARGS+=("$1")
      shift
      ;;
  esac
done

# Default: run non-integration tests if no marker specified
if [[ ${#ARGS[@]} -eq 0 ]]; then
  ARGS=(-m "not integration" -q)
fi

if [[ "$TAIL_LINES" -gt 0 ]]; then
  uv run --directory api pytest tests/ "${ARGS[@]}" 2>&1 | tail -n "$TAIL_LINES"
else
  exec uv run --directory api pytest tests/ "${ARGS[@]}"
fi
