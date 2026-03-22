export interface DataSource {
  id: string
  name: string
  display_name: string | null
  adapter_type: string
  adapter_url: string
  tags: Record<string, string>
  has_token: boolean
  created_at: string
  updated_at: string
}

export interface DataSourceCreate {
  name: string
  display_name?: string
  adapter_type: string
  adapter_url: string
  token?: string
  tags?: Record<string, string>
}

export interface DataSourceUpdate {
  display_name?: string
  adapter_url?: string
  token?: string
  tags?: Record<string, string>
}

export interface TagKeyCount {
  key: string
  count: number
}

export interface TagValueCount {
  value: string
  count: number
}
