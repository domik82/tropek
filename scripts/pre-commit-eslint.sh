#!/usr/bin/env bash
# Pre-commit wrapper for ESLint. Receives full paths from repo root
# (e.g., ui/src/features/Foo.tsx), strips the ui/ prefix, and runs
# eslint from the ui/ directory.
#
# Git GUIs on Windows+WSL (PyCharm, GitHub Desktop, ...) run hooks in a
# non-interactive shell that never sources ~/.bashrc, so pnpm and the
# nvm-managed node are off PATH. Make both discoverable before running.
set -euo pipefail

if ! command -v pnpm >/dev/null 2>&1; then
  export PATH="${PNPM_HOME:-$HOME/.local/share/pnpm}:$PATH"
fi

if ! command -v node >/dev/null 2>&1; then
  node_bin=$(ls -d "$HOME"/.nvm/versions/node/*/bin 2>/dev/null | sort -V | tail -n1 || true)
  [ -n "$node_bin" ] && export PATH="$node_bin:$PATH"
fi

cd "$(dirname "$0")/../ui"

files=()
for f in "$@"; do
  files+=("${f#ui/}")
done

exec pnpm exec eslint "${files[@]}"
