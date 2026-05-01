# Forms

Guide to TROPEK's form patterns, conventions, and shared components.

## Form Patterns Overview

TROPEK uses three form patterns depending on context:

| Pattern | When | Examples |
|---|---|---|
| **Inline action forms** | Quick operations in popover | Invalidate, Override, Restore, Baseline, ReEvaluate |
| **Modal dialogs** | Entity CRUD | SliForm, DatasourceForm, SloLinkDialogRevised, asset dialogs |
| **Multi-step wizard** | Complex creation flows | SloWizard (4-step progressive disclosure) |

## Action Form System (Evaluations)

**Files:** `src/features/evaluations/components/actions/`

All 5 evaluation action forms (Invalidate, Override, Baseline, ReEvaluate, Restore) share a common architecture.

### Shared Components

| Component | File | Purpose |
|---|---|---|
| `ActionFormShell` | `actions/ActionFormShell.tsx` | Layout container: accent strip + title + description + Cancel/Confirm |
| `SloScopeField` | `actions/slo-scope/SloScopeField.tsx` | Inline "N of M SLOs" summary with picker trigger |
| `SloScopeModal` | `actions/slo-scope/SloScopeModal.tsx` | Full-screen SLO multi-select with search |
| `ReasonAuthorFields` | `actions/ReasonAuthorFields.tsx` | Shared reason + author input pair |
| `useReasonAuthor` | `actions/useReasonAuthor.ts` | State hook with `canConfirm` guard |

### Colour Identity Pattern

Action forms use the "colour identity via accents" pattern:
- Cards/forms use neutral `bg-popover` background
- Identity comes from a **3px top accent strip** + accent-coloured title text + confirm button
- Each action kind has a distinct accent colour (gray for Invalidate, red for Override, blue for Baseline, purple for ReEvaluate)
- **No tinted backgrounds** — this is intentional

### Execution Pattern

All forms follow the same flow:
1. User configures scope via `SloScopeField` + `SloScopeModal`
2. Optionally fills reason/author via `ReasonAuthorFields`
3. On confirm, form fires API calls in parallel via `Promise.all`, collecting per-row results
4. Shows result summary with success/failure/skipped counts per SLO
5. "Retry failed" button re-seeds scope with only failed SLO names
6. `invalidateColumnQueries()` invalidates React Query caches

### SLO Scope System

**Files:** `src/features/evaluations/components/actions/slo-scope/`

`useSloScope()` derives available SLOs from the Navigator's `GroupedMetricHeatmap` domain data. It auto-reseeds selection when the column or filter changes (via "adjusting state during render" pattern, not useEffect).

This creates a cross-feature dependency: the evaluations action system requires navigator heatmap data to determine which SLOs are available for batch operations.

### Action Menu

`EvaluationActionsButton` (`src/features/evaluations/components/EvaluationActions.tsx`) renders a dropdown with all action kinds. Each menu item shows a label + description with a coloured left accent bar. Invalidate is disabled when all rows are already invalidated; Restore only appears when some rows are invalidated.

Actions are displayed in `ActionPopover` (`src/features/evaluations/components/ActionPopover.tsx`) — a fixed-width (380px) escape-dismissible container.

## SLO Wizard (Registry)

**File:** `src/features/registry/forms/SloWizard.tsx` (~360 lines)

4-step progressive-disclosure wizard for SLO creation/versioning.

### Steps

| Step | Component | Visible When |
|---|---|---|
| 1. Identity | `WizardStepIdentity.tsx` | Always |
| 2. Pick SLI | `WizardStepPickSli.tsx` | Name is non-empty |
| 3. Indicators | `WizardStepIndicators.tsx` | Indicators loaded from SLI |
| 4. Comparison | `WizardStepComparison.tsx` | At least one indicator has criteria |

### State Management

State is lifted to the wizard parent — no form library. Each step receives data + onChange callback:
- `identity: IdentityData` — name, display name, author, notes
- `pickSli: PickSliData` — SLI name + full indicators map
- `indicatorRows: IndicatorRow[]` — per-indicator criteria state
- `comparison: ComparisonData` — thresholds, tags, variables

On SLI change, indicator rows are rebuilt, merging existing criteria with new indicators. In edit mode, all steps are pre-filled from the existing SLO.

### Aggregated SLI Mode

When the linked SLI has `mode === 'aggregated'`, Step 3 renders `MethodCriteriaTable` instead of per-indicator rows. This shows per-method criteria overrides with inherited (italic) vs overridden values.

### StructuredCriteriaInput

**File:** `src/components/shared/StructuredCriteriaInput.tsx`

Structured input for SLO criteria expressions (e.g., `<=+10%`). Provides operator select, sign select, numeric input, and percent toggle. Uses `criteriaUtils.ts` for parsing/serialization.

## Entity CRUD Dialogs

### Modal Pattern

Most dialogs use `{ open, onOpenChange }` props with the `FormDialog` wrapper (`src/components/ui/form-dialog.tsx`) or a custom overlay. All have a 3px entity-colour accent strip at the top.

### Asset Dialogs

**Files:** `src/features/assets/components/`

| Dialog | Purpose | Validation |
|---|---|---|
| `AssetCreateDialog` | Create asset with type, labels, optional group | `isValidEntityName` |
| `AssetEditDialog` | Edit display name, type, labels | useEffect resets on data change |
| `AssetTypesDialog` | Full CRUD for asset types in table layout | Inline rename with Enter/Escape |
| `GroupCreateDialog` | Create group with optional parent | `isValidEntityName` |
| `GroupEditDialog` | Edit group, manage parent, linked SLOs | Scans tree for current parent |
| `GroupDeleteDialog` | Two-step delete with SLO handling choice | Radio: keep active vs deactivate |
| `AddAssetToGroupDialog` | Searchable asset picker | Custom modal (not shadcn Dialog) |

### SLI and Datasource Forms

**Files:** `src/features/registry/forms/`

| Form | Validation | Notes |
|---|---|---|
| `SliForm` | Zod + react-hook-form + useFieldArray | Two schemas: raw (>=1 indicator) and aggregated |
| `DatasourceForm` | Zod + react-hook-form | Dual useForm instances for create vs edit |

Both use `TagRowEditor` (duplicated in each file) for managing key-value tags.

### SLO Link Dialogs

Two versions coexist:
- `SloLinkDialog` (`src/features/slos/components/`) — original, native `<select>` + cascading flow
- `SloLinkDialogRevised` (`src/features/registry/forms/`) — revised, uses `SearchableComboBox`

## Form Validation Approaches

| Approach | Used By | Notes |
|---|---|---|
| **Zod + react-hook-form** | SliForm, DatasourceForm, SloCreateForm, SloObjectiveEditor | Full schema validation at module level |
| **Lifted state + manual checks** | SloWizard, SloGroupForm | No Zod; manual validity checks |
| **Backend validation** | SloObjectiveEditor | Two-phase: validate via API, then save |

## Design Conventions

- **Compact, right-aligned forms:** Inline action forms use `max-w-md` + `flex justify-end`. Single-line inputs, not textareas.
- **Sans-serif for UI chrome:** Forms use inline `fontFamily: SANS_SERIF` (from `lib/fonts.ts`).
- **Two-line menu items:** Dropdown items show label + description with coloured left accent bar.
- **Entity accent strips:** Every form/dialog has a 3px coloured strip matching the entity type.
- **No tinted backgrounds:** Colour identity comes from accent strips, title text, and confirm buttons — never from background tinting.

## Shared Form Components

| Component | File | Purpose |
|---|---|---|
| `SearchableComboBox` | `src/components/shared/SearchableComboBox.tsx` | Generic searchable dropdown with badge support |
| `StructuredCriteriaInput` | `src/components/shared/StructuredCriteriaInput.tsx` | SLO criteria expression builder |
| `TagFilterBar` | `src/components/shared/TagFilterBar.tsx` | Search + tag filter pills with key → value picker |
| `VariableResolutionPanel` | `src/components/shared/VariableResolutionPanel.tsx` | Resolved template variables display |
| `BindingChainBreadcrumb` | `src/components/shared/BindingChainBreadcrumb.tsx` | SLO → SLI → Datasource breadcrumb |
| `DeletionConfirmForm` | `src/components/DeletionConfirmForm.tsx` | Destructive action confirmation with red accent |
| `LabelChips` | `src/components/labels/LabelChips.tsx` | Expandable key=value label display |
| `LabelComboBox` | `src/components/labels/LabelComboBox.tsx` | Typeahead for label keys/values |
| `LabelsEditorDialog` | `src/components/labels/LabelsEditorDialog.tsx` | Full label management dialog |
| `GroupTreeSelector` | `src/features/assets/components/GroupTreeSelector.tsx` | Recursive group hierarchy picker |
