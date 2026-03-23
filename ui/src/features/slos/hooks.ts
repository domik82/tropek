// src/features/slos/hooks.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { sloKeys, groupKeys, assetKeys } from '@/lib/queryKeys'
import { fetchSlos, fetchSloDetail, validateSlo, createSloDefinition, deleteSlo, fetchSloVersions } from './api'
import {
  fetchGroupTree, createGroup, updateGroup, deleteGroup,
  fetchGroupSloLinks, createGroupSloLink, deleteGroupSloLink,
  addSubgroup, fetchSloTagKeys, fetchSloTagValues,
} from './api'

export function useSlos() {
  return useQuery({
    queryKey: sloKeys.all,
    queryFn: () => fetchSlos(),
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
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: groupKeys.all })
      void qc.invalidateQueries({ queryKey: assetKeys.groups() })
    },
  })
}

export function useUpdateGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, ...body }: { name: string; display_name?: string; description?: string }) =>
      updateGroup(name, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: groupKeys.all })
      void qc.invalidateQueries({ queryKey: assetKeys.groups() })
    },
  })
}

export function useDeleteGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, deactivateSlos }: { name: string; deactivateSlos: boolean }) =>
      deleteGroup(name, deactivateSlos),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: groupKeys.all })
      void qc.invalidateQueries({ queryKey: assetKeys.groups() })
      void qc.invalidateQueries({ queryKey: sloKeys.all })
    },
  })
}

export function useAddSubgroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ parentName, childGroupId }: { parentName: string; childGroupId: string }) =>
      addSubgroup(parentName, childGroupId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: groupKeys.all })
      void qc.invalidateQueries({ queryKey: assetKeys.groups() })
    },
  })
}

export function useCreateGroupSloLink() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ groupName, ...body }: { groupName: string; slo_name: string; sli_name: string; data_source_name: string }) =>
      createGroupSloLink(groupName, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: groupKeys.all })
      void qc.invalidateQueries({ queryKey: assetKeys.groups() })
      void qc.invalidateQueries({ queryKey: sloKeys.all })
    },
  })
}

export function useDeleteGroupSloLink() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ groupName, linkName }: { groupName: string; linkName: string }) =>
      deleteGroupSloLink(groupName, linkName),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: groupKeys.all })
      void qc.invalidateQueries({ queryKey: assetKeys.groups() })
    },
  })
}

export function useSloTagKeys() {
  return useQuery({ queryKey: sloKeys.tagKeys(), queryFn: fetchSloTagKeys })
}

export function useSloTagValues(key: string) {
  return useQuery({
    queryKey: sloKeys.tagValues(key),
    queryFn: () => fetchSloTagValues(key),
    enabled: !!key,
  })
}
