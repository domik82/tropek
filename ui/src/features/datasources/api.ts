import type { DataSource, DataSourceCreate, DataSourceUpdate, TagKeyCount, TagValueCount } from './types'

const BASE = '/api'

export async function fetchDatasources(tagKey?: string, tagVal?: string): Promise<DataSource[]> {
  const params = new URLSearchParams()
  if (tagKey) params.set('tag_key', tagKey)
  if (tagVal) params.set('tag_val', tagVal)
  const qs = params.toString()
  const res = await fetch(`${BASE}/datasources${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error(`fetchDatasources: ${res.status}`)
  const data: { items: DataSource[]; total: number } = await res.json()
  return data.items
}

export async function fetchDatasource(name: string): Promise<DataSource> {
  const res = await fetch(`${BASE}/datasources/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`fetchDatasource: ${res.status}`)
  return res.json()
}

export async function createDatasource(payload: DataSourceCreate): Promise<DataSource> {
  const res = await fetch(`${BASE}/datasources`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`createDatasource: ${res.status}`)
  return res.json()
}

export async function updateDatasource(name: string, payload: DataSourceUpdate): Promise<DataSource> {
  const res = await fetch(`${BASE}/datasources/${encodeURIComponent(name)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`updateDatasource: ${res.status}`)
  return res.json()
}

export async function deleteDatasource(name: string): Promise<void> {
  const res = await fetch(`${BASE}/datasources/${encodeURIComponent(name)}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`deleteDatasource: ${res.status}`)
}

export async function fetchDatasourceTagKeys(): Promise<TagKeyCount[]> {
  const res = await fetch(`${BASE}/datasources/tag-keys`)
  if (!res.ok) throw new Error(`fetchDatasourceTagKeys: ${res.status}`)
  return res.json()
}

export async function fetchDatasourceTagValues(key: string): Promise<TagValueCount[]> {
  const res = await fetch(`${BASE}/datasources/tag-values?key=${encodeURIComponent(key)}`)
  if (!res.ok) throw new Error(`fetchDatasourceTagValues: ${res.status}`)
  return res.json()
}
