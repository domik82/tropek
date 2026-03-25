export interface SloGroup {
  id: string
  name: string
  display_name: string | null
  template_slo_name: string
  template_slo_version: number
  gen_variables: Record<string, string[]>
  tags: Record<string, string>
  author: string | null
  version: number
  active: boolean
  created_at: string
  updated_at: string
  generated_slo_count: number
}

export interface SloGroupCreate {
  name: string
  display_name?: string
  template_slo_name: string
  template_slo_version: number
  gen_variables: Record<string, string[]>
  tags?: Record<string, string>
  author?: string
}
