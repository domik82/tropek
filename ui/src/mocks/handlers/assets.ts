// src/mocks/handlers/assets.ts
import { http, HttpResponse } from 'msw'

async function gen() {
  return import('../generate')
}

export const assetHandlers = [
  http.get('/api/assets', async () => {
    const { getAssets } = await gen()
    const items = getAssets()
    return HttpResponse.json({ items, total: (items as unknown[]).length })
  }),

  http.get('/api/asset-groups/tree', async () => {
    const { getAssetGroupTree } = await gen()
    return HttpResponse.json(getAssetGroupTree())
  }),
]
