// src/features/slos/api.ts
import type { SloDefinition, SloObjective, SloValidationResult, SloComparisonConfig } from './types'
import type { AssetGroupUpdate } from './types'
import type { SloBinding, SloBindingCreate } from './types'
import type { AssetGroup, AssetGroupTree } from '@/features/assets/types'

const BASE = '/api'

export async function fetchSlos(tagKey?: string, tagVal?: string): Promise<SloDefinition[]> {
  const params = new URLSearchParams()
  if (tagKey) params.set('tag_key', tagKey)
  if (tagVal) params.set('tag_val', tagVal)
  const qs = params.toString()
  const res = await fetch(`${BASE}/slo-definitions${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error(`fetchSlos: ${res.status}`)
  const data: { items: SloDefinition[]; total: number } = await res.json()
  return data.items
}

export async function fetchSloDetail(name: string): Promise<SloDefinition> {
  const res = await fetch(`${BASE}/slo-definitions/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`fetchSloDetail: ${res.status}`)
  return res.json()
}

export async function validateSlo(payload: {
  objectives: SloObjective[]
  total_score_pass_pct: number
  total_score_warning_pct: number
  comparison: SloComparisonConfig
}): Promise<SloValidationResult> {
  const res = await fetch(`${BASE}/slo-definitions/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`validateSlo: ${res.status}`)
  return res.json()
}

export async function createSloDefinition(payload: {
  name: string
  objectives: SloObjective[]
  total_score_pass_pct: number
  total_score_warning_pct: number
  comparison: SloComparisonConfig
  display_name?: string
  notes?: string
  author?: string
  tags?: Record<string, string>
  variables?: Record<string, string>
  comparable_from_version?: number
  kind?: string
  sli_name?: string
  sli_version?: number
  method_criteria?: Record<string, import('./types').MethodCriteriaOverride>
}): Promise<SloDefinition> {
  const res = await fetch(`${BASE}/slo-definitions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`createSloDefinition: ${res.status}`)
  return res.json()
}

export async function deleteSlo(name: string): Promise<void> {
  const res = await fetch(`${BASE}/slo-definitions/${encodeURIComponent(name)}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`deleteSlo: ${res.status}`)
}

export async function fetchSloVersions(name: string): Promise<SloDefinition[]> {
  const res = await fetch(`${BASE}/slo-definitions/${encodeURIComponent(name)}/versions`)
  if (!res.ok) throw new Error(`fetchSloVersions: ${res.status}`)
  return res.json()
}

export async function fetchGroupTree(): Promise<AssetGroupTree> {
  const res = await fetch(`${BASE}/asset-groups/tree`)
  if (!res.ok) throw new Error(`fetchGroupTree: ${res.status}`)
  return res.json()
}

export async function createGroup(body: {
  name: string; display_name?: string; description?: string
}): Promise<AssetGroup> {
  const res = await fetch(`${BASE}/asset-groups`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`createGroup: ${res.status}`)
  return res.json()
}

export async function updateGroup(name: string, body: AssetGroupUpdate): Promise<AssetGroup> {
  const res = await fetch(`${BASE}/asset-groups/${encodeURIComponent(name)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`updateGroup: ${res.status}`)
  return res.json()
}

export async function deleteGroup(name: string, deactivateSlos: boolean): Promise<void> {
  const res = await fetch(
    `${BASE}/asset-groups/${encodeURIComponent(name)}?deactivate_slos=${deactivateSlos}`,
    { method: 'DELETE' },
  )
  if (!res.ok) throw new Error(`deleteGroup: ${res.status}`)
}

export async function addSubgroup(parentName: string, childGroupId: string): Promise<AssetGroup> {
  const res = await fetch(`${BASE}/asset-groups/${encodeURIComponent(parentName)}/subgroups`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ child_group_id: childGroupId, weight: 1.0 }),
  })
  if (!res.ok) throw new Error(`addSubgroup: ${res.status}`)
  return res.json()
}


export async function fetchSloTagKeys(): Promise<{ key: string; count: number }[]> {
  const res = await fetch(`${BASE}/slo-definitions/tag-keys`)
  if (!res.ok) throw new Error(`fetchSloTagKeys: ${res.status}`)
  return res.json()
}

export async function fetchSloTagValues(key: string): Promise<{ value: string; count: number }[]> {
  const res = await fetch(`${BASE}/slo-definitions/tag-values?key=${encodeURIComponent(key)}`)
  if (!res.ok) throw new Error(`fetchSloTagValues: ${res.status}`)
  return res.json()
}

// ---- SLO Bindings ----

export async function fetchAssetSloBindings(assetName: string): Promise<SloBinding[]> {
  const res = await fetch(`${BASE}/assets/${encodeURIComponent(assetName)}/slo-bindings`)
  if (!res.ok) throw new Error(`fetchAssetSloBindings: ${res.status}`)
  return res.json()
}

export async function createAssetSloBinding(assetName: string, body: SloBindingCreate): Promise<SloBinding> {
  const res = await fetch(`${BASE}/assets/${encodeURIComponent(assetName)}/slo-bindings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`createAssetSloBinding: ${res.status}`)
  return res.json()
}

export async function fetchGroupSloBindings(groupName: string): Promise<SloBinding[]> {
  const res = await fetch(`${BASE}/asset-groups/${encodeURIComponent(groupName)}/slo-bindings`)
  if (!res.ok) throw new Error(`fetchGroupSloBindings: ${res.status}`)
  return res.json()
}

export async function createGroupSloBinding(groupName: string, body: SloBindingCreate): Promise<SloBinding> {
  const res = await fetch(`${BASE}/asset-groups/${encodeURIComponent(groupName)}/slo-bindings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`createGroupSloBinding: ${res.status}`)
  return res.json()
}

export async function deleteGroupSloBinding(groupName: string, sloName: string): Promise<void> {
  const res = await fetch(
    `${BASE}/asset-groups/${encodeURIComponent(groupName)}/slo-bindings/${encodeURIComponent(sloName)}`,
    { method: 'DELETE' },
  )
  if (!res.ok) throw new Error(`deleteGroupSloBinding: ${res.status}`)
}
