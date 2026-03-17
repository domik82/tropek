# Feature Modules

Each feature is a self-contained domain module with API functions, React Query hooks,
TypeScript types, and components.

## Evaluations

Evaluation list, detail views, SLI breakdown, annotations, and trend charts.

### API Functions (`api.ts`)
- `fetchEvaluations(filters)` -- Paginated list with filtering
- `fetchEvaluationDetail(id)` -- Full detail with annotations + indicators
- `fetchTrend(id, metric)` -- Time-series trend for one metric
- `triggerEvaluation(params)` -- Enqueue new evaluation
- `addAnnotation(evalId, data)` -- Attach annotation
- `invalidateEvaluation(evalId, note)` -- Mark as invalid
- `overrideStatus(evalId, status)` -- Manual status override
- `pinBaseline(evalId)` -- Pin as baseline for future comparisons
- `fetchMetricHeatmap(params)` -- 2D metric heatmap data

### Key Types (`types.ts`)
- `EvaluationSummary` -- List item (id, name, status, result, score, period, asset, top failures)
- `EvaluationDetail` -- Extended with annotations, indicator_results, compared_evaluation_ids
- `IndicatorResult` -- Per-metric breakdown (value, baseline, change, status, targets)
- `TrendPoint` -- Time-series data point (timestamp, value, eval_id, result, baseline)
- `Annotation` -- Content, author, category, timestamps

### Components
- `EvaluationTable` -- Main table with column picker and click handlers
- `EvaluationHeader` -- Result badge, score, metadata
- `EvaluationTabs` -- Tab bar for grouped indicators
- `SLIBreakdownTable` -- Metric-by-metric results
- `MetricTrendBlock` -- 30-day trend chart with baseline overlay
- `TriggerEvaluationModal` -- Modal to enqueue evaluation
- `AnnotationForm` -- Add/display annotations
- `ResultBadge` -- Pass/warning/fail badge

---

## Assets

Asset inventory with type filtering, label search, and group management.

### API Functions (`api.ts`)
- `fetchAssets(filters)` -- List with type/label filters
- `fetchAssetGroupTree()` -- Full group hierarchy

### Key Types (`types.ts`)
- `Asset` -- Name, display_name, type, labels, timestamps
- `AssetGroup` -- Name, display_name, description, members[], subgroups[]
- `AssetGroupTree` -- Groups[] + links[] (hierarchical)

### Components
- `AssetGroupCard` -- Group card with member count
- `AssetFilter` -- Filter UI (platform, OS, version)
- `ColourLegend` -- OS-to-color mapping legend

---

## Navigator

Drill-down navigation: tree panel -> group or asset detail -> evaluation detail.

### API Functions (via hooks)
- Asset tree and heatmap data queries
- Metric heatmap for individual assets

### Key Types (`types.ts`)
- `HeatmapCell` -- Row/column cell with value and result
- `GroupHeatmapData` -- Group-level heatmap matrix
- `AssetScorePoint` -- Score data point per time slot

### Components
- `AssetTreePanel` -- Tree-view navigator (groups, assets, selection)
- `GroupPanel` -- Group evaluations + score chart + heatmap
- `AssetPanel` -- Asset evaluations + metric heatmap + score chart
- `AssetScoreChart` -- Stacked bar chart by time slot
- `GroupScoreChart` -- Stacked bar chart (assets within group)
- `AssetHeatmap` -- 2D heatmap (rows=metrics, cols=time slots)
- `AllEvaluationsPanel` -- Global evaluation table (no filter)

---

## SLOs

SLO definition CRUD, versioning, group hierarchy management, and SLO-group linking.

### API Functions (`api.ts`)
- **SLO**: `fetchSlos()`, `fetchSloDetail()`, `validateSlo()`, `createSloDefinition()`, `deleteSlo()`, `fetchSloVersions()`
- **Groups**: `fetchGroupTree()`, `createGroup()`, `updateGroup()`, `deleteGroup()`, `addSubgroup()`
- **Links**: `fetchGroupSloLinks()`, `createGroupSloLink()`, `deleteGroupSloLink()`
- **Related**: `fetchDatasources()`, `fetchSliDefinitions()`

### Key Types (`types.ts`)
- `SloObjective` -- SLI, criteria, weight, key_sli flag
- `SloDefinition` -- Name, version, objectives[], pass/warning thresholds
- `SloValidationResult` -- Valid flag + error list
- `AssetGroupSLOLink` -- Group-to-SLO binding

### Components
- `SloObjectiveTable` -- Read-only objectives display
- `SloObjectiveEditor` -- Editable objectives form
- `SloHistoryPanel` -- Version history
- `SloCreateForm` -- New SLO creation form
- `GroupSidebar` -- Group tree with CRUD actions
- `GroupCreateDialog` / `GroupEditDialog` / `GroupDeleteDialog` -- Group management modals
- `SloLinkDialog` -- Link SLO to group (datasource -> SLI -> group chain)

---

## SLIs

SLI (Service Level Indicator) definition management.

### API Functions (`api.ts`)
- `fetchSlis(filters)` -- List with adapter_type filter
- `createSli(data)` -- Create new SLI definition

### Key Types (`types.ts`)
- `SliDefinition` -- Name, adapter_type, version, indicators (metric -> query map)
- `SliDefinitionCreate` -- Creation payload
