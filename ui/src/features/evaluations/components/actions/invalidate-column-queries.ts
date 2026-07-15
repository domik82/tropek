import type { QueryClient } from '@tanstack/react-query'
import { evaluationKeys } from '@/lib/queryKeys'

export function invalidateColumnQueries(
  queryClient: QueryClient,
  affectedSloEvaluationIds: string[],
): void {
  for (const id of affectedSloEvaluationIds) {
    queryClient.invalidateQueries({ queryKey: evaluationKeys.detail(id) })
  }
  queryClient.invalidateQueries({ queryKey: evaluationKeys.all })
  queryClient.invalidateQueries({ queryKey: evaluationKeys.allNames })
  queryClient.invalidateQueries({ queryKey: evaluationKeys.allHeatmaps })
  queryClient.invalidateQueries({ queryKey: evaluationKeys.allTrends })
  queryClient.invalidateQueries({ queryKey: evaluationKeys.allSloTrends })
}
