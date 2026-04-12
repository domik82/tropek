# Contract Testing — Phase 1: OpenAPI Type Generation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make FastAPI the single source of truth for all API types. Generate TypeScript types from the live OpenAPI spec. CI fails if frontend and backend drift apart.

**Architecture:** A Python script imports the FastAPI `app` object and writes `api/openapi.json` (no server boot needed). `openapi-typescript` reads that file and writes `ui/src/generated/api.ts`. A freshness check in CI regenerates both and fails if `git diff` is non-empty.

**Tech Stack:** Python 3.13, FastAPI, `openapi-typescript` (Node CLI), just, pnpm.

**Recommended subagent model (per task group):**

| Tasks | Model | Why |
|---|---|---|
| 1, 2, 3, 4, 7, 8 | **Haiku** | Pure mechanical — write a script, add a recipe, install a dep, write a README, create a CI YAML. Deterministic file production. |
| 5 (type-level sanity test) | **Haiku** | Template assertion, no judgment. |
| 6 (migrate assets feature to generated types) | **Sonnet** | Requires reading the real generated schema names, matching them to existing interfaces, and handling any shape drift. This is where real judgment calls happen — if the generated `Asset` shape differs from the UI's expectation, the agent has to decide "fix UI" vs "fix backend Pydantic". Haiku would silently paper over mismatches. |
| **Phase 1 verification gate** | **Sonnet** | Runs the full `just check-schema-fresh` loop, reviews all committed diffs, and confirms the pattern is actually reusable for the remaining features. Reviewer needs to spot subtle issues Haiku's implementation might have missed. |

Default for this phase: **Haiku**, with Sonnet called in explicitly for Task 6 and the final verification.

**Spec reference:** `docs/superpowers/specs/2026-04-12-contract-testing-design.md` (Phase 1 section).

---

### Task 1: Create the schema export script

**Files:**
- Create: `scripts/export-schema.py`

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Export the FastAPI OpenAPI schema to api/openapi.json.

Imports the app object directly — no uvicorn, no network, no database.
Run via `just export-schema` or `uv run python scripts/export-schema.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

from tropek.main import app

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / 'api' / 'openapi.json'


def main() -> None:
    schema = app.openapi()
    OUTPUT_PATH.write_text(json.dumps(schema, indent=2, sort_keys=True) + '\n')
    print(f'wrote {OUTPUT_PATH.relative_to(REPO_ROOT)}')


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Make it executable**

Run: `chmod +x scripts/export-schema.py`

- [ ] **Step 3: Run the script and verify output**

Run: `uv run --directory api python ../scripts/export-schema.py`

Expected: prints `wrote api/openapi.json`; file exists at `api/openapi.json` and starts with `{\n  "components":` or similar. Check with `head -5 api/openapi.json` (via Read tool).

- [ ] **Step 4: Commit**

```bash
git add scripts/export-schema.py api/openapi.json
git commit -m "feat(contract): export FastAPI OpenAPI schema to api/openapi.json"
```

---

### Task 2: Add `just export-schema` recipe

**Files:**
- Modify: `justfile`

- [ ] **Step 1: Add the recipe**

Add this block after the `migrate-regen` recipe:

```makefile
# ─── Contract Testing ─────────────────────────────────────────────────

# Export FastAPI OpenAPI schema to api/openapi.json
export-schema:
    uv run --directory api python ../scripts/export-schema.py
```

- [ ] **Step 2: Verify recipe works**

Run: `just export-schema`
Expected: prints `wrote api/openapi.json`, no errors.

- [ ] **Step 3: Commit**

```bash
git add justfile
git commit -m "chore(contract): add just export-schema recipe"
```

---

### Task 3: Install openapi-typescript

**Files:**
- Modify: `ui/package.json`

- [ ] **Step 1: Install as devDependency**

Run: `cd ui && pnpm add -D openapi-typescript`

Expected: `openapi-typescript` appears in `ui/package.json` devDependencies.

- [ ] **Step 2: Verify CLI works**

Run: `cd ui && pnpm exec openapi-typescript --version`
Expected: prints a version number (7.x or later).

- [ ] **Step 3: Commit**

```bash
git add ui/package.json ui/pnpm-lock.yaml
git commit -m "chore(contract): add openapi-typescript devDependency"
```

---

### Task 4: Generate initial TypeScript types

**Files:**
- Create: `ui/src/generated/.gitkeep`
- Create: `ui/src/generated/api.ts` (generated)
- Modify: `justfile`

- [ ] **Step 1: Add the codegen recipe**

Add this block right after `export-schema`:

```makefile
# Regenerate TypeScript types from api/openapi.json
codegen:
    cd ui && pnpm exec openapi-typescript ../api/openapi.json -o src/generated/api.ts

# Regenerate schema + types and fail if anything changed (CI freshness check)
check-schema-fresh: export-schema codegen
    @git diff --exit-code api/openapi.json ui/src/generated/api.ts || \
        (echo "ERROR: schema or generated types are stale — run 'just export-schema && just codegen' and commit" && exit 1)
```

- [ ] **Step 2: Run codegen**

Run: `just codegen`
Expected: file `ui/src/generated/api.ts` created, several hundred to a few thousand lines, starts with a header like `/** This file was auto-generated by openapi-typescript. */`.

- [ ] **Step 3: Verify types compile**

Run: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add justfile ui/src/generated/api.ts
git commit -m "feat(contract): generate TypeScript types from OpenAPI schema"
```

---

### Task 5: Add a type-level sanity test

**Files:**
- Create: `ui/src/generated/api.test-d.ts`

- [ ] **Step 1: Write a compile-time assertion**

```typescript
// Compile-time assertion that generated types actually exist and look right.
// If this file fails to compile, codegen is broken.
import type { paths, components } from './api'

// Every known endpoint must be present in the paths type.
type _AssertEvaluationsPath = paths['/api/evaluations']['get']
type _AssertEvaluationDetailPath = paths['/api/evaluations/{evaluation_id}']['get']
type _AssertAssetsPath = paths['/api/assets']['get']

// Every known schema must be present in components.
type _AssertComponentsSchemas = components['schemas']

// Unused-export suppression: reference the types so tsc keeps them alive.
export type __Check =
  | _AssertEvaluationsPath
  | _AssertEvaluationDetailPath
  | _AssertAssetsPath
  | _AssertComponentsSchemas
```

- [ ] **Step 2: Verify it compiles**

Run: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json`
Expected: no errors. If any path doesn't exist, fix the path string in the test to match what's in `api/openapi.json` (check the real router paths — they may use different param names).

- [ ] **Step 3: Commit**

```bash
git add ui/src/generated/api.test-d.ts
git commit -m "test(contract): add type-level sanity check for generated types"
```

---

### Task 6: Migrate one feature to generated types (proof of concept)

**Files:**
- Modify: `ui/src/features/assets/types.ts`

Pick the simplest feature — assets — to prove the migration works. The goal is to delete manually-maintained interfaces and replace them with aliases that point at generated types.

- [ ] **Step 1: Read current types**

Read `ui/src/features/assets/types.ts`. Note every exported interface/type.

- [ ] **Step 2: Find the matching generated schemas**

Open `ui/src/generated/api.ts` and grep for `Asset`. Identify the components that match: `Asset`, `AssetGroup`, `AssetType`, `TagKeyCount`, `TagValueCount`.

- [ ] **Step 3: Replace with type aliases**

Rewrite `ui/src/features/assets/types.ts`:

```typescript
// Asset feature types — thin aliases over the generated OpenAPI types.
// DO NOT add fields here. If a field is missing, add it to the backend schema
// and regenerate: `just export-schema && just codegen`.
import type { components } from '@/generated/api'

type Schemas = components['schemas']

export type Asset = Schemas['Asset']
export type AssetGroup = Schemas['AssetGroup']
export type AssetGroupTree = Schemas['AssetGroupTree']
export type AssetType = Schemas['AssetType']
export type TagKeyCount = Schemas['TagKeyCount']
export type TagValueCount = Schemas['TagValueCount']
```

Note: the actual schema names may differ slightly — check `ui/src/generated/api.ts` and adjust. If a generated schema has a different shape than what the UI expected, that's a real drift and should be fixed at the source by updating the backend Pydantic model.

- [ ] **Step 4: Verify compilation**

Run: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json`
Expected: no errors. If there are errors, they indicate real drift — fix by updating either the consumer code or (if the backend is authoritative) the backend schema.

- [ ] **Step 5: Run asset-related UI tests**

Run: `./scripts/ui-test.sh --tail 10 src/features/assets`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add ui/src/features/assets/types.ts
git commit -m "refactor(assets): use generated OpenAPI types for asset feature"
```

---

### Task 7: Document the migration pattern

**Files:**
- Create: `ui/src/generated/README.md`

- [ ] **Step 1: Write the README**

```markdown
# Generated Types

This directory contains TypeScript types generated from the FastAPI OpenAPI schema.

## Rules

- **Do not edit `api.ts` by hand.** It is regenerated from `api/openapi.json` by `just codegen`.
- **Do not add new types in other `types.ts` files that duplicate shapes from here.** Alias instead.
- **When the backend schema changes**, run `just export-schema && just codegen` and commit both files.

## Migration pattern

Feature-local `types.ts` files should become thin aliases:

\`\`\`typescript
import type { components } from '@/generated/api'

type Schemas = components['schemas']

export type Evaluation = Schemas['EvaluationDetail']
export type Indicator = Schemas['IndicatorResult']
\`\`\`

If a frontend-only type is truly needed (e.g. a UI-only derived shape that
has no backend equivalent), keep it in the feature `types.ts` but clearly
comment it as UI-only.

## CI freshness check

`just check-schema-fresh` regenerates schema and types, then fails if
`git diff` is non-empty. Run this locally before pushing if you touched
any Pydantic response model.
```

- [ ] **Step 2: Commit**

```bash
git add ui/src/generated/README.md
git commit -m "docs(contract): document generated types migration pattern"
```

---

### Task 8: Wire into GitHub Actions

**Files:**
- Create: `.github/workflows/contract-freshness.yml`

Check first whether `.github/workflows/` exists; if not, this is the first workflow in the repo.

- [ ] **Step 1: Write the workflow**

```yaml
name: Contract Freshness

on:
  pull_request:
    paths:
      - 'api/tropek/**/*.py'
      - 'ui/src/generated/**'
      - 'api/openapi.json'
      - 'scripts/export-schema.py'
  push:
    branches: [main]

jobs:
  freshness:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install Python 3.13
        run: uv python install 3.13

      - name: Install API dependencies
        run: uv sync --all-extras

      - name: Setup pnpm
        uses: pnpm/action-setup@v4
        with:
          version: 9

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm
          cache-dependency-path: ui/pnpm-lock.yaml

      - name: Install UI dependencies
        run: cd ui && pnpm install --frozen-lockfile

      - name: Check schema and generated types are fresh
        run: just check-schema-fresh

      - name: TypeScript compile check
        run: cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/contract-freshness.yml
git commit -m "ci(contract): add freshness check for OpenAPI schema and generated types"
```

---

## Self-review gate

After all tasks complete, run the full check locally:

```bash
just check-schema-fresh
cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json
./scripts/ui-test.sh --tail 10
./scripts/api-test.sh --tail 5
```

Everything should pass. The repo should now have:

1. `api/openapi.json` committed and regeneratable via `just export-schema`
2. `ui/src/generated/api.ts` committed and regeneratable via `just codegen`
3. `just check-schema-fresh` detects drift between them
4. At least one feature (`assets`) migrated to use generated types as the proof pattern
5. CI workflow that fails on drift

Other feature migrations (evaluations, slos, datasources, etc.) are **out of scope** for Phase 1 — they become incremental cleanup tasks done alongside normal feature work. Phase 1 proves the pattern; it does not migrate everything at once.
