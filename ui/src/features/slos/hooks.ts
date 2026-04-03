// src/features/slos/hooks.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { sloKeys, groupKeys, assetKeys, assignmentKeys } from '@/lib/queryKeys'
import { fetchSlos, fetchSloDetail, validateSlo, createSloDefinition, deleteSlo, fetchSloVersions } from './api'
import {
  fetchGroupTree, createGroup, updateGroup, deleteGroup,
  addSubgroup, fetchSloTagKeys, fetchSloTagValues,
  fetchAssetSloAssignments, fetchGroupSloAssignments,
  fetchAssetSloGroupAssignments,
  createGroupSloAssignment, deleteGroupSloAssignment,
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

// ---- SLO Assignments ----

export function useAssetSloAssignments(assetName: string) {
  return useQuery({
    queryKey: assignmentKeys.asset(assetName),
    queryFn: () => fetchAssetSloAssignments(assetName),
    enabled: !!assetName,
  })
}

export function useAssetSloGroupAssignments(assetName: string) {
  return useQuery({
    queryKey: ['slo-group-assignments', 'asset', assetName],
    queryFn: () => fetchAssetSloGroupAssignments(assetName),
    enabled: !!assetName,
  })
}

export function useGroupSloAssignments(groupName: string) {
  return useQuery({
    queryKey: assignmentKeys.group(groupName),
    queryFn: () => fetchGroupSloAssignments(groupName),
    enabled: !!groupName,
  })
}

export function useCreateGroupSloAssignment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ groupName, ...body }: { groupName: string; slo_definition_id: string; data_source_name: string }) =>
      createGroupSloAssignment(groupName, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: assignmentKeys.all })
      void qc.invalidateQueries({ queryKey: groupKeys.all })
    },
  })
}

export function useDeleteGroupSloAssignment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ groupName, assignmentId }: { groupName: string; assignmentId: string }) =>
      deleteGroupSloAssignment(groupName, assignmentId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: assignmentKeys.all })
      void qc.invalidateQueries({ queryKey: groupKeys.all })
    },
  })
}
