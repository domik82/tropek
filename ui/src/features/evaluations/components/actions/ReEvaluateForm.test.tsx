import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReEvaluateForm } from './ReEvaluateForm'
import type { SloScopeResult } from './slo-scope/types'

const reEvalSpy = vi.fn()
const refetchSpy = vi.fn()
vi.mock('../../api', async () => {
  const actual = await vi.importActual<typeof import('../../api')>('../../api')
  return {
    ...actual,
    reEvaluate: (...args: unknown[]) => reEvalSpy(...args),
    refetch: (...args: unknown[]) => refetchSpy(...args),
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
  refetchSpy.mockReset()
  refetchSpy.mockResolvedValue({ matched: 30, refetched: 23, skipped: [], runIds: ['r1'], dryRun: true })
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

const PREVIEW_TIMEOUT = { timeout: 3000 }

function renderRefetchForm(onComplete = vi.fn(), evaluationName: string | null = 'daily') {
  render(
    <QueryClientProvider client={queryClient}>
      <ReEvaluateForm
        scope={makeScope()}
        columnEvalId='col-1'
        assetName='checkout-api'
        evaluationName={evaluationName}
        defaultFromDate='2026-10-01T00:00'
        defaultRefetchDate='2026-10-15T00:00'
        onComplete={onComplete}
      />
    </QueryClientProvider>,
  )
  return onComplete
}

describe('ReEvaluateForm (refetch mode)', () => {
  it('hides the baseline option, shows the warning and disables Run until confirmed', async () => {
    const user = userEvent.setup()
    renderRefetchForm()
    await user.click(screen.getByLabelText(/refetch from source/i))
    expect(screen.queryByLabelText(/run from last baseline/i)).toBeNull()
    expect(screen.getByText(/deleted and fetched again/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /run/i })).toBeDisabled()
    await screen.findByText(/will refetch 23 of 30/i, undefined, PREVIEW_TIMEOUT)
    await user.click(screen.getByLabelText(/i understand/i))
    expect(screen.getByRole('button', { name: /run/i })).toBeEnabled()
  })

  it('previews from a dry run and sends dryRun=false on Run', async () => {
    const user = userEvent.setup()
    const onComplete = renderRefetchForm()
    await user.click(screen.getByLabelText(/refetch from source/i))
    await screen.findByText(/will refetch 23 of 30/i, undefined, PREVIEW_TIMEOUT)
    expect(refetchSpy.mock.calls.at(-1)?.[0].dryRun).toBe(true)
    await user.click(screen.getByLabelText(/i understand/i))
    await user.click(screen.getByRole('button', { name: /run/i }))
    await waitFor(() => expect(onComplete).toHaveBeenCalled())
    const payload = refetchSpy.mock.calls.at(-1)?.[0]
    expect(payload.dryRun).toBe(false)
    expect(payload.sloNames).toEqual(['latency-slo'])
    expect(payload.assetName).toBe('checkout-api')
    // Refetch defaults to the one selected day, not the re-score start date.
    expect(payload.from).toBe('2026-10-15T00:00:00.000Z')
    expect(payload.to).toBe('2026-10-15T00:00:00.000Z')
    expect(payload.evaluationName).toBe('daily')
  })

  it('sends no evaluation name when the panel does not filter to exactly one', async () => {
    const user = userEvent.setup()
    renderRefetchForm(vi.fn(), null)
    await user.click(screen.getByLabelText(/refetch from source/i))
    await screen.findByText(/will refetch 23 of 30/i, undefined, PREVIEW_TIMEOUT)
    expect(refetchSpy.mock.calls.at(-1)?.[0].evaluationName).toBeNull()
  })

  it('keeps the re-score start date when refetch mode opens on the selected day', async () => {
    const user = userEvent.setup()
    renderRefetchForm()
    await user.click(screen.getByLabelText(/refetch from source/i))
    expect(screen.getByLabelText(/start date \(utc\)/i)).toHaveValue('2026-10-15T00:00')
    expect(screen.getByLabelText(/end date/i)).toHaveValue('2026-10-15T00:00')
    await user.click(screen.getByLabelText(/re-score from stored data/i))
    expect(screen.getByDisplayValue('2026-10-01T00:00')).toBeInTheDocument()
  })

  it('shows Nothing to refetch and keeps Run disabled when the preview is empty', async () => {
    refetchSpy.mockResolvedValue({ matched: 4, refetched: 0, skipped: [], runIds: [], dryRun: true })
    const user = userEvent.setup()
    renderRefetchForm()
    await user.click(screen.getByLabelText(/refetch from source/i))
    await screen.findByText(/nothing to refetch/i, undefined, PREVIEW_TIMEOUT)
    await user.click(screen.getByLabelText(/i understand/i))
    expect(screen.getByRole('button', { name: /run/i })).toBeDisabled()
  })

  it('revokes the confirmation when the end date changes', async () => {
    const user = userEvent.setup()
    renderRefetchForm()
    await user.click(screen.getByLabelText(/refetch from source/i))
    await screen.findByText(/will refetch 23 of 30/i, undefined, PREVIEW_TIMEOUT)
    await user.click(screen.getByLabelText(/i understand/i))
    expect(screen.getByRole('button', { name: /run/i })).toBeEnabled()
    fireEvent.change(screen.getByLabelText(/end date/i), { target: { value: '2026-10-17T00:00' } })
    expect(screen.getByLabelText(/i understand/i)).not.toBeChecked()
    expect(screen.getByRole('button', { name: /run/i })).toBeDisabled()
  })

  it('switching back to re-score restores the original content', async () => {
    const user = userEvent.setup()
    renderRefetchForm()
    await user.click(screen.getByLabelText(/refetch from source/i))
    await user.click(screen.getByLabelText(/re-score from stored data/i))
    expect(screen.getByLabelText(/run from last baseline/i)).toBeInTheDocument()
    expect(screen.queryByText(/deleted and fetched again/i)).toBeNull()
    expect(screen.queryByLabelText(/i understand/i)).toBeNull()
  })
})
