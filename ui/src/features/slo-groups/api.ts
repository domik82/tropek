import type { SloGroup, SloGroupCreate } from './types'

const BASE = '/api'

export async function fetchSloGroups(): Promise<SloGroup[]> {
  const res = await fetch(`${BASE}/slo-groups`)
  if (!res.ok) throw new Error(`fetchSloGroups: ${res.status}`)
  const data: { items: SloGroup[]; total: number } = await res.json()
  return data.items
}

export async function fetchSloGroupDetail(name: string): Promise<SloGroup> {
  const res = await fetch(`${BASE}/slo-groups/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`fetchSloGroupDetail: ${res.status}`)
  return res.json()
}

export async function createSloGroup(body: SloGroupCreate): Promise<SloGroup> {
  const res = await fetch(`${BASE}/slo-groups`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`createSloGroup: ${res.status}`)
  return res.json()
}

export async function deleteSloGroup(name: string): Promise<void> {
  const res = await fetch(`${BASE}/slo-groups/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`deleteSloGroup: ${res.status}`)
}
