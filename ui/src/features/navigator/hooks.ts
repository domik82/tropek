import { useQuery } from '@tanstack/react-query'
import { fetchEvaluations, fetchMetricHeatmap } from '@/features/evaluations/api'

export function useAssetEvaluations(assetName: string | undefined) {
  return useQuery({
    queryKey: ['evaluations', { asset_name: assetName }],
    queryFn: () => fetchEvaluations({ asset_name: assetName }),
    enabled: !!assetName,
  })
}

export function useMetricHeatmap(assetName: string | undefined) {
  return useQuery({
    queryKey: ['metric-heatmap', assetName],
    queryFn: () => fetchMetricHeatmap(assetName!),
    enabled: !!assetName,
  })
}
