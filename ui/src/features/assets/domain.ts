// Domain types for the assets feature. UI vocabulary; camelCase;
// Date objects rather than ISO strings. Hand-written — never regenerated.

// Opaque per-asset filter preferences (§15.4 of the UI layering spec —
// design deferred; see memory note project_heatmap_config_investigation.md).
export type AssetHeatmapConfig = Record<string, unknown> | null

export interface Asset {
  id: string
  name: string
  displayName: string | null
  typeName: string
  color: string | null
  tags: Record<string, string>
  variables: Record<string, string>
  heatmapConfig: AssetHeatmapConfig
  createdAt: Date
  updatedAt: Date
}

export interface AssetType {
  id: string
  name: string
  isDefault: boolean
  assetCount: number
}

export interface AssetGroupMember {
  assetId: string
  assetName: string
  assetDisplayName: string | null
  assetTypeName: string
  weight: number
}

export interface AssetGroupSubgroup {
  groupId: string
  groupName: string
  weight: number
}

export interface AssetGroup {
  id: string
  name: string
  displayName: string | null
  description: string | null
  color: string | null
  members: AssetGroupMember[]
  subgroups: AssetGroupSubgroup[]
  createdAt: Date
  updatedAt: Date
}

export interface AssetGroupTree {
  topLevel: AssetGroup[]
  allGroups: AssetGroup[]
}

export interface TagKeyCount {
  key: string
  count: number
}

export interface TagValueCount {
  value: string
  count: number
}
