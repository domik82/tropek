// src/features/slos/types.ts

export interface MethodCriteriaOverride {
  pass_threshold?: string[]
  warning_threshold?: string[]
  weight?: number
  key_sli?: boolean
}

export interface SloObjective {
  sli: string
  display_name: string
  pass_threshold: string[]
  warning_threshold: string[]
  weight: number
  key_sli: boolean
  sort_order: number
}

export interface SloComparisonConfig {
  baseline_mode?: string
  number_of_comparison_results?: number
  aggregate_function?: string
  include_result_with_score?: string
  compare_with?: string
}

export interface SloDefinition {
  id: string
  name: string
  version: number
  comparable_from_version: number
  display_name: string | null
  author: string | null
  notes: string | null
  tags: Record<string, string>
  variables: Record<string, string>
  kind: 'standard' | 'template'
  sli_name: string | null
  sli_version: number | null
  created_at: string
  active: boolean
  objectives: SloObjective[]
  total_score_pass_threshold: number
  total_score_warning_threshold: number
  comparison: SloComparisonConfig
  method_criteria: Record<string, MethodCriteriaOverride> | null
}

export interface SloValidationResult {
  valid: boolean
  errors: { field: string; message: string }[]
  objectives?: SloObjective[]
}


export interface AssetGroupUpdate {
  display_name?: string
  description?: string
}

export interface SloAssignment {
  id: string
  asset_id: string | null
  asset_group_id: string | null
  slo_definition_id: string
  slo_name: string
  slo_version: number
  data_source_id: string
  data_source_name: string
  comparison_rules: Record<string, unknown>[] | null
  created_at: string
}

export interface SloAssignmentCreate {
  slo_definition_id: string
  data_source_name: string
  comparison_rules?: Record<string, unknown>[] | null
}
