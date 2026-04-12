# SLO Registry Phase 2 — Chunk D: Wizard + Page Integration (Tasks 15-16, 18-19)

> Copy-paste this entire file into a new chat window to start Chunk D.

---

## What's Already Done

**Chunk A (Tasks 1-4):** criteriaUtils, registry types, datasource module, API consolidation with tag filtering.

**Chunk B (Tasks 5-8):** Shared components — TagFilterBar, StructuredCriteriaInput, BindingChainBreadcrumb, VariableResolutionPanel, SearchableComboBox.

**Chunk C (Tasks 9-14, 17):** useRegistryTree builders, RegistryTree, RegistrySidebar, DatasourceDetailView + Form, SliDetailView + Form, SloDetailView, AssetBindingView, RegistryDetailPanel router.

---

## Your Task — Chunk D: Tasks 15-16, 18-19

Full plan with code: `docs/superpowers/plans/2026-03-22-slo-registry-phase2-ui.md`

### Task 15: SLO Creation Wizard (plan lines 1970-2142)

**Files:** Create in `ui/src/features/registry/forms/`:
- `SloWizard.tsx` + `.test.tsx`
- `WizardStepIdentity.tsx`
- `WizardStepPickSli.tsx`
- `WizardStepIndicators.tsx` + `.test.tsx`
- `WizardStepComparison.tsx`

4-step progressive disclosure wizard. Supports **create** and **edit** flows.

**Create vs Edit flow:**
- Create: title = "New SLO Definition", footer button = "Create SLO"
- Edit: title = "{name} · New Version", subtitle = "Editing creates version {N+1} · All fields pre-filled from v{N}", footer button = "Create Version"
- Optional `editSlo?: SloDefinition` prop. When present, all steps pre-filled.

**Step 1 — WizardStepIdentity:**
- Fields: name (slug, readonly in edit), display_name, author, notes
- `onComplete(data)` when name is non-empty

**Step 2 — WizardStepPickSli:**
- Two SearchableComboBox: Datasource (UI filter only) → SLI (filtered by adapter_type)
- `onComplete({ sliName, indicators })` when SLI selected
- Edit mode: pre-selects matching SLI

**Step 3 — WizardStepIndicators (most complex):**
- Table columns: `☑ | Indicator | Wt | Key | PASS CRITERIA (Op, Sign, Value, %, Preview) | WARNING CRITERIA (Op, Sign, Value, %, Preview) | +`
- Each row = one indicator from selected SLI
- Unchecked rows dimmed with "(unchecked — will not be included)" at `opacity-40`
- **Multi-criteria AND logic:**
  - `pass_criteria` and `warning_criteria` are **lists** — ALL must pass
  - 1+ pass rows and 1+ warn rows per indicator
  - "AND" label between multi-criteria rows
  - `+` button adds criterion row (both pass + warn), `−` removes (min 1 remains)
  - Each row has its own `StructuredCriteriaInput` for pass AND for warn
  - Both pass and warn show Preview cells
- Subtitle: "Multiple criteria = AND logic. Use + to add."

**Step 4 — WizardStepComparison:**
- Left column — Comparison: Baseline Mode dropdown, compare against last N, aggregate function, include result filter
- Right column — Score Thresholds: Pass ≥ %, Warn ≥ %
- **Visual threshold bar:** three colored zones (Fail red 0→warn%, Warning yellow warn%→pass%, Pass green pass%→100%) — reactive
- Tags section: reuse `TagBuilder` from asset views with SLO-colored accents (#7dc540)
- Variables section: simple key-value rows with + to add

**SloWizard container:**
- Full-page form (not dialog). Progressive disclosure: each step reveals when previous complete.
- On submit: serialize all criteria via `serializeCriteria()`, call `useCreateSlo()`
- Both create and edit call same POST endpoint (backend auto-increments version)

**Pre-fill logic (edit mode):**
- Step 1: name (readonly), display_name, author, notes
- Step 2: auto-select SLI matching existing indicator names
- Step 3: check indicators, fill criteria from `pass_criteria[]`/`warning_criteria[]`, weights, key_sli
- Step 4: comparison config, thresholds, tags, variables

**Tests:** Step 1 only visible initially, progressive reveal, multi-criteria AND rows + labels, create vs edit titles/buttons, pre-fill, Create button disabled until valid.

### Task 16: Revised SLO Link Dialog (plan lines 2145-2170)

**Files:** `ui/src/features/registry/forms/SloLinkDialogRevised.tsx` + `.test.tsx`

Replaces existing `SloLinkDialog` with SearchableComboBox pickers. Used by AssetBindingView "Link an SLO" action.

- 4-step cascade: DS → SLI → SLO → Group
- SLI picker disabled until DS selected
- All pickers use `SearchableComboBox`
- Accepts `lockedGroupName` and `lockedSloName` props for contextual usage
- Uses hooks from canonical modules

**Tests:** cascade behavior, duplicate link detection, submit calls `createGroupSloLink`.

### Task 18: Page Integration — Replace SloRegistryPage (plan lines 2223-2299)

**Files:** Replace `ui/src/pages/SloRegistryPage.tsx` + `.test.tsx`

Wire everything together: `RegistrySidebar` + `RegistryDetailPanel` + form dialogs/wizard.

**URL state:** `?mode=asset&type=slo&selected=http-slo&group=core`

**Cross-entity navigation:** `onNavigate` callback switches mode based on target type.

**Form routing:**
- DatasourceForm, SliForm — dialogs
- SloWizard — **full-page form** replacing detail panel content
  - Opened via: Create → "New SLO", SloDetailView "New Version", AssetBindingView "Edit"
  - Cancel returns to previous detail view
- SloLinkDialogRevised — dialog for linking SLO to group

**Tests:** segmented control renders, search input renders, empty state in main panel.

### Task 19: TypeScript Type Check & Final Verification (plan lines 2302-2338)

- Run `cd ui && npx tsc --noEmit -p tsconfig.app.json` — fix any errors
- Run `./scripts/ui-test.sh --tail 40` — all tests PASS
- Visual smoke test checklist:
  - Segmented control: Asset (default) | SLO | Datasource
  - Search filters tree nodes
  - Tree node click → detail panel
  - Create dropdown: 4 items (SLO, SLI, DS, Group)
  - SLO wizard progressive disclosure
  - Multi-criteria AND rows with + button and AND labels
  - Both pass AND warn columns show previews
  - % toggle green when active
  - Unchecked indicators dimmed
  - Score threshold bar reactive
  - Tags via TagBuilder
  - Edit flow: "New Version" → wizard pre-filled, title shows "· New Version"
  - Binding chain breadcrumbs clickable
  - Tag pills add/remove

---

## Execution

Use `superpowers:subagent-driven-development` — fresh subagent per task with spec compliance + code quality review after each.

Create a worktree branch `slo-registry-phase2-chunk-d` off main.

## Project Conventions

- Test runner: `./scripts/ui-test.sh --tail 10 src/features/registry/forms/SloWizard.test.tsx`
- All tests: `./scripts/ui-test.sh --tail 10`
- Git: `git -C <worktree-path> add <files>` then `git -C <worktree-path> commit -m "..."` (separate calls, never chain with &&)
- Imports: always top of file, never inside functions
- Type check: `cd ui && npx tsc --noEmit -p tsconfig.app.json`
- Entity colors: SLO=#7dc540, SLI=#A371F7, DS=#58A6FF, Group=#8B949E
- Use lucide-react for icons
- Sans-serif font: `fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"` for UI chrome
- Use `--primary` for interactive elements, never hardcode button colors
- TDD: write test → verify fail → implement → verify pass → commit
