import type { components } from '@/generated/api'
import type {
  ChangePoint,
  ChangePointFilters,
  ChangePointDirection,
  ChangePointStatus,
  BulkTriageInput,
  TriageInput,
} from './domain'

type ChangePointReadDto = components['schemas']['ChangePointRead']

const BASE = '/api'

function dtoToChangePoint(dto: ChangePointReadDto): ChangePoint {
  return {
    id: dto.id,
    assetId: dto.asset_id,
    sloName: dto.slo_name,
    metricName: dto.metric_name,
    periodStart: new Date(dto.period_start),
    direction: dto.direction as ChangePointDirection,
    changeRelativePct: dto.change_relative_pct,
    changeAbsolute: dto.change_absolute,
    preSegmentMean: dto.pre_segment_mean,
    postSegmentMean: dto.post_segment_mean,
    pvalue: dto.pvalue,
    status: dto.status as ChangePointStatus,
    triageAuthor: dto.triage_author,
    triageNote: dto.triage_note,
    triageAt: dto.triage_at ? new Date(dto.triage_at) : null,
    linkedTicket: dto.linked_ticket,
    createdAt: new Date(dto.created_at),
  }
}

export async function fetchChangePoints(
  filters: ChangePointFilters,
): Promise<ChangePoint[]> {
  const params = new URLSearchParams()
  if (filters.status) params.set('status', filters.status)
  if (filters.direction) params.set('direction', filters.direction)
  if (filters.assetId) params.set('asset_id', filters.assetId)
  if (filters.sloName) params.set('slo_name', filters.sloName)
  if (filters.metric) params.set('metric', filters.metric)
  if (filters.limit != null) params.set('limit', String(filters.limit))
  if (filters.offset != null) params.set('offset', String(filters.offset))

  const query = params.toString()
  const url = `${BASE}/change-points${query ? `?${query}` : ''}`
  const response = await fetch(url)
  if (!response.ok) throw new Error(`failed to fetch change points: ${response.status}`)
  const data: ChangePointReadDto[] = await response.json()
  return data.map(dtoToChangePoint)
}

export async function triageChangePoint(
  id: string,
  input: TriageInput,
): Promise<ChangePoint> {
  const response = await fetch(`${BASE}/change-points/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      status: input.status,
      triage_author: input.triageAuthor ?? null,
      triage_note: input.triageNote ?? null,
    }),
  })
  if (!response.ok) throw new Error(`failed to triage change point: ${response.status}`)
  const dto: ChangePointReadDto = await response.json()
  return dtoToChangePoint(dto)
}

export async function bulkTriageChangePoints(
  input: BulkTriageInput,
): Promise<void> {
  const response = await fetch(`${BASE}/change-points/bulk-triage`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ids: input.ids,
      status: input.status,
      triage_author: input.triageAuthor ?? null,
      triage_note: input.triageNote ?? null,
    }),
  })
  if (!response.ok) throw new Error(`failed to bulk triage change points: ${response.status}`)
}

export const changePointKeys = {
  all: ['change-points'] as const,
  list: (filters: ChangePointFilters) => [...changePointKeys.all, 'list', filters] as const,
}
