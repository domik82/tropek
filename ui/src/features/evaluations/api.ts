// src/features/evaluations/api.ts
// Pure async fetch functions — no mock logic, no caching.
// MSW intercepts these calls in development; the real API handles them in production.

import type {
  EvaluationSummary,
  EvaluationDetail,
  TrendPoint,
  EvaluationFilters,
  TriggerEvaluationPayload,
  Annotation,
  ReEvaluatePayload,
  ReEvaluateResponse,
  PinConflictInfo,
} from './types'
import type { MetricHeatmapResponse } from '@/features/navigator/types'

const BASE = '/api'

function toParams(filters: EvaluationFilters): string {
  const p = new URLSearchParams()
  if (filters.group_name) p.set('group_name', filters.group_name)
  if (filters.asset_name) p.set('asset_name', filters.asset_name)
  if (filters.evaluation_name?.length) {
    for (const n of filters.evaluation_name) p.append('evaluation_name', n)
  }
  if (filters.date) p.set('date', filters.date)
  if (filters.from) p.set('from', filters.from)
  if (filters.to) p.set('to', filters.to)
  return p.toString()
}

import { getConfig } from '@/lib/config'

export interface EvaluationResult {
  items: EvaluationSummary[]
  total: number
  truncated: boolean
}

export async function fetchEvaluations(
  filters: EvaluationFilters = {}
): Promise<EvaluationResult> {
  const base = toParams(filters)
  const all: EvaluationSummary[] = []
  const { maxEvaluations, pageSize } = getConfig()
  let total = 0
  let offset = 0

  for (;;) {
    const qs = `${base}&limit=${pageSize}&offset=${offset}`
    const res = await fetch(`${BASE}/evaluations?${qs}`)
    if (!res.ok) throw new Error(`fetchEvaluations: ${res.status}`)
    const data: { items: EvaluationSummary[]; total: number } = await res.json()
    total = data.total
    all.push(...data.items)
    if (all.length >= data.total || data.items.length < pageSize) break
    if (all.length >= maxEvaluations) break
    offset += pageSize
  }

  return {
    items: all.slice(0, maxEvaluations),
    total,
    truncated: total > maxEvaluations,
  }
}

export async function fetchEvaluationDetail(id: string): Promise<EvaluationDetail> {
  const res = await fetch(`${BASE}/evaluations/${id}`)
  if (!res.ok) throw new Error(`fetchEvaluationDetail: ${res.status}`)
  return res.json()
}

export async function fetchTrend(
  assetName: string,
  sloName: string,
  metric: string,
  dateRange?: { from?: string; to?: string },
): Promise<TrendPoint[]> {
  const params = new URLSearchParams({ asset_name: assetName, slo_name: sloName, metric })
  if (dateRange?.from) params.set('from', dateRange.from)
  if (dateRange?.to) params.set('to', dateRange.to)
  const res = await fetch(`${BASE}/trend?${params}`)
  if (!res.ok) throw new Error(`fetchTrend: ${res.status}`)
  return res.json()
}

export async function triggerEvaluation(
  payload: TriggerEvaluationPayload
): Promise<{ id: string }> {
  const res = await fetch(`${BASE}/evaluations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`triggerEvaluation: ${res.status}`)
  return res.json()
}

export async function addAnnotation(
  evalId: string,
  payload: { content: string; category?: string; author?: string }
): Promise<Annotation> {
  const res = await fetch(`${BASE}/evaluations/${evalId}/annotations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`addAnnotation: ${res.status}`)
  return res.json()
}

export async function hideAnnotation(
  evalId: string,
  annotationId: string,
  payload: { reason: string; author?: string }
): Promise<Annotation> {
  const res = await fetch(`${BASE}/evaluations/${evalId}/annotations/${annotationId}/hide`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`hideAnnotation: ${res.status}`)
  return res.json()
}

export async function invalidateEvaluation(
  evalId: string,
  note: string
): Promise<EvaluationSummary> {
  const res = await fetch(`${BASE}/evaluations/${evalId}/invalidate`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ invalidation_note: note }),
  })
  if (!res.ok) throw new Error(`invalidateEvaluation: ${res.status}`)
  return res.json()
}

export async function restoreEvaluation(
  evalId: string
): Promise<EvaluationSummary> {
  const res = await fetch(`${BASE}/evaluations/${evalId}/restore`, {
    method: 'PATCH',
  })
  if (!res.ok) throw new Error(`restoreEvaluation: ${res.status}`)
  return res.json()
}

export async function overrideStatus(
  evalId: string,
  payload: { new_result: string; reason: string; author: string }
): Promise<EvaluationDetail> {
  const res = await fetch(`${BASE}/evaluations/${evalId}/override-status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`overrideStatus: ${res.status}`)
  return res.json()
}

export async function pinBaseline(
  evalId: string,
  payload: { reason: string; author: string }
): Promise<EvaluationDetail> {
  const res = await fetch(`${BASE}/evaluations/${evalId}/pin-baseline`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`pinBaseline: ${res.status}`)
  return res.json()
}

export async function fetchMetricHeatmap(
  assetName: string,
  filters?: { from?: string; to?: string; evaluation_name?: string[] },
): Promise<MetricHeatmapResponse> {
  const params = new URLSearchParams({ asset_name: assetName })
  if (filters?.from) params.set('from', filters.from)
  if (filters?.to) params.set('to', filters.to)
  if (filters?.evaluation_name?.length) {
    for (const n of filters.evaluation_name) params.append('evaluation_name', n)
  }
  const res = await fetch(`${BASE}/evaluations/metric-heatmap?${params}`)
  if (!res.ok) throw new Error(`fetchMetricHeatmap: ${res.status}`)
  return res.json()
}

export async function fetchGroupedMetricHeatmap(
  assetName: string,
  filters: { evaluation_name?: string[]; from?: string; to?: string } = {}
): Promise<MetricHeatmapResponse> {
  const p = new URLSearchParams({ asset_name: assetName })
  if (filters.evaluation_name?.length) {
    for (const n of filters.evaluation_name) p.append('evaluation_name', n)
  }
  if (filters.from) p.set('from', filters.from)
  if (filters.to) p.set('to', filters.to)
  const res = await fetch(`${BASE}/evaluate/metric-heatmap?${p}`)
  if (!res.ok) throw new Error(`fetchGroupedMetricHeatmap: ${res.status}`)
  return res.json()
}

export async function fetchColumnAnnotations(
  evaluationId: string,
): Promise<Annotation[]> {
  const params = new URLSearchParams({ evaluation_id: evaluationId })
  const res = await fetch(`${BASE}/evaluations/column-annotations?${params}`)
  if (!res.ok) throw new Error(`fetchColumnAnnotations: ${res.status}`)
  return res.json()
}

export interface EvaluationNameEntry {
  name: string
  count: number
  last_run: string
}

export async function fetchEvaluationNames(
  params: { asset_name?: string; group_name?: string },
): Promise<EvaluationNameEntry[]> {
  const p = new URLSearchParams()
  if (params.asset_name) p.set('asset_name', params.asset_name)
  if (params.group_name) p.set('group_name', params.group_name)
  const qs = p.toString()
  const res = await fetch(`${BASE}/evaluations/names${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error(`fetchEvaluationNames: ${res.status}`)
  return res.json()
}

export class PinConflictError extends Error {
  pin_date: string
  pin_evaluation_id: string

  constructor(info: PinConflictInfo) {
    super('re-evaluation start date is before the active baseline pin')
    this.pin_date = info.pin_date
    this.pin_evaluation_id = info.pin_evaluation_id
  }
}

export async function reEvaluate(
  payload: ReEvaluatePayload
): Promise<ReEvaluateResponse> {
  const res = await fetch(`${BASE}/evaluations/re-evaluate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    if (res.status === 409 && body.detail?.pin_date) {
      throw new PinConflictError(body.detail)
    }
    const message = typeof body.detail === 'string' ? body.detail : `reEvaluate: ${res.status}`
    throw new Error(message)
  }
  return res.json()
}
