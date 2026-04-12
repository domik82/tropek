# Asset-Group CRUD Relocation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the five asset-group CRUD fetchers + their hook wrappers + their React components from `features/slos/` to `features/assets/` where they belong, eliminating the cross-feature mapper import that Chunk B1 left behind.

**Architecture:** Pure code relocation. No behavior changes, no new tests beyond fixture imports. The work closes a pattern hole: `features/slos/api.ts` currently reaches into `@/features/assets/mappers` to map DTOs for endpoints that have nothing to do with SLOs (they hit `/asset-groups/*`). After this cleanup, each feature owns its own mappers as a private implementation detail, and the ESLint rule added in Chunk B1 Task 7 can be tightened later to forbid cross-feature mapper imports entirely.

**Tech Stack:** TypeScript 5.9, React 19, React Query 5, Vite 8, Vitest. Same worktree pattern as Chunk B1.

---

## Context

Chunk B1 (commits `5d76ebd` through `8a5a241` on `feat/contract-testing-phase-1`) migrated six features to DTO/Domain/Mapper. During Task 6 (assets), the implementer flagged that `slos/api.ts:19-25` imports from `@/features/assets/mappers` to map asset-group responses. That's a smell: mappers are supposed to be private to each feature. The root cause is misfiled code — five functions in `slos/api.ts` are actually asset-group work that was dropped into `slos/` historically (probably next to the `useGroupTree` hook that an SLO-linking dialog originally needed).

The full set of consumer files importing asset-group symbols from `@/features/slos` today (grep evidence collected during B1):

```
components/AssetTree/useAssetTreeActions.ts        → useUpdateGroup
components/AssetTree/AssetTreeDialogs.tsx          → GroupCreateDialog, GroupEditDialog, GroupDeleteDialog
features/registry/RegistrySidebar.tsx              → useGroupTree
features/registry/details/SloDetailView.tsx        → useGroupTree, fetchGroupSloAssignments
features/registry/details/AssetBindingView.tsx     → (group-binding hooks — SEE §Scope below)
features/registry/forms/SloLinkDialogRevised.tsx   → useGroupTree
features/registry/useAllGroupLinks.ts              → fetchGroupSloAssignments
pages/SloRegistryPage.tsx                          → useCreateGroup
```

The assets-side destinations already exist and have the pattern in place — this plan just moves code across the feature boundary and updates imports.

## Scope — what moves, what stays

### Moves to `features/assets/`

Five fetcher functions from `features/slos/api.ts`:

- `fetchGroupTree` — `GET /asset-groups/tree`
- `createGroup` — `POST /asset-groups`
- `updateGroup` — `PUT /asset-groups/{name}`
- `deleteGroup` — `DELETE /asset-groups/{name}?deactivate_slos=...`
- `addSubgroup` — `POST /asset-groups/{parent}/subgroups`

Their React Query hook wrappers from `features/slos/hooks.ts`:

- `useGroupTree`
- `useCreateGroup`
- `useUpdateGroup`
- `useDeleteGroup`
- `useAddSubgroup`

The three CRUD dialog components from `features/slos/components/`:

- `GroupCreateDialog.tsx`
- `GroupEditDialog.tsx`
- `GroupDeleteDialog.tsx`

(plus any associated `.test.tsx` files — move them in lockstep).

### Stays in `features/slos/`

Three SLO-assignment endpoints and their hooks — these are the *binding* between a group and an SLO, which is legitimately SLO-assignment domain:

- `fetchGroupSloAssignments` + `useGroupSloAssignments`
- `createGroupSloAssignment` + `useCreateGroupSloAssignment`
- `deleteGroupSloAssignment` + `useDeleteGroupSloAssignment`

Plus the asset-binding variants:

- `fetchAssetSloAssignments` + hook
- `fetchAssetSloGroupAssignments` + hook

These all stay put.

### Cross-feature imports the cleanup removes

After this plan lands:

- `slos/api.ts` imports from `@/features/assets/mappers` → **gone**. `slos/api.ts` no longer touches asset-group DTOs at all.
- `slos/api.ts` imports `AssetGroup`, `AssetGroupTree` from `@/features/assets` → **gone** (the five fetchers moved out took those with them).

New cross-feature imports this plan introduces:

- None. All new imports are intra-feature (inside `assets/`).

## Migration order

The plan runs as a sequence of tasks on the `feat/contract-testing-phase-1` branch (or a fresh branch off main if Chunk B1 has already merged by the time this runs). One commit per task. No need for parallel subagents — the changes are sequential by design.

Verification after every task: `tsc --noEmit`, ESLint, UI test suite. All three clean before committing.

---

## Task 1: Move fetcher functions

**Files:**
- Modify: `ui/src/features/assets/api.ts` (add five functions)
- Modify: `ui/src/features/slos/api.ts` (delete five functions + their type helpers + the cross-feature imports)

- [ ] **Step 1: Copy the five fetchers from `slos/api.ts` to `assets/api.ts`**

Open `ui/src/features/slos/api.ts` and read lines 87–132 (the five functions). Copy them into `ui/src/features/assets/api.ts`, placing them after the existing asset / asset-type fetchers but before any shared helper sections.

For each copied function:

- Remove the `AssetGroupDto` / `AssetGroupTreeDto` type aliases that need to come from `./mappers` — in `assets/api.ts` they're already imported from the local `./mappers` module, so use the existing imports.
- Remove the `dtoToAssetGroup` / `dtoToAssetGroupTree` imports that came from `@/features/assets/mappers` — they're already local.
- Change `AssetGroupUpdateInput` reference. In `slos/api.ts` it's declared as `components['schemas']['AssetGroupUpdate']` at the top. In `assets/api.ts`, either import it from `@/generated/api` directly at the top of the file (the ESLint rule allows this inside `api.ts`) or declare a local type alias. Prefer the local alias form, matching the pattern from other inputs.
- Update `BASE` constant usage: if `slos/api.ts` and `assets/api.ts` both have `const BASE = '/api'`, the copy works as-is.

- [ ] **Step 2: Delete the functions from `slos/api.ts`**

Remove:
- `fetchGroupTree` (line 87)
- `createGroup` (line 94)
- `updateGroup` (line 107)
- `deleteGroup` (line 118)
- `addSubgroup` (line 126)

Remove the now-unused imports at the top:
- `AssetGroup, AssetGroupTree` from `@/features/assets` (if no remaining fetchers in `slos/api.ts` reference them)
- `dtoToAssetGroup, dtoToAssetGroupTree, AssetGroupDto, AssetGroupTreeDto` from `@/features/assets/mappers`

Also remove `AssetGroupUpdateInput` from `slos/api.ts` if nothing else in the file uses it after the deletion. If something in `slos/api.ts` still uses it (e.g., a still-resident assignment endpoint that touches asset groups by reference), keep it.

Grep-verify after the edit:

```
grep -n "@/features/assets" ui/src/features/slos/api.ts
```

Expected: zero hits. If there are still cross-feature imports, they're for a legit reason (e.g., a domain type used by an SLO-assignment response) — leave those alone.

- [ ] **Step 3: Run verification**

```
pnpm --dir ui exec tsc --noEmit -p tsconfig.app.json
./scripts/ui-lint.sh --tail 10
./scripts/ui-test.sh --tail 10
```

Expected outcome: tsc fails with "Module has no exported member 'fetchGroupTree'" (and similar) errors in `slos/hooks.ts` — those are the hook wrappers that still reference the deleted functions. That's expected; Task 2 fixes them. For now, tsc errors localized to `slos/hooks.ts` and its consumers are OK — do NOT commit until Task 2 clears them.

- [ ] **Step 4: Do NOT commit yet**

This task is incomplete without Task 2 — committing mid-state would leave the branch broken. Proceed directly to Task 2.

---

## Task 2: Move hook wrappers

**Files:**
- Modify: `ui/src/features/assets/hooks.ts` (add five hook wrappers)
- Modify: `ui/src/features/slos/hooks.ts` (delete five hook wrappers)
- Modify: `ui/src/features/assets/index.ts` (re-export new hooks)
- Modify: `ui/src/features/slos/index.ts` (un-export moved hooks)

- [ ] **Step 1: Copy the five hook wrappers from `slos/hooks.ts` to `assets/hooks.ts`**

In `slos/hooks.ts` find:

- `useGroupTree` (around line 64)
- `useCreateGroup`
- `useUpdateGroup`
- `useDeleteGroup`
- `useAddSubgroup`

Copy each into `assets/hooks.ts`. For each:

- Update the `fetchGroupTree` / `createGroup` / etc. import to come from `./api` (local) instead of the current source.
- Update the query key usage. Currently `slos/hooks.ts` uses a `groupKeys` object (or similar — grep to find the exact name). That key factory needs to come with the hooks. Options:
  - (a) Move the `groupKeys` factory from `lib/queryKeys.ts` to live in `assets/hooks.ts` if it's not used by anything else
  - (b) If `groupKeys` is shared between assets and the remaining SLO-group-assignment hooks in `slos/hooks.ts`, leave it in `lib/queryKeys.ts` and both features import from there
  - Grep `grep -rn "groupKeys" ui/src/` to pick the right option before touching the file

- Update any `invalidateQueries` calls that reference related query keys (e.g., invalidating group-SLO assignments after a group delete). Those assignment hooks still live in `slos/hooks.ts` — the invalidation needs to cross the feature boundary. That's an acceptable cross-feature knowledge leak (assets knows about SLO-assignment cache keys), but it's worth flagging in a comment. Alternative: emit a custom event or expose an invalidation hook from slos; both are over-engineered for this cleanup. A one-line comment next to the cross-feature invalidate call is enough.

- [ ] **Step 2: Delete the hook wrappers from `slos/hooks.ts`**

Remove the five hook wrappers. Remove any now-unused imports (the five fetcher functions from `./api` that moved in Task 1; these should already be unreachable since Task 1 deleted the source functions).

Grep-verify:

```
grep -n "useGroupTree\|useCreateGroup\|useUpdateGroup\|useDeleteGroup\|useAddSubgroup" ui/src/features/slos/hooks.ts
```

Expected: zero hits.

- [ ] **Step 3: Update `assets/index.ts`**

Add the new hook names to the barrel's re-export list so consumers can import from `@/features/assets`:

```typescript
export {
  // existing asset / type / tag hooks
  useGroupTree, useCreateGroup, useUpdateGroup, useDeleteGroup, useAddSubgroup,
  fetchGroupTree, // if any consumer still needs the bare fetcher
} from './hooks'
```

- [ ] **Step 4: Update `slos/index.ts`**

Remove the five hook names and the five fetcher function names from the re-export list. Confirm nothing in `slos/hooks.ts` still uses the deleted identifiers.

- [ ] **Step 5: Update consumer imports**

Run a grep across `ui/src/` for every consumer file identified in the Context section and change their imports from `@/features/slos` to `@/features/assets`. Expected hits (verify — the real list is whatever grep returns):

- `components/AssetTree/useAssetTreeActions.ts` — `useUpdateGroup`
- `features/registry/RegistrySidebar.tsx` — `useGroupTree`
- `features/registry/details/SloDetailView.tsx` — `useGroupTree`
- `features/registry/forms/SloLinkDialogRevised.tsx` — `useGroupTree`
- `pages/SloRegistryPage.tsx` — `useCreateGroup`

For files that import BOTH asset-group symbols AND SLO symbols from `@/features/slos`, split into two imports:

```typescript
// Before
import { useSlos, useGroupTree, useSloTagKeys } from '@/features/slos'

// After
import { useSlos, useSloTagKeys } from '@/features/slos'
import { useGroupTree } from '@/features/assets'
```

`RegistrySidebar.tsx` is the most complex consumer — it imports seven symbols from `@/features/slos` today. After the split it'll import from both `@/features/slos` and `@/features/assets`.

- [ ] **Step 6: Run verification**

```
pnpm --dir ui exec tsc --noEmit -p tsconfig.app.json
./scripts/ui-lint.sh --tail 10
./scripts/ui-test.sh --tail 10
```

Expected: tsc clean, lint clean, 539 tests passing (same baseline as after Chunk B1).

If a test file mocks the old import path (`vi.mock('@/features/slos', ...)` and expects `useGroupTree` to come back from that mock), update the mock target to `@/features/assets`. Grep for `vi.mock.*features/slos` and check each hit.

- [ ] **Step 7: Commit**

```bash
git -C <worktree> add ui/src/features/assets/ ui/src/features/slos/ ui/src/
git -C <worktree> commit -m "refactor(ui): relocate asset-group CRUD fetchers and hooks from slos to assets"
```

This commit includes both the fetcher move (Task 1) and the hook wrapper move (Task 2) because they are interdependent — Task 1 alone leaves the branch broken, Task 2 completes the move. Do NOT split this into two commits.

---

## Task 3: Move CRUD dialog components

**Files:**
- Create: `ui/src/features/assets/components/GroupCreateDialog.tsx` (copied from slos)
- Create: `ui/src/features/assets/components/GroupEditDialog.tsx`
- Create: `ui/src/features/assets/components/GroupDeleteDialog.tsx`
- Create: the associated `.test.tsx` files
- Delete: the originals in `ui/src/features/slos/components/`
- Modify: `ui/src/features/assets/index.ts` (add dialog re-exports)
- Modify: `ui/src/features/slos/index.ts` (remove dialog re-exports)
- Modify: `ui/src/components/AssetTree/AssetTreeDialogs.tsx` (update imports)

- [ ] **Step 1: Use `git mv` to preserve history**

```bash
git -C <worktree> mv ui/src/features/slos/components/GroupCreateDialog.tsx ui/src/features/assets/components/GroupCreateDialog.tsx
git -C <worktree> mv ui/src/features/slos/components/GroupEditDialog.tsx ui/src/features/assets/components/GroupEditDialog.tsx
git -C <worktree> mv ui/src/features/slos/components/GroupDeleteDialog.tsx ui/src/features/assets/components/GroupDeleteDialog.tsx
```

Plus any `.test.tsx` files that exist next to them (grep to confirm — if a test file doesn't exist, skip it for that dialog).

- [ ] **Step 2: Fix imports inside the moved files**

Each moved dialog file now sits in `features/assets/components/` and likely imports its hook (`useCreateGroup` etc.) from a relative path that's now wrong. Update:

```typescript
// Before (when file was in slos/components/)
import { useCreateGroup } from '../hooks'

// After (file now in assets/components/)
import { useCreateGroup } from '../hooks'
```

If the import was using a relative `../hooks` path, it works unchanged because `../hooks` now resolves to `assets/hooks.ts` (where Task 2 put the hook). Verify with `pnpm exec tsc --noEmit` and fix whichever imports TypeScript complains about.

Same check for imports of domain types (`AssetGroup`, `AssetGroupTree`) and UI primitives.

- [ ] **Step 3: Update `assets/index.ts` to re-export the dialogs**

```typescript
export { GroupCreateDialog } from './components/GroupCreateDialog'
export { GroupEditDialog } from './components/GroupEditDialog'
export { GroupDeleteDialog } from './components/GroupDeleteDialog'
```

(Or follow whatever existing export pattern the barrel uses — inline vs. split.)

- [ ] **Step 4: Remove the dialogs from `slos/index.ts`**

Delete the three export lines. Confirm nothing in `slos/components/index.ts` (if one exists) still re-exports them.

- [ ] **Step 5: Update the AssetTreeDialogs consumer**

`ui/src/components/AssetTree/AssetTreeDialogs.tsx:3` imports all three dialogs from `@/features/slos`. Change to `@/features/assets`. Verify no other consumers (grep `GroupCreateDialog\|GroupEditDialog\|GroupDeleteDialog` across `ui/src/`).

- [ ] **Step 6: Run verification**

```
pnpm --dir ui exec tsc --noEmit -p tsconfig.app.json
./scripts/ui-lint.sh --tail 10
./scripts/ui-test.sh --tail 10
```

Expected: clean, 539 tests passing.

- [ ] **Step 7: Commit**

```bash
git -C <worktree> add ui/src/features/assets/ ui/src/features/slos/ ui/src/components/AssetTree/
git -C <worktree> commit -m "refactor(ui): relocate asset-group CRUD dialogs from slos to assets"
```

---

## Task 4: Optional — tighten ESLint to forbid cross-feature mapper imports

After Tasks 1-3 land, zero cross-feature mapper imports exist in the codebase. This is the moment to add an ESLint rule that forbids them going forward, so the pattern hole we just closed stays closed.

**Files:**
- Modify: `ui/eslint.config.js`

- [ ] **Step 1: Add a second `no-restricted-imports` pattern**

In the top-level rules block of `ui/eslint.config.js`, extend the existing `patterns` array:

```javascript
'no-restricted-imports': ['error', {
  patterns: [
    {
      group: ['@/generated/api', '@/generated/api/*'],
      message:
        'Components must import domain types from features/<x>, never DTOs directly. ' +
        'Only features/*/api.ts and features/*/mappers.ts may import from @/generated/api.',
    },
    {
      group: ['@/features/*/mappers', '@/features/*/mappers/*'],
      message:
        'Mappers are private to each feature. Import domain types from ' +
        "'@/features/<x>' instead.",
    },
  ],
}],
```

The per-file override for `features/*/api.ts` and `features/*/mappers.ts` already turns `no-restricted-imports` off inside those boundary files, so the new pattern inherits the same escape hatch for free — a feature's own api.ts can still import from its own mappers.ts via the relative `./mappers` path (which doesn't match the `@/features/*/mappers` glob anyway).

- [ ] **Step 2: Run lint, confirm zero violations**

```
./scripts/ui-lint.sh --tail 10
```

Expected: clean. If any file trips the new rule, the cleanup in Tasks 1-3 missed a spot — fix the source import, don't add to the allow-list.

- [ ] **Step 3: Sanity test**

Temporarily add `import { dtoToAsset } from '@/features/assets/mappers'` to a non-boundary file (e.g., `features/datasources/hooks.ts`). Run lint. Confirm the rule fires with the new message. Revert.

- [ ] **Step 4: Commit**

```bash
git -C <worktree> add ui/eslint.config.js
git -C <worktree> commit -m "feat(ui): forbid cross-feature mapper imports via ESLint no-restricted-imports"
```

---

## Self-review checklist

After Task 3 (or Task 4 if you did the optional step):

- `grep -n "@/features/assets/mappers" ui/src/` → zero hits (except inside `features/assets/` itself, where relative imports are used)
- `grep -n "from '@/features/slos'" ui/src/` → no hits referencing the five moved hooks or three dialogs
- `grep -n "useGroupTree\|useCreateGroup\|useUpdateGroup\|useDeleteGroup\|useAddSubgroup" ui/src/features/slos/` → zero hits
- `grep -n "GroupCreateDialog\|GroupEditDialog\|GroupDeleteDialog" ui/src/features/slos/` → zero hits
- tsc clean
- ESLint clean
- 539 UI tests passing
- `git log --oneline` shows the three (or four with Task 4) cleanup commits stacked on top of Chunk B1

## Why this is a separate plan rather than a B1 commit

Chunk B1 was "migrate features to DTO/Domain/Mapper." This cleanup is "move misfiled code to the right feature." Those are two different refactors that happened to surface together. Keeping them separate:

- Makes the B1 PR reviewable without conflating "pattern migration" and "feature boundary correction"
- Produces a cleaner git log: the relocation commits read as their own atomic change
- Lets the B1 smoke test exercise the system as-migrated before any additional churn
- Gives Task 4 (the tighter ESLint rule) a clean moment to land — there's zero cross-feature mapper imports to baseline against

## Estimated effort

- Task 1 + 2 (fetchers + hooks): 20–30 minutes including consumer updates and verification
- Task 3 (dialog components): 15–20 minutes (mostly mechanical file moves + import path updates)
- Task 4 (ESLint tightening): 10 minutes
- Total: 45–60 minutes of focused work, single session

## Risks

- **`RegistrySidebar.tsx` split** — this file imports seven symbols from `@/features/slos` today. Splitting three of them out to a new `@/features/assets` import is the largest single edit in the plan. Risk: missing a symbol or typo'ing an import path. Mitigation: rely on `tsc --noEmit` to surface misses, don't hand-trust the grep.

- **Cross-feature cache invalidation in the moved hooks** — `useDeleteGroup` likely invalidates SLO-group-assignment query keys (`groupSloAssignmentKeys` or similar) that live alongside the remaining SLO-assignment hooks. After the move, `assets/hooks.ts` will import those cache keys from the shared `lib/queryKeys.ts` module. If the keys were defined inside `slos/hooks.ts` itself (unlikely but possible), they'd need to move to `lib/queryKeys.ts` first as a setup step. Check before diving in.

- **Test mock path updates** — any test that does `vi.mock('@/features/slos', ...)` expecting `useGroupTree` to surface from the mock needs its mock target updated. `grep -rn "vi.mock.*features/slos" ui/src/` before Task 2's verification step.

## Execution handoff

**When you pick this up:** dispatch each task to a subagent using `superpowers:subagent-driven-development`. Tasks 1+2 must be a single subagent session (they're interdependent). Task 3 is independent and can be a second session. Task 4 is optional and tiny — do it inline if you feel like it.

Do NOT start implementation until Chunk B1 has been smoke-tested and merged (or until you've accepted the risk of stacking this cleanup on top of an unmerged branch). The branch is in a working state at commit `8a5a241` — this plan builds on top of that commit.
