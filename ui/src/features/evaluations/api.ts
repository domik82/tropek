// src/features/evaluations/api.ts
import { getConfig } from '@/lib/config'
import type {
  Annotation,
  AnnotationCreateInput,
  Evaluation,
  EvaluationDetail,
  EvaluationFilters,
  EvaluationList,
  EvaluationNameEntry,
  OverrideStatusInput,
  PinConflictInfo,
  ReEvaluateInput,
  ReEvaluateResponse,
  TrendPoint,
  TriggerEvaluationInput,
} from './domain'
import {
  annotationCreateInputToDto,
  dtoToAnnotation,
  dtoToEvaluationDetail,
  dtoToEvaluationList,
  dtoToEvaluationNameEntry,
  dtoToEvaluationSummary,
  dtoToReEvaluateResponse,
  dtoToTrendPoint,
  overrideStatusInputToDto,
  reEvaluateInputToDto,
  triggerEvaluationInputToDto,
  type AnnotationDto,
  type EvaluationDetailDto,
  type EvaluationNameEntryDto,
  type EvaluationSummaryDto,
  type EvaluateSingleResponseDto,
  type ReEvaluateResponseDto,
  type TrendPointDto,
} from './mappers'

const BASE = '/api'

function toParams(filters: EvaluationFilters): string {
  const params = new URLSearchParams()
  if (filters.groupName) params.set('group_name', filters.groupName)
  if (filters.assetName) params.set('asset_name', filters.assetName)
  if (filters.evaluationName?.length) {
    for (const name of filters.evaluationName) params.append('evaluation_name', name)
  }
  if (filters.date) params.set('date', filters.date)
  if (filters.from) params.set('from', filters.from)
  if (filters.to) params.set('to', filters.to)
  return params.toString()
}

export async function fetchEvaluations(filters: EvaluationFilters = {}): Promise<EvaluationList> {
  const base = toParams(filters)
  const allItems: EvaluationSummaryDto[] = []
  const { maxEvaluations, pageSize } = getConfig()
  let total: number
  let offset = 0

  for (;;) {
    const qs = `${base}&limit=${pageSize}&offset=${offset}`
    const res = await fetch(`${BASE}/evaluations?${qs}`)
    if (!res.ok) throw new Error(`fetchEvaluations: ${res.status}`)
    const page: { items: EvaluationSummaryDto[]; total: number } = await res.json()
    total = page.total
    allItems.push(...page.items)
    if (allItems.length >= page.total || page.items.length < pageSize) break
    if (allItems.length >= maxEvaluations) break
    offset += pageSize
  }

  return dtoToEvaluationList({
    items: allItems.slice(0, maxEvaluations),
    total,
    truncated: total > maxEvaluations,
  })
}

export async function fetchEvaluationDetail(id: string): Promise<EvaluationDetail> {
  const res = await fetch(`${BASE}/evaluation/${id}`)
  if (!res.ok) throw new Error(`fetchEvaluationDetail: ${res.status}`)
  const body: EvaluationDetailDto = await res.json()
  return dtoToEvaluationDetail(body)
}

export async function fetchTrend(
  assetName: string,
  sloName: string,
  metric: string,
  dateRange?: { from?: string; to?: string },
): Promise<TrendPoint[]> {
  const params = new URLSearchParams({ metric })
  if (dateRange?.from) params.set('from', dateRange.from)
  if (dateRange?.to) params.set('to', dateRange.to)
  const res = await fetch(
    `${BASE}/assets/${encodeURIComponent(assetName)}/slos/${encodeURIComponent(sloName)}/trend?${params}`,
  )
  if (!res.ok) throw new Error(`fetchTrend: ${res.status}`)
  const body: TrendPointDto[] = await res.json()
  return body.map(dtoToTrendPoint)
}

export async function triggerEvaluation(
  input: TriggerEvaluationInput,
): Promise<{ evaluationId: string; sloEvaluationIds: string[] }> {
  const res = await fetch(`${BASE}/evaluations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(triggerEvaluationInputToDto(input)),
  })
  if (!res.ok) throw new Error(`triggerEvaluation: ${res.status}`)
  const body: EvaluateSingleResponseDto = await res.json()
  return { evaluationId: body.evaluation_id, sloEvaluationIds: body.slo_evaluation_ids }
}

export async function addAnnotation(
  evalId: string,
  payload: AnnotationCreateInput,
): Promise<Annotation> {
  const res = await fetch(`${BASE}/evaluation/${evalId}/annotations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(annotationCreateInputToDto(payload)),
  })
  if (!res.ok) throw new Error(`addAnnotation: ${res.status}`)
  const body: AnnotationDto = await res.json()
  return dtoToAnnotation(body)
}

export async function addRunAnnotation(
  runId: string,
  payload: AnnotationCreateInput,
): Promise<Annotation> {
  const res = await fetch(`${BASE}/evaluation-run/${runId}/annotations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(annotationCreateInputToDto(payload)),
  })
  if (!res.ok) throw new Error(`addRunAnnotation: ${res.status}`)
  const body: AnnotationDto = await res.json()
  return dtoToAnnotation(body)
}

export async function hideAnnotation(
  evalId: string,
  annotationId: string,
  payload: { reason: string; author?: string },
): Promise<Annotation> {
  const res = await fetch(
    `${BASE}/evaluation/${evalId}/annotations/${annotationId}/hide`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
  if (!res.ok) throw new Error(`hideAnnotation: ${res.status}`)
  const body: AnnotationDto = await res.json()
  return dtoToAnnotation(body)
}

export async function invalidateEvaluation(evalId: string, note: string): Promise<Evaluation> {
  const res = await fetch(`${BASE}/evaluation/${evalId}/invalidate`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ invalidation_note: note }),
  })
  if (!res.ok) throw new Error(`invalidateEvaluation: ${res.status}`)
  const body: EvaluationSummaryDto = await res.json()
  return dtoToEvaluationSummary(body)
}

export async function restoreEvaluation(evalId: string): Promise<Evaluation> {
  const res = await fetch(`${BASE}/evaluation/${evalId}/restore`, { method: 'PATCH' })
  if (!res.ok) throw new Error(`restoreEvaluation: ${res.status}`)
  const body: EvaluationSummaryDto = await res.json()
  return dtoToEvaluationSummary(body)
}

export async function overrideStatus(
  evalId: string,
  input: OverrideStatusInput,
): Promise<EvaluationDetail> {
  const res = await fetch(`${BASE}/evaluation/${evalId}/override-status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(overrideStatusInputToDto(input)),
  })
  if (!res.ok) throw new Error(`overrideStatus: ${res.status}`)
  const body: EvaluationDetailDto = await res.json()
  return dtoToEvaluationDetail(body)
}

export async function pinBaseline(
  evalId: string,
  payload: { reason: string; author: string },
): Promise<EvaluationDetail> {
  const res = await fetch(`${BASE}/evaluation/${evalId}/pin-baseline`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`pinBaseline: ${res.status}`)
  const body: EvaluationDetailDto = await res.json()
  return dtoToEvaluationDetail(body)
}

export async function fetchTrendAnnotations(
  asset: string,
  slo: string,
): Promise<Map<string, Annotation[]>> {
  const params = new URLSearchParams({ asset, slo })
  const res = await fetch(`${BASE}/evaluations/trend-annotations?${params}`)
  if (!res.ok) throw new Error(`fetchTrendAnnotations: ${res.status}`)
  const body: Record<string, AnnotationDto[]> = await res.json()
  const map = new Map<string, Annotation[]>()
  for (const [evalId, dtos] of Object.entries(body)) {
    map.set(evalId, dtos.map(dtoToAnnotation))
  }
  return map
}

export async function fetchColumnAnnotations(evaluationId: string): Promise<Annotation[]> {
  const params = new URLSearchParams({ evaluation_id: evaluationId })
  const res = await fetch(`${BASE}/evaluations/column-annotations?${params}`)
  if (!res.ok) throw new Error(`fetchColumnAnnotations: ${res.status}`)
  const body: AnnotationDto[] = await res.json()
  return body.map(dtoToAnnotation)
}

export async function fetchEvaluationNames(
  params: { assetName?: string; groupName?: string },
): Promise<EvaluationNameEntry[]> {
  const query = new URLSearchParams()
  if (params.assetName) query.set('asset_name', params.assetName)
  if (params.groupName) query.set('group_name', params.groupName)
  const qs = query.toString()
  const res = await fetch(`${BASE}/evaluations/names${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error(`fetchEvaluationNames: ${res.status}`)
  const body: EvaluationNameEntryDto[] = await res.json()
  return body.map(dtoToEvaluationNameEntry)
}

export class PinConflictError extends Error {
  pinDate: string
  pinEvaluationId: string

  constructor(info: PinConflictInfo) {
    super('re-evaluation start date is before the active baseline pin')
    this.pinDate = info.pinDate
    this.pinEvaluationId = info.pinEvaluationId
  }
}

export async function reEvaluate(input: ReEvaluateInput): Promise<ReEvaluateResponse> {
  const { endpoint, requestBody } = reEvaluateInputToDto(input)
  const res = await fetch(`${BASE}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(requestBody),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    if (res.status === 409 && body.detail?.pin_date) {
      throw new PinConflictError({
        pinDate: body.detail.pin_date,
        pinEvaluationId: body.detail.pin_evaluation_id,
      })
    }
    const message = typeof body.detail === 'string' ? body.detail : `reEvaluate: ${res.status}`
    throw new Error(message)
  }
  const body: ReEvaluateResponseDto = await res.json()
  return dtoToReEvaluateResponse(body)
}
