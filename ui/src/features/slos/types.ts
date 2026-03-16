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
  display_name: string | null
  author: string | null
  notes: string | null
  meta: Record<string, unknown>
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
