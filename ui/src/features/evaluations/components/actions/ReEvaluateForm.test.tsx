import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReEvaluateForm } from './ReEvaluateForm'
import type { SloScopeResult } from './slo-scope/types'

const reEvalSpy = vi.fn()
vi.mock('../../api', async () => {
  const actual = await vi.importActual<typeof import('../../api')>('../../api')
  return {
    ...actual,
    reEvaluate: (...args: unknown[]) => reEvalSpy(...args),
  }
})

function makeScope(): SloScopeResult {
  return {
    availableSlos: [
      { sloName: 'latency-slo', displayName: 'Latency', sloEvaluationId: 'e1', currentResult: 'fail' },
      { sloName: 'avail-slo', displayName: 'Availability', sloEvaluationId: 'e2', currentResult: 'pass' },
    ],
    selected: new Set(['latency-slo']),
    setSelected: vi.fn(),
    reset: vi.fn(),
    lookupEvalId: (sloName: string) => ({ 'latency-slo': 'e1', 'avail-slo': 'e2' })[sloName],
  }
}

let queryClient: QueryClient
beforeEach(() => {
  reEvalSpy.mockReset()
  reEvalSpy.mockResolvedValue({ affectedEvaluations: 1, sloVersionUsed: 3, results: [] })
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
})
afterEach(() => {
  queryClient.cancelQueries()
  queryClient.clear()
  cleanup()
})

describe('ReEvaluateForm (scoped)', () => {
  it('sends sloNames list from selected scope', async () => {
    const user = userEvent.setup()
    render(
      <QueryClientProvider client={queryClient}>
        <ReEvaluateForm
          scope={makeScope()}
          columnEvalId='col-1'
          assetName='checkout-api'
          onComplete={vi.fn()}
        />
      </QueryClientProvider>,
    )
    await user.click(screen.getByLabelText(/run from last baseline/i))
    await user.click(screen.getByRole('button', { name: /run/i }))
    await waitFor(() => expect(reEvalSpy).toHaveBeenCalledOnce())
    const payload = reEvalSpy.mock.calls[0][0]
    expect(payload.sloNames).toEqual(['latency-slo'])
    expect(payload.sloName).toBeNull()
  })
})
