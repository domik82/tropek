// src/features/assets/api.ts
import type {
  Asset, AssetGroup, AssetGroupTree, AssetType,
  TagKeyCount, TagValueCount,
} from './types'

const BASE = '/api'

// ---- Asset Types ----

export async function fetchAssetTypes(): Promise<AssetType[]> {
  const res = await fetch(`${BASE}/asset-types`)
  if (!res.ok) throw new Error(`fetchAssetTypes: ${res.status}`)
  const data: { items: AssetType[]; total: number } = await res.json()
  return data.items
}

export async function createAssetType(name: string, isDefault = false): Promise<AssetType> {
  const res = await fetch(`${BASE}/asset-types`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, is_default: isDefault }),
  })
  if (!res.ok) throw new Error(`createAssetType: ${res.status}`)
  return res.json()
}

export async function renameAssetType(oldName: string, newName: string): Promise<AssetType> {
  const res = await fetch(`${BASE}/asset-types/${encodeURIComponent(oldName)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: newName }),
  })
  if (!res.ok) throw new Error(`renameAssetType: ${res.status}`)
  return res.json()
}

export async function setDefaultAssetType(name: string): Promise<AssetType> {
  const res = await fetch(`${BASE}/asset-types/${encodeURIComponent(name)}/set-default`, {
    method: 'PATCH',
  })
  if (!res.ok) throw new Error(`setDefaultAssetType: ${res.status}`)
  return res.json()
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
  const data: { items: Asset[]; total: number } = await res.json()
  return data.items
}

export async function fetchAsset(name: string): Promise<Asset> {
  const res = await fetch(`${BASE}/assets/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`fetchAsset: ${res.status}`)
  return res.json()
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
  return res.json()
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
  return res.json()
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
  return res.json()
}

export async function fetchAssetGroup(name: string): Promise<AssetGroup> {
  const res = await fetch(`${BASE}/asset-groups/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`fetchAssetGroup: ${res.status}`)
  return res.json()
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
  return res.json()
}

export async function removeGroupMember(groupName: string, assetId: string): Promise<void> {
  const res = await fetch(
    `${BASE}/asset-groups/${encodeURIComponent(groupName)}/members/${assetId}`,
    { method: 'DELETE' },
  )
  if (!res.ok) throw new Error(`removeGroupMember: ${res.status}`)
}
