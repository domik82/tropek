// src/mocks/handlers/index.ts
import { http, HttpResponse } from 'msw'
import { evaluationHandlers } from './evaluations'
import { assetHandlers } from './assets'
import { sloHandlers } from './slos'
import { sliHandlers } from './slis'

export const handlers = [
  http.get('/api/config/ui', () =>
    HttpResponse.json({ maxEvaluations: 1000, pageSize: 200 }),
  ),
  ...evaluationHandlers,
  ...assetHandlers,
  ...sloHandlers,
  ...sliHandlers,
]
