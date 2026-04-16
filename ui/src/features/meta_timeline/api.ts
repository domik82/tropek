// ui/src/features/meta_timeline/api.ts
//
// Fetch functions for the meta timeline feature. Each function calls the
// mapper before returning so React Query stores domain types, not DTOs.

import type { components } from '@/generated/api'
import type { MetaTimelineResponse, MetaTimelineSummary } from './domain'
import { dtoToMetaTimelineResponse, dtoToMetaTimelineSummary } from './mappers'

type TimelineResponseDto = components['schemas']['TimelineResponse']
type TimelineSummaryDto = components['schemas']['TimelineSummaryResponse']

const BASE = '/api'

export async function fetchMetaTimeline(
  assetId: string,
  from: Date,
  to: Date,
): Promise<MetaTimelineResponse> {
  const params = new URLSearchParams({
    from: from.toISOString(),
    to: to.toISOString(),
  })
  const response = await fetch(`${BASE}/assets/${assetId}/meta/timeline?${params}`)
  if (!response.ok) throw new Error(`fetchMetaTimeline: ${response.status}`)
  const dto: TimelineResponseDto = await response.json()
  return dtoToMetaTimelineResponse(dto)
}

export async function fetchMetaTimelineSummary(
  assetId: string,
  from: Date,
  to: Date,
): Promise<MetaTimelineSummary> {
  const params = new URLSearchParams({
    from: from.toISOString(),
    to: to.toISOString(),
  })
  const response = await fetch(`${BASE}/assets/${assetId}/meta/timeline/summary?${params}`)
  if (!response.ok) throw new Error(`fetchMetaTimelineSummary: ${response.status}`)
  const dto: TimelineSummaryDto = await response.json()
  return dtoToMetaTimelineSummary(dto)
}
