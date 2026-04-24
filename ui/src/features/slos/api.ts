// src/features/slos/api.ts
import type { components } from '@/generated/api'
import type {
  Slo,
  SloAssignment,
  SloGroupAssignment,
  SloValidationResult,
} from './domain'
import {
  dtoToSlo,
  dtoToSloAssignment,
  dtoToSloGroupAssignment,
  dtoToSloValidationResult,
  type SloDto,
  type SloAssignmentDto,
  type SloGroupAssignmentDto,
  type SloValidationResultDto,
} from './mappers'

export type SloCreateInput = components['schemas']['SLODefinitionCreate']

export interface SloAssignmentCreateInput {
  slo_definition_id: string
  data_source_name: string
  comparison_rules?: Record<string, unknown>[] | null
}

const BASE = '/api'

export async function fetchSlos(tagKey?: string, tagVal?: string): Promise<Slo[]> {
  const params = new URLSearchParams()
  if (tagKey) params.set('tag_key', tagKey)
  if (tagVal) params.set('tag_val', tagVal)
  const qs = params.toString()
  const res = await fetch(`${BASE}/slo-definitions${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error(`fetchSlos: ${res.status}`)
  const data: { items: SloDto[]; total: number } = await res.json()
  return data.items.map(dtoToSlo)
}

export async function fetchSloDetail(name: string): Promise<Slo> {
  const res = await fetch(`${BASE}/slo-definitions/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`fetchSloDetail: ${res.status}`)
  const body: SloDto = await res.json()
  return dtoToSlo(body)
}

export async function validateSlo(
  payload: components['schemas']['SLOValidateRequest'],
): Promise<SloValidationResult> {
  const res = await fetch(`${BASE}/slo-definitions/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`validateSlo: ${res.status}`)
  const body: SloValidationResultDto = await res.json()
  return dtoToSloValidationResult(body)
}

export async function createSloDefinition(payload: SloCreateInput): Promise<Slo> {
  const res = await fetch(`${BASE}/slo-definitions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`createSloDefinition: ${res.status}`)
  const body: SloDto = await res.json()
  return dtoToSlo(body)
}

export async function deleteSlo(name: string): Promise<void> {
  const res = await fetch(`${BASE}/slo-definitions/${encodeURIComponent(name)}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`deleteSlo: ${res.status}`)
}

export async function fetchSloVersions(name: string): Promise<Slo[]> {
  const res = await fetch(`${BASE}/slo-definitions/${encodeURIComponent(name)}/versions`)
  if (!res.ok) throw new Error(`fetchSloVersions: ${res.status}`)
  const body: SloDto[] = await res.json()
  return body.map(dtoToSlo)
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

// ---- SLO Assignments ----

export async function fetchAssetSloAssignments(assetName: string): Promise<SloAssignment[]> {
  const res = await fetch(`${BASE}/assets/${encodeURIComponent(assetName)}/slo-assignments`)
  if (!res.ok) throw new Error(`fetchAssetSloAssignments: ${res.status}`)
  const body: SloAssignmentDto[] = await res.json()
  return body.map(dtoToSloAssignment)
}

export async function fetchAssetSloGroupAssignments(
  assetName: string,
): Promise<SloGroupAssignment[]> {
  const res = await fetch(`${BASE}/assets/${encodeURIComponent(assetName)}/slo-group-assignments`)
  if (!res.ok) throw new Error(`fetchAssetSloGroupAssignments: ${res.status}`)
  const body: SloGroupAssignmentDto[] = await res.json()
  return body.map(dtoToSloGroupAssignment)
}

export async function createAssetSloAssignment(
  assetName: string,
  body: SloAssignmentCreateInput,
): Promise<SloAssignment> {
  const { slo_definition_id, ...putBody } = body
  const res = await fetch(
    `${BASE}/assets/${encodeURIComponent(assetName)}/slo-definitions/${encodeURIComponent(slo_definition_id)}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(putBody),
    },
  )
  if (!res.ok) throw new Error(`createAssetSloAssignment: ${res.status}`)
  const response: SloAssignmentDto = await res.json()
  return dtoToSloAssignment(response)
}

export async function fetchGroupSloAssignments(groupName: string): Promise<SloAssignment[]> {
  const res = await fetch(`${BASE}/asset-groups/${encodeURIComponent(groupName)}/slo-assignments`)
  if (!res.ok) throw new Error(`fetchGroupSloAssignments: ${res.status}`)
  const body: SloAssignmentDto[] = await res.json()
  return body.map(dtoToSloAssignment)
}

export async function createGroupSloAssignment(
  groupName: string,
  body: SloAssignmentCreateInput,
): Promise<SloAssignment> {
  const { slo_definition_id, ...putBody } = body
  const res = await fetch(
    `${BASE}/asset-groups/${encodeURIComponent(groupName)}/slo-definitions/${encodeURIComponent(slo_definition_id)}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(putBody),
    },
  )
  if (!res.ok) throw new Error(`createGroupSloAssignment: ${res.status}`)
  const response: SloAssignmentDto = await res.json()
  return dtoToSloAssignment(response)
}

export async function deleteGroupSloAssignment(
  groupName: string,
  sloDefinitionId: string,
): Promise<void> {
  const res = await fetch(
    `${BASE}/asset-groups/${encodeURIComponent(groupName)}/slo-definitions/${encodeURIComponent(sloDefinitionId)}`,
    { method: 'DELETE' },
  )
  if (!res.ok) throw new Error(`deleteGroupSloAssignment: ${res.status}`)
}
