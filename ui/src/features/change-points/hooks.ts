import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchChangePoints,
  triageChangePoint,
  bulkTriageChangePoints,
  changePointKeys,
} from './api'
import type { ChangePointFilters, TriageInput, BulkTriageInput } from './domain'

export function useChangePoints(filters: ChangePointFilters) {
  return useQuery({
    queryKey: changePointKeys.list(filters),
    queryFn: () => fetchChangePoints(filters),
  })
}

export function useTriageChangePoint() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: TriageInput }) =>
      triageChangePoint(id, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: changePointKeys.all })
    },
  })
}

export function useBulkTriageChangePoints() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: BulkTriageInput) => bulkTriageChangePoints(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: changePointKeys.all })
    },
  })
}
