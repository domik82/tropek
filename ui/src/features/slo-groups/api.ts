import type { components } from '@/generated/api'
import type { SloGroup } from './domain'
import { dtoToSloGroup, type SloGroupDto } from './mappers'

export type SloGroupCreateInput = components['schemas']['SLOGroupCreate']
export type SloGroupUpdateInput = components['schemas']['SLOGroupUpdate']

type SloGroupListDto = { items: SloGroupDto[]; total: number }

const BASE = '/api'

export async function fetchSloGroups(): Promise<SloGroup[]> {
  const res = await fetch(`${BASE}/slo-groups`)
  if (!res.ok) throw new Error(`fetchSloGroups: ${res.status}`)
  const body: SloGroupListDto = await res.json()
  return body.items.map(dtoToSloGroup)
}

export async function fetchSloGroupDetail(name: string): Promise<SloGroup> {
  const res = await fetch(`${BASE}/slo-groups/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`fetchSloGroupDetail: ${res.status}`)
  const body: SloGroupDto = await res.json()
  return dtoToSloGroup(body)
}

export async function createSloGroup(payload: SloGroupCreateInput): Promise<SloGroup> {
  const res = await fetch(`${BASE}/slo-groups`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`createSloGroup: ${res.status}`)
  const body: SloGroupDto = await res.json()
  return dtoToSloGroup(body)
}

export async function updateSloGroup(
  name: string,
  payload: SloGroupUpdateInput,
): Promise<SloGroup> {
  const res = await fetch(`${BASE}/slo-groups/${encodeURIComponent(name)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`updateSloGroup: ${res.status}`)
  const body: SloGroupDto = await res.json()
  return dtoToSloGroup(body)
}

export async function deleteSloGroup(name: string): Promise<void> {
  const res = await fetch(`${BASE}/slo-groups/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`deleteSloGroup: ${res.status}`)
}
