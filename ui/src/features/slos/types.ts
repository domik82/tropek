// src/features/slos/types.ts

export interface SloObjective {
  sli: string
  display_name: string
  pass_criteria: string[]
  warning_criteria: string[]
  weight: number
  key_sli: boolean
  sort_order: number
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
  created_at: string
  active: boolean
  objectives: SloObjective[]
  total_score_pass_pct: number
  total_score_warning_pct: number
  comparison: Record<string, unknown>
}

export interface SloValidationResult {
  valid: boolean
  errors: { field: string; message: string }[]
  objectives?: SloObjective[]
}

export interface AssetGroupSLOLink {
  id: string
  link_name: string
  group_id: string
  slo_name: string
  sli_name: string
  data_source_name: string
  created_at: string
}

export interface AssetGroupSLOLinkCreate {
  slo_name: string
  sli_name: string
  data_source_name: string
}

export interface AssetGroupUpdate {
  display_name?: string
  description?: string
}
