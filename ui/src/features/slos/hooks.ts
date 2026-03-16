// src/features/slos/hooks.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { sloKeys } from '@/lib/queryKeys'
import { fetchSlos, fetchSloDetail, validateSlo, createSloDefinition, deleteSlo, fetchSloVersions } from './api'

export function useSlos() {
  return useQuery({
    queryKey: sloKeys.all,
    queryFn: fetchSlos,
  })
}

export function useSloDetail(name: string) {
  return useQuery({
    queryKey: sloKeys.detail(name),
    queryFn: () => fetchSloDetail(name),
    enabled: !!name,
  })
}

export function useSloValidation() {
  return useMutation({
    mutationFn: validateSlo,
  })
}

export function useCreateSlo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof createSloDefinition>[0]) => createSloDefinition(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: sloKeys.all })
    },
  })
}

export function useDeleteSlo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteSlo,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: sloKeys.all })
    },
  })
}

export function useSloVersions(name: string, enabled: boolean) {
  return useQuery({
    queryKey: [...sloKeys.detail(name), 'versions'],
    queryFn: () => fetchSloVersions(name),
    enabled: enabled && !!name,
  })
}
