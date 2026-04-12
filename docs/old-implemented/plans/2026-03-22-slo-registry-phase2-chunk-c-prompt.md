# SLO Registry Phase 2 — Chunk C: Sidebar + Detail Views (Tasks 9-14, 17)

> Copy-paste this entire file into a new chat window to start Chunk C.

---

## What's Already Done

**Chunk A (Tasks 1-4, merged):** criteriaUtils, registry types, datasource module, API consolidation with tag filtering.

**Chunk B (Tasks 5-8, merged):** Shared components in `ui/src/components/shared/`:
- `TagFilterBar` — search + tag pill filtering
- `StructuredCriteriaInput` — operator/sign/value/% controls with preview
- `BindingChainBreadcrumb` — SLO→SLI→DS colored clickable badges
- `VariableResolutionPanel` — dark panel showing merged variable sources
- `SearchableComboBox` — dropdown with search replacing native select

---

## What Comes After (Chunk D)

Chunk D (Tasks 15-16, 18-19): SLO wizard, revised link dialog, page integration, final verification.

---

## Your Task — Chunk C: Tasks 9-14, 17

Full plan with code: `docs/superpowers/plans/2026-03-22-slo-registry-phase2-ui.md`

### Task 9: useRegistryTree Hook — Tree Builders (plan lines 1156-1399)

**Files:** `ui/src/features/registry/useRegistryTree.ts` + `.test.ts`

Pure data transformation — builds tree data from API responses for each sidebar mode.

**Three builder functions:**
- `buildSloTree(slos, slis, datasources, links)` → SLO → SLI → DS hierarchy
- `buildDatasourceTree(datasources, slis, slos, links)` → DS → SLI → SLO hierarchy
- `buildAssetTree(groups, groupLinksMap)` → Group → Asset → Binding chain hierarchy
  - `groupLinksMap: Record<string, MinLink[]>` keyed by group name (avoids showing all links for every group)

**Plus `filterTree(nodes, search):`**
- Filters by name substring (case insensitive)
- Keeps parent if any child matches
- Returns all when search empty

**Minimal interfaces:** `MinSlo`, `MinSli`, `MinDs`, `MinLink`, `MinGroup` — just the fields needed for tree building.

**Tests:** all three builders + filterTree with parent/child matching logic. See plan for full test code.

### Task 10: RegistryTree Component (plan lines 1403-1597)

**Files:** `ui/src/features/registry/RegistryTree.tsx` + `.test.tsx`

Renders hierarchical tree with expand/collapse, entity-colored icons, and click selection.

**Props:**
- `nodes: TreeNode[]`, `selected: SelectedNode | null`, `onSelect: (node: SelectedNode) => void`

**Key details:**
- `TYPE_COLORS`: slo=#7dc540, sli=#A371F7, datasource=#58A6FF, group=#8b949e, asset=#c9d1d9, binding=#7dc540
- Expand/collapse via `data-testid="toggle-{node.id}"` buttons with ChevronRight/ChevronDown
- Selected node: left border + tinted background using entity color
- Node name click → `onSelect({ type, name })`, badge in muted text
- `data-testid="node-{node.id}"` with `data-selected="true|false"`
- Sans-serif font, empty state "No items"

**Tests:** renders root nodes, expands on toggle, calls onSelect, highlights selected, shows badges.

### Task 11: RegistrySidebar Component (plan lines 1600-1849)

**Files:** `ui/src/features/registry/RegistrySidebar.tsx` + `.test.tsx`

Composes: segmented control + TagFilterBar + RegistryTree + Create button.

**Props:**
- `mode: RegistryMode`, `onModeChange`, `selected: SelectedNode | null`, `onSelect`
- `onCreateAction: (type: 'datasource' | 'sli' | 'slo' | 'group', context?) => void`

**Key details:**
- 3-button segmented control: Asset | SLO | Datasource (active = `bg-primary/15 text-primary`)
- Wires TagFilterBar with mode-dependent tag suggestions (SLO tags for SLO mode, DS tags for DS mode, asset tags for asset mode)
- Builds tree nodes using builders from Task 9, applies filterTree with search
- CreateDropdown: "Create" button at bottom → popup with 4 items (New SLO/SLI/DS/Group) each with entity-colored left accent bar
- Width: 260px, border-r

**Data fetching:** uses `useSlos`, `useSliDefinitions`, `useDatasources`, `useGroupTree`, tag key/value hooks, `useAllGroupLinks` (note: this hook may need to be created — fetches SLO links for all groups).

**Tests:** renders segmented control, switches mode, renders search, renders create button. Wrap in QueryClientProvider.

### Task 12: Datasource Detail & Form (plan lines 1852-1886)

**Files:** Create 4 files in `ui/src/features/registry/details/` and `forms/`:
- `DatasourceDetailView.tsx` + `.test.tsx`
- `DatasourceForm.tsx` + `.test.tsx`

**DatasourceDetailView:**
- Header: display_name + name (mono) + adapter_type badge
- Fields: adapter_url (mono), token display (has_token ? `••••••••` : "None"), tags as pills
- "Used by" section: SLIs with same adapter_type (clickable → `onNavigate({ type: 'sli', name })`)
- Actions: Edit (opens DatasourceForm), Delete (confirmation, checks 409 for affected SLO links)

**DatasourceForm:**
- Dialog with react-hook-form + zod
- Fields: name (create only), display_name, adapter_type, adapter_url, token (password), tags (key-value rows)
- Token: create = plain input, edit = `••••••••` placeholder, only in payload if changed

**Tests:** rendering, interactions, submit mutations, edit mode pre-fill.

### Task 13: SLI Detail & Form (plan lines 1888-1921)

**Files:** Create 4 files:
- `SliDetailView.tsx` + `.test.tsx`
- `SliForm.tsx` + `.test.tsx`

**SliDetailView:**
- Header: display_name + name (mono) + version badge + active badge
- Indicators table: monospace query with `$variable` highlighted orange (#FFA657) via regex
- Tags, notes, author
- "Used by" SLOs section (clickable → onNavigate)
- Actions: New Version (opens SliForm pre-filled), Deactivate

**SliForm:**
- Dialog. Props: `editFrom?: SliDefinition`, `defaultAdapterType?: string`
- Fields: name (create only), display_name, adapter_type (pre-filled), author, notes
- Indicators: useFieldArray — name + query rows, `+ Add indicator`
- Tags: key-value rows
- Submit: `useCreateSli()`

**Tests:** rendering, dynamic indicator rows, pre-fill, submit.

### Task 14: SLO Detail & Asset Binding Views (plan lines 1924-1967)

**Files:** Create 4 files:
- `SloDetailView.tsx` + `.test.tsx`
- `AssetBindingView.tsx` + `.test.tsx`

**SloDetailView:**
- Objectives table with pass AND warn criteria
- Score thresholds: "Pass ≥ 90% · Warning ≥ 75%"
- Comparison summary: "several_results (3) · include: pass_or_warn · aggregate: avg"
- Tags, variables, notes, author, linked assets, version history
- **Actions:** "New Version" (calls onEdit → opens SloWizard pre-filled), "Deactivate"
- **No "Edit" button** — editing IS creating a new version

**AssetBindingView:**
- Shows SLO bindings for selected asset (from parent group's links)
- Each binding card: BindingChainBreadcrumb + VariableResolutionPanel + objectives summary
- Per-binding actions: Test SLO, Edit (→ new version), Unlink
- Empty state: "Link an SLO" button

### Task 17: RegistryDetailPanel Router (plan lines 2173-2220)

**Files:** `ui/src/features/registry/RegistryDetailPanel.tsx` + `.test.tsx`

Routes `SelectedNode` to correct detail view:
- `slo` → SloDetailView
- `sli` → SliDetailView
- `datasource` → DatasourceDetailView
- `asset` / `group` → AssetBindingView
- `null` → "Select an item from the sidebar"

**Tests:** empty state when nothing selected.

---

## Execution

Use `superpowers:subagent-driven-development` — fresh subagent per task with spec compliance + code quality review after each.

Create a worktree branch `slo-registry-phase2-chunk-c` off main.

## Project Conventions

- Test runner: `./scripts/ui-test.sh --tail 10 src/features/registry/RegistryTree.test.tsx`
- All tests: `./scripts/ui-test.sh --tail 10`
- Git: `git -C <worktree-path> add <files>` then `git -C <worktree-path> commit -m "..."` (separate calls, never chain with &&)
- Imports: always top of file, never inside functions
- Type check: `cd ui && npx tsc --noEmit -p tsconfig.app.json`
- Entity colors: SLO=#7dc540, SLI=#A371F7, DS=#58A6FF, Group=#8B949E
- Use lucide-react for icons
- Sans-serif font: `fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"` for UI chrome
- Use `--primary` for interactive elements, never hardcode button colors
- TDD: write test → verify fail → implement → verify pass → commit
