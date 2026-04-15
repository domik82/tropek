import type { ReactNode } from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { EvaluationDetailPage } from './EvaluationDetailPage'
import type { EvaluationDetail } from '@/features/evaluations'

vi.mock('@/lib/theme-context', () => ({
  useTheme: () => ({ theme: 'current' as const, fontSize: 14 }),
}))

const mockUseEvaluationDetail = vi.fn()

vi.mock('@/features/evaluations/hooks', () => ({
  useEvaluationDetail: (...args: unknown[]) => mockUseEvaluationDetail(...args),
}))

vi.mock('@/features/evaluations/components/EvaluationSummaryCard', () => ({
  EvaluationSummaryCard: ({ evaluation }: { evaluation: EvaluationDetail }) => (
    <div data-testid="summary-card">{evaluation.evaluationName}</div>
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
  EvaluationActionsButton: () => <button data-testid="actions-btn">Actions</button>,
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
vi.mock('@/features/evaluations/components/actions/ReEvaluateForm', () => ({
  ReEvaluateForm: () => <div data-testid="reevaluate-form">reeval</div>,
}))

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
    assetSnapshot: { name: 'api-gateway', displayName: null, tags: {}, primaryVersion: null, buildRef: null },
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
})
