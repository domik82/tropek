# API Schemas

Request/response contracts for all TROPEK API endpoints. Schema files live in
`api/tropek/modules/*/schemas.py` and `api/tropek/modules/quality_gate/schemas/`.

For shared base types, see the [Common Types](#common-types) section.

## Evaluation Trigger

Source: `quality_gate/schemas/trigger.py`.

| Type | Direction | Key Fields |
|------|-----------|------------|
| `EvaluateSingleRequest` | Request | `asset_name`, `eval_name`, `period_start`, `period_end`, `variables: dict[IdentifierKey, SafeStr]` |
| `EvaluateSingleResponse` | Response | `evaluation_id: UUID`, `slo_evaluation_ids: list[UUID]` |
| `EvaluateBatchRequest` | Request | `mode` (`by_date` / `by_asset`), `asset_name?`, `periods?`, `asset_names?`, `period_start/end?`, `eval_name`, `variables` |
| `EvaluateBatchResponse` | Response | `evaluation_ids: list[UUID]`, `slo_evaluation_ids: list[UUID]` |
| `BatchPeriod` | Nested | `period_start`, `period_end` |

## Evaluation Summary and Detail

Source: `quality_gate/schemas/evaluations.py`.

| Type | Direction | Key Fields |
|------|-----------|------------|
| `EvaluationSummary` | Response | Full eval metadata + `annotation_count`, `latest_annotation`, `top_failures: list[FailingIndicator]` |
| `EvaluationDetail` | Response | Extends `EvaluationSummary`. Adds `invalidation_note`, `compared_evaluation_ids`, `annotations`, `indicator_results`, score thresholds, `sli_metadata` |
| `IndicatorResult` | Nested | `metric`, `display_name`, `tab_group`, `value`, `compared_value`, `change_absolute`, `change_relative_pct`, `status`, `score`, `weight`, `key_sli`, `pass_targets`, `warning_targets` |
| `PassTarget` | Nested | `criteria: str`, `target_value: float`, `violated: bool` |
| `FailingIndicator` | Nested | `metric`, `display_name`, `value`, `threshold` |
| `EvaluationNameEntry` | Response | `name`, `count`, `last_run` |
| `AssetSnapshot` | Nested | `asset_id?`, `name`, `display_name?`, `tags`, `primary_version?`, `build_ref?` |
| `SliMetadata` | Nested | `mode`, `expected_samples`, `actual_samples`, `missing_pct`, `chunks_failed` |

`EvaluationDetail` uses a `@model_validator` to sync `annotation_count` from loaded
annotations. `top_failures` extracts failing indicators with their threshold info.

## Trend

Source: `quality_gate/schemas/evaluations.py`.

| Type | Direction | Fields |
|------|-----------|--------|
| `TrendPoint` | Response | `timestamp`, `value`, `score`, `eval_id`, `result`, `baseline`, `evaluation_name?`, `targets?` |
| `TrendTargets` | Nested | `pass_targets` (aliased from `"pass"`), `warn` |
| `TrendTargetEntry` | Nested | `criteria`, `target_value`, `violated` |

## Heatmap

Source: `quality_gate/schemas/heatmap.py`.

### Flat Heatmap

| Type | Purpose |
|------|---------|
| `MetricHeatmapResponse` | `asset_name`, `slots`, `metrics`, `cells` |

### Grouped Heatmap

| Type | Purpose |
|------|---------|
| `GroupedMetricHeatmapResponse` | `asset_name`, `columns` (oldest-first), `groups: list[HeatmapSloGroupSection]`, `composite: list[HeatmapSummaryCell]` |
| `EvaluationColumn` | `evaluation_id`, `period_start/end`, `eval_name`, `has_notes` |
| `HeatmapSloGroupSection` | One SLO's rows: `slo_name`, `slo_display_name`, `metrics`, `cells`, `summary` |
| `HeatmapCellGrouped` | Per-cell: `evaluation_id`, `slo_evaluation_id`, `period_start`, metric info, `result`, `score`, `value`, deltas, weights, targets |
| `HeatmapSummaryCell` | Per-column aggregate: `evaluation_id`, `result`, `score` (0-100), thresholds, `sli_metadata`, version info, `invalidated` |

### Cache Types

| Type | Purpose |
|------|---------|
| `HeatmapColumnFragment` | Cache unit: `schema_version: 1`, `evaluation_run_id`, `column`, `per_slo`, `composite_summary` |
| `HeatmapColumnSloFragment` | One SLO's contribution to one column |

Cache key: `heatmap:col:v1:{run_id}`.

## Annotations

Source: `quality_gate/schemas/annotations.py`.

| Type | Direction | Fields |
|------|-----------|--------|
| `AnnotationRead` | Response | Full annotation with category, group fields, hidden state. XOR: `slo_evaluation_id` or `evaluation_run_id`. |
| `AnnotationCreate` | Request | `content: SafeStr`, `author?`, `category_id: UUID`, `tags: Tags` |
| `AnnotationUpdate` | Request | All fields optional for partial update |
| `AnnotationHide` | Request | `reason: SafeStr`, `author?` |

## Annotation Categories

Source: `quality_gate/schemas/annotation_categories.py`.

| Type | Direction | Fields |
|------|-----------|--------|
| `AnnotationCategoryRead` | Response | `id`, `name`, `label`, `color: CategoryColor`, `show_on_graph`, `is_system`, timestamps |
| `AnnotationCategoryCreate` | Request | `name: NameStr` (slug), `label: LabelStr` (max 12), `color: CategoryColor`, `show_on_graph` |
| `AnnotationCategoryUpdate` | Request | All optional |

`CategoryColor` enum: `sky`, `green`, `amber`, `red`, `purple`, `pink`, `slate`, `gray`.

## Baseline and Override

Source: `quality_gate/schemas/baseline.py`.

| Type | Direction | Fields |
|------|-----------|--------|
| `InvalidateRequest` | Request | `invalidation_note: SafeStr` |
| `PinBaselineRequest` | Request | `reason`, `author` |
| `OverrideStatusRequest` | Request | `new_result`, `reason`, `author` |

## Re-evaluation

Source: `quality_gate/schemas/re_evaluation.py`.

### Request Types (Discriminated Unions)

| Type | Direction | Key Fields |
|------|-----------|------------|
| `ReEvaluateFromDateRequest` | Request | `scope: Scope`, `selector?`, `from_date`, `slo_version?`, `dry_run`, `pin_strategy?` |
| `ReEvaluateFromBaselineRequest` | Request | Same minus `from_date` |
| `ReEvaluateFromEvaluationRequest` | Request | Same; `from_evaluation_id` via URL path |
| `ReEvaluateRequest` | Internal | Flat parameter object for core service |

### Response Types

| Type | Direction | Fields |
|------|-----------|--------|
| `ReEvaluateResponse` | Response | `affected_evaluations`, `slo_version_used`, `results: list[ReEvalResultItem]` |
| `ReEvalResultItem` | Nested | Old/new result + score, period, eval name, SLO info |

### Scope and Selector (Discriminated Unions)

| Type | Discriminator | Fields |
|------|---------------|--------|
| `AssetScope` | `kind='asset'` | `asset_name` |
| `GroupScope` | `kind='group'` | `group_name` (not yet implemented in split endpoints) |
| `SloSelector` | `kind='slo'` | `slo_name` |
| `EvalNamesSelector` | `kind='evaluation_names'` | `evaluation_names: list[str]` |

## SLO Registry

Source: `slo_registry/schemas.py`.

| Type | Direction | Key Fields |
|------|-----------|------------|
| `SLODefinitionCreate` | Request | `name`, `sli_name`, `sli_version?`, `objectives: list[SLOObjectiveIn]`, `comparison: ComparisonConfig`, `kind` (`standard`/`template`), `tags` |
| `SLODefinitionRead` | Response | Flattens `sli_definition` relationship into `sli_name` + `sli_version` via `model_validator` |
| `SLOObjectiveIn` | Nested | `sli`, `display_name`, `weight`, `key_sli`, `pass_criteria: list[str]`, `warning_criteria: list[str]` |
| `SLOObjectiveRead` | Nested | Same plus `id`, `sort_order`, `tab_group` |
| `ComparisonConfig` | Nested | `compare_with`, `number_of_comparison_results`, `include_result_with_score`, `aggregate_function`, `scope_tags` |
| `SLOValidationResult` | Response | Dry-run validation result |
| `SLOTestResult` | Response | Dry-run evaluation with full indicator results |

## SLI Registry

Source: `sli_registry/schemas.py`.

| Type | Direction | Key Fields |
|------|-----------|------------|
| `SLIDefinitionCreate` | Request | `name`, `adapter_type`, `mode` (`raw`/`aggregated`), `indicators?`, `query_template?`, `interval?`, `methods?`, `tags` |
| `SLIDefinitionRead` | Response | All fields |

Mode-dependent validation via `model_validator(mode='after')`:
- **Raw**: requires non-empty `indicators`, disallows `query_template`/`interval`/`methods`
- **Aggregated**: requires `query_template`/`interval`/non-empty `methods`, disallows `indicators`

`AggregationMethod` enum: `min`, `mean`, `max`, `std`, `sum`, `median`, `p75`, `p90`, `p95`, `p99`.

## DataSource

Source: `datasource/schemas.py`.

| Type | Direction | Key Fields |
|------|-----------|------------|
| `DataSourceCreate` | Request | `name`, `adapter_type`, `adapter_url`, `tags`, `token?` |
| `DataSourceUpdate` | Request | All optional |
| `DataSourceRead` | Response | Includes derived `has_token: bool` -- actual token never exposed |

## Assets

Source: `assets/schemas.py`.

| Type | Direction | Key Fields |
|------|-----------|------------|
| `AssetTypeCreate` | Request | `name`, `is_default?` |
| `AssetTypeRead` | Response | `name`, `is_default`, `asset_count?` |
| `AssetCreate` | Request | `name`, `display_name?`, `type_name`, `tags`, `variables?`, `color?` |
| `AssetUpdate` | Request | All optional |
| `AssetRead` | Response | All fields |
| `AssetGroupCreate` | Request | `name`, `display_name?`, `description?`, `color?`, `members?`, `subgroups?` |
| `AssetGroupRead` | Response | Members and subgroups with denormalized names |
| `AssetGroupTreeResponse` | Response | Full hierarchy of top-level groups |

## Assignments

Source: `assignments/schemas.py`.

| Type | Direction | Key Fields |
|------|-----------|------------|
| `SLOAssignmentUpsert` | Request | `data_source_id`, `comparison_rules?` |
| `SLOAssignmentRead` | Response | Includes resolved `slo_name`, `slo_version`, `data_source_name` |
| `SLOAssignmentUpgrade` | Request | `new_slo_definition_id` |
| `SLOGroupAssignmentUpsert` | Request | `data_source_id` |
| `SLOGroupAssignmentRead` | Response | Includes resolved group and datasource names |

## SLO Groups

Source: `slo_groups/schemas.py`.

| Type | Direction | Key Fields |
|------|-----------|------------|
| `SLOGroupCreate` | Request | `name`, `template_slo_name`, `gen_variables`, `tags?` |
| `SLOGroupUpdate` | Request | `template_slo_name?`, `gen_variables?`, `display_name?` |
| `SLOGroupRead` | Response | Includes `generated_slo_count` |
| `ExtractRequest` | Request | `slo_name` to extract from group |

## Display Groups

Source: `display_groups/schemas.py`.

| Type | Direction | Key Fields |
|------|-----------|------------|
| `DisplayGroupCreate` | Request | `name`, `display_name?`, `parent_id?`, `sort_order?` |
| `DisplayGroupRead` | Response | All fields |
| `DisplayGroupMemberAdd` | Request | `slo_name` |

Members reference SLO concept names (strings), not definition IDs.

## Asset Metadata

Source: `asset_meta/schemas.py`.

| Type | Direction | Key Fields |
|------|-----------|------------|
| `MetaSnapshotCreate` | Request | `source`, `observed_at`, `values: list[MetaValueInput]`, `closed: list[MetaClosureInput]` |
| `MetaSnapshotCreated` | Response | `snapshot_id: UUID` |
| `TimelineResponse` | Response | `groups: list[TimelineGroup]`, `items: list[TimelineItem]` |
| `TimelineSummaryResponse` | Response | `itemCount: int` |

## Common Types

Source: `modules/common/schemas.py`.

### Base Models

| Type | Purpose |
|------|---------|
| `StrictInput` | `extra='forbid'` -- all request body models must inherit this |
| `PagedResponse[T]` | Generic paginated response: `items: list[T]`, `total: int` |

### Validated String Types

| Type | Constraint | Used For |
|------|-----------|----------|
| `SafeStr` | Pattern `^[^\x00]*$` + runtime null-byte check | All user-facing string fields |
| `SafeQueryStr` | Same as `SafeStr` for query parameters | Query params |
| `TagKey` | K8s label key syntax, 1-63 chars | JSONB tag dict keys |
| `TagValue` | K8s label value syntax, 0-63 chars | JSONB tag dict values |
| `Tags` | `dict[TagKey, TagValue]` | Tag fields throughout |
| `IdentifierKey` | `[A-Za-z_][A-Za-z0-9_]*`, 1-128 chars | Variable dict keys |

### Numeric Types

| Type | Purpose |
|------|---------|
| `IntNotBool` | Integer that rejects `bool` (since `isinstance(True, int)` is True) |
| `FloatNotBool` | Float that rejects `bool` |
| `StrictQueryBool` | Query parameter accepting only `true`/`false` strings |

### Null-Byte Protection

Three layers to prevent `\x00` crashes in asyncpg:

| Validator | Scope |
|-----------|-------|
| `SafeStr` pattern | Simple string fields |
| `SafeJsonDict` | Flat JSONB dicts (shallow walk) |
| `SafeJsonAny` | Nested JSONB structures (recursive walk) |

Converts what would be 500 (`UntranslatableCharacterError`) into 422.
