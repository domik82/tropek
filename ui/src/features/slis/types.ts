// src/features/slis/types.ts

export interface SliDefinition {
  id: string
  name: string
  display_name: string | null
  adapter_type: string
  version: number
  comparable_from_version: number
  indicators: Record<string, string>  // metric_name → query_string
  notes: string | null
  author: string | null
  tags: Record<string, string>
  active: boolean
  created_at: string
}

export interface SliDefinitionCreate {
  name: string
  display_name?: string
  adapter_type: string
  indicators: Record<string, string>
  comparable_from_version?: number
  notes?: string
  author?: string
  tags?: Record<string, string>
}
