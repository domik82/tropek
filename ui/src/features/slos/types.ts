// src/features/slos/types.ts

export interface SliQuery {
  indicator: string
  query: string
}

export interface SloObjective {
  sli: string
  display_name?: string
  pass: { criteria: string[] }[]
  warning?: { criteria: string[] }[]
  weight: number
  key_sli: boolean
  tab_group?: string
}

export interface SloScoreThresholds {
  total_pass?: number
  total_warning?: number
  comparison?: string
}

export interface SloDefinition {
  id: string
  name: string
  version: number
  display_name: string | null
  author: string | null
  notes: string | null
  meta: Record<string, unknown>
  created_at: string
  active: boolean
  slo_yaml: string
}

export interface SloValidationResult {
  valid: boolean
  errors: { field: string; message: string }[]
  objectives?: SloObjective[]
}
