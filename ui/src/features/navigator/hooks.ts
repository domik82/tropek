import { useQuery } from '@tanstack/react-query'
import { evaluationKeys } from '@/lib/queryKeys'
import { fetchEvaluations, fetchMetricHeatmap } from '@/features/evaluations/api'
import { useTimeRange } from '@/lib/time-range-context'

export function useAssetEvaluations(assetName: string | undefined) {
  const { from } = useTimeRange()
  const filters = { asset_name: assetName, from }
  return useQuery({
    queryKey: evaluationKeys.list(filters),
    queryFn: () => fetchEvaluations(filters),
    enabled: !!assetName,
  })
}

export function useMetricHeatmap(assetName: string | undefined) {
  return useQuery({
    queryKey: evaluationKeys.heatmap(assetName!),
    queryFn: () => fetchMetricHeatmap(assetName!),
    enabled: !!assetName,
  })
}
