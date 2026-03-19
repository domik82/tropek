// src/features/slos/hooks.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { sloKeys, groupKeys, datasourceKeys, sliKeys } from '@/lib/queryKeys'
import { fetchSlos, fetchSloDetail, validateSlo, createSloDefinition, deleteSlo, fetchSloVersions } from './api'
import {
  fetchGroupTree, createGroup, updateGroup, deleteGroup,
  fetchGroupSloLinks, createGroupSloLink, deleteGroupSloLink,
  addSubgroup, fetchDatasources, fetchSliDefinitions,
} from './api'

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

export function useGroupTree() {
  return useQuery({ queryKey: groupKeys.tree(), queryFn: fetchGroupTree })
}

export function useGroupSloLinks(name: string) {
  return useQuery({
    queryKey: groupKeys.links(name),
    queryFn: () => fetchGroupSloLinks(name),
    enabled: !!name && name !== '__ungrouped__',
  })
}

export function useCreateGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createGroup,
    onSuccess: () => { qc.invalidateQueries({ queryKey: groupKeys.all }) },
  })
}

export function useUpdateGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, ...body }: { name: string; display_name?: string; description?: string }) =>
      updateGroup(name, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: groupKeys.all }) },
  })
}

export function useDeleteGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, deactivateSlos }: { name: string; deactivateSlos: boolean }) =>
      deleteGroup(name, deactivateSlos),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: groupKeys.all })
      qc.invalidateQueries({ queryKey: sloKeys.all })
    },
  })
}

export function useAddSubgroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ parentName, childGroupId }: { parentName: string; childGroupId: string }) =>
      addSubgroup(parentName, childGroupId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: groupKeys.all }) },
  })
}

export function useCreateGroupSloLink() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ groupName, ...body }: { groupName: string; slo_name: string; sli_name: string; data_source_name: string }) =>
      createGroupSloLink(groupName, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: groupKeys.all })
      qc.invalidateQueries({ queryKey: sloKeys.all })
    },
  })
}

export function useDeleteGroupSloLink() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ groupName, linkName }: { groupName: string; linkName: string }) =>
      deleteGroupSloLink(groupName, linkName),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: groupKeys.all })
    },
  })
}

export function useDatasources() {
  return useQuery({ queryKey: datasourceKeys.all, queryFn: fetchDatasources })
}

export function useSliDefinitions(adapterType?: string) {
  return useQuery({
    queryKey: [...sliKeys.all, { adapterType }],
    queryFn: () => fetchSliDefinitions(adapterType),
    enabled: adapterType !== undefined,
  })
}
