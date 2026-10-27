import type { ReactNode } from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { EvaluationDetailPage } from './EvaluationDetailPage'
import type { EvaluationDetail } from '@/features/evaluations'

vi.mock('@/lib/theme-context', () => ({
  useTheme: () => ({ theme: 'current' as const, fontSize: 14 }),
}))

const mockUseEvaluationDetail = vi.fn()

vi.mock('@/features/evaluations/hooks', async () => {
  const actual = await vi.importActual<typeof import('@/features/evaluations/hooks')>('@/features/evaluations/hooks')
  return {
    ...actual,
    useEvaluationDetail: (...args: unknown[]) => mockUseEvaluationDetail(...args),
  }
})

vi.mock('@/features/evaluations/components/EvaluationSummaryCard', () => ({
  EvaluationSummaryCard: ({ evaluation, actions }: { evaluation: EvaluationDetail; actions: ReactNode }) => (
    <div data-testid="summary-card">
      {evaluation.evaluationName}
      {actions}
    </div>
  ),
}))

vi.mock('@/features/evaluations/components/EvaluationIndicatorSection', () => ({
  EvaluationIndicatorSection: () => <div data-testid="indicator-section">indicators</div>,
}))

vi.mock('@/features/evaluations/components/EvaluationNotesSection', () => ({
  EvaluationNotesSection: vi.fn().mockImplementation(() => (
    <div data-testid="notes-section">notes</div>
  )),
  useNotesActions: () => ({
    notesSectionRef: { current: null },
    handleAddNote: vi.fn(),
  }),
}))

vi.mock('@/features/evaluations/components/EvaluationActions', () => ({
  EvaluationActionsButton: ({ onSelectAction }: { onSelectAction: (action: 're-evaluate') => void }) => (
    <>
      <button data-testid="actions-btn">Actions</button>
      <button onClick={() => onSelectAction('re-evaluate')}>Run Evaluations</button>
    </>
  ),
}))

vi.mock('@/features/evaluations/components/ActionPopover', () => ({
  ActionPopover: ({ open, children }: { open: boolean; children: ReactNode }) =>
    open ? <div data-testid="action-popover">{children}</div> : null,
}))

vi.mock('@/features/evaluations/components/actions/OverrideForm', () => ({
  OverrideForm: () => <div data-testid="override-form">override</div>,
}))
vi.mock('@/features/evaluations/components/actions/InvalidateForm', () => ({
  InvalidateForm: () => <div data-testid="invalidate-form">invalidate</div>,
}))
vi.mock('@/features/evaluations/components/actions/RestoreForm', () => ({
  RestoreForm: () => <div data-testid="restore-form">restore</div>,
}))
vi.mock('@/features/evaluations/components/actions/BaselineForm', () => ({
  BaselineForm: () => <div data-testid="baseline-form">baseline</div>,
}))
vi.mock('@/features/evaluations/api', async () => {
  const actual = await vi.importActual<typeof import('@/features/evaluations/api')>('@/features/evaluations/api')
  return {
    ...actual,
    refetch: vi.fn().mockResolvedValue({ matched: 1, refetched: 1, runIds: ['run-1'], dryRun: true }),
  }
})

vi.mock('@/features/assets/hooks', () => ({
  useAssets: () => ({ data: [] }),
}))

vi.mock('@/features/slos/hooks', () => ({
  useSlos: () => ({ data: [] }),
}))

function makeEval(overrides: Partial<EvaluationDetail> = {}): EvaluationDetail {
  return {
    id: 'eval-1',
    evaluationId: 'run-1',
    evaluationName: 'nightly-perf',
    status: 'completed',
    outcome: 'pass',
    score: 95,
    period: { from: '2026-03-15T10:00:00Z', to: '2026-03-15T10:30:00Z' },
    sloName: 'latency-slo',
    sloVersion: 2,
    sliName: null,
    sliVersion: null,
    dataSourceName: null,
    ingestionMode: 'push',
    adapterUsed: null,
    invalidated: false,
    originalOutcome: null,
    originalScore: null,
    overrideReason: null,
    overrideAuthor: null,
    invalidationNote: null,
    assetSnapshot: { assetId: null, name: 'api-gateway', displayName: null, tags: {}, primaryVersion: null, buildRef: null },
    variables: {},
    comparedEvaluationIds: [],
    annotations: [],
    indicators: [],
    totalScorePassThreshold: 90,
    totalScoreWarningThreshold: 75,
    createdAt: new Date('2026-03-15T10:30:00Z'),
    topFailures: [],
    baselinePin: null,
    latestAnnotation: null,
    annotationCount: 0,
    sliMetadata: {},
    ...overrides,
  }
}

function renderPage(evalId = 'eval-1', search = '') {
  return render(
    <MemoryRouter initialEntries={[`/evaluations/${evalId}${search}`]}>
      <Routes>
        <Route path="/evaluations/:id" element={<EvaluationDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('EvaluationDetailPage', () => {
  it('renders loading state while fetching', () => {
    mockUseEvaluationDetail.mockReturnValue({ data: undefined, isLoading: true })
    renderPage()
    expect(screen.getByText(/Loading/)).toBeInTheDocument()
  })

  it('renders 404 when evaluation not found', () => {
    mockUseEvaluationDetail.mockReturnValue({ data: undefined, isLoading: false })
    renderPage()
    expect(screen.getByText(/not found/i)).toBeInTheDocument()
  })

  it('renders all sections for a valid evaluation', () => {
    mockUseEvaluationDetail.mockReturnValue({ data: makeEval(), isLoading: false })
    renderPage()
    expect(screen.getByTestId('summary-card')).toBeInTheDocument()
    expect(screen.getByTestId('indicator-section')).toBeInTheDocument()
    expect(screen.getByTestId('notes-section')).toBeInTheDocument()
  })

  it('renders breadcrumb navigation with back link', () => {
    mockUseEvaluationDetail.mockReturnValue({ data: makeEval(), isLoading: false })
    renderPage()
    expect(screen.getByText(/Navigator/)).toBeInTheDocument()
    // Eval name appears in both breadcrumb and summary card
    expect(screen.getAllByText('nightly-perf').length).toBeGreaterThanOrEqual(2)
  })

  it('includes group name in breadcrumb when group_name param present', () => {
    mockUseEvaluationDetail.mockReturnValue({ data: makeEval(), isLoading: false })
    renderPage('eval-1', '?group_name=production')
    expect(screen.getByText(/production/)).toBeInTheDocument()
  })

  it('includes asset name in breadcrumb when asset_name param present', () => {
    mockUseEvaluationDetail.mockReturnValue({ data: makeEval(), isLoading: false })
    renderPage('eval-1', '?asset_name=api-gateway')
    expect(screen.getByText(/api-gateway/)).toBeInTheDocument()
  })

  it('renders evaluation name in summary card', () => {
    mockUseEvaluationDetail.mockReturnValue({ data: makeEval(), isLoading: false })
    renderPage()
    expect(screen.getByTestId('summary-card')).toHaveTextContent('nightly-perf')
  })

  it('opens refetch mode on the evaluation day for the evaluation name', async () => {
    const user = userEvent.setup()
    const evaluation = makeEval()
    mockUseEvaluationDetail.mockReturnValue({ data: evaluation, isLoading: false })
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/evaluations/eval-1']}>
          <Routes>
            <Route path="/evaluations/:id" element={<EvaluationDetailPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    await user.click(screen.getByRole('button', { name: 'Run Evaluations' }))
    await user.click(screen.getByLabelText(/refetch from source/i))
    expect(screen.getByLabelText(/start date/i)).toHaveValue(evaluation.period.from.slice(0, 16))
    queryClient.clear()
  })
})
