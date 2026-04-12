// Domain types for the datasources feature. UI vocabulary; camelCase;
// Date objects rather than ISO strings. Hand-written — never regenerated.

export interface Datasource {
  id: string
  name: string
  displayName: string | null
  adapterType: string
  adapterUrl: string
  tags: Record<string, string>
  hasToken: boolean
  createdAt: Date
  updatedAt: Date
}

export interface DatasourceCreateInput {
  name: string
  display_name?: string
  adapter_type: string
  adapter_url: string
  token?: string
  tags?: Record<string, string>
}

export interface DatasourceUpdateInput {
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
