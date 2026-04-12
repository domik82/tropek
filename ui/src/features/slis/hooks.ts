// src/features/slis/hooks.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { sliKeys } from '@/lib/queryKeys'
import {
  fetchSliDefinitions,
  fetchSliDetail,
  createSliDefinition,
  deleteSliDefinition,
  fetchSliVersions,
  fetchSliTagKeys,
  fetchSliTagValues,
} from './api'
import type { SliCreateInput } from './api'

export function useSliDefinitions(adapterType?: string) {
  return useQuery({
    queryKey: [...sliKeys.all, { adapterType }],
    queryFn: () => fetchSliDefinitions(adapterType),
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
    mutationFn: (payload: SliCreateInput) => createSliDefinition(payload),
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

export function useSliTagKeys() {
  return useQuery({ queryKey: sliKeys.tagKeys(), queryFn: fetchSliTagKeys })
}

export function useSliTagValues(key: string) {
  return useQuery({
    queryKey: sliKeys.tagValues(key),
    queryFn: () => fetchSliTagValues(key),
    enabled: !!key,
  })
}
