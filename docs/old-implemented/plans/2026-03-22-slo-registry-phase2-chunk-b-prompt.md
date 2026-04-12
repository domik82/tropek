# SLO Registry Phase 2 — Chunk B: Shared Components (Tasks 5-8)

> Copy-paste this entire file into a new chat window to start Chunk B.

---

## What's Already Done (Chunk A — merged to main)

Tasks 1-4 are complete. These files exist on main:

- `ui/src/features/registry/forms/criteriaUtils.ts` — `parseCriteria()`, `serializeCriteria()`, types `Operator`, `Sign`, `CriteriaParts`
- `ui/src/features/registry/forms/criteriaUtils.test.ts` — 11 tests
- `ui/src/features/registry/types.ts` — `RegistryMode`, `NodeType`, `TreeNode`, `SelectedNode`, `TagFilter`
- `ui/src/features/datasources/types.ts` — `DataSource`, `DataSourceCreate`, `DataSourceUpdate`, `TagKeyCount`, `TagValueCount`
- `ui/src/features/datasources/api.ts` + `hooks.ts` — Full CRUD + tag endpoints
- `ui/src/features/slos/types.ts` — `meta` → `tags: Record<string, string>`, `variables` added, `DataSource`/`SliDefinition` removed
- `ui/src/features/slis/types.ts` — `meta` → `tags`, `adapter_type` added
- `ui/src/features/slos/api.ts` + `hooks.ts` — tag filtering hooks (`useSloTagKeys`, `useSloTagValues`)
- `ui/src/features/slis/api.ts` + `hooks.ts` — tag filtering + adapter type filter
- `ui/src/lib/queryKeys.ts` — `tagKeys()` and `tagValues(key)` on `sloKeys`, `sliKeys`, `datasourceKeys`

All 316 tests pass on main.

---

## What Comes After (Chunks C & D)

Chunk C (Tasks 9-14, 17): Sidebar tree, detail views, detail panel router.
Chunk D (Tasks 15-16, 18-19): SLO wizard, revised link dialog, page integration, final verification.

---

## Your Task — Chunk B: Tasks 5-8

Create 4 shared components in `ui/src/components/shared/` (directory doesn't exist yet — create it).

Full plan with code: `docs/superpowers/plans/2026-03-22-slo-registry-phase2-ui.md`

### Task 5: TagFilterBar (plan lines 825-911)

**Files:** `ui/src/components/shared/TagFilterBar.tsx` + `TagFilterBar.test.tsx`

Reusable search + tag filter bar used in sidebar and form dropdowns.

**Props:**
- `search: string`, `onSearchChange: (s: string) => void`
- `tags: TagFilter[]`, `onTagsChange: (tags: TagFilter[]) => void`
- `tagKeySuggestions: { key: string; count: number }[]`
- `tagValueSuggestions: { value: string; count: number }[]`
- `onTagKeySelected: (key: string) => void`
- `isLoadingKeys: boolean`, `isLoadingValues: boolean`

**Behavior:**
- Search input with `Filter...` placeholder
- Active tags as pills showing `key:value` with `×` remove button (`aria-label="remove tag"`)
- "Add tag filter" button → pick key dropdown → pick value dropdown → pill added
- Escape cancels add flow
- Uses `Search`, `X`, `Plus` from lucide-react. Sans-serif font.

**Tests:** renders search, calls onSearchChange, renders tag pills, removes tags on × click.

### Task 6: StructuredCriteriaInput (plan lines 913-988)

**Files:** `ui/src/components/shared/StructuredCriteriaInput.tsx` + `StructuredCriteriaInput.test.tsx`

Single criteria row: `[Operator ▼] [Sign ▼] [Value] [%]` with optional Preview cell.

**Props:**
- `value: CriteriaParts` (from `@/features/registry/forms/criteriaUtils`)
- `onChange: (parts: CriteriaParts) => void`
- `showPreview?: boolean`

**Four inline controls:**
1. Operator `<select>`: `<`, `<=`, `>`, `>=`, `=`
2. Sign `<select>`: `—` (null), `+`, `-`
3. Value `<input type="number">`
4. `%` toggle `<button>` — green (`--primary`) when active

When `showPreview` is true, render preview using `serializeCriteria()`. This is a single criterion input — multiple criteria (AND logic) are handled by WizardStepIndicators in Chunk D.

**Tests:** renders controls, shows preview, calls onChange on value change, toggles percent.

### Task 7: BindingChainBreadcrumb & VariableResolutionPanel (plan lines 991-1087)

**Files:** Create 4 files in `ui/src/components/shared/`:
- `BindingChainBreadcrumb.tsx` + `.test.tsx`
- `VariableResolutionPanel.tsx` + `.test.tsx`

**BindingChainBreadcrumb** — Three clickable badges with entity-colored borders:
- SLO = #7dc540, SLI = #A371F7, DS = #58A6FF
- Props: `sloName`, `sloVersion?`, `sliName`, `dsName`, `onClickSlo`, `onClickSli`, `onClickDs`
- Separated by `→` arrows (lucide ArrowRight). Version badge in muted color. Sans-serif font.
- Tests: renders chain, calls onClick handlers on badge click.

**VariableResolutionPanel** — Dark panel with monospace text showing merged variable sources:
- Props: `assetVariables`, `sloVariables`, `reserved` (all `Record<string, string>`)
- Each source on own line: label (muted) + `$key=value` pairs with `$key` in orange (#FFA657)
- Hides empty sections
- Tests: renders variable sources in priority order, hides empty sections.

### Task 8: SearchableComboBox (plan lines 1090-1154)

**Files:** `ui/src/components/shared/SearchableComboBox.tsx` + `SearchableComboBox.test.tsx`

Replaces native `<select>` for SLI/SLO/DS pickers.

**Props:**
- `value: string`, `items: { value: string; label: string; badge?: string }[]`
- `onSelect: (value: string) => void`
- `placeholder?: string`

**Behavior:**
- Button trigger showing selected label or placeholder + ChevronDown icon
- Dropdown with search input (magnifying glass) + scrollable item list
- Items filtered by text matching label/value
- Badges right-aligned
- Click-outside closes dropdown. Sans-serif font.

**Tests:** shows placeholder, shows selected label, opens dropdown, calls onSelect.

---

## Execution

Use `superpowers:subagent-driven-development` — fresh subagent per task with spec compliance + code quality review after each.

Create a worktree branch `slo-registry-phase2-chunk-b` off main.

## Project Conventions

- Test runner: `./scripts/ui-test.sh --tail 10 src/components/shared/TagFilterBar.test.tsx`
- All tests: `./scripts/ui-test.sh --tail 10`
- Git: `git -C <worktree-path> add <files>` then `git -C <worktree-path> commit -m "..."` (separate calls, never chain with &&)
- Imports: always top of file, never inside functions
- Type check: `cd ui && npx tsc --noEmit -p tsconfig.app.json`
- Entity colors: SLO=#7dc540, SLI=#A371F7, DS=#58A6FF, Group=#8B949E
- Use lucide-react for icons
- Sans-serif font: `fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"` for UI chrome
- Use `--primary` for interactive elements, never hardcode button colors
- TDD: write test → verify fail → implement → verify pass → commit
