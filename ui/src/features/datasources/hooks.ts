import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { datasourceKeys } from '@/lib/queryKeys'
import {
  fetchDatasources, fetchDatasource, createDatasource,
  updateDatasource, deleteDatasource,
  fetchDatasourceTagKeys, fetchDatasourceTagValues,
} from './api'
import type { DatasourceCreateInput, DatasourceUpdateInput } from './api'

export function useDatasources(tagKey?: string, tagVal?: string) {
  return useQuery({
    queryKey: [...datasourceKeys.all, { tagKey, tagVal }],
    queryFn: () => fetchDatasources(tagKey, tagVal),
  })
}

export function useDatasource(name: string) {
  return useQuery({
    queryKey: datasourceKeys.detail(name),
    queryFn: () => fetchDatasource(name),
    enabled: !!name,
  })
}

export function useCreateDatasource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: DatasourceCreateInput) => createDatasource(payload),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: datasourceKeys.all }) },
  })
}

export function useUpdateDatasource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, ...body }: DatasourceUpdateInput & { name: string }) =>
      updateDatasource(name, body),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: datasourceKeys.all }) },
  })
}

export function useDeleteDatasource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => deleteDatasource(name),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: datasourceKeys.all }) },
  })
}

export function useDatasourceTagKeys() {
  return useQuery({ queryKey: datasourceKeys.tagKeys(), queryFn: fetchDatasourceTagKeys })
}

export function useDatasourceTagValues(key: string) {
  return useQuery({
    queryKey: datasourceKeys.tagValues(key),
    queryFn: () => fetchDatasourceTagValues(key),
    enabled: !!key,
  })
}
