# Component Catalogue

Reference catalogue of all TROPEK UI components, organised by feature area.

## Shared Components

### Charts (`src/components/charts/`)

| Component | File | Description |
|---|---|---|
| HeatmapChart | `HeatmapChart.tsx` | Core shared heatmap render component (ECharts custom series). **~450 lines.** |
| MultiSeriesChart | `MultiSeriesChart.tsx` | Multi-line/bar time-series chart on shared X axis |
| NoteIndicatorRow | `NoteIndicatorRow.tsx` | Annotation icons above heatmap grid, aligned to columns |
| MetricLabelPanel | `MetricLabelPanel.tsx` | Grouped, paginated metric label panel with toggles |
| ViewToggle | `ViewToggle.tsx` | Two-mode toggle between heatmap and chart views |
| colors.ts | `colors.ts` | OKLCH colour generation (golden-angle hue + lightness cycling) |

### AssetTree (`src/components/AssetTree/`)

| Component | File | Description |
|---|---|---|
| AssetTree | `AssetTree.tsx` | Full sidebar tree for asset groups (3 modes: navigator, slo, assets). **~310 lines.** |
| AssetTreeNode | `AssetTreeNode.tsx` | Recursive tree node with filtering, rename, context menu |
| AssetTreeContextMenu | `AssetTreeContextMenu.tsx` | Right-click context menu for groups and assets |
| AssetTreeDialogs | `AssetTreeDialogs.tsx` | Centralised dialog mount point (7 dialog slots) |
| AssetTreeFooter | `AssetTreeFooter.tsx` | Footer with "New Group" / "Add Asset" buttons |
| AssetTreeInlineRename | `AssetTreeInlineRename.tsx` | Inline rename input with Enter/Escape/blur |

### Tree Primitives (`src/components/tree/`)

| Component | File | Description |
|---|---|---|
| TreeNode | `TreeNode.tsx` | Generic tree node with keyboard support (Enter/Space) |
| TreeFilter | `TreeFilter.tsx` | Search input with clear button and result count |
| tree-icons.ts | `tree-icons.ts` | Lucide icon maps for asset types and entities |

### Labels (`src/components/labels/`)

| Component | File | Description |
|---|---|---|
| LabelChips | `LabelChips.tsx` | Expandable key=value label chip display |
| LabelComboBox | `LabelComboBox.tsx` | Typeahead combo box for label keys/values |
| LabelsEditorDialog | `LabelsEditorDialog.tsx` | Full dialog for managing entity labels |

### Shared UI (`src/components/shared/`)

| Component | File | Description |
|---|---|---|
| BindingChainBreadcrumb | `BindingChainBreadcrumb.tsx` | SLO → SLI → Datasource clickable breadcrumb |
| SearchableComboBox | `SearchableComboBox.tsx` | Generic searchable dropdown select |
| StructuredCriteriaInput | `StructuredCriteriaInput.tsx` | SLO criteria expression builder (operator/sign/value/%) |
| TagFilterBar | `TagFilterBar.tsx` | Search + tag filter pills with key → value picker |
| VariableResolutionPanel | `VariableResolutionPanel.tsx` | Resolved template variables display (grouped by source) |

### Top-Level Components (`src/components/`)

| Component | File | Description |
|---|---|---|
| TimeRangePicker | `TimeRangePicker.tsx` | Preset + absolute date range picker popover |
| DeletionConfirmForm | `DeletionConfirmForm.tsx` | Destructive action confirmation with red accent strip |
| ErrorBoundary | `ErrorBoundary.tsx` | React error boundary (class component) |
| GroupTreeRenderer | `GroupTreeRenderer.tsx` | Recursive group tree with Collapsible (render props) |

### shadcn/ui Primitives (`src/components/ui/`)

15 components: `badge`, `button`, `calendar`, `collapsible`, `command`, `data-table`, `dialog`, `field-label`, `form-dialog`, `input-group`, `input`, `popover`, `select`, `tabs`, `textarea`.

## Navigator Components

**Directory:** `src/features/navigator/components/`

| Component | File | Description |
|---|---|---|
| AssetPanel | `AssetPanel.tsx` | Primary single-asset detail panel; state hub (10 state pieces). **~620 lines.** |
| AssetPanelHeatmapView | `AssetPanelHeatmapView.tsx` | Heatmap mode: stacked heatmap + SLI breakdown + trend charts. **~336 lines.** |
| AssetPanelChartView | `AssetPanelChartView.tsx` | Chart mode: score chart + per-metric trend blocks |
| AssetHeatmap | `AssetHeatmap.tsx` | Stacked mini-heatmap orchestrator with visibility tracking |
| SloMiniHeatmap | `SloMiniHeatmap.tsx` | Single segment wrapping HeatmapChart with tooltip formatting |
| LazyHeatmap | `LazyHeatmap.tsx` | IntersectionObserver-based lazy mount (400px lookahead) |
| GroupPanel | `GroupPanel.tsx` | Group-level evaluation heatmap + table or stacked bar |
| AllEvaluationsPanel | `AllEvaluationsPanel.tsx` | Default panel: all evaluations across assets |
| AssetScoreChart | `AssetScoreChart.tsx` | ECharts line chart of scores over time |
| GroupScoreChart | `GroupScoreChart.tsx` | ECharts stacked bar chart of group scores |
| EvaluationNameFilter | `EvaluationNameFilter.tsx` | Chip filter for evaluation names (All / individual) |
| MetricGroupFilter | `MetricGroupFilter.tsx` | Button group for indicator tab-group filtering |

**Page:** `src/pages/AssetNavigatorPage.tsx` — Route component, URL state via `useSearchParams`.

## Evaluations Components

**Directory:** `src/features/evaluations/components/`

### Core Display

| Component | File | Description |
|---|---|---|
| EvaluationTable | `EvaluationTable.tsx` | Paginated data table with dynamic column picker |
| EvaluationHeader | `EvaluationHeader.tsx` | 3-column header card (title+badge / score / actions) |
| EvaluationHeatmap | `EvaluationHeatmap.tsx` | Thin wrapper over HeatmapChart; groups evals by asset+slot |
| EvaluationTabs | `EvaluationTabs.tsx` | Tab bar for indicator group filtering |
| EvaluationSummaryCard | `EvaluationSummaryCard.tsx` | Header + status badges (invalidated, overridden, pinned) |
| EvaluationIndicatorSection | `EvaluationIndicatorSection.tsx` | SLI table + trend chart grid orchestrator |
| SLIBreakdownTable | `SLIBreakdownTable.tsx` | Indicator table with collapsible groups, key-SLI markers. **~328 lines.** |
| SLIBreakdownGrouped | `SLIBreakdownGrouped.tsx` | Multi-SLO breakdown (navigator); one table per SLO group |
| MetricTrendBlock | `MetricTrendBlock.tsx` | Per-metric trend chart with targets, notes, Y-axis controls |
| ResultBadge | `ResultBadge.tsx` | Coloured pill badge for outcome display |
| TruncationWarning | `TruncationWarning.tsx` | Amber banner when evaluations exceed limit |

### Annotations

| Component | File | Description |
|---|---|---|
| AnnotationSection | `AnnotationForm.tsx` | Full annotation section: header, add form, note list |
| EvaluationNotesSection | `EvaluationNotesSection.tsx` | Scroll-aware wrapper around AnnotationSection |
| NoteEntry | `NoteEntry.tsx` | Single note card with category accent, linkified text |
| NoteGroup | `NoteGroup.tsx` | Grouped re-evaluation notes |
| AddNoteForm | `AddNoteForm.tsx` | Inline note creation form with category picker |
| AnnotationCell | `AnnotationCell.tsx` | Compact note preview for table rows |

### Actions

| Component | File | Description |
|---|---|---|
| EvaluationActionsButton | `EvaluationActions.tsx` | Action menu dropdown (5 action kinds) |
| ActionPopover | `ActionPopover.tsx` | Escape-dismissible container for action forms |
| ActionFormShell | `actions/ActionFormShell.tsx` | Reusable form layout with accent strip |
| InvalidateForm | `actions/InvalidateForm.tsx` | Batch invalidation with SLO scope + reason |
| OverrideForm | `actions/OverrideForm.tsx` | Batch result override (pass/warning/fail radio) |
| BaselineForm | `actions/BaselineForm.tsx` | Batch baseline pinning |
| ReEvaluateForm | `actions/ReEvaluateForm.tsx` | Re-evaluation with from-date/baseline mode |
| RestoreForm | `actions/RestoreForm.tsx` | Batch un-invalidation |
| SloScopeField | `actions/slo-scope/SloScopeField.tsx` | Inline "N of M SLOs" summary |
| SloScopeModal | `actions/slo-scope/SloScopeModal.tsx` | Full-screen SLO multi-select |

### Other

| Component | File | Description |
|---|---|---|
| TriggerEvaluationModal | `TriggerEvaluationModal.tsx` | Dialog for manually triggering evaluations |
| ReasonAuthorFields | `actions/ReasonAuthorFields.tsx` | Shared reason + author input pair |

**Page:** `src/pages/EvaluationDetailPage.tsx`

## Registry Components

**Directory:** `src/features/registry/`

### Core

| Component | File | Description |
|---|---|---|
| RegistrySidebar | `RegistrySidebar.tsx` | Mode switcher + search + tag filter + tree + create dropdown |
| RegistryTree | `RegistryTree.tsx` | Recursive entity tree with colour-coded icons |
| RegistryDetailPanel | `RegistryDetailPanel.tsx` | Routes SelectedNode.type to correct detail view |

### Detail Views (`features/registry/details/`)

| Component | File | Description |
|---|---|---|
| SloDetailView | `SloDetailView.tsx` | Read-only SLO detail with objectives, criteria, version history |
| SliDetailView | `SliDetailView.tsx` | Read-only SLI detail with indicators/query template |
| DatasourceDetailView | `DatasourceDetailView.tsx` | Datasource detail with adapter URL and cross-references |
| AssetBindingView | `AssetBindingView.tsx` | Asset/group context with SLO assignment cards |
| TemplateDetailView | `TemplateDetailView.tsx` | Template SLO detail with `$__gen_` variable highlighting |
| SloGroupDetailView | `SloGroupDetailView.tsx` | SLO group detail with inline regeneration form |

### Forms (`features/registry/forms/`)

| Component | File | Description |
|---|---|---|
| SloWizard | `SloWizard.tsx` | 4-step SLO creation wizard (progressive disclosure). **~362 lines.** |
| WizardStepIdentity | `WizardStepIdentity.tsx` | Step 1: name, display name, author, notes |
| WizardStepPickSli | `WizardStepPickSli.tsx` | Step 2: SLI selection with tag filtering |
| WizardStepIndicators | `WizardStepIndicators.tsx` | Step 3: per-indicator criteria configuration |
| WizardStepComparison | `WizardStepComparison.tsx` | Step 4: comparison settings, thresholds, tags |
| MethodCriteriaTable | `MethodCriteriaTable.tsx` | Per-method criteria overrides for aggregated SLIs |
| AggregatedModeFields | `AggregatedModeFields.tsx` | Aggregated SLI config: query template, interval, methods |
| SliForm | `SliForm.tsx` | Modal for creating/versioning SLI definitions |
| DatasourceForm | `DatasourceForm.tsx` | Modal for creating/editing datasources |
| SloGroupForm | `SloGroupForm.tsx` | In-panel form for creating SLO groups |
| SloLinkDialogRevised | `SloLinkDialogRevised.tsx` | Modal for assigning SLOs to groups (revised version) |

**Page:** `src/pages/SloRegistryPage.tsx`

## Assets & Datasources Components

**Directory:** `src/features/assets/components/`

| Component | File | Description |
|---|---|---|
| AssetCreateDialog | `AssetCreateDialog.tsx` | Create asset with type, labels, optional group |
| AssetEditDialog | `AssetEditDialog.tsx` | Edit display name, type, labels |
| AssetTypesDialog | `AssetTypesDialog.tsx` | Full asset-type CRUD in table layout |
| GroupCreateDialog | `GroupCreateDialog.tsx` | Create group with optional parent |
| GroupEditDialog | `GroupEditDialog.tsx` | Edit group, manage parent, linked SLOs |
| GroupDeleteDialog | `GroupDeleteDialog.tsx` | Two-step delete with SLO handling choice |
| AddAssetToGroupDialog | `AddAssetToGroupDialog.tsx` | Searchable asset picker to add to group |
| GroupDetailPanel | `GroupDetailPanel.tsx` | Full group detail: subgroups, members, linked SLOs |
| GroupTreeSelector | `GroupTreeSelector.tsx` | Recursive tree picker for group selection |
| AllAssetsPanel | `AllAssetsPanel.tsx` | Flat table of all assets with inline delete |

**Page:** `src/pages/AssetsPage.tsx`

## SLO Components

**Directory:** `src/features/slos/components/`

| Component | File | Description |
|---|---|---|
| SloObjectiveTable | `SloObjectiveTable.tsx` | Read-only objectives table with expandable query preview |
| SloObjectiveEditor | `SloObjectiveEditor.tsx` | Editable objectives form with backend validation |
| SloCreateForm | `SloCreateForm.tsx` | Full SLO creation form (older, traditional layout). **~328 lines.** |
| SloList | `SloList.tsx` | Expandable SLO card list with view/edit/history tabs |
| SloLinkDialog | `SloLinkDialog.tsx` | Original SLO-to-group link dialog (cascading selects) |
| SloHistoryPanel | `SloHistoryPanel.tsx` | Version history accordion |

## Timeline Components

**Directory:** `src/features/meta_timeline/components/`

The meta-timeline uses **vis-timeline** (Gantt-style library), not ECharts.

| Component | File | Description |
|---|---|---|
| MetaTimelineSection | (main component) | Timeline wrapper with vis-timeline integration |
| spanColor.ts | `spanColor.ts` | DJB2 hash for deterministic span colours |

## Note Categories

**Directory:** `src/features/note-categories/`

| Component | File | Description |
|---|---|---|
| CategoryManagementPage | `components/CategoryManagementPage.tsx` | CRUD page for note categories |
| CategoryRow | `components/CategoryRow.tsx` | Row with inline editing and colour preview |

**Page:** Route `/settings/note-categories`

## Metric Explorer

**Page:** `src/pages/MetricExplorerPage.tsx`

Two vertically stacked chart sections (Values + Scores), each with a `MetricLabelPanel` sidebar and `MultiSeriesChart`. Supports line/bar toggle and per-metric enable/disable.
