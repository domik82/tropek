#!/usr/bin/env bash
# Run UI component tests (Vitest + React Testing Library).
# Must run from ui/ so vitest picks up vite.config.ts (jsdom environment).
#
# Usage:
#   ./scripts/ui-test.sh                              # run all UI tests
#   ./scripts/ui-test.sh src/features/.../Foo.test.tsx # run specific file(s)
#   ./scripts/ui-test.sh --tail 20                     # show only last 20 lines
#   ./scripts/ui-test.sh --tail 10 src/.../Foo.test.tsx

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

if [[ "$TAIL_LINES" -gt 0 ]]; then
  npx vitest run "${ARGS[@]}" 2>&1 | tail -n "$TAIL_LINES"
else
  exec npx vitest run "${ARGS[@]}"
fi
