// src/features/slis/types.ts

export interface SliDefinition {
  id: string
  name: string
  display_name: string | null
  version: number
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
  notes?: string
  author?: string
  meta?: Record<string, unknown>
}
