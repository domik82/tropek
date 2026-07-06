import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { OverrideForm } from './OverrideForm'
import type { SloScopeResult } from './slo-scope/types'

const overrideStatusSpy = vi.fn()

vi.mock('../../api', async () => {
  const actual = await vi.importActual<typeof import('../../api')>('../../api')
  return {
    ...actual,
    overrideStatusMany: (...args: unknown[]) => overrideStatusSpy(...args),
  }
})

function makeScope(overrides: Partial<SloScopeResult> = {}): SloScopeResult {
  return {
    availableSlos: [
      { sloName: 'a', displayName: 'A', sloEvaluationId: 'eid-a', currentResult: 'fail' },
      { sloName: 'b', displayName: 'B', sloEvaluationId: 'eid-b', currentResult: 'pass' },
      { sloName: 'c', displayName: 'C', sloEvaluationId: 'eid-c', currentResult: 'warning' },
    ],
    selected: new Set(['a', 'b', 'c']),
    setSelected: vi.fn(),
    reset: vi.fn(),
    lookupEvalId: (sloName: string) =>
      ({ a: 'eid-a', b: 'eid-b', c: 'eid-c' })[sloName],
    ...overrides,
  }
}

let queryClient: QueryClient
beforeEach(() => {
  overrideStatusSpy.mockReset()
  overrideStatusSpy.mockResolvedValue({ succeeded: ['eid-a', 'eid-b', 'eid-c'], notFound: [], updated: 3 })
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
})
afterEach(() => {
  queryClient.cancelQueries()
  queryClient.clear()
  cleanup()
})

function renderForm(scope: SloScopeResult, onComplete = vi.fn()) {
  return render(
    <QueryClientProvider client={queryClient}>
      <OverrideForm scope={scope} columnEvalId='col-1' onComplete={onComplete} />
    </QueryClientProvider>,
  )
}

describe('OverrideForm (multi-SLO)', () => {
  it('one batch call carries only the SLOs that need a change', async () => {
    const user = userEvent.setup()
    renderForm(makeScope())
    await user.click(screen.getByRole('radio', { name: /^fail$/i }))
    await user.type(screen.getByPlaceholderText(/reason/i), 'noise')
    await user.type(screen.getByPlaceholderText(/author/i), 'domik')
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    // SLO 'a' is already fail (skipped client-side). 'b'=pass and 'c'=warning are batched.
    await waitFor(() => expect(overrideStatusSpy).toHaveBeenCalledTimes(1))
    const idsCalled = overrideStatusSpy.mock.calls[0][0]
    expect(idsCalled).toEqual(expect.arrayContaining(['eid-b', 'eid-c']))
    expect(idsCalled).not.toContain('eid-a')
  })

  it('skipped SLOs are reported in the result list', async () => {
    const user = userEvent.setup()
    renderForm(makeScope())
    await user.click(screen.getByRole('radio', { name: /^pass$/i }))
    await user.type(screen.getByPlaceholderText(/reason/i), 'manual')
    await user.type(screen.getByPlaceholderText(/author/i), 'domik')
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(screen.getByText(/1 skipped/i)).toBeInTheDocument())
  })

  it('fires no request when every selected SLO is already at the target', async () => {
    const user = userEvent.setup()
    // 'b' is already 'pass'; selecting only it and targeting 'pass' leaves nothing to apply.
    renderForm(makeScope({ selected: new Set(['b']) }))
    await user.click(screen.getByRole('radio', { name: /^pass$/i }))
    await user.type(screen.getByPlaceholderText(/reason/i), 'noop')
    await user.type(screen.getByPlaceholderText(/author/i), 'domik')
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(screen.getByText(/1 skipped/i)).toBeInTheDocument())
    expect(overrideStatusSpy).not.toHaveBeenCalled()
  })

  it('partial failure (id in not_found) surfaces the Retry failed button', async () => {
    // target=fail applies to 'b' and 'c'; 'b' comes back in not_found.
    overrideStatusSpy.mockResolvedValue({ succeeded: ['eid-c'], notFound: ['eid-b'], updated: 1 })
    const user = userEvent.setup()
    renderForm(makeScope())
    await user.click(screen.getByRole('radio', { name: /^fail$/i }))
    await user.type(screen.getByPlaceholderText(/reason/i), 'noise')
    await user.type(screen.getByPlaceholderText(/author/i), 'domik')
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /retry failed/i })).toBeInTheDocument(),
    )
    expect(screen.getByText(/1 failed/i)).toBeInTheDocument()
  })
})
