import type { BulkActionOutcome } from '../../domain'

export interface BatchTarget {
  sloName: string
  sloEvaluationId: string
}

export interface BatchRowResult {
  sloName: string
  sloEvaluationId: string
  status: 'success' | 'failed'
  error?: string
}

// Run one bulk action over `targets` and map the outcome back to per-row
// results for the result table. On a thrown request error every row is marked
// failed; ids the backend did not apply (reported outside `succeeded`, e.g. a
// precondition such as "not completed") are marked failed with a short note.
export async function runBatch(
  targets: BatchTarget[],
  call: (ids: string[]) => Promise<BulkActionOutcome>,
): Promise<BatchRowResult[]> {
  const ids = targets.map((target) => target.sloEvaluationId)
  try {
    const outcome = await call(ids)
    const succeeded = new Set(outcome.succeeded)
    return targets.map((target) => ({
      sloName: target.sloName,
      sloEvaluationId: target.sloEvaluationId,
      status: succeeded.has(target.sloEvaluationId) ? 'success' : 'failed',
      error: succeeded.has(target.sloEvaluationId) ? undefined : 'not applied',
    }))
  } catch (err) {
    const message = err instanceof Error ? err.message : 'unknown error'
    return targets.map((target) => ({
      sloName: target.sloName,
      sloEvaluationId: target.sloEvaluationId,
      status: 'failed' as const,
      error: message,
    }))
  }
}
