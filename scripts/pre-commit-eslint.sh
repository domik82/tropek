#!/usr/bin/env bash
# Pre-commit wrapper for ESLint. Receives full paths from repo root
# (e.g., ui/src/features/Foo.tsx), strips the ui/ prefix, and runs
# eslint from the ui/ directory.
set -euo pipefail

cd "$(dirname "$0")/../ui"

files=()
for f in "$@"; do
  files+=("${f#ui/}")
done

exec pnpm exec eslint "${files[@]}"
