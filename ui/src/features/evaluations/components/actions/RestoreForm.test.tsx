import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RestoreForm } from './RestoreForm'
import type { SloScopeResult } from './slo-scope/types'

const restoreSpy = vi.fn()
vi.mock('../../api', async () => {
  const actual = await vi.importActual<typeof import('../../api')>('../../api')
  return {
    ...actual,
    restoreEvaluations: (...args: unknown[]) => restoreSpy(...args),
  }
})

function makeScope(): SloScopeResult {
  return {
    availableSlos: [
      { sloName: 'a', displayName: 'A', sloEvaluationId: 'eid-a', currentResult: 'invalidated' },
      { sloName: 'b', displayName: 'B', sloEvaluationId: 'eid-b', currentResult: 'invalidated' },
    ],
    selected: new Set(['a', 'b']),
    setSelected: vi.fn(),
    reset: vi.fn(),
    lookupEvalId: (sloName: string) => ({ a: 'eid-a', b: 'eid-b' })[sloName],
  }
}

let queryClient: QueryClient
beforeEach(() => {
  restoreSpy.mockReset()
  restoreSpy.mockResolvedValue({ succeeded: ['eid-a', 'eid-b'], notFound: [], updated: 2 })
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
})
afterEach(() => {
  queryClient.cancelQueries()
  queryClient.clear()
  cleanup()
})

function renderForm(scope: SloScopeResult) {
  return render(
    <QueryClientProvider client={queryClient}>
      <RestoreForm scope={scope} columnEvalId='col-1' onComplete={vi.fn()} />
    </QueryClientProvider>,
  )
}

describe('RestoreForm (multi-SLO)', () => {
  it('issues one batch call with all selected SLO ids', async () => {
    const user = userEvent.setup()
    renderForm(makeScope())
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(restoreSpy).toHaveBeenCalledTimes(1))
    expect(restoreSpy.mock.calls[0][0]).toEqual(expect.arrayContaining(['eid-a', 'eid-b']))
  })

  it('partial failure (id in not_found) surfaces Retry failed button', async () => {
    restoreSpy.mockResolvedValue({ succeeded: ['eid-a'], notFound: ['eid-b'], updated: 1 })
    const user = userEvent.setup()
    renderForm(makeScope())
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /retry failed/i })).toBeInTheDocument())
    expect(screen.getByText(/1 failed/i)).toBeInTheDocument()
  })
})
