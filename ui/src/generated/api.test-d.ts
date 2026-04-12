// Compile-time assertion that generated types actually exist and look right.
// If this file fails to compile, codegen is broken.
//
// Path strings use the same base path as the FastAPI routers — no /api prefix.
// The /api prefix is added by the Vite dev proxy and by the deployed web
// server; the generated types reflect the raw FastAPI route table.
import type { paths, components } from './api'

type _AssertEvaluationsPath = paths['/evaluations']['get']
type _AssertEvaluationDetailPath = paths['/evaluations/{eval_id}']['get']
type _AssertAssetsPath = paths['/assets']['get']

type _AssertComponentsSchemas = components['schemas']

export type __Check =
  | _AssertEvaluationsPath
  | _AssertEvaluationDetailPath
  | _AssertAssetsPath
  | _AssertComponentsSchemas
