// src/mocks/handlers/index.ts
import { evaluationHandlers } from './evaluations'
import { assetHandlers } from './assets'
import { sloHandlers } from './slos'
import { sliHandlers } from './slis'

export const handlers = [
  ...evaluationHandlers,
  ...assetHandlers,
  ...sloHandlers,
  ...sliHandlers,
]
