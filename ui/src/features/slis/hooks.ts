// src/features/slis/hooks.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { sliKeys } from '@/lib/queryKeys'
import {
  fetchSliDefinitions,
  fetchSliDetail,
  createSliDefinition,
  deleteSliDefinition,
  fetchSliVersions,
} from './api'
import type { SliDefinitionCreate } from './types'

export function useSliDefinitions() {
  return useQuery({
    queryKey: sliKeys.all,
    queryFn: fetchSliDefinitions,
  })
}

export function useSliDetail(name: string) {
  return useQuery({
    queryKey: sliKeys.detail(name),
    queryFn: () => fetchSliDetail(name),
    enabled: !!name,
  })
}

export function useSliVersions(name: string) {
  return useQuery({
    queryKey: sliKeys.versions(name),
    queryFn: () => fetchSliVersions(name),
    enabled: !!name,
  })
}

export function useCreateSli() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: SliDefinitionCreate) => createSliDefinition(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sliKeys.all })
    },
  })
}

export function useDeleteSli() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => deleteSliDefinition(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sliKeys.all })
    },
  })
}
