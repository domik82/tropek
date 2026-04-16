// ui/src/features/meta_timeline/hooks.ts
//
// React Query hooks for the meta timeline feature. Components call these
// hooks, never fetch directly.

import { useQuery } from '@tanstack/react-query'
import { fetchMetaTimeline, fetchMetaTimelineSummary } from './api'

export function useMetaTimeline(
  assetId: string,
  from: Date,
  to: Date,
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: ['meta-timeline', assetId, from.toISOString(), to.toISOString()],
    queryFn: () => fetchMetaTimeline(assetId, from, to),
    enabled: options?.enabled ?? true,
  })
}

export function useMetaTimelineSummary(assetId: string, from: Date, to: Date) {
  return useQuery({
    queryKey: ['meta-timeline-summary', assetId, from.toISOString(), to.toISOString()],
    queryFn: () => fetchMetaTimelineSummary(assetId, from, to),
  })
}
