// src/features/slos/api.ts
import type { SloDefinition, SloObjective, SloValidationResult } from './types'

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
