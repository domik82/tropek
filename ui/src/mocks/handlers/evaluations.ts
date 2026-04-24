// src/mocks/handlers/evaluations.ts
import { http, HttpResponse } from 'msw'

async function gen() {
  return import('../generate')
}

function makeReEvaluateResponse(fromDate: string | undefined) {
  return {
    affected_evaluations: 3,
    slo_version_used: 2,
    results: [
      {
        id: crypto.randomUUID(),
        evaluation_name: 'nightly-run',
        slo_name: 'my-slo',
        slo_version: 2,
        period_start: fromDate ?? '2026-03-10T00:00:00Z',
        period_end: '2026-03-10T00:30:00Z',
        old_result: 'fail',
        new_result: 'pass',
        old_score: 45.0,
        new_score: 92.0,
      },
      {
        id: crypto.randomUUID(),
        evaluation_name: 'nightly-run',
        slo_name: 'my-slo',
        slo_version: 2,
        period_start: '2026-03-11T00:00:00Z',
        period_end: '2026-03-11T00:30:00Z',
        old_result: 'fail',
        new_result: 'pass',
        old_score: 52.0,
        new_score: 88.0,
      },
      {
        id: crypto.randomUUID(),
        evaluation_name: 'nightly-run',
        slo_name: 'my-slo',
        slo_version: 2,
        period_start: '2026-03-12T00:00:00Z',
        period_end: '2026-03-12T00:30:00Z',
        old_result: 'warning',
        new_result: 'pass',
        old_score: 71.0,
        new_score: 95.0,
      },
    ],
  }
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

  http.get('/api/evaluations/heatmap', async ({ request }) => {
    const url = new URL(request.url)
    const assetName = url.searchParams.get('asset_name') ?? ''
    const { getMetricHeatmap } = await gen()
    return HttpResponse.json(getMetricHeatmap(assetName))
  }),

  http.get('/api/evaluations/heatmap/by-metric', async ({ request }) => {
    const url = new URL(request.url)
    const assetName = url.searchParams.get('asset_name') ?? ''
    const { getGroupedMetricHeatmap } = await gen()
    return HttpResponse.json(getGroupedMetricHeatmap(assetName))
  }),

  http.get('/api/evaluation/:id', async ({ params }) => {
    const { getEvaluationDetail } = await gen()
    return HttpResponse.json(getEvaluationDetail(params.id as string))
  }),

  http.get('/api/assets/:assetName/slos/:sloName/trend', async ({ params, request }) => {
    const url = new URL(request.url)
    const metric = url.searchParams.get('metric') ?? ''
    const { getTrend } = await gen()
    // Use asset+slo+metric as composite key; fall back to metric only
    return HttpResponse.json(getTrend(params.assetName as string, metric))
  }),

  http.post('/api/evaluations', async ({ request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json(
      { id: crypto.randomUUID(), status: 'triggered', ...body },
      { status: 202 }
    )
  }),

  http.post('/api/evaluations/re-evaluate/from-date', async ({ request }) => {
    const body = await request.json() as { from_date?: string }
    return HttpResponse.json(makeReEvaluateResponse(body.from_date))
  }),

  http.post('/api/evaluations/re-evaluate/from-baseline', async () => {
    return HttpResponse.json(makeReEvaluateResponse(undefined))
  }),

  http.post('/api/evaluations/re-evaluate/from-evaluation/:evaluationId', async () => {
    return HttpResponse.json(makeReEvaluateResponse(undefined))
  }),

  http.post('/api/evaluation/:id/annotations', async ({ params, request }) => {
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

  http.post('/api/evaluation-run/:runId/annotations', async ({ params, request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json(
      {
        id: crypto.randomUUID(),
        evaluation_run_id: params.runId,
        created_at: new Date().toISOString(),
        ...body,
      },
      { status: 201 }
    )
  }),

  http.post('/api/evaluation/:id/annotations/:annId/hide', async ({ params, request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({
      id: params.annId,
      content: '',
      author: null,
      category: null,
      meta: {},
      hidden_at: new Date().toISOString(),
      hidden_by: (body.author as string) ?? null,
      hidden_reason: (body.reason as string) ?? null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    })
  }),

  http.patch('/api/evaluation/:id/invalidate', async ({ params, request }) => {
    const body = await request.json() as { invalidation_note?: string }
    const { getEvaluationDetail } = await gen()
    const detail = getEvaluationDetail(params.id as string)
    return HttpResponse.json({
      ...detail,
      invalidated: true,
      invalidation_note: body.invalidation_note ?? null,
    })
  }),

  http.patch('/api/evaluation/:id/override-status', async ({ params, request }) => {
    const body = await request.json() as { new_result: string; reason: string; author: string }
    const { getEvaluationDetail } = await gen()
    const detail = getEvaluationDetail(params.id as string)
    return HttpResponse.json({
      ...detail,
      result: body.new_result,
      result_override: { original_result: detail.result, new_result: body.new_result, reason: body.reason, author: body.author },
    })
  }),

  http.patch('/api/evaluation/:id/pin-baseline', async ({ params, request }) => {
    const body = await request.json() as { reason: string; author: string }
    const { getEvaluationDetail } = await gen()
    const detail = getEvaluationDetail(params.id as string)
    return HttpResponse.json({
      ...detail,
      baseline_pinned: true,
      baseline_pin: { reason: body.reason, author: body.author },
    })
  }),

  http.patch('/api/evaluation/:id/restore', async ({ params }) => {
    const { getEvaluationDetail } = await gen()
    const detail = getEvaluationDetail(params.id as string)
    return HttpResponse.json({ ...detail, invalidated: false, invalidation_note: null })
  }),
]
