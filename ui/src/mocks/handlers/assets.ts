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

  http.get('/api/asset-groups/:name/slo-links', async ({ params }) => {
    const { getGroupSloLinks } = await gen()
    const links = getGroupSloLinks(params.name as string)
    return HttpResponse.json(links)
  }),

  http.post('/api/asset-groups/:name/slo-links', async ({ request, params }) => {
    const body = await request.json() as { slo_name: string; sli_name: string; data_source_name: string }
    const groupName = params.name as string
    return HttpResponse.json({
      id: crypto.randomUUID(),
      link_name: `${groupName}-${body.slo_name}`,
      group_id: crypto.randomUUID(),
      slo_name: body.slo_name,
      sli_name: body.sli_name,
      data_source_name: body.data_source_name,
      created_at: new Date().toISOString(),
    }, { status: 201 })
  }),

  http.delete('/api/asset-groups/:name/slo-links/:linkName', async () => {
    return new HttpResponse(null, { status: 204 })
  }),

  http.post('/api/asset-groups', async ({ request }) => {
    const body = await request.json() as { name: string; display_name?: string; description?: string }
    return HttpResponse.json({
      id: crypto.randomUUID(),
      name: body.name,
      display_name: body.display_name ?? null,
      description: body.description ?? null,
      members: [],
      subgroups: [],
    }, { status: 201 })
  }),

  http.put('/api/asset-groups/:name', async ({ params, request }) => {
    const body = await request.json() as { display_name?: string; description?: string }
    return HttpResponse.json({
      id: crypto.randomUUID(),
      name: params.name,
      display_name: body.display_name ?? null,
      description: body.description ?? null,
      members: [],
      subgroups: [],
    })
  }),

  http.delete('/api/asset-groups/:name', async () => {
    return new HttpResponse(null, { status: 204 })
  }),
]
