#!/usr/bin/env bash
# Syncs uncommitted/untracked files from Windows drive to Linux clone.
# Usage: ./scripts/sync-from-windows.sh

SRC="/mnt/d/DEV/keptn_rewrite/tropek"
DST="/home/domik/projects/tropek"

if [ ! -d "$SRC/.git" ]; then
  echo "Source not found: $SRC"
  exit 1
fi

echo "Collecting dirty files from $SRC ..."

# Get gitignored config files that won't appear in git status
for envfile in .env .env.test .env.local .env.development .env.production; do
  if [ -f "$SRC/$envfile" ]; then
    files+=("$envfile")
  fi
done

# Get modified and untracked files from git status
while IFS= read -r line; do
  # status --porcelain: first 2 chars are status, then space, then path
  # Handle quoted paths (spaces in filenames)
  path="${line:3}"
  # Remove surrounding quotes if present
  path="${path%\"}"
  path="${path#\"}"
  files+=("$path")
done < <(git -C "$SRC" status --porcelain)

if [ ${#files[@]} -eq 0 ]; then
  echo "No dirty files to sync."
  exit 0
fi

echo "Syncing ${#files[@]} files ..."

copied=0
skipped=0
for f in "${files[@]}"; do
  src_file="$SRC/$f"
  dst_file="$DST/$f"

  if [ ! -e "$src_file" ]; then
    echo "  SKIP (missing): $f"
    ((skipped++))
    continue
  fi

  # Create parent directory if needed
  mkdir -p "$(dirname "$dst_file")"
  cp -a "$src_file" "$dst_file"
  echo "  OK: $f"
  ((copied++))
done

echo ""
echo "Done: $copied copied, $skipped skipped."
