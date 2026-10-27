import { describe, it, expect, vi, beforeAll, beforeEach, afterEach, afterAll } from 'vitest'
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
  refetchSpy.mockResolvedValue({ matched: 30, refetched: 23, runIds: ['r1'], dryRun: true })
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

interface RefetchFormOptions {
  evaluationName?: string
  defaultRefetchDate?: string
  scope?: SloScopeResult
}

function renderRefetchForm(
  onComplete = vi.fn(),
  { evaluationName = 'daily', defaultRefetchDate = '2026-10-15T00:00', scope = makeScope() }: RefetchFormOptions = {},
) {
  render(
    <QueryClientProvider client={queryClient}>
      <ReEvaluateForm
        scope={scope}
        columnEvalId='col-1'
        assetName='checkout-api'
        evaluationName={evaluationName}
        defaultFromDate='2026-10-01T00:00'
        defaultRefetchDate={defaultRefetchDate}
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

  it('hides refetch mode when the panel does not filter to one evaluation', () => {
    render(
      <QueryClientProvider client={queryClient}>
        <ReEvaluateForm
          scope={makeScope()}
          columnEvalId='col-1'
          assetName='checkout-api'
          defaultRefetchDate='2026-10-15T00:00'
          onComplete={vi.fn()}
        />
      </QueryClientProvider>,
    )
    expect(screen.queryByLabelText(/refetch from source/i)).toBeNull()
    expect(screen.getByLabelText(/re-score from stored data/i)).toBeInTheDocument()
  })

  it('falls back to re-score when the evaluation filter goes away while in refetch mode', async () => {
    const user = userEvent.setup()
    const makeForm = (evaluationName?: string) => (
      <QueryClientProvider client={queryClient}>
        <ReEvaluateForm
          scope={makeScope()}
          columnEvalId='col-1'
          assetName='checkout-api'
          evaluationName={evaluationName}
          defaultRefetchDate='2026-10-15T00:00'
          onComplete={vi.fn()}
        />
      </QueryClientProvider>
    )
    const { rerender } = render(makeForm('daily'))
    await user.click(screen.getByLabelText(/refetch from source/i))
    expect(screen.queryByLabelText(/run from last baseline/i)).toBeNull()
    rerender(makeForm(undefined))
    expect(screen.getByLabelText(/run from last baseline/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/re-score from stored data/i)).toBeChecked()
    expect(screen.queryByLabelText(/i understand/i)).toBeNull()
  })

  it('sends onlyFailed when the checkbox is ticked', async () => {
    const user = userEvent.setup()
    const onComplete = renderRefetchForm()
    await user.click(screen.getByLabelText(/refetch from source/i))
    await user.click(screen.getByLabelText(/only slo evaluations that failed/i))
    await waitFor(() => expect(refetchSpy.mock.calls.at(-1)?.[0].onlyFailed).toBe(true), PREVIEW_TIMEOUT)
    await user.click(screen.getByLabelText(/i understand/i))
    await waitFor(() => expect(screen.getByRole('button', { name: /run/i })).toBeEnabled(), PREVIEW_TIMEOUT)
    await user.click(screen.getByRole('button', { name: /run/i }))
    await waitFor(() => expect(onComplete).toHaveBeenCalled())
    expect(refetchSpy.mock.calls.at(-1)?.[0]).toMatchObject({ onlyFailed: true, dryRun: false })
  })

  it('keeps Run disabled while the preview is stale', async () => {
    const user = userEvent.setup()
    renderRefetchForm()
    await user.click(screen.getByLabelText(/refetch from source/i))
    await screen.findByText(/will refetch 23 of 30/i, undefined, PREVIEW_TIMEOUT)
    fireEvent.change(screen.getByLabelText(/end date/i), { target: { value: '2026-10-17T00:00' } })
    // Confirm the new period before the debounced preview for it has run: the old preview must not unlock Run.
    await user.click(screen.getByLabelText(/i understand/i))
    expect(screen.getByLabelText(/i understand/i)).toBeChecked()
    expect(screen.getByRole('button', { name: /run/i })).toBeDisabled()
    await waitFor(() => expect(screen.getByRole('button', { name: /run/i })).toBeEnabled(), PREVIEW_TIMEOUT)
  })

  it('prompts for dates when the input is incomplete', async () => {
    const user = userEvent.setup()
    renderRefetchForm(vi.fn(), { defaultRefetchDate: '' })
    await user.click(screen.getByLabelText(/refetch from source/i))
    expect(screen.getByText('Pick a start and end date')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /run/i })).toBeDisabled()
  })

  it('says nothing to refetch, not checking, when the scope is empty', async () => {
    const user = userEvent.setup()
    renderRefetchForm(vi.fn(), { scope: { ...makeScope(), selected: new Set() } })
    await user.click(screen.getByLabelText(/refetch from source/i))
    expect(screen.getByText('Nothing to refetch')).toBeInTheDocument()
    expect(screen.queryByText(/checking/i)).toBeNull()
    expect(screen.getByRole('button', { name: /run/i })).toBeDisabled()
  })

  it('accepts a seconds-precision default', async () => {
    const user = userEvent.setup()
    const onComplete = renderRefetchForm(vi.fn(), { defaultRefetchDate: '2026-10-15T00:00:30' })
    await user.click(screen.getByLabelText(/refetch from source/i))
    await screen.findByText(/will refetch 23 of 30/i, undefined, PREVIEW_TIMEOUT)
    await user.click(screen.getByLabelText(/i understand/i))
    await user.click(screen.getByRole('button', { name: /run/i }))
    await waitFor(() => expect(onComplete).toHaveBeenCalled())
    expect(refetchSpy.mock.calls.at(-1)?.[0].from).toBe('2026-10-15T00:00:30.000Z')
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
    refetchSpy.mockResolvedValue({ matched: 4, refetched: 0, runIds: [], dryRun: true })
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

describe('ReEvaluateForm (refetch dates are UTC)', () => {
  beforeAll(() => {
    vi.stubEnv('TZ', 'America/New_York')
  })
  afterAll(() => {
    vi.unstubAllEnvs()
  })

  it('sends the typed dates as UTC whatever the machine time zone is', async () => {
    const user = userEvent.setup()
    const onComplete = renderRefetchForm()
    await user.click(screen.getByLabelText(/refetch from source/i))
    await screen.findByText(/will refetch 23 of 30/i, undefined, PREVIEW_TIMEOUT)
    await user.click(screen.getByLabelText(/i understand/i))
    await user.click(screen.getByRole('button', { name: /run/i }))
    await waitFor(() => expect(onComplete).toHaveBeenCalled())
    expect(refetchSpy.mock.calls.at(-1)?.[0].from).toMatch(/T00:00:00\.000Z$/)
  })
})
