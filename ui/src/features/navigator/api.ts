// Navigator fetch functions. The grouped metric heatmap endpoint was
// previously hosted under features/evaluations/api.ts — it has been moved
// here as part of the Chunk B2 migration so navigator owns its own data
// access. See §15.5 of the UI layering spec.

import type { GroupedMetricHeatmapResponseDto } from './mappers'

const BASE = '/api'

export async function fetchGroupedMetricHeatmap(
  assetName: string,
  filters: { evaluation_name?: string[]; from?: string; to?: string } = {},
): Promise<GroupedMetricHeatmapResponseDto> {
  const params = new URLSearchParams({ asset_name: assetName })
  if (filters.evaluation_name?.length) {
    for (const name of filters.evaluation_name) {
      params.append('evaluation_name', name)
    }
  }
  if (filters.from) params.set('from', filters.from)
  if (filters.to) params.set('to', filters.to)
  const response = await fetch(`${BASE}/evaluations/heatmap?${params}`)
  if (!response.ok) {
    throw new Error(`fetchGroupedMetricHeatmap: ${response.status}`)
  }
  return response.json()
}
