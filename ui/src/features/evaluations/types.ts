// src/features/evaluations/types.ts
// All evaluation-domain types. Replaces the type section of api/client.ts.

export type ActionKind = 'invalidate' | 'override' | 'baseline' | 're-evaluate'

export interface FailingIndicator {
  metric: string
  display_name: string
  value: number
  threshold: string
}

export interface Annotation {
  id: string
  content: string
  author: string | null
  category: string | null
  meta: Record<string, unknown>
  hidden_at: string | null
  hidden_by: string | null
  hidden_reason: string | null
  created_at: string
  updated_at: string
}

export interface EvaluationSummary {
  id: string
  evaluation_name: string
  status: string
  result: 'pass' | 'warning' | 'fail' | 'error'
  score: number
  period_start: string
  period_end: string
  slo_name: string | null
  slo_version: number | null
  sli_name: string | null
  sli_version: number | null
  data_source_name: string | null
  ingestion_mode: string
  adapter_used: string | null
  invalidated: boolean
  original_result: string | null
  original_score: number | null
  override_reason: string | null
  override_author: string | null
  asset_snapshot: {
    name: string
    display_name?: string | null
    tags: Record<string, string>
    primary_version?: string
    build_ref?: string
  }
  evaluation_metadata: Record<string, string>
  latest_annotation?: Annotation
  annotation_count?: number
  created_at: string
  top_failures?: FailingIndicator[]
}

export interface PassTarget {
  criteria: string
  target_value: number
  violated: boolean
}

export interface IndicatorResult {
  metric: string
  display_name: string
  tab_group?: string
  value: number
  compared_value: number | null
  change_absolute: number | null
  change_relative_pct: number | null
  aggregation: string
  status: 'pass' | 'warning' | 'fail'
  score: number
  weight: number
  key_sli: boolean
  pass_targets: PassTarget[] | null
  warning_targets: PassTarget[] | null
}

export interface EvaluationDetail extends EvaluationSummary {
  invalidation_note: string | null
  evaluation_metadata: Record<string, string>
  compared_evaluation_ids: string[]
  annotations: Annotation[]
  indicator_results: IndicatorResult[]
}

export interface TrendPoint {
  timestamp: string
  value: number
  score: number
  eval_id: string
  result: 'pass' | 'warning' | 'fail'
  baseline?: number | null
}

export interface EvaluationFilters {
  group_name?: string
  asset_name?: string
  evaluation_name?: string[]
  date?: string
  from?: string
  to?: string
}

export interface TriggerEvaluationPayload {
  group_name: string
  evaluation_name: string
  slo_name: string
  period_start: string
  period_end: string
  metadata?: Record<string, string>
}

// Column definition for EvaluationTable column picker.
// Defined here (types.ts) so it can be imported by both constants.ts and hooks.ts.
export interface ColumnDef {
  key: string
  label: string
  required: boolean
}

export interface ReEvaluatePayload {
  asset_name: string
  slo_name: string
  from_date?: string
  from_baseline?: boolean
  from_evaluation_id?: string
  slo_version?: number
  dry_run?: boolean
}

export interface ReEvalResultItem {
  id: string
  evaluation_name: string
  period_start: string
  period_end: string
  old_result: string
  new_result: string
  old_score: number
  new_score: number
}

export interface ReEvaluateResponse {
  affected_evaluations: number
  slo_version_used: number
  results: ReEvalResultItem[]
}
