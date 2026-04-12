import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { sloGroupKeys, sloKeys } from '@/lib/queryKeys'
import {
  fetchSloGroups,
  fetchSloGroupDetail,
  createSloGroup,
  updateSloGroup,
  deleteSloGroup,
  type SloGroupCreateInput,
  type SloGroupUpdateInput,
} from './api'

export function useSloGroups() {
  return useQuery({
    queryKey: sloGroupKeys.all,
    queryFn: fetchSloGroups,
  })
}

export function useSloGroupDetail(name: string) {
  return useQuery({
    queryKey: sloGroupKeys.detail(name),
    queryFn: () => fetchSloGroupDetail(name),
    enabled: !!name,
  })
}

export function useCreateSloGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: SloGroupCreateInput) => createSloGroup(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: sloGroupKeys.all })
      void qc.invalidateQueries({ queryKey: sloKeys.all })
    },
  })
}

export function useUpdateSloGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, body }: { name: string; body: SloGroupUpdateInput }) =>
      updateSloGroup(name, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: sloGroupKeys.all })
      void qc.invalidateQueries({ queryKey: sloKeys.all })
    },
  })
}

export function useDeleteSloGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteSloGroup,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: sloGroupKeys.all })
      void qc.invalidateQueries({ queryKey: sloKeys.all })
    },
  })
}
