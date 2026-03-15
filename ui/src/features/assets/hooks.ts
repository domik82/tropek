// src/features/assets/hooks.ts
import { useQuery } from '@tanstack/react-query'
import { assetKeys } from '@/lib/queryKeys'
import { fetchAssets, fetchAssetGroupTree } from './api'

export function useAssets() {
  return useQuery({
    queryKey: assetKeys.all,
    queryFn: fetchAssets,
  })
}

export function useAssetGroups() {
  return useQuery({
    queryKey: assetKeys.groups(),
    queryFn: fetchAssetGroupTree,
  })
}
