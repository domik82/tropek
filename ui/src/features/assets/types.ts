// src/features/assets/types.ts

export interface Asset {
  id: string
  name: string
  display_name?: string
  type: 'vm' | 'server' | 'container' | 'endpoint' | 'service' | 'sensor'
  labels: Record<string, string>
  created_at: string
}

export interface AssetGroupMember {
  asset_id: string
  asset_name: string
  weight: number
}

export interface AssetGroupSubgroup {
  group_id: string
  weight: number
}

export interface AssetGroup {
  id: string
  name: string
  display_name?: string
  description?: string
  members: AssetGroupMember[]
  subgroups: AssetGroupSubgroup[]
}

export interface AssetGroupTree {
  top_level: AssetGroup[]
  all_groups: AssetGroup[]
}
