#!/usr/bin/env bash
# Run ESLint on UI source files (TypeScript + React).
# Catches stale hook deps, unused vars, and React Compiler issues.
#
# Usage:
#   ./scripts/ui-lint.sh                                 # lint all UI files
#   ./scripts/ui-lint.sh src/features/.../Foo.tsx         # lint specific file(s)
#   ./scripts/ui-lint.sh --tail 20                        # show only last 20 lines

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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UI_DIR="$SCRIPT_DIR/../ui"

cd "$UI_DIR"

if [[ ${#ARGS[@]} -eq 0 ]]; then
  ARGS=("src/")
fi

if [[ "$TAIL_LINES" -gt 0 ]]; then
  pnpm exec eslint "${ARGS[@]}" 2>&1 | tail -n "$TAIL_LINES"
else
  exec pnpm exec eslint "${ARGS[@]}"
fi
