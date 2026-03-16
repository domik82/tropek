// src/mocks/handlers/evaluations.ts
import { http, HttpResponse } from 'msw'

async function gen() {
  return import('../generate')
}

export const evaluationHandlers = [
  http.get('/api/evaluations', async ({ request }) => {
    const url = new URL(request.url)
    const group_name = url.searchParams.get('group_name') ?? undefined
    const asset_name = url.searchParams.get('asset_name') ?? undefined
    const date = url.searchParams.get('date') ?? undefined
    const from = url.searchParams.get('from') ?? undefined
    const to = url.searchParams.get('to') ?? undefined
    const { getEvaluations } = await gen()
    const items = getEvaluations({ group_name, asset_name, date, from, to })
    return HttpResponse.json({ items, total: items.length })
  }),

  http.get('/api/evaluations/metric-heatmap', async ({ request }) => {
    const url = new URL(request.url)
    const assetName = url.searchParams.get('asset_name') ?? ''
    const { getMetricHeatmap } = await gen()
    return HttpResponse.json(getMetricHeatmap(assetName))
  }),

  http.get('/api/evaluations/:id', async ({ params }) => {
    const { getEvaluationDetail } = await gen()
    return HttpResponse.json(getEvaluationDetail(params.id as string))
  }),

  http.get('/api/trend', async ({ request }) => {
    const url = new URL(request.url)
    const evalId = url.searchParams.get('eval_id') ?? ''
    const metric = url.searchParams.get('metric') ?? ''
    const { getTrend } = await gen()
    return HttpResponse.json(getTrend(evalId, metric))
  }),

  http.post('/api/evaluations', async ({ request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json(
      { id: crypto.randomUUID(), status: 'triggered', ...body },
      { status: 202 }
    )
  }),

  http.post('/api/evaluations/:id/annotations', async ({ params, request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json(
      {
        id: crypto.randomUUID(),
        eval_id: params.id,
        created_at: new Date().toISOString(),
        ...body,
      },
      { status: 201 }
    )
  }),

  http.patch('/api/evaluations/:id/invalidate', async ({ params, request }) => {
    const body = await request.json() as { invalidation_note?: string }
    const { getEvaluationDetail } = await gen()
    const detail = getEvaluationDetail(params.id as string)
    return HttpResponse.json({
      ...detail,
      invalidated: true,
      invalidation_note: body.invalidation_note ?? null,
    })
  }),

  http.patch('/api/evaluations/:id/override-status', async ({ params, request }) => {
    const body = await request.json() as { new_result: string; reason: string; author: string }
    const { getEvaluationDetail } = await gen()
    const detail = getEvaluationDetail(params.id as string)
    return HttpResponse.json({
      ...detail,
      result: body.new_result,
      result_override: { original_result: detail.result, new_result: body.new_result, reason: body.reason, author: body.author },
    })
  }),

  http.patch('/api/evaluations/:id/pin-baseline', async ({ params, request }) => {
    const body = await request.json() as { reason: string; author: string }
    const { getEvaluationDetail } = await gen()
    const detail = getEvaluationDetail(params.id as string)
    return HttpResponse.json({
      ...detail,
      baseline_pinned: true,
      baseline_pin: { reason: body.reason, author: body.author },
    })
  }),
]
