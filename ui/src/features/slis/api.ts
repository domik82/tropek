// src/features/slis/api.ts
import type { SliDefinition, SliDefinitionCreate } from './types'

const BASE = '/api'

export async function fetchSliDefinitions(
  adapterType?: string, tagKey?: string, tagVal?: string,
): Promise<SliDefinition[]> {
  const params = new URLSearchParams()
  if (adapterType) params.set('adapter_type', adapterType)
  if (tagKey) params.set('tag_key', tagKey)
  if (tagVal) params.set('tag_val', tagVal)
  const qs = params.toString()
  const res = await fetch(`${BASE}/sli-definitions${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error(`fetchSliDefinitions: ${res.status}`)
  const data: { items: SliDefinition[]; total: number } = await res.json()
  return data.items
}

export async function fetchSliDetail(name: string): Promise<SliDefinition> {
  const res = await fetch(`${BASE}/sli-definitions/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`fetchSliDetail: ${res.status}`)
  return res.json()
}

export async function createSliDefinition(
  payload: SliDefinitionCreate
): Promise<SliDefinition> {
  const res = await fetch(`${BASE}/sli-definitions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`createSliDefinition: ${res.status}`)
  return res.json()
}

export async function deleteSliDefinition(name: string): Promise<void> {
  const res = await fetch(`${BASE}/sli-definitions/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`deleteSliDefinition: ${res.status}`)
}

export async function fetchSliVersions(name: string): Promise<SliDefinition[]> {
  const res = await fetch(
    `${BASE}/sli-definitions/${encodeURIComponent(name)}/versions`
  )
  if (!res.ok) throw new Error(`fetchSliVersions: ${res.status}`)
  return res.json()
}

export async function fetchSliTagKeys(): Promise<{ key: string; count: number }[]> {
  const res = await fetch(`${BASE}/sli-definitions/tag-keys`)
  if (!res.ok) throw new Error(`fetchSliTagKeys: ${res.status}`)
  return res.json()
}

export async function fetchSliTagValues(key: string): Promise<{ value: string; count: number }[]> {
  const res = await fetch(`${BASE}/sli-definitions/tag-values?key=${encodeURIComponent(key)}`)
  if (!res.ok) throw new Error(`fetchSliTagValues: ${res.status}`)
  return res.json()
}
