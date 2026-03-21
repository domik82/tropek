// src/features/assets/types.ts

export interface AssetType {
  id: string
  name: string
  is_default: boolean
  asset_count: number
}

export interface Asset {
  id: string
  name: string
  display_name?: string
  type_name: string
  tags: Record<string, string>
  created_at: string
  updated_at: string
}

export interface AssetGroupMember {
  asset_id: string
  asset_name: string
  weight: number
}

export interface AssetGroupSubgroup {
  group_id: string
  group_name: string
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

export interface TagKeyCount {
  key: string
  count: number
}

export interface TagValueCount {
  value: string
  count: number
}
