#!/usr/bin/env bash
# Pre-commit wrapper for the UI TypeScript compile check. tsc is
# project-based (it type-checks the whole program defined by the
# tsconfig, not a file list), so this ignores the staged paths and runs
# the same command CI uses. The hook is gated on ui/src changes via
# .pre-commit-config.yaml, so it only fires when the UI actually changes.
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

exec pnpm exec tsc --noEmit -p tsconfig.app.json
