// src/features/slos/api.ts
import type { SloDefinition, SloObjective, SloValidationResult } from './types'
import type {
  AssetGroupSLOLink, AssetGroupSLOLinkCreate, AssetGroupUpdate,
  DataSource, SliDefinition,
} from './types'
import type { AssetGroup, AssetGroupTree } from '@/features/assets/types'

const BASE = '/api'

export async function fetchSlos(): Promise<SloDefinition[]> {
  const res = await fetch(`${BASE}/slo-definitions`)
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
  comparison: Record<string, unknown>
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
  comparison: Record<string, unknown>
  display_name?: string
  notes?: string
  author?: string
  comparable_from_version?: number
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

export async function fetchGroupSloLinks(name: string): Promise<AssetGroupSLOLink[]> {
  const res = await fetch(`${BASE}/asset-groups/${encodeURIComponent(name)}/slo-links`)
  if (!res.ok) throw new Error(`fetchGroupSloLinks: ${res.status}`)
  return res.json()
}

export async function createGroupSloLink(
  groupName: string, body: AssetGroupSLOLinkCreate,
): Promise<AssetGroupSLOLink> {
  const res = await fetch(`${BASE}/asset-groups/${encodeURIComponent(groupName)}/slo-links`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`createGroupSloLink: ${res.status}`)
  return res.json()
}

export async function deleteGroupSloLink(groupName: string, linkName: string): Promise<void> {
  const res = await fetch(
    `${BASE}/asset-groups/${encodeURIComponent(groupName)}/slo-links/${encodeURIComponent(linkName)}`,
    { method: 'DELETE' },
  )
  if (!res.ok) throw new Error(`deleteGroupSloLink: ${res.status}`)
}

export async function fetchDatasources(): Promise<DataSource[]> {
  const res = await fetch(`${BASE}/datasources`)
  if (!res.ok) throw new Error(`fetchDatasources: ${res.status}`)
  const data: { items: DataSource[]; total: number } = await res.json()
  return data.items
}

export async function fetchSliDefinitions(adapterType?: string): Promise<SliDefinition[]> {
  const url = adapterType
    ? `${BASE}/sli-definitions?adapter_type=${encodeURIComponent(adapterType)}`
    : `${BASE}/sli-definitions`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`fetchSliDefinitions: ${res.status}`)
  const data: { items: SliDefinition[]; total: number } = await res.json()
  return data.items
}
