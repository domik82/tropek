#!/usr/bin/env bash
# Run Schemathesis fuzzing against the API. Single auto-approvable command.
#
# Usage:
#   ./scripts/schemathesis-run.sh
#   ./scripts/schemathesis-run.sh --tail 20   # show last 20 lines only
#   ./scripts/schemathesis-run.sh -v          # pass-through pytest args

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

CMD=(uv run --directory api pytest tests/schemathesis -m schemathesis -n auto --maxprocesses 4 "${ARGS[@]}")

if [[ "$TAIL_LINES" -gt 0 ]]; then
  "${CMD[@]}" 2>&1 | tail -n "$TAIL_LINES"
else
  exec "${CMD[@]}"
fi
