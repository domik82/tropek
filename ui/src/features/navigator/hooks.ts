import { useQuery } from '@tanstack/react-query'
import { evaluationKeys } from '@/lib/queryKeys'
import { fetchEvaluations, fetchGroupedMetricHeatmap, fetchEvaluationNames } from '@/features/evaluations/api'
import { useTimeRange } from '@/lib/time-range-context'

export function useAssetEvaluations(assetName: string | undefined, evaluationNames?: string[]) {
  const { from, to } = useTimeRange()
  const filters = {
    asset_name: assetName,
    evaluation_name: evaluationNames,
    from,
    ...(to ? { to } : {}),
  }
  const query = useQuery({
    queryKey: evaluationKeys.list(filters),
    queryFn: () => fetchEvaluations(filters),
    enabled: !!assetName,
  })
  return {
    ...query,
    data: query.data?.items,
    truncated: query.data?.truncated ?? false,
    total: query.data?.total ?? 0,
  }
}

export function useMetricHeatmap(assetName: string | undefined, evaluationNames?: string[]) {
  const { from, to } = useTimeRange()
  const timeFilters = { from, ...(to ? { to } : {}) }
  const fetchFilters = { ...timeFilters, evaluation_name: evaluationNames }
  return useQuery({
    queryKey: evaluationKeys.heatmap(assetName!, timeFilters, evaluationNames),
    queryFn: () => fetchGroupedMetricHeatmap(assetName!, fetchFilters),
    enabled: !!assetName,
  })
}

export function useEvaluationNames(assetName?: string, groupName?: string) {
  return useQuery({
    queryKey: evaluationKeys.names({ asset_name: assetName, group_name: groupName }),
    queryFn: () => fetchEvaluationNames({ asset_name: assetName, group_name: groupName }),
  })
}
