#!/usr/bin/env bash
# PreToolUse hook: auto-approve safe single commands, block compounds.
# Reads JSON from stdin with tool_input.command, outputs permission decision JSON.

set -euo pipefail

CMD=$(jq -r '.tool_input.command // ""')

allow() { echo "{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"allow\",\"permissionDecisionReason\":\"$1\"}}"; exit 0; }
pass()  { echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse"}}'; exit 0; }

# ── Step 0: Allow "cd <path> && <safe-script>" (worktree pattern) ──
if [[ "$CMD" =~ ^cd[[:space:]]+[^'&;|']+[[:space:]]*'&&'[[:space:]]*(\.\/)?scripts\/(api-test\.sh|ui-test\.sh|db-regen-migrations\.sh|start-test-infra\.sh|stop-test-infra\.sh) ]]; then
  allow "cd + safe project script (worktree)"
fi

# ── Step 1: Block compound commands globally ──
# Pipes, chains, subshells, backticks, redirects (except harmless 2>&1)
if [[ "$CMD" == *'|'* ]] || [[ "$CMD" == *'&&'* ]] || [[ "$CMD" == *';'* ]] ||
   [[ "$CMD" == *'$('* ]] || [[ "$CMD" == *'`'* ]] || [[ "$CMD" == *'>>'* ]]; then
  pass  # no opinion, let normal permissions handle it (will prompt)
fi
# Single > redirect (but not 2>&1 which is harmless)
if [[ "$CMD" =~ [^2\&]\> ]] || [[ "$CMD" =~ ^\> ]]; then
  pass
fi

# ── Step 2: Auto-approve known safe commands ──

# Extract first word (the binary/command)
FIRST=$(echo "$CMD" | awk '{print $1}')
# Strip path to get basename for commands invoked via absolute path
BASE=$(basename "$FIRST")

# --- Project scripts (any path, including worktrees) ---
case "$BASE" in
  api-test.sh|ui-test.sh|db-regen-migrations.sh|start-test-infra.sh|stop-test-infra.sh)
    allow "safe project script" ;;
esac

# --- Read-only / inspection commands ---
case "$BASE" in
  # File search & content inspection
  grep|egrep|fgrep|rg|ag|find|fd|locate)     allow "read-only search" ;;
  cat|head|tail|less|more|bat)                allow "read-only file read" ;;
  wc|file|stat|du|df)                         allow "read-only file info" ;;
  ls|tree|exa|eza)                            allow "read-only listing" ;;
  diff|comm|cmp)                              allow "read-only comparison" ;;
  sort|uniq|cut|tr|tee|rev|nl|column|fold)    allow "read-only text transform" ;;
  jq|yq|xq)                                  allow "read-only data query" ;;
  sed|awk)                                    allow "read-only text processing" ;;

  # System info
  pwd|whoami|hostname|id|groups)              allow "system info" ;;
  date|cal|uptime)                            allow "system info" ;;
  uname|arch|nproc|lscpu|free)                allow "system info" ;;
  which|type|command|whereis|hash)            allow "command lookup" ;;
  env|printenv|set|locale)                    allow "env info" ;;
  ps|top|htop|pgrep|lsof|ss|netstat)         allow "process/net info" ;;

  # File management (safe in dev context — rm excluded, requires ask)
  mkdir|touch|chmod|cp|mv|ln|install)         allow "safe file operation" ;;
  echo|printf|true|false|test)                allow "basic shell builtin" ;;
  realpath|readlink|dirname|basename)         allow "path resolution" ;;
  tar|zip|unzip|gzip|gunzip|xz)              allow "archive operation" ;;
esac

# --- Git (all non-destructive + common write ops) ---
if [[ "$FIRST" == "git" ]] || [[ "$FIRST" == "git.exe" ]]; then
  SUBCMD=$(echo "$CMD" | awk '{print $2}')
  case "$SUBCMD" in
    # Read-only
    status|diff|log|show|branch|tag|grep|blame|shortlog|reflog) allow "read-only git" ;;
    ls-files|ls-tree|ls-remote|rev-parse|rev-list|cat-file)     allow "read-only git" ;;
    config|remote|describe|name-rev|for-each-ref|count-objects) allow "read-only git" ;;
    # Safe write ops (commit, merge, rebase, cherry-pick excluded — require ask)
    add|stash|checkout|switch|restore|worktree)                 allow "safe git write" ;;
    fetch|pull)                                                 allow "safe git write" ;;
    -C)                                                         allow "safe git (with -C)" ;;
  esac
fi

# --- Package managers & build tools ---
case "$FIRST" in
  uv)       allow "safe uv command" ;;
  just)     allow "safe just recipe" ;;
  pnpm)     allow "safe pnpm command" ;;
  npm)      allow "safe npm command" ;;
  npx)      allow "safe npx command" ;;
  node)     allow "safe node command" ;;
  ruff)     allow "safe ruff command" ;;
  mypy)     allow "safe mypy command" ;;
  pytest)   allow "safe pytest command" ;;
  pre-commit) allow "safe pre-commit" ;;
  make)     allow "safe make command" ;;
esac

# --- Docker (read-only / lifecycle, not run) ---
if [[ "$FIRST" == "docker" ]] || [[ "$FIRST" == "docker.exe" ]]; then
  SUBCMD=$(echo "$CMD" | awk '{print $2}')
  case "$SUBCMD" in
    compose|ps|logs|inspect|images|volume|network|info|version|stats) allow "safe docker" ;;
    stop|rm|exec|start|restart|build|pull)                            allow "safe docker lifecycle" ;;
  esac
fi

# --- Misc safe tools ---
case "$FIRST" in
  superdesign) allow "safe tool" ;;
  gh)          allow "safe github cli" ;;
  curl)        pass ;;  # let permissions handle (in ask list)
esac

# No opinion — fall through to normal permission handling
pass
