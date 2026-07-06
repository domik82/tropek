import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BaselineForm } from './BaselineForm'
import type { SloScopeResult } from './slo-scope/types'

const pinSpy = vi.fn()
vi.mock('../../api', async () => {
  const actual = await vi.importActual<typeof import('../../api')>('../../api')
  return {
    ...actual,
    pinBaselineMany: (...args: unknown[]) => pinSpy(...args),
  }
})

function makeScope(count: number): SloScopeResult {
  const slos = Array.from({ length: count }, (_, i) => ({
    sloName: `slo-${i}`,
    displayName: `SLO ${i}`,
    sloEvaluationId: `eid-${i}`,
    currentResult: 'pass' as const,
  }))
  return {
    availableSlos: slos,
    selected: new Set(slos.map(slo => slo.sloName)),
    setSelected: vi.fn(),
    reset: vi.fn(),
    lookupEvalId: (sloName: string) => slos.find(slo => slo.sloName === sloName)?.sloEvaluationId,
  }
}

let queryClient: QueryClient
beforeEach(() => {
  pinSpy.mockReset()
  pinSpy.mockResolvedValue({ succeeded: ['eid-0', 'eid-1', 'eid-2'], notFound: [], updated: 3 })
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
      <BaselineForm scope={scope} columnEvalId='col-1' onComplete={vi.fn()} />
    </QueryClientProvider>,
  )
}

describe('BaselineForm (multi-SLO)', () => {
  it('issues one batch call with all selected SLO ids', async () => {
    const user = userEvent.setup()
    renderForm(makeScope(3))
    await user.type(screen.getByPlaceholderText(/reason/i), 'release')
    await user.type(screen.getByPlaceholderText(/author/i), 'domik')
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(pinSpy).toHaveBeenCalledTimes(1))
    expect(pinSpy.mock.calls[0][0]).toEqual(expect.arrayContaining(['eid-0', 'eid-1', 'eid-2']))
  })

  it('shows the inline count warning when scope > 5', () => {
    renderForm(makeScope(10))
    expect(screen.getByText(/10 baseline pins/i)).toBeInTheDocument()
  })

  it('does not show the count warning when scope <= 5', () => {
    renderForm(makeScope(5))
    expect(screen.queryByText(/baseline pins/i)).not.toBeInTheDocument()
  })

  it('an id skipped by the backend (not_found) is reported as failed', async () => {
    pinSpy.mockResolvedValue({ succeeded: ['eid-0', 'eid-2'], notFound: ['eid-1'], updated: 2 })
    const user = userEvent.setup()
    renderForm(makeScope(3))
    await user.type(screen.getByPlaceholderText(/reason/i), 'release')
    await user.type(screen.getByPlaceholderText(/author/i), 'domik')
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(screen.getByText(/1 failed/i)).toBeInTheDocument())
  })
})
