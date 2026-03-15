// src/features/assets/api.ts
import type { Asset, AssetGroupTree } from './types'

const BASE = '/api'

export async function fetchAssets(): Promise<Asset[]> {
  const res = await fetch(`${BASE}/assets`)
  if (!res.ok) throw new Error(`fetchAssets: ${res.status}`)
  const data: { items: Asset[]; total: number } = await res.json()
  return data.items
}

export async function fetchAssetGroupTree(): Promise<AssetGroupTree> {
  const res = await fetch(`${BASE}/asset-groups/tree`)
  if (!res.ok) throw new Error(`fetchAssetGroupTree: ${res.status}`)
  return res.json()
}
