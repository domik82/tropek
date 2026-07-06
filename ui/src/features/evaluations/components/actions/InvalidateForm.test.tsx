import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { InvalidateForm } from './InvalidateForm'
import type { SloScopeResult } from './slo-scope/types'

const invalidateSpy = vi.fn()
vi.mock('../../api', async () => {
  const actual = await vi.importActual<typeof import('../../api')>('../../api')
  return {
    ...actual,
    invalidateEvaluations: (...args: unknown[]) => invalidateSpy(...args),
  }
})

function makeScope(): SloScopeResult {
  return {
    availableSlos: [
      { sloName: 'a', displayName: 'A', sloEvaluationId: 'eid-a', currentResult: 'pass' },
      { sloName: 'b', displayName: 'B', sloEvaluationId: 'eid-b', currentResult: 'fail' },
    ],
    selected: new Set(['a', 'b']),
    setSelected: vi.fn(),
    reset: vi.fn(),
    lookupEvalId: (sloName: string) => ({ a: 'eid-a', b: 'eid-b' })[sloName],
  }
}

let queryClient: QueryClient
beforeEach(() => {
  invalidateSpy.mockReset()
  invalidateSpy.mockResolvedValue({ succeeded: ['eid-a', 'eid-b'], notFound: [], updated: 2 })
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
      <InvalidateForm scope={scope} columnEvalId='col-1' onComplete={vi.fn()} />
    </QueryClientProvider>,
  )
}

describe('InvalidateForm (multi-SLO)', () => {
  it('issues one batch call with all selected SLO ids', async () => {
    const user = userEvent.setup()
    renderForm(makeScope())
    await user.type(screen.getByPlaceholderText(/reason/i), 'bad data')
    await user.type(screen.getByPlaceholderText(/author/i), 'domik')
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(invalidateSpy).toHaveBeenCalledTimes(1))
    expect(invalidateSpy.mock.calls[0][0]).toEqual(expect.arrayContaining(['eid-a', 'eid-b']))
  })

  it('passes reason as the note argument', async () => {
    const user = userEvent.setup()
    renderForm(makeScope())
    await user.type(screen.getByPlaceholderText(/reason/i), 'specific note text')
    await user.type(screen.getByPlaceholderText(/author/i), 'domik')
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(invalidateSpy).toHaveBeenCalled())
    expect(invalidateSpy.mock.calls[0][1]).toBe('specific note text')
  })

  it('partial failure (id in not_found) surfaces Retry failed button', async () => {
    invalidateSpy.mockResolvedValue({ succeeded: ['eid-a'], notFound: ['eid-b'], updated: 1 })
    const user = userEvent.setup()
    renderForm(makeScope())
    await user.type(screen.getByPlaceholderText(/reason/i), 'cleanup')
    await user.type(screen.getByPlaceholderText(/author/i), 'domik')
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /retry failed/i })).toBeInTheDocument(),
    )
    expect(screen.getByText(/1 failed/i)).toBeInTheDocument()
  })
})
