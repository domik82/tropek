// src/features/assets/api.ts
import type { components } from '@/generated/api'
import type {
  Asset,
  AssetGroup,
  AssetGroupTree,
  AssetType,
  TagKeyCount,
  TagValueCount,
} from './domain'
import {
  dtoToAsset,
  dtoToAssetGroup,
  dtoToAssetGroupTree,
  dtoToAssetType,
  type AssetDto,
  type AssetGroupDto,
  type AssetGroupTreeDto,
  type AssetTypeDto,
} from './mappers'

// Input types as direct DTO aliases — forms send backend-shaped bodies directly.
export type AssetCreateInput = components['schemas']['AssetCreate']
export type AssetUpdateInput = components['schemas']['AssetUpdate']
export type AssetTypeCreateInput = components['schemas']['AssetTypeCreate']
export type AssetTypeUpdateInput = components['schemas']['AssetTypeUpdate']
export type AssetGroupUpdateInput = components['schemas']['AssetGroupUpdate']

const BASE = '/api'

// ---- Asset Types ----

export async function fetchAssetTypes(): Promise<AssetType[]> {
  const res = await fetch(`${BASE}/asset-types`)
  if (!res.ok) throw new Error(`fetchAssetTypes: ${res.status}`)
  const data: { items: AssetTypeDto[]; total: number } = await res.json()
  return data.items.map(dtoToAssetType)
}

export async function createAssetType(name: string, isDefault = false): Promise<AssetType> {
  const res = await fetch(`${BASE}/asset-types`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, is_default: isDefault }),
  })
  if (!res.ok) throw new Error(`createAssetType: ${res.status}`)
  const body: AssetTypeDto = await res.json()
  return dtoToAssetType(body)
}

export async function renameAssetType(oldName: string, newName: string): Promise<AssetType> {
  const res = await fetch(`${BASE}/asset-types/${encodeURIComponent(oldName)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: newName }),
  })
  if (!res.ok) throw new Error(`renameAssetType: ${res.status}`)
  const body: AssetTypeDto = await res.json()
  return dtoToAssetType(body)
}

export async function setDefaultAssetType(name: string): Promise<AssetType> {
  const res = await fetch(`${BASE}/asset-types/${encodeURIComponent(name)}/set-default`, {
    method: 'PATCH',
  })
  if (!res.ok) throw new Error(`setDefaultAssetType: ${res.status}`)
  const body: AssetTypeDto = await res.json()
  return dtoToAssetType(body)
}

export async function deleteAssetType(name: string): Promise<void> {
  const res = await fetch(`${BASE}/asset-types/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`deleteAssetType: ${res.status}`)
}

// ---- Assets ----

export async function fetchAssets(): Promise<Asset[]> {
  const res = await fetch(`${BASE}/assets`)
  if (!res.ok) throw new Error(`fetchAssets: ${res.status}`)
  const data: { items: AssetDto[]; total: number } = await res.json()
  return data.items.map(dtoToAsset)
}

export async function fetchAsset(name: string): Promise<Asset> {
  const res = await fetch(`${BASE}/assets/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`fetchAsset: ${res.status}`)
  const body: AssetDto = await res.json()
  return dtoToAsset(body)
}

export async function createAsset(body: {
  name: string
  type_name: string
  display_name?: string
  tags?: Record<string, string>
}): Promise<Asset> {
  const res = await fetch(`${BASE}/assets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`createAsset: ${res.status}`)
  const response: AssetDto = await res.json()
  return dtoToAsset(response)
}

export async function updateAsset(
  name: string,
  body: { display_name?: string; type_name?: string; tags?: Record<string, string> },
): Promise<Asset> {
  const res = await fetch(`${BASE}/assets/${encodeURIComponent(name)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`updateAsset: ${res.status}`)
  const response: AssetDto = await res.json()
  return dtoToAsset(response)
}

export async function deleteAsset(name: string): Promise<void> {
  const res = await fetch(`${BASE}/assets/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`deleteAsset: ${res.status}`)
}

// ---- Tags ----

export async function fetchTagKeys(): Promise<TagKeyCount[]> {
  const res = await fetch(`${BASE}/assets/tag-keys`)
  if (!res.ok) throw new Error(`fetchTagKeys: ${res.status}`)
  return res.json()
}

export async function fetchTagValues(key: string): Promise<TagValueCount[]> {
  const res = await fetch(`${BASE}/assets/tag-values?key=${encodeURIComponent(key)}`)
  if (!res.ok) throw new Error(`fetchTagValues: ${res.status}`)
  return res.json()
}

// ---- Asset Groups ----

export async function fetchAssetGroupTree(): Promise<AssetGroupTree> {
  const res = await fetch(`${BASE}/asset-groups/tree`)
  if (!res.ok) throw new Error(`fetchAssetGroupTree: ${res.status}`)
  const body: AssetGroupTreeDto = await res.json()
  return dtoToAssetGroupTree(body)
}

export async function fetchAssetGroup(name: string): Promise<AssetGroup> {
  const res = await fetch(`${BASE}/asset-groups/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`fetchAssetGroup: ${res.status}`)
  const body: AssetGroupDto = await res.json()
  return dtoToAssetGroup(body)
}

export async function addGroupMember(
  groupName: string,
  assetId: string,
  weight = 1.0,
): Promise<AssetGroup> {
  const res = await fetch(`${BASE}/asset-groups/${encodeURIComponent(groupName)}/members`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ asset_id: assetId, weight }),
  })
  if (!res.ok) throw new Error(`addGroupMember: ${res.status}`)
  const body: AssetGroupDto = await res.json()
  return dtoToAssetGroup(body)
}

export async function removeGroupMember(groupName: string, assetId: string): Promise<void> {
  const res = await fetch(
    `${BASE}/asset-groups/${encodeURIComponent(groupName)}/members/${assetId}`,
    { method: 'DELETE' },
  )
  if (!res.ok) throw new Error(`removeGroupMember: ${res.status}`)
}

// ---- Asset Group CRUD ----

export async function fetchGroupTree(): Promise<AssetGroupTree> {
  const res = await fetch(`${BASE}/asset-groups/tree`)
  if (!res.ok) throw new Error(`fetchGroupTree: ${res.status}`)
  const body: AssetGroupTreeDto = await res.json()
  return dtoToAssetGroupTree(body)
}

export async function createGroup(body: {
  name: string; display_name?: string; description?: string
}): Promise<AssetGroup> {
  const res = await fetch(`${BASE}/asset-groups`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`createGroup: ${res.status}`)
  const response: AssetGroupDto = await res.json()
  return dtoToAssetGroup(response)
}

export async function updateGroup(name: string, body: AssetGroupUpdateInput): Promise<AssetGroup> {
  const res = await fetch(`${BASE}/asset-groups/${encodeURIComponent(name)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`updateGroup: ${res.status}`)
  const response: AssetGroupDto = await res.json()
  return dtoToAssetGroup(response)
}

export async function deleteGroup(name: string, deactivateSlos: boolean): Promise<void> {
  const res = await fetch(
    `${BASE}/asset-groups/${encodeURIComponent(name)}?deactivate_slos=${deactivateSlos}`,
    { method: 'DELETE' },
  )
  if (!res.ok) throw new Error(`deleteGroup: ${res.status}`)
}

export async function addSubgroup(parentName: string, childGroupId: string): Promise<AssetGroup> {
  const res = await fetch(`${BASE}/asset-groups/${encodeURIComponent(parentName)}/subgroups`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ child_group_id: childGroupId, weight: 1.0 }),
  })
  if (!res.ok) throw new Error(`addSubgroup: ${res.status}`)
  const body: AssetGroupDto = await res.json()
  return dtoToAssetGroup(body)
}
