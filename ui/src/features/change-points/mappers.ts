import type { components } from '@/generated/api'
import type { ChangePoint, ChangePointDirection, ChangePointStatus } from './domain'

type ChangePointReadDto = components['schemas']['ChangePointRead']

export function dtoToChangePoint(dto: ChangePointReadDto): ChangePoint {
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
