# UI Layering — Chunk B1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the DTO / Domain / Mapper pattern to the six simple features — `datasources`, `registry`, `slis`, `slo-groups`, `slos`, `assets` — before tackling the navigator (B2) and evaluations (B3).

**Architecture:** Each feature gets a `domain.ts` (hand-written UI vocabulary), a `mappers.ts` (`dtoToX` functions with compile-time exhaustiveness checks), and a rewritten `api.ts` that runs the mapper once at the fetch boundary before returning to React Query. Components import domain types from `features/<x>` (re-exported via `index.ts`). `registry` is special — all five types are pure UI state, so migration is a `types.ts` → `ui-types.ts` rename with no mapper. `assets` already has Phase 1 pure-alias types; the aliases become the starting point for the domain, and a real `dtoToAsset` mapper replaces the alias indirection.

**Tech Stack:** TypeScript 5.9, React 19, React Query 5, Vite 8, Vitest, ESLint flat config.

---

## Context

- **Worktree:** `.worktrees/contract-testing-phase-1/` — reuse. Branch `feat/contract-testing-phase-1` continues.
- **Generated DTOs:** `ui/src/generated/api.ts` was landed on `main` in Chunk A. The worktree must be rebased onto `main` before work starts so it picks up the generated file, the 9+2 backend Pydantic fixes, and the Trigger Evaluation modal fix.
- **Chunk A commits already on `main`:** all 9+2 backend bugs fixed, `evaluation_metadata` → `variables` rename, Trigger Evaluation modal fix, Phase 1 tooling (`just codegen`, CI freshness check). Cache-invalidation commit `9951bf0` touched `features/evaluations/hooks.ts` only — evaluations is B3, not B1. B1 files untouched.
- **Pattern document:** `CLAUDE.md` section "Layering: DTO / Domain / Mapper". Spec §5, §6, §7.1, §11, §15.5.
- **Migration order** (revised §15.6 / D6 — simplest first, registry moved earlier because it has zero mapper cost):
  1. `datasources` — validates the pattern end-to-end on a trivial CRUD feature.
  2. `registry` — file-only rename, no mapper (confidence booster).
  3. `slis` — 2 types, trivial CRUD.
  4. `slo-groups` — 3 types, trivial CRUD.
  5. `slos` — 9 types, nested objectives, `method_criteria` now typed after Chunk A.
  6. `assets` — upgrade Phase 1 pure aliases to real mappers. Also fixes the `heatmap_config` passthrough per §15.4.

- **ESLint rule** (`no-restricted-imports` against `@/generated/api`) is added **after** all six features are migrated. Adding it earlier would flag the Phase 1 assets `types.ts` (the current only violator) until its migration lands.
- **Manual test checkpoint:** a single cross-feature dev-server smoke at the end of B1. Not per-feature.

## File-level scope

Per-feature files touched (all paths relative to worktree root):

```
ui/src/features/datasources/
  + domain.ts       (new)
  + mappers.ts      (new)
  - types.ts        (deleted)
  ~ api.ts          (rewrite to run mapper)
  ~ hooks.ts        (import from ./domain)
  ~ index.ts        (re-export from ./domain)

ui/src/features/registry/
  + ui-types.ts     (renamed from types.ts)
  - types.ts        (deleted)
  ~ <all registry files importing './types'>  (grep-and-replace)

ui/src/features/slis/               # same template as datasources
ui/src/features/slo-groups/         # same template as datasources
ui/src/features/slos/               # same template as datasources, larger domain
ui/src/features/assets/             # same template — types.ts already aliases, upgrade

ui/eslint.config.js                 (add no-restricted-imports + file-glob override)
```

Cross-feature consumers to update (grep results from discovery D1):

- `navigator/components/*`, `navigator/components/treeUtils.ts` import `Asset`, `AssetGroup`, `AssetGroupTree` from `@/features/assets` — they continue to work via the new `index.ts` re-export.
- `registry/*` imports from `@/features/slos`, `@/features/slis`, `@/features/slo-groups`, `@/features/assets` — same, continues via re-exports.
- `slos/api.ts` imports `AssetGroupUpdate` from `./types` — the misfiled type moves with the rest of the slos domain rewrite (§15.6 calls this out as a slos-task cleanup opportunity, but we keep it in place during B1 to avoid cross-feature churn; it stays re-exported from `slos/domain.ts`).

## Exhaustiveness check pattern (used by every mapper)

Every `mappers.ts` file uses this shape so a newly added DTO field forces a compile-time decision on the next `just codegen`:

```typescript
import type { components } from '@/generated/api'
import type { Foo } from './domain'

type FooDto = components['schemas']['FooRead']

// Every DTO field the UI intentionally ignores. Each entry MUST carry a comment.
type DroppedFooKeys = never   // or: 'internal_hash' | 'worker_id' etc.

// Every DTO key that the mapper body reads. Hand-maintained in lock-step.
type MappedFooKeys =
  | 'id'
  | 'name'
  // ...

// Compile-time assertion: every DTO key is either mapped or explicitly dropped.
type _FooCoverage = Exclude<keyof FooDto, MappedFooKeys | DroppedFooKeys>
const _fooExhaustive: _FooCoverage extends never ? true : _FooCoverage = true

export function dtoToFoo(dto: FooDto): Foo {
  return {
    id: dto.id,
    name: dto.name,
    // ...
  }
}
```

If a future backend field lands in `FooDto` that's neither mapped nor dropped, `_FooCoverage` widens to a string literal union and `const _fooExhaustive: … = true` fails to typecheck — forcing the author to either add the field to `MappedFooKeys`/`DroppedFooKeys` or update the mapper body. This is the §7.1 mechanism.

---

## Task 0: Rebase worktree onto main

**Files:** `.worktrees/contract-testing-phase-1/` (whole tree)

- [ ] **Step 1: Verify worktree + branch**

Run: `git -C .worktrees/contract-testing-phase-1 status`
Expected: `On branch feat/contract-testing-phase-1`, clean working tree.

Run: `git -C .worktrees/contract-testing-phase-1 log --oneline main..HEAD`
Expected: empty (worktree is at the same commit as `main` after Chunk A landing) OR a short list of unlanded commits. If non-empty, inspect before rebasing.

- [ ] **Step 2: Fetch + rebase**

Run: `git fetch origin`
Run: `git -C .worktrees/contract-testing-phase-1 rebase main`
Expected: clean rebase, no conflicts (Chunk A already landed the files this branch has in common with `main`).

If conflicts occur: stop, inspect `git -C .worktrees/contract-testing-phase-1 status`, resolve and report before proceeding.

- [ ] **Step 3: Verify generated DTOs are present**

Run: `ls .worktrees/contract-testing-phase-1/ui/src/generated/api.ts`
Expected: file exists.

Run: `./scripts/ui-lint.sh --tail 5`
Expected: clean (baseline before mapper work starts).

Run: `./scripts/ui-test.sh --tail 10`
Expected: all UI tests green.

- [ ] **Step 4: Verify typecheck baseline**

Run: `./scripts/ui-lint.sh --tail 5`
Run from `ui/`: `pnpm exec tsc --noEmit -p tsconfig.app.json`
Expected: clean.

No commit for this task — it's just a precondition check.

---

## Task 1: Migrate `datasources` (pattern-setter)

**Files:**
- Create: `.worktrees/contract-testing-phase-1/ui/src/features/datasources/domain.ts`
- Create: `.worktrees/contract-testing-phase-1/ui/src/features/datasources/mappers.ts`
- Delete: `.worktrees/contract-testing-phase-1/ui/src/features/datasources/types.ts`
- Modify: `.worktrees/contract-testing-phase-1/ui/src/features/datasources/api.ts`
- Modify: `.worktrees/contract-testing-phase-1/ui/src/features/datasources/hooks.ts`
- Modify: `.worktrees/contract-testing-phase-1/ui/src/features/datasources/index.ts`

This task sets the pattern for every subsequent feature. The code here is verbatim; later tasks reference this shape.

- [ ] **Step 1: Write `domain.ts`**

Create `ui/src/features/datasources/domain.ts`:

```typescript
// Domain types for the datasources feature. UI vocabulary; camelCase;
// Date objects rather than ISO strings. Hand-written — never regenerated.

export interface Datasource {
  id: string
  name: string
  displayName: string | null
  adapterType: string
  adapterUrl: string
  tags: Record<string, string>
  hasToken: boolean
  createdAt: Date
  updatedAt: Date
}

// Write-path input types. These equal the backend request-body shape,
// so forms can send them directly — no reverse mapper needed (§11.3).
export interface DatasourceCreateInput {
  name: string
  display_name?: string
  adapter_type: string
  adapter_url: string
  token?: string
  tags?: Record<string, string>
}

export interface DatasourceUpdateInput {
  display_name?: string
  adapter_url?: string
  token?: string
  tags?: Record<string, string>
}

export interface TagKeyCount {
  key: string
  count: number
}

export interface TagValueCount {
  value: string
  count: number
}
```

- [ ] **Step 2: Write `mappers.ts`**

Create `ui/src/features/datasources/mappers.ts`:

```typescript
import type { components } from '@/generated/api'
import type { Datasource } from './domain'

type DatasourceDto = components['schemas']['DataSourceRead']

type DroppedDatasourceKeys = never

type MappedDatasourceKeys =
  | 'id'
  | 'name'
  | 'display_name'
  | 'adapter_type'
  | 'adapter_url'
  | 'tags'
  | 'has_token'
  | 'created_at'
  | 'updated_at'

type _DatasourceCoverage = Exclude<
  keyof DatasourceDto,
  MappedDatasourceKeys | DroppedDatasourceKeys
>
const _datasourceExhaustive: _DatasourceCoverage extends never
  ? true
  : _DatasourceCoverage = true
void _datasourceExhaustive

export function dtoToDatasource(dto: DatasourceDto): Datasource {
  return {
    id: dto.id,
    name: dto.name,
    displayName: dto.display_name,
    adapterType: dto.adapter_type,
    adapterUrl: dto.adapter_url,
    tags: dto.tags,
    hasToken: dto.has_token,
    createdAt: new Date(dto.created_at),
    updatedAt: new Date(dto.updated_at),
  }
}
```

If the generated `DataSourceRead` has fields not in `MappedDatasourceKeys`, the exhaustiveness check fails and the correct action is to add the missing key(s) to `MappedDatasourceKeys` AND extend the mapper body — not to silence the error.

- [ ] **Step 3: Rewrite `api.ts` to run the mapper**

Replace the entire file with:

```typescript
import type { components } from '@/generated/api'
import type { Datasource, DatasourceCreateInput, DatasourceUpdateInput, TagKeyCount, TagValueCount } from './domain'
import { dtoToDatasource } from './mappers'

type DatasourceDto = components['schemas']['DataSourceRead']
type DatasourceListDto = { items: DatasourceDto[]; total: number }

const BASE = '/api'

export async function fetchDatasources(tagKey?: string, tagVal?: string): Promise<Datasource[]> {
  const params = new URLSearchParams()
  if (tagKey) params.set('tag_key', tagKey)
  if (tagVal) params.set('tag_val', tagVal)
  const qs = params.toString()
  const res = await fetch(`${BASE}/datasources${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error(`fetchDatasources: ${res.status}`)
  const body: DatasourceListDto = await res.json()
  return body.items.map(dtoToDatasource)
}

export async function fetchDatasource(name: string): Promise<Datasource> {
  const res = await fetch(`${BASE}/datasources/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`fetchDatasource: ${res.status}`)
  const body: DatasourceDto = await res.json()
  return dtoToDatasource(body)
}

export async function createDatasource(payload: DatasourceCreateInput): Promise<Datasource> {
  const res = await fetch(`${BASE}/datasources`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`createDatasource: ${res.status}`)
  const body: DatasourceDto = await res.json()
  return dtoToDatasource(body)
}

export async function updateDatasource(name: string, payload: DatasourceUpdateInput): Promise<Datasource> {
  const res = await fetch(`${BASE}/datasources/${encodeURIComponent(name)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`updateDatasource: ${res.status}`)
  const body: DatasourceDto = await res.json()
  return dtoToDatasource(body)
}

export async function deleteDatasource(name: string): Promise<void> {
  const res = await fetch(`${BASE}/datasources/${encodeURIComponent(name)}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`deleteDatasource: ${res.status}`)
}

export async function fetchDatasourceTagKeys(): Promise<TagKeyCount[]> {
  const res = await fetch(`${BASE}/datasources/tag-keys`)
  if (!res.ok) throw new Error(`fetchDatasourceTagKeys: ${res.status}`)
  return res.json()
}

export async function fetchDatasourceTagValues(key: string): Promise<TagValueCount[]> {
  const res = await fetch(`${BASE}/datasources/tag-values?key=${encodeURIComponent(key)}`)
  if (!res.ok) throw new Error(`fetchDatasourceTagValues: ${res.status}`)
  return res.json()
}
```

Note: `TagKeyCount` / `TagValueCount` are structurally identical DTO and domain (snake_case doesn't matter on two-field objects), so `fetchDatasourceTagKeys` / `fetchDatasourceTagValues` return the JSON as-is — no mapper.

- [ ] **Step 4: Update `hooks.ts`**

Replace the type import line so hooks reference domain input types, not the deleted `./types`:

```typescript
import type { DatasourceCreateInput, DatasourceUpdateInput } from './domain'
```

And update the mutation type parameters:

```typescript
export function useCreateDatasource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: DatasourceCreateInput) => createDatasource(payload),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: datasourceKeys.all }) },
  })
}

export function useUpdateDatasource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, ...body }: DatasourceUpdateInput & { name: string }) =>
      updateDatasource(name, body),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: datasourceKeys.all }) },
  })
}
```

Leave the rest of `hooks.ts` unchanged.

- [ ] **Step 5: Update `index.ts`**

Replace the file with:

```typescript
export type { Datasource, DatasourceCreateInput, DatasourceUpdateInput } from './domain'
export {
  useDatasources, useDatasource,
  useCreateDatasource, useUpdateDatasource, useDeleteDatasource,
  useDatasourceTagKeys, useDatasourceTagValues,
} from './hooks'
export { fetchDatasources } from './api'
```

`DataSource` / `DataSourceCreate` / `DataSourceUpdate` (the old hand-written names) are no longer exported. The domain rename is `Datasource` (one word, matches discovery §D5).

- [ ] **Step 6: Delete `types.ts`**

Run: `rm .worktrees/contract-testing-phase-1/ui/src/features/datasources/types.ts`

- [ ] **Step 7: Update external consumers**

Find every consumer that imports `DataSource`, `DataSourceCreate`, `DataSourceUpdate`, or `TagKeyCount`/`TagValueCount` from `features/datasources`.

Run: Grep for `from '@/features/datasources'` and `from './types'` in `ui/src/features/datasources/` and anywhere else referencing the old names.

For each hit, rename the type:

- `DataSource` → `Datasource`
- `DataSourceCreate` → `DatasourceCreateInput`
- `DataSourceUpdate` → `DatasourceUpdateInput`

If a consumer imports `TagKeyCount`/`TagValueCount` from `@/features/datasources`, add an explicit re-export from `index.ts`:

```typescript
export type { TagKeyCount, TagValueCount } from './domain'
```

(Only if there are existing consumers. If none, skip.)

Also update any field-access sites that used snake_case property names from the old `DataSource` type — `display_name` → `displayName`, `adapter_type` → `adapterType`, `adapter_url` → `adapterUrl`, `has_token` → `hasToken`, `created_at` → `createdAt` (now a `Date`, so `.toISOString()` or `.toLocaleString()` for rendering), `updated_at` → `updatedAt`.

- [ ] **Step 8: Typecheck + lint**

Run from `ui/`: `pnpm exec tsc --noEmit -p tsconfig.app.json`
Expected: clean.

Run: `./scripts/ui-lint.sh --tail 10`
Expected: clean.

- [ ] **Step 9: Run UI tests**

Run: `./scripts/ui-test.sh --tail 10`
Expected: all green. Any failures caused by the camelCase rename must be fixed in the test file, not by reverting the mapper.

- [ ] **Step 10: Commit**

```bash
git -C .worktrees/contract-testing-phase-1 add ui/src/features/datasources/
git -C .worktrees/contract-testing-phase-1 commit -m "refactor(ui): migrate datasources to DTO/domain/mapper pattern"
```

---

## Task 2: Migrate `registry` (rename only, no mapper)

**Files:**
- Create: `.worktrees/contract-testing-phase-1/ui/src/features/registry/ui-types.ts`
- Delete: `.worktrees/contract-testing-phase-1/ui/src/features/registry/types.ts`
- Modify: every file in `ui/src/features/registry/` that imports from `./types`

Discovery §D1/§D4 established that all five registry types (`RegistryMode`, `NodeType`, `TreeNode`, `SelectedNode`, `TagFilter`) are pure UI state. No backend analogue. No mapper, no `domain.ts`.

- [ ] **Step 1: Copy `types.ts` to `ui-types.ts`**

Read the current content of `registry/types.ts` (5 type declarations). Create `registry/ui-types.ts` with the same content, unchanged.

- [ ] **Step 2: Delete `types.ts`**

Run: `rm .worktrees/contract-testing-phase-1/ui/src/features/registry/types.ts`

- [ ] **Step 3: Update every import from `./types`**

Find: every file in `ui/src/features/registry/` plus any external file importing from `@/features/registry/types`.

Run: Grep for `from './types'` in `ui/src/features/registry/` and for `from '@/features/registry/types'` in all of `ui/src/`.

For each hit, replace:
- `from './types'` → `from './ui-types'`
- `from '@/features/registry/types'` → `from '@/features/registry/ui-types'`

Expected hits (from discovery): `RegistryTree.tsx`, `useRegistryTree.ts`, `RegistryDetailPanel.tsx`, `details/*`, `RegistrySidebar.tsx`, `useRegistryTree.test.ts`, `forms/*`.

- [ ] **Step 4: Update `index.ts`**

Open `registry/index.ts`. If it re-exports any of the five types from `./types`, change the source to `./ui-types`. Per the pattern's hard rule, `features/<x>/index.ts` exports domain types + hooks only — since registry has no domain types, the barrel should export hooks/components only and leave UI types as direct imports from `ui-types`. If `index.ts` currently re-exports these types, keep the re-export pointing to `./ui-types` for backward compatibility with current consumers; a follow-up can tighten this.

- [ ] **Step 5: Typecheck + lint + tests**

Run from `ui/`: `pnpm exec tsc --noEmit -p tsconfig.app.json`
Expected: clean.

Run: `./scripts/ui-lint.sh --tail 5`
Expected: clean.

Run: `./scripts/ui-test.sh --tail 10 src/features/registry/`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git -C .worktrees/contract-testing-phase-1 add ui/src/features/registry/
git -C .worktrees/contract-testing-phase-1 commit -m "refactor(ui): rename registry/types.ts to ui-types.ts (pure UI state)"
```

---

## Task 3: Migrate `slis`

**Files:**
- Create: `ui/src/features/slis/domain.ts`
- Create: `ui/src/features/slis/mappers.ts`
- Delete: `ui/src/features/slis/types.ts`
- Modify: `ui/src/features/slis/api.ts`, `hooks.ts`, `index.ts`

Follows the Task 1 template. Discovery D2 match: `SliDefinition` → DTO `SLIDefinitionRead`; `SliDefinitionCreate` → DTO `SLIDefinitionCreate`. Domain rename: `Sli` / `SliCreateInput` (§D5).

- [ ] **Step 1: Write `domain.ts`**

```typescript
export interface Sli {
  id: string
  name: string
  displayName: string | null
  adapterType: string
  version: number
  comparableFromVersion: number
  indicators: Record<string, string>
  mode: 'raw' | 'aggregated'
  queryTemplate: string | null
  interval: string | null
  methods: string[] | null
  notes: string | null
  author: string | null
  tags: Record<string, string>
  active: boolean
  createdAt: Date
}

export interface SliCreateInput {
  name: string
  display_name?: string
  adapter_type: string
  indicators?: Record<string, string>
  mode?: 'raw' | 'aggregated'
  query_template?: string
  interval?: string
  methods?: string[]
  comparable_from_version?: number
  notes?: string
  author?: string
  tags?: Record<string, string>
}
```

If the generated `SLIDefinitionRead` narrows `mode` to a literal union, keep this literal union. If it's `string`, the mapper casts via the MappedKeys assertion; prefer fixing the Pydantic schema if the mismatch appears.

- [ ] **Step 2: Write `mappers.ts`**

```typescript
import type { components } from '@/generated/api'
import type { Sli } from './domain'

type SliDto = components['schemas']['SLIDefinitionRead']

type DroppedSliKeys = never

type MappedSliKeys =
  | 'id' | 'name' | 'display_name' | 'adapter_type' | 'version'
  | 'comparable_from_version' | 'indicators' | 'mode' | 'query_template'
  | 'interval' | 'methods' | 'notes' | 'author' | 'tags' | 'active' | 'created_at'

type _SliCoverage = Exclude<keyof SliDto, MappedSliKeys | DroppedSliKeys>
const _sliExhaustive: _SliCoverage extends never ? true : _SliCoverage = true
void _sliExhaustive

export function dtoToSli(dto: SliDto): Sli {
  return {
    id: dto.id,
    name: dto.name,
    displayName: dto.display_name,
    adapterType: dto.adapter_type,
    version: dto.version,
    comparableFromVersion: dto.comparable_from_version,
    indicators: dto.indicators,
    mode: dto.mode as Sli['mode'],
    queryTemplate: dto.query_template,
    interval: dto.interval,
    methods: dto.methods,
    notes: dto.notes,
    author: dto.author,
    tags: dto.tags,
    active: dto.active,
    createdAt: new Date(dto.created_at),
  }
}
```

If `_SliCoverage` fails because `SLIDefinitionRead` has fields this list doesn't know about, add them. If the generated `mode` is already a literal union, drop the `as` cast.

- [ ] **Step 3: Rewrite `api.ts` to call `dtoToSli(body)` / `body.items.map(dtoToSli)` before returning**

Open the current `slis/api.ts`. For every fetch function that currently returns `Promise<SliDefinition | SliDefinition[] | {items: SliDefinition[], total: number}>`:

1. Type the raw `await res.json()` as `SliDto` (or `{ items: SliDto[]; total: number }`).
2. Run the mapper over it.
3. Return the mapped value.

Mutation endpoints (`createSli`, `updateSli`) take the `SliCreateInput` domain input (which equals the backend shape — no reverse mapper) and return the mapped read type.

- [ ] **Step 4: Update `hooks.ts` type imports**

Replace `from './types'` with `from './domain'`. Rename `SliDefinition` → `Sli`, `SliDefinitionCreate` → `SliCreateInput`.

- [ ] **Step 5: Update `index.ts`**

```typescript
export type { Sli, SliCreateInput } from './domain'
export { /* hooks list from current index */ } from './hooks'
```

- [ ] **Step 6: Delete `types.ts`**

Run: `rm .worktrees/contract-testing-phase-1/ui/src/features/slis/types.ts`

- [ ] **Step 7: Update external consumers**

Grep for `SliDefinition` across `ui/src/`. Likely hits: `features/registry/**`, `features/slos/components/**`, `features/slis/components/**`. For each:

- `SliDefinition` → `Sli`
- `SliDefinitionCreate` → `SliCreateInput`
- Field accesses that used snake_case: `display_name` → `displayName`, `adapter_type` → `adapterType`, `comparable_from_version` → `comparableFromVersion`, `query_template` → `queryTemplate`, `created_at` → `createdAt` (Date now).

- [ ] **Step 8: Typecheck + lint + test**

Run from `ui/`: `pnpm exec tsc --noEmit -p tsconfig.app.json`
Run: `./scripts/ui-lint.sh --tail 10`
Run: `./scripts/ui-test.sh --tail 10`
Expected: all clean.

- [ ] **Step 9: Commit**

```bash
git -C .worktrees/contract-testing-phase-1 add ui/src/features/slis/ ui/src/
git -C .worktrees/contract-testing-phase-1 commit -m "refactor(ui): migrate slis to DTO/domain/mapper pattern"
```

(`ui/src/` in the add list catches any consumer file that was touched during Step 7.)

---

## Task 4: Migrate `slo-groups`

**Files:**
- Create: `ui/src/features/slo-groups/domain.ts`
- Create: `ui/src/features/slo-groups/mappers.ts`
- Delete: `ui/src/features/slo-groups/types.ts`
- Modify: `ui/src/features/slo-groups/api.ts`, `hooks.ts`, plus external consumers

Discovery D2 match: `SloGroup` → DTO `SLOGroupRead`. After Chunk A the OpenAPI name collision with the heatmap `SloGroup` has been fixed — the registry type is `SLOGroupRead`, the heatmap type is `HeatmapSloGroupSection` (or equivalent); confirm the exact generated schema key at mapper-writing time by grepping `generated/api.ts` for `SLOGroupRead`.

- [ ] **Step 1: Write `domain.ts`**

```typescript
export interface SloGroup {
  id: string
  name: string
  displayName: string | null
  templateSloName: string
  templateSloVersion: number
  genVariables: Record<string, string[]>
  tags: Record<string, string>
  author: string | null
  version: number
  active: boolean
  createdAt: Date
  updatedAt: Date
  generatedSloCount: number
}

export interface SloGroupCreateInput {
  name: string
  display_name?: string
  template_slo_name: string
  template_slo_version: number
  gen_variables: Record<string, string[]>
  tags?: Record<string, string>
  author?: string
}

export interface SloGroupUpdateInput {
  template_slo_version?: number
  template_slo_name?: string
  gen_variables?: Record<string, string[]>
  display_name?: string
  tags?: Record<string, string>
}
```

- [ ] **Step 2: Write `mappers.ts`**

```typescript
import type { components } from '@/generated/api'
import type { SloGroup } from './domain'

type SloGroupDto = components['schemas']['SLOGroupRead']

type DroppedSloGroupKeys = never

type MappedSloGroupKeys =
  | 'id' | 'name' | 'display_name' | 'template_slo_name' | 'template_slo_version'
  | 'gen_variables' | 'tags' | 'author' | 'version' | 'active'
  | 'created_at' | 'updated_at' | 'generated_slo_count'

type _SloGroupCoverage = Exclude<keyof SloGroupDto, MappedSloGroupKeys | DroppedSloGroupKeys>
const _sloGroupExhaustive: _SloGroupCoverage extends never ? true : _SloGroupCoverage = true
void _sloGroupExhaustive

export function dtoToSloGroup(dto: SloGroupDto): SloGroup {
  return {
    id: dto.id,
    name: dto.name,
    displayName: dto.display_name,
    templateSloName: dto.template_slo_name,
    templateSloVersion: dto.template_slo_version,
    genVariables: dto.gen_variables,
    tags: dto.tags,
    author: dto.author,
    version: dto.version,
    active: dto.active,
    createdAt: new Date(dto.created_at),
    updatedAt: new Date(dto.updated_at),
    generatedSloCount: dto.generated_slo_count,
  }
}
```

- [ ] **Step 3: Rewrite `api.ts`**

For each fetch function, type raw JSON as `SloGroupDto` (or list wrapper) and call `dtoToSloGroup` before returning. Mutations take `SloGroupCreateInput` / `SloGroupUpdateInput` directly (no reverse mapper).

- [ ] **Step 4: Update `hooks.ts`**

Change `from './types'` → `from './domain'`. Type names stay the same (`SloGroup`, `SloGroupCreate` → `SloGroupCreateInput`, `SloGroupUpdate` → `SloGroupUpdateInput`).

- [ ] **Step 5: Create `index.ts` if missing**

Current `slo-groups/` has no `index.ts`. Create one:

```typescript
export type { SloGroup, SloGroupCreateInput, SloGroupUpdateInput } from './domain'
export * from './hooks'
```

Update any consumer that imports from `@/features/slo-groups/types` (discovery lists `registry/useRegistryTree.ts`, `registry/useRegistryTree.test.ts`) to import from `@/features/slo-groups`.

- [ ] **Step 6: Delete `types.ts`**

Run: `rm .worktrees/contract-testing-phase-1/ui/src/features/slo-groups/types.ts`

- [ ] **Step 7: Update external consumers**

Grep for `from '@/features/slo-groups/types'` and `SloGroupCreate`/`SloGroupUpdate` across `ui/src/`. Replace import paths; rename `Create`/`Update` → `CreateInput`/`UpdateInput`. Also update snake_case field accesses on `SloGroup` to camelCase.

- [ ] **Step 8: Typecheck + lint + test**

Run from `ui/`: `pnpm exec tsc --noEmit -p tsconfig.app.json`
Run: `./scripts/ui-lint.sh --tail 10`
Run: `./scripts/ui-test.sh --tail 10`
Expected: all clean.

- [ ] **Step 9: Commit**

```bash
git -C .worktrees/contract-testing-phase-1 add ui/src/features/slo-groups/ ui/src/
git -C .worktrees/contract-testing-phase-1 commit -m "refactor(ui): migrate slo-groups to DTO/domain/mapper pattern"
```

---

## Task 5: Migrate `slos`

**Files:**
- Create: `ui/src/features/slos/domain.ts`
- Create: `ui/src/features/slos/mappers.ts`
- Delete: `ui/src/features/slos/types.ts`
- Modify: `ui/src/features/slos/api.ts`, `hooks.ts`, `index.ts`, plus cross-feature consumers

Largest of the trivial features. 9 types. Nested `objectives`, optional `method_criteria: Record<string, MethodCriteriaOverride> | null`, optional nested `comparison`. After Chunk A all three are strongly typed in `generated/api.ts` — no `dict[str, Any]` fallbacks.

Note: the current `types.ts` contains a misfiled `AssetGroupUpdate`. Discovery D6 flags it as a cleanup opportunity; this plan keeps it in `slos/domain.ts` during B1 to avoid cross-feature churn. A follow-up can move it to `features/assets/` cleanly once navigator (B2) is done. Re-export it from `slos/index.ts` the same way the current `slos/api.ts` consumes it.

- [ ] **Step 1: Write `domain.ts`**

```typescript
export interface MethodCriteriaOverride {
  passThreshold?: string[]
  warningThreshold?: string[]
  weight?: number
  keySli?: boolean
}

export interface SloObjective {
  sli: string
  displayName: string
  passThreshold: string[]
  warningThreshold: string[]
  weight: number
  keySli: boolean
  sortOrder: number
}

export interface SloComparisonConfig {
  baselineMode?: string
  numberOfComparisonResults?: number
  aggregateFunction?: string
  includeResultWithScore?: string
  compareWith?: string
}

export interface Slo {
  id: string
  name: string
  version: number
  comparableFromVersion: number
  displayName: string | null
  author: string | null
  notes: string | null
  tags: Record<string, string>
  variables: Record<string, string>
  kind: 'standard' | 'template'
  sliDefinitionId: string | null
  sliName: string | null
  sliVersion: number | null
  createdAt: Date
  active: boolean
  objectives: SloObjective[]
  totalScorePassThreshold: number
  totalScoreWarningThreshold: number
  comparison: SloComparisonConfig
  methodCriteria: Record<string, MethodCriteriaOverride> | null
}

export interface SloValidationResult {
  valid: boolean
  errors: { field: string; message: string }[]
  objectives?: SloObjective[]
}

// Misfiled here historically — kept for B1 to avoid cross-feature churn.
// Moves to features/assets/domain.ts in a follow-up.
export interface AssetGroupUpdateInput {
  display_name?: string
  description?: string
}

export interface SloAssignment {
  id: string
  assetId: string | null
  assetGroupId: string | null
  sloDefinitionId: string
  sloName: string
  sloVersion: number
  dataSourceId: string
  dataSourceName: string
  comparisonRules: Record<string, unknown>[] | null
  createdAt: Date
}

export interface SloAssignmentCreateInput {
  slo_definition_id: string
  data_source_name: string
  comparison_rules?: Record<string, unknown>[] | null
}

export interface SloGroupAssignment {
  id: string
  assetId: string | null
  assetGroupId: string | null
  sloGroupId: string
  sloGroupName: string
  dataSourceId: string
  dataSourceName: string
  createdAt: Date
}
```

- [ ] **Step 2: Write `mappers.ts`**

```typescript
import type { components } from '@/generated/api'
import type {
  Slo, SloObjective, SloComparisonConfig, MethodCriteriaOverride,
  SloAssignment, SloGroupAssignment,
} from './domain'

type SloDto = components['schemas']['SLODefinitionRead']
type SloObjectiveDto = components['schemas']['SLOObjectiveRead']
type SloAssignmentDto = components['schemas']['SLOAssignmentRead']
type SloGroupAssignmentDto = components['schemas']['SLOGroupAssignmentRead']
type ComparisonDto = NonNullable<SloDto['comparison']>
type MethodCriteriaDto = NonNullable<NonNullable<SloDto['method_criteria']>[string]>

// -------------------------------------------------------------------
// Slo
// -------------------------------------------------------------------

type DroppedSloKeys = never

type MappedSloKeys =
  | 'id' | 'name' | 'version' | 'comparable_from_version' | 'display_name'
  | 'author' | 'notes' | 'tags' | 'variables' | 'kind'
  | 'sli_definition_id' | 'sli_name' | 'sli_version' | 'created_at'
  | 'active' | 'objectives' | 'total_score_pass_threshold'
  | 'total_score_warning_threshold' | 'comparison' | 'method_criteria'

type _SloCoverage = Exclude<keyof SloDto, MappedSloKeys | DroppedSloKeys>
const _sloExhaustive: _SloCoverage extends never ? true : _SloCoverage = true
void _sloExhaustive

function dtoToObjective(dto: SloObjectiveDto): SloObjective {
  return {
    sli: dto.sli,
    displayName: dto.display_name,
    passThreshold: dto.pass_threshold,
    warningThreshold: dto.warning_threshold,
    weight: dto.weight,
    keySli: dto.key_sli,
    sortOrder: dto.sort_order,
  }
}

function dtoToComparison(dto: ComparisonDto | null | undefined): SloComparisonConfig {
  if (!dto) return {}
  return {
    baselineMode: dto.baseline_mode ?? undefined,
    numberOfComparisonResults: dto.number_of_comparison_results ?? undefined,
    aggregateFunction: dto.aggregate_function ?? undefined,
    includeResultWithScore: dto.include_result_with_score ?? undefined,
    compareWith: dto.compare_with ?? undefined,
  }
}

function dtoToMethodCriteria(
  dto: Record<string, MethodCriteriaDto> | null | undefined,
): Record<string, MethodCriteriaOverride> | null {
  if (!dto) return null
  const out: Record<string, MethodCriteriaOverride> = {}
  for (const [key, value] of Object.entries(dto)) {
    out[key] = {
      passThreshold: value.pass_threshold ?? undefined,
      warningThreshold: value.warning_threshold ?? undefined,
      weight: value.weight ?? undefined,
      keySli: value.key_sli ?? undefined,
    }
  }
  return out
}

export function dtoToSlo(dto: SloDto): Slo {
  return {
    id: dto.id,
    name: dto.name,
    version: dto.version,
    comparableFromVersion: dto.comparable_from_version,
    displayName: dto.display_name,
    author: dto.author,
    notes: dto.notes,
    tags: dto.tags,
    variables: dto.variables,
    kind: dto.kind as Slo['kind'],
    sliDefinitionId: dto.sli_definition_id,
    sliName: dto.sli_name,
    sliVersion: dto.sli_version,
    createdAt: new Date(dto.created_at),
    active: dto.active,
    objectives: dto.objectives.map(dtoToObjective),
    totalScorePassThreshold: dto.total_score_pass_threshold,
    totalScoreWarningThreshold: dto.total_score_warning_threshold,
    comparison: dtoToComparison(dto.comparison),
    methodCriteria: dtoToMethodCriteria(dto.method_criteria),
  }
}

// -------------------------------------------------------------------
// SloAssignment
// -------------------------------------------------------------------

type MappedSloAssignmentKeys =
  | 'id' | 'asset_id' | 'asset_group_id' | 'slo_definition_id'
  | 'slo_name' | 'slo_version' | 'data_source_id' | 'data_source_name'
  | 'comparison_rules' | 'created_at'

type _SloAssignmentCoverage = Exclude<keyof SloAssignmentDto, MappedSloAssignmentKeys>
const _sloAssignmentExhaustive: _SloAssignmentCoverage extends never ? true : _SloAssignmentCoverage = true
void _sloAssignmentExhaustive

export function dtoToSloAssignment(dto: SloAssignmentDto): SloAssignment {
  return {
    id: dto.id,
    assetId: dto.asset_id,
    assetGroupId: dto.asset_group_id,
    sloDefinitionId: dto.slo_definition_id,
    sloName: dto.slo_name,
    sloVersion: dto.slo_version,
    dataSourceId: dto.data_source_id,
    dataSourceName: dto.data_source_name,
    comparisonRules: dto.comparison_rules,
    createdAt: new Date(dto.created_at),
  }
}

// -------------------------------------------------------------------
// SloGroupAssignment
// -------------------------------------------------------------------

type MappedSloGroupAssignmentKeys =
  | 'id' | 'asset_id' | 'asset_group_id' | 'slo_group_id'
  | 'slo_group_name' | 'data_source_id' | 'data_source_name' | 'created_at'

type _SloGroupAssignmentCoverage =
  Exclude<keyof SloGroupAssignmentDto, MappedSloGroupAssignmentKeys>
const _sloGroupAssignmentExhaustive:
  _SloGroupAssignmentCoverage extends never ? true : _SloGroupAssignmentCoverage = true
void _sloGroupAssignmentExhaustive

export function dtoToSloGroupAssignment(dto: SloGroupAssignmentDto): SloGroupAssignment {
  return {
    id: dto.id,
    assetId: dto.asset_id,
    assetGroupId: dto.asset_group_id,
    sloGroupId: dto.slo_group_id,
    sloGroupName: dto.slo_group_name,
    dataSourceId: dto.data_source_id,
    dataSourceName: dto.data_source_name,
    createdAt: new Date(dto.created_at),
  }
}
```

`SloValidationResult` has no DTO in the generated schema (it's a UI-side result of a validator API) — if it does match a generated schema, add a trivial mapper. Otherwise it stays as a domain-only type imported directly by forms that call the validation endpoint, and `slos/api.ts` can either return it as-is (if the wire shape already matches camelCase) or add a small inline mapper.

**Spot-check at mapper time:** grep the generated `api.ts` for `SLOValidationResult` and `SLOObjectiveRead`. If field names differ from what this task assumes, adjust `MappedSloKeys` and the objective mapper accordingly — the exhaustiveness check will flag mismatches on the next typecheck.

- [ ] **Step 3: Rewrite `api.ts`**

For every fetch function in `slos/api.ts`, cast the raw response to its DTO type and run the appropriate mapper. Collection fetches use `.map(dtoToSlo)` / `.map(dtoToSloAssignment)` etc. Mutation endpoints take domain input types (which match backend request-body shape).

- [ ] **Step 4: Update `hooks.ts`**

Replace `from './types'` → `from './domain'`. Rename `SloDefinition` → `Slo` at every usage site inside `hooks.ts`.

- [ ] **Step 5: Update `index.ts`**

```typescript
export type {
  Slo, SloObjective, SloComparisonConfig, MethodCriteriaOverride,
  SloValidationResult, AssetGroupUpdateInput,
  SloAssignment, SloAssignmentCreateInput, SloGroupAssignment,
} from './domain'
export * from './hooks'
```

- [ ] **Step 6: Delete `types.ts`**

Run: `rm .worktrees/contract-testing-phase-1/ui/src/features/slos/types.ts`

- [ ] **Step 7: Update consumers**

Grep for `SloDefinition` and `from '@/features/slos/types'` across `ui/src/`. Likely hits: `slos/components/*.tsx`, `registry/details/TemplateDetailView.tsx`, anything that renders objectives or comparison config.

For each:
- Rename type: `SloDefinition` → `Slo`
- Rename field accesses from snake_case to camelCase (large file set — go systematically, relying on TypeScript to surface missed renames as `tsc --noEmit` errors).
- `created_at: string` → `createdAt: Date` — any `.toLocaleString()` / `.split('T')` render calls now work on a `Date` directly; string formatting calls may need an explicit `.toISOString()` or domain helper.

This is the most consumer-heavy step in B1. Take it in small batches and re-run `tsc --noEmit` between batches to keep the error list short.

- [ ] **Step 8: Typecheck + lint + test**

Run from `ui/`: `pnpm exec tsc --noEmit -p tsconfig.app.json`
Run: `./scripts/ui-lint.sh --tail 10`
Run: `./scripts/ui-test.sh --tail 10`
Expected: all clean.

- [ ] **Step 9: Commit**

```bash
git -C .worktrees/contract-testing-phase-1 add ui/src/features/slos/ ui/src/
git -C .worktrees/contract-testing-phase-1 commit -m "refactor(ui): migrate slos to DTO/domain/mapper pattern"
```

---

## Task 6: Migrate `assets` (upgrade Phase 1 aliases)

**Files:**
- Create: `ui/src/features/assets/domain.ts`
- Create: `ui/src/features/assets/mappers.ts`
- Delete: `ui/src/features/assets/types.ts` (currently pure aliases to `@/generated/api`)
- Modify: `ui/src/features/assets/api.ts`, `hooks.ts`, `index.ts`
- Possibly modify: `ui/src/features/assets/types.test.ts`, `utils.ts`, `utils.test.ts`

Phase 1 already aliased eight types to DTOs. Upgrade: replace each alias with a hand-written camelCase domain type and add a mapper. Per §15.4 the `heatmap_config` field stays opaque as `Record<string, unknown> | null` (pass-through in the mapper, no typed shape).

- [ ] **Step 1: Write `domain.ts`**

```typescript
export type AssetHeatmapConfig = Record<string, unknown> | null

export interface AssetType {
  id: string
  name: string
  displayName: string | null
  description: string | null
  createdAt: Date
  updatedAt: Date
}

export interface Asset {
  id: string
  name: string
  displayName: string | null
  assetTypeId: string
  assetTypeName: string
  tags: Record<string, string>
  primaryVersion: string | null
  buildRef: string | null
  heatmapConfig: AssetHeatmapConfig
  createdAt: Date
  updatedAt: Date
}

export interface AssetGroupMember {
  assetId: string
  assetName: string
  assetDisplayName: string | null
  addedAt: Date
}

export interface AssetGroupSubgroup {
  id: string
  name: string
  displayName: string | null
}

export interface AssetGroup {
  id: string
  name: string
  displayName: string | null
  description: string | null
  parentId: string | null
  members: AssetGroupMember[]
  subgroups: AssetGroupSubgroup[]
  createdAt: Date
  updatedAt: Date
}

export interface AssetGroupTree {
  roots: AssetGroup[]
}

export interface TagKeyCount { key: string; count: number }
export interface TagValueCount { value: string; count: number }
```

**Important:** the exact field list on each type must match the generated `AssetRead` / `AssetGroupRead` / etc. **at mapper-writing time**. Grep `generated/api.ts` for each schema and reconcile this domain file with reality. The field list above is the discovery's best understanding; treat it as a starting point and let the exhaustiveness check drive it to correctness.

- [ ] **Step 2: Write `mappers.ts`**

```typescript
import type { components } from '@/generated/api'
import type {
  Asset, AssetType, AssetGroup, AssetGroupMember, AssetGroupSubgroup, AssetGroupTree,
} from './domain'

type AssetDto = components['schemas']['AssetRead']
type AssetTypeDto = components['schemas']['AssetTypeRead']
type AssetGroupDto = components['schemas']['AssetGroupRead']
type AssetGroupMemberDto = components['schemas']['AssetGroupMemberRead']
type AssetGroupSubgroupDto = components['schemas']['AssetGroupSubgroupRead']
type AssetGroupTreeDto = components['schemas']['AssetGroupTreeResponse']

// Every type below follows the same pattern:
//   DroppedXKeys — fields intentionally ignored (with comments)
//   MappedXKeys  — fields consumed by the mapper
//   _XCoverage assertion
//   dtoToX function

// --- AssetType ---
type DroppedAssetTypeKeys = never
type MappedAssetTypeKeys = 'id' | 'name' | 'display_name' | 'description' | 'created_at' | 'updated_at'
type _AssetTypeCoverage = Exclude<keyof AssetTypeDto, MappedAssetTypeKeys | DroppedAssetTypeKeys>
const _assetTypeExhaustive: _AssetTypeCoverage extends never ? true : _AssetTypeCoverage = true
void _assetTypeExhaustive

export function dtoToAssetType(dto: AssetTypeDto): AssetType {
  return {
    id: dto.id,
    name: dto.name,
    displayName: dto.display_name,
    description: dto.description,
    createdAt: new Date(dto.created_at),
    updatedAt: new Date(dto.updated_at),
  }
}

// --- Asset ---
type DroppedAssetKeys = never
type MappedAssetKeys =
  | 'id' | 'name' | 'display_name' | 'asset_type_id' | 'asset_type_name'
  | 'tags' | 'primary_version' | 'build_ref' | 'heatmap_config'
  | 'created_at' | 'updated_at'

type _AssetCoverage = Exclude<keyof AssetDto, MappedAssetKeys | DroppedAssetKeys>
const _assetExhaustive: _AssetCoverage extends never ? true : _AssetCoverage = true
void _assetExhaustive

export function dtoToAsset(dto: AssetDto): Asset {
  return {
    id: dto.id,
    name: dto.name,
    displayName: dto.display_name,
    assetTypeId: dto.asset_type_id,
    assetTypeName: dto.asset_type_name,
    tags: dto.tags,
    primaryVersion: dto.primary_version,
    buildRef: dto.build_ref,
    // heatmap_config stays opaque — §15.4 defers design
    heatmapConfig: dto.heatmap_config as Record<string, unknown> | null,
    createdAt: new Date(dto.created_at),
    updatedAt: new Date(dto.updated_at),
  }
}

// --- AssetGroupMember ---
type MappedAssetGroupMemberKeys = 'asset_id' | 'asset_name' | 'asset_display_name' | 'added_at'
type _AssetGroupMemberCoverage = Exclude<keyof AssetGroupMemberDto, MappedAssetGroupMemberKeys>
const _assetGroupMemberExhaustive:
  _AssetGroupMemberCoverage extends never ? true : _AssetGroupMemberCoverage = true
void _assetGroupMemberExhaustive

export function dtoToAssetGroupMember(dto: AssetGroupMemberDto): AssetGroupMember {
  return {
    assetId: dto.asset_id,
    assetName: dto.asset_name,
    assetDisplayName: dto.asset_display_name,
    addedAt: new Date(dto.added_at),
  }
}

// --- AssetGroupSubgroup ---
type MappedAssetGroupSubgroupKeys = 'id' | 'name' | 'display_name'
type _AssetGroupSubgroupCoverage = Exclude<keyof AssetGroupSubgroupDto, MappedAssetGroupSubgroupKeys>
const _assetGroupSubgroupExhaustive:
  _AssetGroupSubgroupCoverage extends never ? true : _AssetGroupSubgroupCoverage = true
void _assetGroupSubgroupExhaustive

export function dtoToAssetGroupSubgroup(dto: AssetGroupSubgroupDto): AssetGroupSubgroup {
  return {
    id: dto.id,
    name: dto.name,
    displayName: dto.display_name,
  }
}

// --- AssetGroup ---
type MappedAssetGroupKeys =
  | 'id' | 'name' | 'display_name' | 'description' | 'parent_id'
  | 'members' | 'subgroups' | 'created_at' | 'updated_at'
type _AssetGroupCoverage = Exclude<keyof AssetGroupDto, MappedAssetGroupKeys>
const _assetGroupExhaustive:
  _AssetGroupCoverage extends never ? true : _AssetGroupCoverage = true
void _assetGroupExhaustive

export function dtoToAssetGroup(dto: AssetGroupDto): AssetGroup {
  return {
    id: dto.id,
    name: dto.name,
    displayName: dto.display_name,
    description: dto.description,
    parentId: dto.parent_id,
    members: dto.members.map(dtoToAssetGroupMember),
    subgroups: dto.subgroups.map(dtoToAssetGroupSubgroup),
    createdAt: new Date(dto.created_at),
    updatedAt: new Date(dto.updated_at),
  }
}

// --- AssetGroupTree ---
type MappedAssetGroupTreeKeys = 'roots'
type _AssetGroupTreeCoverage = Exclude<keyof AssetGroupTreeDto, MappedAssetGroupTreeKeys>
const _assetGroupTreeExhaustive:
  _AssetGroupTreeCoverage extends never ? true : _AssetGroupTreeCoverage = true
void _assetGroupTreeExhaustive

export function dtoToAssetGroupTree(dto: AssetGroupTreeDto): AssetGroupTree {
  return {
    roots: dto.roots.map(dtoToAssetGroup),
  }
}
```

If the generated DTOs have fields this mapper doesn't name, the `_XCoverage` assertions fail with a string literal telling you exactly which keys are missing. Add each to its `MappedXKeys` and the mapper body (or to a `DroppedXKeys` union with a comment explaining why). This is how §15.4 is enforced — `heatmap_config` is in the mapped list, with a passthrough cast, and a comment citing the spec.

- [ ] **Step 3: Rewrite `api.ts`**

For every fetch function, cast raw JSON to DTO and run the matching mapper. Collection endpoints (`fetchAssets`, `fetchAssetGroups`, etc.) do `.items.map(dtoToAsset)` / `.items.map(dtoToAssetGroup)` as appropriate. `fetchAssetGroupTree` calls `dtoToAssetGroupTree`.

- [ ] **Step 4: Update `hooks.ts`**

Replace `from './types'` → `from './domain'`. No type renames needed — the domain names match the Phase 1 alias names (`Asset`, `AssetGroup`, etc.).

- [ ] **Step 5: Update `index.ts`**

```typescript
export type {
  Asset, AssetType, AssetGroup, AssetGroupMember, AssetGroupSubgroup,
  AssetGroupTree, TagKeyCount, TagValueCount,
} from './domain'
export * from './hooks'
```

- [ ] **Step 6: Delete `types.ts` and update `types.test.ts`**

Run: `rm .worktrees/contract-testing-phase-1/ui/src/features/assets/types.ts`

Open `assets/types.test.ts`. It currently validates the pure-alias wiring (asserting that `AssetRead` is assignable to `Asset`). After the migration, the test should assert that `dtoToAsset` produces a valid `Asset` from a representative DTO fixture — rewrite the test body to import `dtoToAsset` from `./mappers` and call it on an inline DTO literal, then assert the camelCase field names exist on the result.

If the test becomes too tangled to salvage, delete it — the exhaustiveness check in `mappers.ts` is stronger than what the alias test was guarding.

- [ ] **Step 7: Update consumers**

Grep for `from '@/features/assets/types'` — there should be none (Phase 1 re-exported through `index.ts`). Grep for snake_case field accesses on `Asset` / `AssetGroup`: `display_name` → `displayName`, `asset_type_id` → `assetTypeId`, `asset_type_name` → `assetTypeName`, `primary_version` → `primaryVersion`, `build_ref` → `buildRef`, `heatmap_config` → `heatmapConfig`, `created_at` → `createdAt` (Date), `updated_at` → `updatedAt` (Date), `asset_display_name` → `assetDisplayName`, `added_at` → `addedAt`, `parent_id` → `parentId`.

Largest consumer set: `components/AssetTree/*`, `features/navigator/components/treeUtils.ts`, `features/assets/components/*`, `features/navigator/components/AssetPanel*.tsx`. Work in small batches, re-running `tsc --noEmit` between each.

`features/assets/utils.ts` and `utils.test.ts` likely touch snake_case fields — update alongside consumer fixes.

- [ ] **Step 8: Typecheck + lint + test**

Run from `ui/`: `pnpm exec tsc --noEmit -p tsconfig.app.json`
Run: `./scripts/ui-lint.sh --tail 10`
Run: `./scripts/ui-test.sh --tail 10`
Expected: all clean.

- [ ] **Step 9: Commit**

```bash
git -C .worktrees/contract-testing-phase-1 add ui/src/features/assets/ ui/src/ ui/src/components/AssetTree/
git -C .worktrees/contract-testing-phase-1 commit -m "refactor(ui): migrate assets to DTO/domain/mapper pattern"
```

---

## Task 7: Add ESLint `no-restricted-imports` rule

**Files:**
- Modify: `.worktrees/contract-testing-phase-1/ui/eslint.config.js`

Landing this rule only after all six B1 features are migrated guarantees a clean starting point. Navigator (B2) and evaluations (B3) still import DTOs directly via their hand-written `types.ts` files — the rule has to permit them until their own migration chunks land. Solution: restrict `@/generated/api` at the project level but allow it inside `features/*/api.ts`, `features/*/mappers.ts`, **and** inside every unmigrated feature's entire directory. After B3 lands, the per-feature allow-list shrinks back to just `api.ts` / `mappers.ts`.

- [ ] **Step 1: Update `ui/eslint.config.js`**

Replace the current file with:

```javascript
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      'no-restricted-imports': ['error', {
        patterns: [{
          group: ['@/generated/api', '@/generated/api/*'],
          message:
            'Components must import domain types from features/<x>, never DTOs directly. ' +
            'Only features/*/api.ts and features/*/mappers.ts may import from @/generated/api.',
        }],
      }],
    },
  },
  // Allow the DTO import inside the mapper / fetch boundary files.
  {
    files: [
      'src/features/*/api.ts',
      'src/features/*/mappers.ts',
    ],
    rules: {
      'no-restricted-imports': 'off',
    },
  },
  // Temporary: allow unmigrated features (navigator = B2, evaluations = B3)
  // to keep using DTOs until their own migration chunks land. Delete these
  // overrides after B2 / B3 complete.
  {
    files: [
      'src/features/navigator/**/*.{ts,tsx}',
      'src/features/evaluations/**/*.{ts,tsx}',
    ],
    rules: {
      'no-restricted-imports': 'off',
    },
  },
])
```

- [ ] **Step 2: Run lint**

Run: `./scripts/ui-lint.sh --tail 20`
Expected: clean. If any `features/<B1 feature>/components/*` file still imports from `@/generated/api`, the rule catches it — fix the import (route through the domain layer) and re-run.

- [ ] **Step 3: Typecheck**

Run from `ui/`: `pnpm exec tsc --noEmit -p tsconfig.app.json`
Expected: clean.

- [ ] **Step 4: Run UI tests**

Run: `./scripts/ui-test.sh --tail 10`
Expected: green.

- [ ] **Step 5: Commit**

```bash
git -C .worktrees/contract-testing-phase-1 add ui/eslint.config.js
git -C .worktrees/contract-testing-phase-1 commit -m "feat(ui): enforce DTO/domain boundary via ESLint no-restricted-imports"
```

---

## Task 8: Cross-feature smoke test (manual checkpoint)

**Files:** none modified — this task verifies behavior, not code.

- [ ] **Step 1: Start dev environment**

Run: `just dev` (in a terminal)
Expected: API on `:8080`, UI on `:5173`, worker + adapters running.

- [ ] **Step 2: Exercise each migrated feature in the browser**

Open `http://localhost:5173` and walk through each B1 feature page, confirming the UI renders and interactive flows still work:

1. **Datasources** — `Admin → Datasources` (or the datasource list route). Verify: list renders, display names show, tag filter works, `create` dialog opens, a new datasource can be created and appears in the list. Confirm browser console is clean.
2. **Registry** — `Registry` page. Toggle each of the three modes (asset, slo, datasource). Verify: tree expands, node selection highlights, detail panel renders, sidebar filters work. Confirm no TypeScript errors in the browser console.
3. **SLIs** — the SLI list/detail route. Verify: list renders, detail view shows indicators and methods, create/edit form opens.
4. **SLO Groups** — the SLO groups list. Verify: list renders with generated count, create dialog opens and accepts template name + gen_variables.
5. **SLOs** — the SLO list. Verify: list renders, clicking an SLO opens detail showing objectives and comparison config, template detail view renders in Registry.
6. **Assets** — `Navigator` page (assets drive the navigator tree). Verify: asset tree renders, groups expand, clicking an asset opens `AssetPanel`, tags/version/build-ref display correctly. (Navigator itself is not migrated, but its inputs — `Asset`, `AssetGroup` — are domain types now.)

- [ ] **Step 3: Confirm evaluations page still works (regression check on unmigrated feature)**

Navigate to `Evaluations`. Verify the list renders. This tests that B1 didn't break cross-feature imports into the unmigrated `evaluations` feature.

- [ ] **Step 4: Stop dev environment**

`Ctrl+C` in the `just dev` terminal.

- [ ] **Step 5: Record result**

If all six B1 feature pages plus the evaluations regression pass, the chunk is complete. If any fail, file the specific failure and stop — do not paper over visual regressions.

No commit for this task.

---

## Self-review against spec and discovery

- **§5 directory structure:** every feature in scope ends with `domain.ts`, `mappers.ts`, `api.ts`, `hooks.ts`, `index.ts` (plus `components/`) — except `registry`, which has `ui-types.ts` per its special treatment in this plan.
- **§6 naming:** DTO types are referenced via local `type XDto = components['schemas']['…']` aliases inside `mappers.ts` and `api.ts`. Domain type names match discovery §D5 (`Datasource`, `Sli`, `SloGroup`, `Slo`, `Asset`, etc.) except where the plan keeps an existing well-known name (`MethodCriteriaOverride`, `SloObjective`) because no better UI name was proposed.
- **§7.1 exhaustiveness:** every `dtoToX` has `DroppedXKeys`, `MappedXKeys`, and a `_XCoverage` compile-time assertion. A new field on the backend → `just codegen` → `tsc --noEmit` fails with the missing key in the error message.
- **§11.1 map in `queryFn`:** every migrated `api.ts` runs the mapper in the fetch function, before returning to React Query. No `select`-based mapping anywhere.
- **§11.2 strict sync:** every mapper is a plain synchronous function. No `await` inside any mapper body.
- **§11.3 write-path split:** B1 features have no reverse mappers. All six features have flat snake_case request bodies that match the Pydantic models, so forms send `CreateInput`/`UpdateInput` directly (the domain types literally are the wire shape).
- **§15.4 heatmap_config:** the assets mapper passes it through as `Record<string, unknown> | null` with a comment citing the spec.
- **§15.5 chunking:** this plan covers Chunk B1 only. Navigator (B2) and evaluations (B3) are explicitly out of scope; the ESLint rule carries a temporary allow-list for those two directories that should be deleted after their own chunks land.
- **§15.6 migration order:** this plan uses the revised order (datasources → registry → slis → slo-groups → slos → assets).
- **Manual test checkpoint:** single cross-feature smoke test at the end of B1 per user instruction.
- **Worktree reuse:** `.worktrees/contract-testing-phase-1/` continues, rebased onto `main` as Task 0.

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-12-ui-layering-chunk-b1.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task (Task 0 through Task 8), review between tasks, fast iteration. Good fit here because each feature migration is independent and the exhaustiveness check gives the subagent a clear success signal per task.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review.

Which approach?
