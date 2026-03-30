import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { EvaluationDetailPage } from './EvaluationDetailPage'
import type { EvaluationDetail } from '@/features/evaluations/types'

vi.mock('@/lib/theme-context', () => ({
  useTheme: () => ({ theme: 'current' as const, fontSize: 14 }),
}))

const mockUseEvaluationDetail = vi.fn()

vi.mock('@/features/evaluations/hooks', () => ({
  useEvaluationDetail: (...args: unknown[]) => mockUseEvaluationDetail(...args),
}))

vi.mock('@/features/evaluations/components/EvaluationSummaryCard', () => ({
  EvaluationSummaryCard: ({ evaluation }: { evaluation: EvaluationDetail }) => (
    <div data-testid="summary-card">{evaluation.evaluation_name}</div>
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
  EvaluationActionForm: () => <div data-testid="action-form">form</div>,
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
    evaluation_name: 'nightly-perf',
    status: 'completed',
    result: 'pass',
    score: 95,
    period_start: '2026-03-15T10:00:00Z',
    period_end: '2026-03-15T10:30:00Z',
    slo_name: 'latency-slo',
    slo_version: 2,
    sli_name: null,
    sli_version: null,
    data_source_name: null,
    ingestion_mode: 'push',
    adapter_used: null,
    invalidated: false,
    original_result: null,
    original_score: null,
    override_reason: null,
    override_author: null,
    invalidation_note: null,
    asset_snapshot: { name: 'api-gateway', tags: {} },
    evaluation_metadata: {},
    compared_evaluation_ids: [],
    annotations: [],
    indicator_results: [],
    total_score_pass_threshold: 90,
    total_score_warning_threshold: 75,
    created_at: '2026-03-15T10:30:00Z',
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
