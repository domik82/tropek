// src/mocks/handlers/slis.ts
import { http, HttpResponse } from 'msw'

async function gen() {
  return import('../generate')
}

export const sliHandlers = [
  http.get('/api/sli-definitions', async () => {
    const { getSliDefinitions } = await gen()
    const data = getSliDefinitions()
    return HttpResponse.json({ items: data, total: data.length })
  }),

  http.get('/api/sli-definitions/:name', async ({ params }) => {
    const { getSliDefinitions } = await gen()
    const sli = getSliDefinitions().find(s => s.name === params.name)
    if (!sli) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    return HttpResponse.json(sli)
  }),

  http.get('/api/sli-definitions/:name/versions', async ({ params }) => {
    const { getSliDefinitions } = await gen()
    const current = getSliDefinitions().find(s => s.name === params.name)
    if (!current) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    const history = [
      { ...current },
      {
        ...current,
        id: crypto.randomUUID(),
        version: current.version - 1,
        active: false,
        notes: current.version > 1 ? `Previous v${current.version - 1}` : undefined,
        created_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
      },
    ].filter(v => v.version > 0)
    return HttpResponse.json(history)
  }),

  http.post('/api/sli-definitions', async ({ request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json(
      {
        id: crypto.randomUUID(),
        version: 1,
        active: true,
        meta: {},
        created_at: new Date().toISOString(),
        ...body,
      },
      { status: 201 }
    )
  }),

  http.delete('/api/sli-definitions/:name', ({ params }) => {
    console.log('[mock] soft-delete SLI:', params.name)
    return new HttpResponse(null, { status: 204 })
  }),
]
