# UI Layering Discovery — D1–D9

**Date:** 2026-04-12
**Spec:** docs/superpowers/specs/2026-04-12-ui-layering-design.md
**Status:** Discovery phase — read-only audit, no code changes

Generated schema source used for D2/D3 cross-reference:
`/home/domik/projects/tropek/.worktrees/contract-testing-phase-1/ui/src/generated/api.ts`
(the main branch does not yet contain `ui/src/generated/api.ts`; the Phase 1 worktree is the only
committed copy). All line-number citations below refer to paths in the main tree unless prefixed
with `.worktrees/contract-testing-phase-1/`.

---

## D1 — Feature inventory

Consumer counts are approximate (grep for `from '@/features/<x>/types'` plus `from './types'`
inside the same feature, excluding `index.ts` barrels). `index.ts` re-exports are not counted as
consumers since they don't *use* the type, they just forward it.

### assets — `ui/src/features/assets/types.ts`

| Type (line) | External consumers (files) | Approx consumers |
|---|---|---|
| `AssetType` (L3) | `assets/api.ts`, `assets/hooks.ts`, `assets/components/*`, AssetTree components | ~6 |
| `Asset` (L10) | `assets/api.ts`, `assets/hooks.ts`, `AssetTree/*`, `navigator/*` | ~8 |
| `AssetGroupMember` (L22) | `assets/components/GroupDetailPanel.tsx`, `AssetTree/*` | ~3 |
| `AssetGroupSubgroup` (L30) | `assets/components/GroupDetailPanel.tsx` | ~2 |
| `AssetGroup` (L36) | `slos/api.ts`, `navigator/components/treeUtils.ts`, `navigator/components/AssetTreePanel.test.ts`, AssetTree components | ~8 |
| `AssetGroupTree` (L46) | `slos/api.ts`, `assets/components/GroupTreeSelector.test.tsx`, `navigator/components/treeUtils.ts`, `navigator/components/AssetTreePanel.test.ts` | ~4 |
| `TagKeyCount` (L51) | `assets/api.ts`, `assets/components/*` | ~2 |
| `TagValueCount` (L56) | `assets/api.ts`, `assets/components/*` | ~2 |

### datasources — `ui/src/features/datasources/types.ts`

| Type (line) | Consumers | Approx |
|---|---|---|
| `DataSource` (L1) | `datasources/api.ts`, `datasources/hooks.ts`, datasource list components | ~4 |
| `DataSourceCreate` (L13) | `datasources/api.ts` | 1 |
| `DataSourceUpdate` (L22) | `datasources/api.ts` | 1 |
| `TagKeyCount` (L29) | local to datasources | ~1 |
| `TagValueCount` (L34) | local to datasources | ~1 |

### evaluations — `ui/src/features/evaluations/types.ts`

Single largest type file. Many cross-feature consumers.

| Type (line) | Consumers (selected) | Approx |
|---|---|---|
| `ActionKind` (L3) | `navigator/components/AssetPanel.tsx`, `evaluations/components/EvaluationActions.tsx`, `AssetTree/AssetTreeContextMenu.tsx` | ~4 |
| `FailingIndicator` (L6) | `evaluations/components/EvaluationSummaryCard.tsx` | ~2 |
| `Annotation` (L13) | `evaluations/components/NoteEntry*.tsx`, `evaluations/components/AnnotationForm.tsx`, `evaluations/components/EvaluationNotesSection.tsx`, `evaluations/components/AnnotationCell.tsx`, `evaluations/api.ts` | ~7 |
| `EvaluationSummary` (L26) | `evaluations/*`, `navigator/components/AssetScoreChart.tsx`, `navigator/components/GroupScoreChart.tsx`, `navigator/components/AssetPanel*.tsx`, `navigator/utils.ts`, `evaluations/components/EvaluationTable.tsx` | ~12 |
| `PassTarget` (L61) | `navigator/types.ts` (L3), `evaluations/components/SLIBreakdownTable.tsx`, grouped breakdown | ~4 |
| `TrendTargetEntry` (L67) | `evaluations/components/MetricTrendBlock.tsx` | ~1 |
| `TrendTargets` (L73) | `evaluations/components/MetricTrendBlock.tsx` | ~1 |
| `IndicatorResult` (L78) | `evaluations/components/SLIBreakdownTable.tsx`, `SLIBreakdownGrouped.tsx`, `EvaluationIndicatorSection.tsx`, `navigator/components/MetricGroupFilter.tsx`, `AssetPanelChartView.tsx` | ~6 |
| `SliMetadata` (L95) | `navigator/components/AssetPanelHeatmapView.tsx`, `evaluations/components/SLIBreakdown*.tsx` | ~3 |
| `EvaluationDetail` (L103) | `evaluations/components/EvaluationSummaryCard*.tsx`, `EvaluationIndicatorSection*.tsx`, `EvaluationActions.tsx`, `evaluations/api.ts` | ~6 |
| `TrendPoint` (L114) | `evaluations/components/MetricTrendBlock.tsx`, `evaluations/api.ts`, `hooks/useMetricTrendState.ts` | ~3 |
| `EvaluationFilters` (L125) | `evaluations/api.ts`, `evaluations/hooks.ts`, `navigator/hooks.ts` | ~3 |
| `TriggerEvaluationPayload` (L134) | `evaluations/api.ts`, trigger form | ~2 |
| `ColumnDef` (L145) | `evaluations/constants.ts`, `evaluations/hooks.ts`, `EvaluationTable.tsx` | ~3 |
| `ReEvaluatePayload` (L151) | `evaluations/api.ts`, re-eval form | ~2 |
| `ReEvalResultItem` (L162) | re-eval result dialog | ~1 |
| `ReEvaluateResponse` (L173) | re-eval result dialog, `evaluations/api.ts` | ~2 |
| `PinConflictInfo` (L179) | `evaluations/api.ts` (`PinConflictError` class) | 1 |

### evaluations — `ui/src/features/evaluations/constants.ts`

Only defines values (`ACTION_ORDER`, column defs). No exported types.

### slis — `ui/src/features/slis/types.ts`

| Type (line) | Consumers | Approx |
|---|---|---|
| `SliDefinition` (L3) | `slis/api.ts`, `slis/hooks.ts`, `registry/*`, SLI forms | ~5 |
| `SliDefinitionCreate` (L22) | `slis/api.ts`, SLI forms | ~2 |

### slos — `ui/src/features/slos/types.ts`

| Type (line) | Consumers | Approx |
|---|---|---|
| `MethodCriteriaOverride` (L3) | `slos/components/*`, `registry/forms/MethodCriteriaTable.tsx`, `registry/forms/WizardStepIndicators.tsx` | ~4 |
| `SloObjective` (L10) | `slos/components/SloObjective*.tsx` | ~3 |
| `SloComparisonConfig` (L20) | `slos/*` forms | ~2 |
| `SloDefinition` (L28) | `slos/api.ts`, `slos/hooks.ts`, `slos/components/SloList.tsx`, `registry/details/TemplateDetailView.tsx` | ~5 |
| `SloValidationResult` (L51) | `slos/*` forms | ~2 |
| `AssetGroupUpdate` (L58) | `slos/api.ts` (misplaced — belongs in assets) | 1 |
| `SloAssignment` (L63) | `slos/api.ts`, `registry/*` | ~3 |
| `SloAssignmentCreate` (L76) | `slos/api.ts` | 1 |
| `SloGroupAssignment` (L82) | `slos/api.ts`, `registry/*` | ~2 |

### slo-groups — `ui/src/features/slo-groups/types.ts`

| Type (line) | Consumers | Approx |
|---|---|---|
| `SloGroup` (L1) | `slo-groups/api.ts`, `slo-groups/hooks.ts`, `registry/useRegistryTree.ts`, `registry/useRegistryTree.test.ts` | ~4 |
| `SloGroupCreate` (L17) | `slo-groups/api.ts`, forms | ~2 |
| `SloGroupUpdate` (L27) | `slo-groups/api.ts`, forms | ~2 |

### navigator — `ui/src/features/navigator/types.ts`

All UI-derived or wire-response shapes (no direct DTO match for most).

| Type (line) | Consumers | Approx |
|---|---|---|
| `HeatmapCell` (L7) | `evaluations/components/EvaluationHeatmap.tsx`, `navigator/utils.ts`, `navigator/components/AssetHeatmap.tsx`, `AssetPanelHeatmapView.tsx` | ~5 |
| `GroupHeatmapData` (L23) | `navigator/utils.ts`, `navigator/components/GroupHeatmap.tsx` | ~2 |
| `AssetScorePoint` (L30) | `navigator/components/AssetScoreChart.tsx`, `GroupScoreChart.tsx`, `navigator/utils.ts` | ~3 |
| `SlotScoreData` (L39) | score chart components | ~2 |
| `EvaluationColumn` (L47) | `navigator/components/AssetHeatmap.tsx`, `AssetPanelHeatmapView.tsx`, `evaluations/components/EvaluationHeatmap.tsx` | ~4 |
| `HeatmapSummaryCell` (L57) | `navigator/components/*Heatmap*`, `evaluations/components/EvaluationHeatmap.tsx` | ~4 |
| `HeatmapSloGroup` (L69) | `navigator/utils.ts`, heatmap components | ~3 |
| `MetricHeatmapCell` (L79) | `navigator/utils.ts`, heatmap components | ~3 |
| `MetricHeatmapResponse` (L98) | `evaluations/api.ts` (return type!), `navigator/hooks.ts`, `navigator/utils.ts` | ~3 |
| `AssetHeatmapData` (L106) | `navigator/components/AssetHeatmap.tsx`, `AssetPanelHeatmapView.tsx`, `navigator/utils.ts` | ~3 |

### registry — `ui/src/features/registry/types.ts`

All UI-only — purely view/selection state.

| Type (line) | Consumers | Approx |
|---|---|---|
| `RegistryMode` (L1) | `registry/*` pages and sidebar | ~4 |
| `NodeType` (L3) | `registry/*`, `AssetTree/*` | ~5 |
| `TreeNode` (L5) | `registry/RegistryTree.tsx`, `registry/useRegistryTree.ts`, tests | ~4 |
| `SelectedNode` (L18) | `registry/RegistryDetailPanel.tsx`, `registry/details/*`, `RegistrySidebar.tsx` | ~5 |
| `TagFilter` (L24) | `registry/RegistrySidebar.tsx` | 1 |

### lib — `ui/src/lib/types.ts`

| Type (line) | Consumers |
|---|---|
| `PagedResponse<T>` (L3) | (currently imported indirectly via api.ts call sites; at least `datasources/api.ts`, `slos/api.ts`) — candidate to retire in favor of `components['schemas']['PagedResponse_X_']` generated variants |

---

## D2 — DTO match table

Columns:  **Match** = Direct / Renamed / Partial / None.  **DTO schema** = key in `components['schemas']` in the generated file.

### assets

| UI type | Match | DTO schema | Notes |
|---|---|---|---|
| `AssetType` | Renamed | `AssetTypeRead` | |
| `Asset` | Renamed | `AssetRead` | UI lacks `heatmap_config` (new DTO field) |
| `AssetGroupMember` | Renamed | `AssetGroupMemberRead` | |
| `AssetGroupSubgroup` | Renamed | `AssetGroupSubgroupRead` | |
| `AssetGroup` | Renamed | `AssetGroupRead` | |
| `AssetGroupTree` | Renamed | `AssetGroupTreeResponse` | |
| `TagKeyCount` | Direct | `TagKeyCount` | |
| `TagValueCount` | Direct | `TagValueCount` | |

### datasources

| UI type | Match | DTO schema | Notes |
|---|---|---|---|
| `DataSource` | Renamed | `DataSourceRead` | |
| `DataSourceCreate` | Direct | `DataSourceCreate` | |
| `DataSourceUpdate` | Direct | `DataSourceUpdate` | |
| `TagKeyCount` / `TagValueCount` | Direct (duplicate with assets) | `TagKeyCount`/`TagValueCount` | De-dupe opportunity: move to shared layer |

### evaluations

| UI type | Match | DTO schema | Notes |
|---|---|---|---|
| `ActionKind` | None | — | UI-only discriminated literal |
| `FailingIndicator` | Partial | `FailingIndicator` | DTO `value: number \| null`; UI `value: number` — drift |
| `Annotation` | Renamed | `AnnotationRead` | |
| `EvaluationSummary` | Partial | `EvaluationSummary` | Major drift, see D3 |
| `PassTarget` | None | — | DTO has `pass_targets: {[k:string]: unknown}[]` — backend bug (see D3). Real payload does have `criteria/target_value/violated` at runtime |
| `TrendTargetEntry` | Direct | `TrendTargetEntry` | |
| `TrendTargets` | Direct | `TrendTargets` | |
| `IndicatorResult` | Partial | `IndicatorResult` | `pass_targets`/`warning_targets` typed as `dict[str, Any]` in backend — bug |
| `SliMetadata` | None (value type) | — | DTO has `sli_metadata: {[k:string]: unknown} \| null` — backend bug, value type untyped |
| `EvaluationDetail` | Partial | `EvaluationDetail` | Major drift, see D3 |
| `TrendPoint` | Direct | `TrendPoint` | |
| `EvaluationFilters` | None | — | UI-only query param bag |
| `TriggerEvaluationPayload` | Renamed | `EvaluateSingleRequest` (approx) / FastAPI route body | UNCLEAR — verify against `features/evaluations/api.ts` POST `/evaluations`; may match `EvaluateSingleRequest` partially |
| `ColumnDef` | None | — | UI-only table column config |
| `ReEvaluatePayload` | Renamed | `ReEvaluateRequest` | |
| `ReEvalResultItem` | Direct | `ReEvalResultItem` | |
| `ReEvaluateResponse` | Direct | `ReEvaluateResponse` | |
| `PinConflictInfo` | None | — | Error-body shape (HTTP 409) not in OpenAPI — UI-only |

### slis

| UI type | Match | DTO schema | Notes |
|---|---|---|---|
| `SliDefinition` | Renamed | `SLIDefinitionRead` | |
| `SliDefinitionCreate` | Renamed | `SLIDefinitionCreate` | |

### slos

| UI type | Match | DTO schema | Notes |
|---|---|---|---|
| `MethodCriteriaOverride` | UNCLEAR | — | No standalone DTO; likely embedded inside `SLODefinitionRead.method_criteria` — needs spot check |
| `SloObjective` | Renamed | `SLOObjectiveRead` | |
| `SloComparisonConfig` | Partial | embedded in `SLODefinitionRead.comparison` (inline) | |
| `SloDefinition` | Renamed | `SLODefinitionRead` | |
| `SloValidationResult` | Renamed | `SLOValidationResult` | |
| `AssetGroupUpdate` | Misfiled | `AssetGroupUpdate` | Belongs in assets feature |
| `SloAssignment` | Renamed | `SLOAssignmentRead` | |
| `SloAssignmentCreate` | Renamed | `SLOAssignmentCreate` | |
| `SloGroupAssignment` | Renamed | `SLOGroupAssignmentRead` | |

### slo-groups

| UI type | Match | DTO schema | Notes |
|---|---|---|---|
| `SloGroup` | Renamed | `SLOGroupRead` | Note: there is also a plain `SloGroup` DTO used by the grouped heatmap response — name collision (see D3) |
| `SloGroupCreate` | Renamed | `SLOGroupCreate` | |
| `SloGroupUpdate` | Renamed | `SLOGroupUpdate` | |

### navigator

| UI type | Match | DTO schema | Notes |
|---|---|---|---|
| `HeatmapCell` | None (same-name collision) | `HeatmapCell` DTO exists but for a different shape | UI `HeatmapCell` is an ECharts cell with `value: [col,row]`, the DTO `HeatmapCell` is `{display_name, eval_id, metric, result, score, slot}`. Collision — demands a rename in the domain layer |
| `GroupHeatmapData` | None | — | UI-only derived |
| `AssetScorePoint` | None | — | UI-only chart data |
| `SlotScoreData` | None | — | UI-only chart data |
| `EvaluationColumn` | Direct | `EvaluationColumn` | |
| `HeatmapSummaryCell` | Direct | `HeatmapSummaryCell` | |
| `HeatmapSloGroup` | Renamed | `SloGroup` (yes, the grouped-heatmap-response `SloGroup`, not the registry one) | Name collision risk with slo-groups `SLOGroupRead` |
| `MetricHeatmapCell` | Renamed | `HeatmapCellGrouped` | |
| `MetricHeatmapResponse` | Renamed | `GroupedMetricHeatmapResponse` | Name collision: DTO also has `MetricHeatmapResponse` which is the older ungrouped shape (`cells/metrics/slots`). Two different endpoints — UI only consumes grouped |
| `AssetHeatmapData` | None | — | UI-only (derived from grouped response) |

### registry

All five types (`RegistryMode`, `NodeType`, `TreeNode`, `SelectedNode`, `TagFilter`) — **None** / UI-only.

### lib

| UI type | Match | Notes |
|---|---|---|
| `PagedResponse<T>` | Partial | DTO has `PagedResponse_<T>_` concrete variants (e.g. `PagedResponse_AssetRead_`). Currently no generic helper exists. Candidate to keep in lib but alias to generated variants per feature |

---

## D3 — Drift report

**BB** = Real Backend Bug (Pydantic typing wrong, fix at source before migration).
**MRD** = Missing/Required Drift (hand-written optional, DTO required or vice versa).
**ND** = Name Divergence (domain rename candidate).
**DS** = Derived/Synthesized field (belongs in mapper output, not DTO).

### evaluations/EvaluationDetail

| Difference | Class | Action |
|---|---|---|
| UI lacks `baseline_pin_author`, `baseline_pin_reason`, `baseline_pinned_at`, `baseline_unpinned_at` (all on DTO) | Coverage gap | Exactly the `BaselinePin` struct the spec §6.2 predicts. Fold into `baselinePin?: BaselinePin` in domain layer |
| DTO `asset_snapshot: {[key: string]: unknown}` | **BB** | Pydantic `dict[str, Any]` where the real shape is `{name, display_name?, tags, primary_version?, build_ref?}`. Needs Pydantic model (same pattern as the Phase 1 tags fix). |
| DTO `sli_metadata?: {[key: string]: unknown} \| null` | **BB** | Value type untyped. Backend should emit `dict[str, SliMetadata]` |
| DTO `variables: {[key: string]: unknown}` — UI type does not expose this field at all | **BB** (probably) + coverage drop | Likely should be `dict[str, str]`. UI has been silently dropping it |
| UI `top_failures?: FailingIndicator[]` optional vs DTO required with default `[]` | MRD | Non-optional after mapper |
| UI `annotation_count?: number` optional vs DTO required default 0 | MRD | Non-optional after mapper |
| UI `latest_annotation?: Annotation` vs DTO `latest_annotation?: AnnotationRead \| null` | ND | Normalize to `latestAnnotation: Annotation \| null` |
| UI `original_result: string \| null` plain-string vs domain `Outcome \| null` | ND | Map to enum in mapper |
| UI `result: 'pass' \| 'warning' \| 'fail' \| 'error' \| null` already typed; DTO `result: string \| null` | BB-ish | UI is more precise than Pydantic. Backend should use Literal; for now mapper narrows the cast |
| UI `period_start`/`period_end: string` vs proposed domain `period: DateRange` | ND | Mapper combines |
| UI `invalidation_note: string \| null` ✓ matches | — | |
| UI `evaluation_metadata: Record<string, string>` on both summary+detail — **DTO has no such field** on either | UNCLEAR | Either (a) UI has a stale ghost field never populated, (b) backend emits it anyway and Pydantic schema is incomplete, or (c) the DTO's `variables` field is the rename target. **Needs user confirmation.** |
| UI `sli_metadata?: Record<string, SliMetadata>` already typed more strictly than DTO | — | Keep UI shape in domain, mapper narrows |

### evaluations/EvaluationSummary

Same set as EvaluationDetail for the overlapping fields, plus:

| Difference | Class | Action |
|---|---|---|
| UI `override_reason`, `override_author` typed `string \| null`; DTO has them as optional `string \| null` | — | Match after mapper |
| UI lacks baseline pin fields (same as Detail) | Coverage gap | Same `BaselinePin` fold |
| UI has `top_failures?`; DTO required | MRD | Same |
| UI has `annotation_count?`; DTO required | MRD | Same |

### evaluations/IndicatorResult

| Difference | Class | Action |
|---|---|---|
| DTO `pass_targets: {[key: string]: unknown}[] \| null` | **BB** | Should be `list[PassTarget]`. Fix in `api/tropek/modules/quality_gate/schemas.py` |
| DTO `warning_targets: {[key: string]: unknown}[] \| null` | **BB** | Same |
| DTO lacks `status: 'pass'\|'warning'\|'fail'` literal — plain `string` | Minor | UI already narrows |

### evaluations/FailingIndicator

| Difference | Class | Action |
|---|---|---|
| UI `value: number` vs DTO `value: number \| null` | MRD | Handle nullable in mapper/display |

### evaluations/HeatmapCellGrouped (UI `MetricHeatmapCell`)

| Difference | Class | Action |
|---|---|---|
| DTO `pass_targets`/`warning_targets: {[key: string]: unknown}[] \| null` | **BB** | Same backend bug as `IndicatorResult` |

### assets/Asset (AssetRead)

| Difference | Class | Action |
|---|---|---|
| UI lacks `heatmap_config?: {[key: string]: unknown} \| null` (new DTO field) | Coverage gap + **BB** | Backend uses `dict[str, Any]`; value shape unclear. Likely a nested typed object. Flag for backend fix |
| UI has `created_at`/`updated_at: string`, DTO same | — | |
| Phase 1 already fixed `tags: dict[str, Any]` → `dict[str, str]` | — | Done |

### slos/SloDefinition (SLODefinitionRead)

| Difference | Class | Action |
|---|---|---|
| `method_criteria: Record<string, MethodCriteriaOverride> \| null` — need to verify DTO typing is not `dict[str, Any]` | UNCLEAR → probable **BB** | Spot check required during migration |
| `variables: Record<string, string>` vs DTO — verify (same pattern as assets) | UNCLEAR | Spot check |

### navigator types

- Most are UI-only (see D4); no drift.
- `MetricHeatmapResponse` name collision — the UI re-used the generic name for the *grouped* endpoint's response. Forces a domain rename.

### slo-groups/SloGroup vs grouped-heatmap `SloGroup`

DTO name collision — the OpenAPI schema has two schemas both called `SloGroup` (registry version is `SLOGroupRead`, heatmap version is plain `SloGroup`). This is a backend naming smell: the grouped-heatmap response type should be renamed in Pydantic (e.g., `HeatmapSloGroupSection`) to avoid the collision. Flag for backend cleanup.

### Real backend bug list (for immediate fix before migration)

1. `EvaluationDetail.asset_snapshot: dict[str, Any]` — should be typed Pydantic model.
2. `EvaluationDetail.sli_metadata: dict[str, Any] | None` — value type should be `SliMetadata`.
3. `EvaluationSummary.variables: dict[str, Any]` — should be `dict[str, str]` (same pattern as Phase 1 asset tags fix).
4. `IndicatorResult.pass_targets`/`warning_targets: list[dict[str, Any]] | None` — should be `list[PassTarget]`.
5. `HeatmapCellGrouped.pass_targets`/`warning_targets: list[dict[str, Any]] | None` — same.
6. `AssetRead.heatmap_config: dict[str, Any] | None` — needs typed model if the shape is known.
7. `SloGroup` vs `SLOGroupRead` name collision in OpenAPI schema — cosmetic but confusing.
8. **Possible** `FailingIndicator.value: float | None` — verify whether real payload ever emits null; if not, tighten to `float`.

---

## D4 — UI-only types

| Type | Feature | Why UI-only | References domain types? |
|---|---|---|---|
| `RegistryMode`, `NodeType`, `TreeNode`, `SelectedNode`, `TagFilter` | registry | Sidebar/tree selection state | No — lives above domain layer |
| `HeatmapCell` (navigator) | navigator | ECharts cell tuple `[col,row]` — visualization primitive | References `PassTarget` transitively via other types |
| `GroupHeatmapData`, `AssetHeatmapData` | navigator | Pre-computed ECharts grid from grouped response | Derived from domain types |
| `AssetScorePoint`, `SlotScoreData` | navigator | Chart series data | Derived |
| `ActionKind` | evaluations | Union of action button identities (`invalidate`, `override`, etc.) — drives UI menus | No |
| `ColumnDef` | evaluations | Table column picker config for `EvaluationTable` | No |
| `EvaluationFilters` | evaluations | Query-string bag used by hooks | No |
| `PinConflictInfo` | evaluations | Shape of HTTP 409 error body; not in OpenAPI | No |
| `PagedResponse<T>` | lib | Generic response wrapper (generated has concrete variants only) | Wraps any domain |

All UI-only types should move to `ui-types.ts` per spec §5.

---

## D5 — Proposed domain vocabulary

Validated against actual wire shapes observed above. Spec-suggested items are marked ✓ or revised.

### Read-side renames

| DTO name | Proposed domain name | Reason |
|---|---|---|
| `EvaluationSummary` / `EvaluationDetail` | `Evaluation` / `EvaluationDetail` | Keep `Evaluation` for the list row, `EvaluationDetail` for the detail view. The spec's `EvaluationRun → Evaluation` rename is aspirational — the DTO is already called `EvaluationSummary`, so the flip is `Summary → Evaluation` (simpler) |
| `result: string` | `outcome: Outcome` where `Outcome = 'pass' \| 'warning' \| 'fail' \| 'error'` | ✓ Typed union |
| `original_result: string \| null` | `originalOutcome: Outcome \| null` | Same |
| `period_start: string` + `period_end: string` | `period: DateRange` where `DateRange = { from: Date; to: Date }` | ✓ Parse dates at boundary |
| `baseline_pin_*` flat fields | `baselinePin: BaselinePin \| null` where `BaselinePin = { author: string; reason: string; pinnedAt: Date; unpinnedAt: Date \| null }` | ✓ Struct |
| `asset_snapshot: dict[str, Any]` | `assetSnapshot: AssetSnapshot` (matching UI's current ad-hoc inline shape) | Requires backend fix first |
| `evaluation_id`, `sli_name`, `slo_name`, `data_source_name` | `evaluationId`, `sliName`, `sloName`, `dataSourceName` | Camel-case at boundary per spec §7.1 examples |
| `IndicatorResult` | `Indicator` | Drop `Result` suffix — the indicator *is* the result in the UI's model |
| `pass_criteria: string` (if present anywhere) | `criteria: Criteria` structured | Criteria grammar parsed at fetch time |
| `HeatmapCellGrouped` | `HeatmapIndicatorCell` | Clearer; disambiguates from UI's own `HeatmapCell` ECharts type |
| `GroupedMetricHeatmapResponse` | `AssetHeatmap` (domain aggregate) | Drop `Response` suffix, name the concept |
| `SLODefinitionRead` | `Slo` | Drop `Definition`/`Read` (those are backend implementation vocabulary) |
| `SLOObjectiveRead` | `SloObjective` | |
| `SLIDefinitionRead` | `Sli` | |
| `SLOGroupRead` | `SloGroup` | Without the `Read` suffix |
| `AssetRead` | `Asset` | Phase 1 already aliases this |
| `AssetGroupRead` | `AssetGroup` | |
| `AssetTypeRead` | `AssetType` | |
| `DataSourceRead` | `Datasource` (one word) | Consistent with existing UI usage |
| `AnnotationRead` | `Annotation` | |

### Proposed additions beyond the spec's suggestions

- `Outcome` as a reusable type alias in `features/evaluations/domain.ts`, re-exported from `lib` if used cross-feature (heatmap cells in navigator need it).
- `ActionKind` stays UI-only, not promoted to domain — it's dispatch state, not data.

### Conflicts flagged

- Spec's `Evaluation` name matches what we want, but `features/evaluations/` already exports `EvaluationSummary` which many components import. Rename is a large find-replace (~12 files).
- The current `features/navigator/types.ts` exports its own `HeatmapCell` type *and* the backend has a `HeatmapCell` DTO with a completely different shape. Domain rename `HeatmapCell → HeatmapEChartsCell` (UI-only) frees the name for a domain cell type if ever needed. The current usage is UI-only anyway, so the simplest path is to move navigator's `HeatmapCell` to `ui-types.ts` under a new name and never have a domain-layer `HeatmapCell`.

### Write-path input types (per §11.3 inspection flags)

| Write path | File / line | Current body shape | Domain proposal | Reverse mapper needed? |
|---|---|---|---|---|
| `triggerEvaluation` | `features/evaluations/api.ts:89` sends `TriggerEvaluationPayload` `{group_name, evaluation_name, slo_name, period_start, period_end, metadata}` | If domain uses `period: DateRange`, the form must provide `{period: DateRange, ...}` and a reverse mapper splits it into `period_start/period_end` strings | **Yes** — `triggerInputToDto` |
| `reEvaluate` | `features/evaluations/api.ts:245` sends `ReEvaluatePayload` with XOR `from_baseline \| from_date \| from_evaluation_id` plus `pin_strategy` enum | If domain models the source as a discriminated union `ReEvalSource = {kind: 'baseline'} \| {kind: 'date'; from: Date} \| {kind: 'evaluation'; id: string}`, the reverse mapper flattens | **Yes** — `reEvaluateInputToDto` |
| `overrideStatus` | `features/evaluations/api.ts:151` sends `{new_result: string, reason, author}` | If domain uses `Outcome`, convert enum → string in reverse mapper | **Yes** — trivial one-liner `outcomeToDto` |
| All other writes (asset/slo/sli/datasource/slo-group CRUD) | various | Already snake_case flat bodies matching DTOs | Keep form shape = DTO | **No** |

---

## D6 — Feature migration order

Spec-suggested order is sound. Minor revisions based on actual audit:

1. **`datasources`** — pure CRUD, 5 types, no drift, 1–2 component consumers. Smallest viable pattern proof.
2. **`slis`** — only 2 types, simple CRUD. Confirms pattern on a second near-trivial case.
3. **`slo-groups`** — 3 types, simple CRUD, but has the `SloGroup` DTO-name collision with the grouped heatmap. Address the collision once during this migration (propose backend rename at the same time).
4. **`slos`** — 9 types, includes nested objectives + the potential `method_criteria: dict[str, Any]` backend bug. Medium cost. Also clean up the misfiled `AssetGroupUpdate`.
5. **`assets`** — already aliased in Phase 1 worktree. Add a real mapper layer and `heatmap_config` handling. Re-validates the pattern on a partially-migrated feature.
6. **`registry`** — all UI-only types (D4). No mapper work at all — just a file split (`types.ts` → `ui-types.ts`) and ESLint enforcement. Cheap migration to keep directory layout uniform.
7. **`navigator`** — heatmap derivations. Mapper converts grouped heatmap DTO → domain + pre-computed `AssetHeatmapData`. Performance-sensitive (see D8).
8. **`evaluations`** — largest, most complex, most value. Includes reverse-mapper work (D5 write paths) and criteria-string parsing. Tackle last with maximum pattern experience.

**Revision vs spec:** move `registry` before `navigator` because registry has zero mapper cost (all UI-only). Doing it early keeps the file-structure refactor separable from the mapper work. The spec had the same relative ordering (registry → navigator → evaluations) but lumped registry in with "complex UIs"; in fact the complexity is purely UI state, not data shape.

---

## D7 — Mapper cost estimate

Rough line counts: `domain.ts` (types), `mappers.ts` (functions + exhaustiveness checks), and any reverse mappers. Boilerplate dominated by TypeScript field listings (each field ~1 line in domain, ~1 line in mapper body, ~1 line in the `EvaluationMapping` exhaustiveness helper = ~3 lines/field).

| Feature | domain.ts | mappers.ts | reverse mappers | Total | Ratio comment |
|---|---|---|---|---|---|
| datasources | ~35 | ~60 | 0 | ~95 | Trivial; pure ceremony, but sets pattern |
| slis | ~25 | ~45 | 0 | ~70 | Trivial |
| slo-groups | ~30 | ~55 | 0 | ~85 | Trivial |
| slos | ~120 | ~200 | 0 | ~320 | Multi-type feature; big but well-shaped |
| assets | ~90 | ~150 | 0 | ~240 | Already partially done; mostly identity mappers |
| registry | ~40 (to `ui-types.ts`) | 0 | 0 | ~40 | **Zero mapper cost** — file move only |
| navigator | ~140 (many UI-only, few domain) | ~180 (grouped-heatmap transform) | 0 | ~320 | Boundary-mapper does real transform |
| evaluations | ~250 | ~400 | ~80 | ~730 | Largest, criteria parsing, 3 reverse mappers |

**Total upfront boilerplate: ~1900 lines** across all features.

**Unfavorable cost ratio:**
- `datasources`, `slis`, `slo-groups` are pure ceremony today (identity mappers). Boilerplate-to-value is low *in isolation*, but they're cheap individually and establish uniformity. Keep in scope.
- `registry` has the best ratio — near-zero cost and immediate ESLint-enforced boundary.

---

## D8 — Performance audit for large-dataset paths

Endpoints returning >100 domain objects per response:

| Endpoint | Typical size | Mapper work | Concern |
|---|---|---|---|
| `GET /api/evaluations?...` (`fetchEvaluations` — `features/evaluations/api.ts:41`) | up to `maxEvaluations` (config — currently on the order of 1,000–5,000 rows, paginated and aggregated client-side) | Per row: ~25 field copies, 3 date parses (`created_at`, `period_start`, `period_end`), nullable-string narrowing on `result`/`original_result` to `Outcome`, nested `top_failures` walk (≤5 items each) | **Moderate.** At 5,000 rows × ~30 ops each = 150k ops per fetch. Microsecond scale. Fine. |
| `GET /api/evaluate/metric-heatmap?asset_name=X` (`fetchGroupedMetricHeatmap` — line 192) | N columns (evaluations) × M indicators per SLO × K SLO groups, plus composite row. A heavy asset: ~50 columns × ~20 indicators × ~5 groups = ~5,000 indicator cells per response | Per cell: ~10 field copies + pass_targets/warning_targets nested arrays (parsed from `dict[str, Any]` bug-fix shape) + result-to-Outcome narrowing | **Watch.** The user already flagged heatmap rendering as slow. Mapper is O(n·m·k) linear. At 5k cells this is ~50k ops — still micros. But if heatmap grows (1000-column year-view), this gets to hundreds of thousands of allocations. **Recommend:** mutate-in-place strategy (cast the DTO response, re-assign fields on the same object) for this one endpoint instead of `.map()`-with-new-objects |
| `GET /api/trend?...` (`fetchTrend` — line 75) | TrendPoint[] typically ~100–500 | ~6 field copies + date parse per point | **Low.** |
| `GET /api/evaluations/metric-heatmap?...` (`fetchMetricHeatmap` — line 177) | Same order as grouped variant | Same | Same caveat |

**Flagged for custom strategy:** `fetchGroupedMetricHeatmap` — use an in-place mapping pattern to avoid doubling allocations. Spec §8.4 anticipated this; discovery confirms the concern is real but not a blocker for the other features.

**Not flagged:** `fetchEvaluations` (paginated, capped), `fetchTrend`, all detail endpoints (single object), all CRUD list endpoints (assets/slos/slis/datasources — all paginated with reasonable `pageSize`).

---

## D9 — ESLint current state

- **Config file:** `ui/eslint.config.js` — **flat config** (uses `defineConfig` from `eslint/config`, imports from `@eslint/js`, `typescript-eslint`, `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh`).
- **Current entries:** a single flat-config object for `**/*.{ts,tsx}` extending recommended rulesets. No `no-restricted-imports` rule exists today. No per-directory overrides exist today. No conflicts.
- **Where the new rule goes:** append a second config object (or add `rules` to the existing one) with `no-restricted-imports`. The per-directory allow-list for `features/*/api.ts`, `features/*/mappers.ts`, and optionally `features/*/queryOptions.ts` goes as additional flat-config objects with narrower `files` globs and a `rules: { 'no-restricted-imports': 'off' }` override. Example sketch:
  ```js
  {
    files: ['ui/src/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': ['error', { patterns: [{
        group: ['@/generated/api', '@/generated/api/*'],
        message: 'Components must import domain types from features/<x>, never DTOs directly.'
      }]}]
    }
  },
  {
    files: ['ui/src/features/*/api.ts', 'ui/src/features/*/mappers.ts'],
    rules: { 'no-restricted-imports': 'off' }
  }
  ```
- **Conflicts with existing rules:** none. The flat config currently only extends recommended rulesets; no custom `no-restricted-imports` to merge with.
- **Note on path alias:** Vite alias `@` → `ui/src` is active; the restriction pattern `@/generated/api` matches what the codebase will actually import once codegen lands in the main branch (it's already used this way in the Phase 1 worktree).

---

## Summary and recommendations

- **Total features to migrate:** 8 (`assets`, `datasources`, `slis`, `slos`, `slo-groups`, `registry`, `navigator`, `evaluations`) plus `lib/types.ts` cleanup.
- **Real backend bugs found (require fix before migration):**
  1. `EvaluationDetail.asset_snapshot: dict[str, Any]` (needs Pydantic model)
  2. `EvaluationDetail.sli_metadata: dict[str, Any] | None` (value type should be `SliMetadata`)
  3. `EvaluationSummary.variables: dict[str, Any]` (should be `dict[str, str]`, mirrors Phase 1 fix)
  4. `IndicatorResult.pass_targets`/`warning_targets: list[dict[str, Any]] | None` (should be `list[PassTarget]`)
  5. `HeatmapCellGrouped.pass_targets`/`warning_targets: list[dict[str, Any]] | None` (same)
  6. `AssetRead.heatmap_config: dict[str, Any] | None` (type the inner shape)
  7. `SloGroup` vs `SLOGroupRead` OpenAPI name collision (rename heatmap `SloGroup`)
- **Features with unfavorable cost/value ratio:** `datasources`, `slis`, `slo-groups` are pure-ceremony identity mappers; accepted as cheap uniformity cost.
- **Features with performance concerns:** `navigator` (`fetchGroupedMetricHeatmap`) — recommend in-place mapping strategy.
- **Total estimated boilerplate:** ~1,900 lines across all 8 features (~730 of which is `evaluations` alone).
- **Recommended first feature to migrate:** `datasources`. Smallest, zero drift, zero UI-only mixing, immediate pattern validation. Register the ESLint rule as part of this migration so subsequent features can't accidentally regress.
- **Blockers:**
  - The generated `ui/src/generated/api.ts` is not yet committed on `main`; it only exists in the Phase 1 worktree. Either land Phase 1 first or run `just codegen` on `main` before migration work starts.
  - `EvaluationSummary.evaluation_metadata` field mismatch (UI has it, DTO does not) — **UNCLEAR**, needs user confirmation whether it's a UI ghost or a backend schema hole.
  - `SloDefinitionRead.method_criteria` and `variables` typing — UNCLEAR without a spot-check of `api/tropek/modules/slo_registry/schemas.py`; likely additional `dict[str, Any]` bugs.

### UNCLEAR items needing user input before implementation planning

1. Is `EvaluationSummary.evaluation_metadata` a live field? If so, add to Pydantic schema; if dead, drop from UI.
2. Should `SLODefinitionRead.method_criteria` and `.variables` be typed maps (`dict[str, MethodCriteriaOverride]` / `dict[str, str]`)? Probably yes — confirm.
3. `TriggerEvaluationPayload` matches `EvaluateSingleRequest` only approximately — verify POST `/evaluations` actually binds to that Pydantic model in `api/tropek/modules/quality_gate/router.py`.
4. `AssetRead.heatmap_config` shape — is it a known structure or opaque user JSON? Drives whether the backend bug fix is mechanical or design work.
