#!/usr/bin/env bash
# Run UI component tests (Vitest + React Testing Library).
# Must run from ui/ so vitest picks up vite.config.ts (jsdom environment).
#
# Usage:
#   ./scripts/ui-test.sh                          # run all UI tests
#   ./scripts/ui-test.sh src/features/.../Foo.test.tsx  # run specific file(s)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UI_DIR="$SCRIPT_DIR/../ui"

cd "$UI_DIR"
exec npx vitest run "$@"
