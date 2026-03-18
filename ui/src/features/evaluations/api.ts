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
} from './types'
import type { MetricHeatmapResponse } from '@/features/navigator/types'

const BASE = '/api'

function toParams(filters: EvaluationFilters): string {
  const p = new URLSearchParams()
  if (filters.group_name) p.set('group_name', filters.group_name)
  if (filters.asset_name) p.set('asset_name', filters.asset_name)
  if (filters.date) p.set('date', filters.date)
  if (filters.from) p.set('from', filters.from)
  if (filters.to) p.set('to', filters.to)
  return p.toString()
}

export async function fetchEvaluations(
  filters: EvaluationFilters = {}
): Promise<EvaluationSummary[]> {
  const qs = toParams(filters)
  const res = await fetch(`${BASE}/evaluations${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error(`fetchEvaluations: ${res.status}`)
  const data: { items: EvaluationSummary[]; total: number } = await res.json()
  return data.items
}

export async function fetchEvaluationDetail(id: string): Promise<EvaluationDetail> {
  const res = await fetch(`${BASE}/evaluations/${id}`)
  if (!res.ok) throw new Error(`fetchEvaluationDetail: ${res.status}`)
  return res.json()
}

export async function fetchTrend(evalId: string, metric: string): Promise<TrendPoint[]> {
  const res = await fetch(`${BASE}/trend?eval_id=${evalId}&metric=${encodeURIComponent(metric)}`)
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

export async function fetchMetricHeatmap(assetName: string): Promise<MetricHeatmapResponse> {
  const res = await fetch(`${BASE}/evaluations/metric-heatmap?asset_name=${encodeURIComponent(assetName)}`)
  if (!res.ok) throw new Error(`fetchMetricHeatmap: ${res.status}`)
  return res.json()
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
    throw new Error(body.detail ?? `reEvaluate: ${res.status}`)
  }
  return res.json()
}
