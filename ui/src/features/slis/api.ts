// src/features/slis/api.ts
import type { PagedResponse } from '@/lib/types'
import type { SliDefinition, SliDefinitionCreate } from './types'

const BASE = '/api'

export async function fetchSliDefinitions(): Promise<PagedResponse<SliDefinition>> {
  const res = await fetch(`${BASE}/sli-definitions`)
  if (!res.ok) throw new Error(`fetchSliDefinitions: ${res.status}`)
  return res.json()
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
