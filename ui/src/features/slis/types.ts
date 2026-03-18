// src/features/slis/types.ts

export interface SliDefinition {
  id: string
  name: string
  display_name: string | null
  version: number
  comparable_from_version: number
  indicators: Record<string, string>  // metric_name → query_string
  notes: string | null
  author: string | null
  meta: Record<string, unknown>
  active: boolean
  created_at: string
}

export interface SliDefinitionCreate {
  name: string
  display_name?: string
  indicators: Record<string, string>
  comparable_from_version?: number
  notes?: string
  author?: string
  meta?: Record<string, unknown>
}
