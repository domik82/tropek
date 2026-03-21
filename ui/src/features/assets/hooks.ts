// src/features/assets/hooks.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { assetKeys, assetTypeKeys, labelKeys, groupKeys } from '@/lib/queryKeys'
import {
  fetchAssets, fetchAsset, createAsset, updateAsset, deleteAsset,
  fetchAssetGroupTree, fetchAssetGroup, addGroupMember, removeGroupMember,
  fetchAssetTypes, createAssetType, renameAssetType, setDefaultAssetType, deleteAssetType,
  fetchTagKeys, fetchTagValues,
} from './api'

// ---- Assets ----

export function useAssets() {
  return useQuery({ queryKey: assetKeys.all, queryFn: fetchAssets })
}

export function useAsset(name: string | null) {
  return useQuery({
    queryKey: [...assetKeys.all, name ?? ''],
    queryFn: () => fetchAsset(name!),
    enabled: name !== null,
  })
}

export function useCreateAsset() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createAsset,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: assetKeys.all })
      void qc.invalidateQueries({ queryKey: groupKeys.all })
    },
  })
}

export function useUpdateAsset() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, ...body }: { name: string; display_name?: string; type_name?: string; tags?: Record<string, string> }) =>
      updateAsset(name, body),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: assetKeys.all }) },
  })
}

export function useDeleteAsset() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteAsset,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: assetKeys.all })
      void qc.invalidateQueries({ queryKey: groupKeys.all })
    },
  })
}

// ---- Asset Groups ----

export function useAssetGroups() {
  return useQuery({ queryKey: assetKeys.groups(), queryFn: fetchAssetGroupTree })
}

export function useAssetGroup(name: string | null) {
  return useQuery({
    queryKey: groupKeys.detail(name ?? ''),
    queryFn: () => fetchAssetGroup(name!),
    enabled: name !== null,
  })
}

export function useAddGroupMember() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ groupName, assetId, weight }: { groupName: string; assetId: string; weight?: number }) =>
      addGroupMember(groupName, assetId, weight),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: groupKeys.all })
      void qc.invalidateQueries({ queryKey: assetKeys.groups() })
    },
  })
}

export function useRemoveGroupMember() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ groupName, assetId }: { groupName: string; assetId: string }) =>
      removeGroupMember(groupName, assetId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: groupKeys.all })
      void qc.invalidateQueries({ queryKey: assetKeys.groups() })
    },
  })
}

// ---- Asset Types ----

export function useAssetTypes() {
  return useQuery({ queryKey: assetTypeKeys.all, queryFn: fetchAssetTypes })
}

export function useCreateAssetType() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => createAssetType(name),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: assetTypeKeys.all }) },
  })
}

export function useRenameAssetType() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ oldName, newName }: { oldName: string; newName: string }) =>
      renameAssetType(oldName, newName),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: assetTypeKeys.all })
      void qc.invalidateQueries({ queryKey: assetKeys.all })
    },
  })
}

export function useSetDefaultAssetType() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: setDefaultAssetType,
    onSuccess: () => { void qc.invalidateQueries({ queryKey: assetTypeKeys.all }) },
  })
}

export function useDeleteAssetType() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteAssetType,
    onSuccess: () => { void qc.invalidateQueries({ queryKey: assetTypeKeys.all }) },
  })
}

// ---- Tags ----

export function useTagKeys() {
  return useQuery({ queryKey: labelKeys.keys(), queryFn: fetchTagKeys })
}

export function useTagValues(key: string | null) {
  return useQuery({
    queryKey: labelKeys.values(key ?? ''),
    queryFn: () => fetchTagValues(key!),
    enabled: key !== null,
  })
}
