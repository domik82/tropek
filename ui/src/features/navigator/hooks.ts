import { useQuery } from '@tanstack/react-query'
import { evaluationKeys } from '@/lib/queryKeys'
import { fetchEvaluations, fetchMetricHeatmap } from '@/features/evaluations/api'

export function useAssetEvaluations(assetName: string | undefined) {
  return useQuery({
    queryKey: evaluationKeys.list({ asset_name: assetName }),
    queryFn: () => fetchEvaluations({ asset_name: assetName }),
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
