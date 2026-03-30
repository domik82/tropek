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
        { sli: 'response_time_p95', display_name: 'Response Time P95', pass_threshold: ['<500'], warning_threshold: ['<800'], weight: 1, key_sli: false, sort_order: 0 },
        { sli: 'error_rate', display_name: 'Error Rate', pass_threshold: ['<=0.5%'], warning_threshold: ['<=2%'], weight: 1, key_sli: false, sort_order: 1 },
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
    const all = getSloDefinitions() as { name: string; version: number; created_at: string; author?: string | null; notes?: string | null; active: boolean }[]
    const current = all.find(s => s.name === params.name)
    if (!current) return HttpResponse.json({ error: 'Not found' }, { status: 404 })
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
    console.log('[mock] soft-delete SLO:', params.name)
    return new HttpResponse(null, { status: 204 })
  }),

  http.post('/api/slo-definitions', async ({ request }) => {
    const body = await request.json() as {
      name: string
      objectives: unknown[]
      total_score_pass_pct: number
      total_score_warning_pct: number
      comparison: Record<string, unknown>
      display_name?: string
      notes?: string
      author?: string
    }
    return HttpResponse.json({
      id: crypto.randomUUID(),
      name: body.name,
      version: 1,
      display_name: body.display_name ?? null,
      author: body.author ?? null,
      notes: body.notes ?? null,
      active: true,
      tags: {},
      variables: {},
      created_at: new Date().toISOString(),
      objectives: body.objectives,
      total_score_pass_pct: body.total_score_pass_pct,
      total_score_warning_pct: body.total_score_warning_pct,
      comparison: body.comparison,
    }, { status: 201 })
  }),
]
