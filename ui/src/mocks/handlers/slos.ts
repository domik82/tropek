// src/mocks/handlers/slos.ts
import { http, HttpResponse } from 'msw'

async function gen() {
  return import('../generate')
}

export const sloHandlers = [
  http.post('/api/slo-definitions/validate', async ({ request }) => {
    await request.json()
    return HttpResponse.json({
      valid: true,
      errors: [],
      objectives: [
        { sli: 'response_time_p95', pass: [{ criteria: ['<500'] }], warning: [{ criteria: ['<800'] }], weight: 1 },
        { sli: 'error_rate', pass: [{ criteria: ['<=0.5%'] }], warning: [{ criteria: ['<=2%'] }], weight: 1 },
      ],
    })
  }),

  http.post('/api/slo-definitions/test', async () => {
    return HttpResponse.json({
      result: 'pass',
      score: 91.5,
      indicator_results: [],
      baseline_mode: 'none',
      metrics_fetched: {},
      fetch_errors: {},
      compared_values: null,
    })
  }),

  http.get('/api/slo-definitions', async () => {
    const { getSloDefinitions } = await gen()
    const items = getSloDefinitions()
    return HttpResponse.json({ items, total: (items as unknown[]).length })
  }),

  http.get('/api/slo-definitions/:name/versions', async ({ params }) => {
    const { getSloDefinitions } = await gen()
    const all = getSloDefinitions() as { name: string; version: number; created_at: string; author?: string | null; notes?: string | null; active: boolean; slo_yaml: string }[]
    const current = all.find(s => s.name === params.name)
    if (!current) return HttpResponse.json({ error: 'Not found' }, { status: 404 })
    // Return mock history: current version + a couple of older ones
    const history = [
      { ...current },
      {
        ...current,
        version: current.version - 1,
        active: false,
        notes: current.version > 1 ? `Previous v${current.version - 1}` : null,
        created_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
      },
    ].filter(v => v.version > 0)
    return HttpResponse.json(history)
  }),

  http.get('/api/slo-definitions/:name', async ({ params }) => {
    const { getSloDefinitions } = await gen()
    const all = getSloDefinitions()
    const slo = (all as { name: string }[]).find(s => s.name === params.name)
    if (!slo) return HttpResponse.json({ error: 'Not found' }, { status: 404 })
    return HttpResponse.json(slo)
  }),

  http.delete('/api/slo-definitions/:name', async ({ params }) => {
    // Soft delete — in real API this marks all versions inactive
    console.log('[mock] soft-delete SLO:', params.name)
    return new HttpResponse(null, { status: 204 })
  }),

  http.post('/api/slo-definitions', async ({ request }) => {
    const body = await request.json() as { name: string; slo_yaml: string; display_name?: string; notes?: string; author?: string }
    return HttpResponse.json({
      id: crypto.randomUUID(),
      name: body.name,
      version: 1,
      display_name: body.display_name ?? null,
      author: body.author ?? null,
      notes: body.notes ?? null,
      active: true,
      meta: {},
      created_at: new Date().toISOString(),
      slo_yaml: body.slo_yaml,
    }, { status: 201 })
  }),
]
