/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { TestWrapper } from '@/test-wrapper'
import { AssetPanel } from './AssetPanel'
import type { EvaluationSummary } from '@/features/evaluations/types'

// ── Hook mocks ─────────────────────────────────────────────────────────────────

const mockUseAssetEvaluations = vi.fn()
const mockUseMetricHeatmap = vi.fn()
const mockUseColumnAnnotations = vi.fn()

vi.mock('../hooks', () => ({
  useAssetEvaluations: (...args: unknown[]) => mockUseAssetEvaluations(...args),
  useMetricHeatmap: (...args: unknown[]) => mockUseMetricHeatmap(...args),
  useEvaluationNames: () => ({ data: [] }),
}))

vi.mock('@/features/evaluations/hooks', () => ({
  useColumnAnnotations: (...args: unknown[]) => mockUseColumnAnnotations(...args),
}))

vi.mock('@/features/evaluations/hooks/useTabState', () => ({
  useTabState: () => ({
    availableGroups: [],
    counts: {},
    activeTab: 'all',
    setActiveTab: vi.fn(),
    tabIndicators: [],
  }),
}))

// ── Component mocks ────────────────────────────────────────────────────────────

vi.mock('@/features/evaluations/components/EvaluationHeader', () => ({
  EvaluationHeader: (props: any) => (
    <div data-testid="eval-header" data-title={props.title}>
      {props.title}
      {props.score != null && <span data-testid="header-score">{props.score}</span>}
    </div>
  ),
}))

vi.mock('@/features/evaluations/components/AnnotationForm', () => ({
  AnnotationSection: () => null,
}))

vi.mock('@/features/evaluations/components/EvaluationActions', () => ({
  EvaluationActionsButton: () => null,
  EvaluationActionForm: () => null,
  NoteIconButton: () => null,
}))

vi.mock('./AssetPanelHeatmapView', () => ({
  AssetPanelHeatmapView: (props: any) => (
    <div data-testid="heatmap-view">
      <span data-testid="heatmap-asset">{props.assetName}</span>
      <span data-testid="heatmap-eval-id">{props.effectiveEvalId ?? 'none'}</span>
    </div>
  ),
}))

vi.mock('./AssetPanelChartView', () => ({
  AssetPanelChartView: () => <div data-testid="chart-view" />,
}))

vi.mock('@/features/assets/hooks', () => ({
  useAssets: () => ({ data: [] }),
}))

vi.mock('@/features/slos/hooks', () => ({
  useSlos: () => ({ data: [] }),
}))

// ── Fixtures ───────────────────────────────────────────────────────────────────

function makeSummary(overrides: Partial<EvaluationSummary> = {}): EvaluationSummary {
  return {
    id: 'eval-1',
    evaluation_id: 'run-1',
    evaluation_name: 'nightly',
    status: 'completed',
    result: 'pass',
    score: 95,
    period_start: '2026-03-15T10:00:00Z',
    period_end: '2026-03-15T10:30:00Z',
    slo_name: 'latency-slo',
    slo_version: 1,
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
    asset_snapshot: { name: 'catalog-db', tags: {} },
    variables: {},
    created_at: '2026-03-15T10:30:00Z',
    ...overrides,
  }
}

function renderPanel(assetName: string, initialEvalId?: string) {
  return render(
    <MemoryRouter>
      <TestWrapper>
        <AssetPanel assetName={assetName} initialEvalId={initialEvalId} />
      </TestWrapper>
    </MemoryRouter>,
  )
}

// ── Setup ──────────────────────────────────────────────────────────────────────

beforeEach(() => {
  mockUseAssetEvaluations.mockReset()
  mockUseMetricHeatmap.mockReset()
  mockUseColumnAnnotations.mockReset()

  mockUseMetricHeatmap.mockReturnValue({ data: undefined, isLoading: false })
  mockUseColumnAnnotations.mockReturnValue({ data: [] })
})

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('AssetPanel', () => {
  it('renders header with asset name', () => {
    mockUseAssetEvaluations.mockReturnValue({ data: [], isLoading: false })
    renderPanel('catalog-db')

    expect(screen.getByTestId('eval-header')).toHaveAttribute('data-title', 'catalog-db')
  })

  it('fetches evaluations for the given asset', () => {
    mockUseAssetEvaluations.mockReturnValue({ data: [], isLoading: false })
    renderPanel('catalog-db')

    expect(mockUseAssetEvaluations).toHaveBeenCalledWith('catalog-db', undefined)
  })

  it('selects latest non-invalidated eval as default', () => {
    const evals = [
      makeSummary({ id: 'old', period_start: '2026-03-14T10:00:00Z' }),
      makeSummary({ id: 'newest-invalidated', period_start: '2026-03-16T10:00:00Z', invalidated: true }),
      makeSummary({ id: 'newest-valid', period_start: '2026-03-15T10:00:00Z' }),
    ]
    mockUseAssetEvaluations.mockReturnValue({ data: evals, isLoading: false })

    renderPanel('catalog-db')

    // The heatmap view should receive the newest non-invalidated eval
    expect(screen.getByTestId('heatmap-eval-id')).toHaveTextContent('newest-valid')
  })

  it('resets selectedEvalId when assetName prop changes', () => {
    // Asset A: user had selected eval-A
    const evalsA = [makeSummary({ id: 'eval-A', asset_snapshot: { name: 'api-gateway', tags: {} } })]
    mockUseAssetEvaluations.mockReturnValue({ data: evalsA, isLoading: false })

    const { rerender } = renderPanel('api-gateway', 'eval-A')

    // Verify eval-A is active
    expect(screen.getByTestId('heatmap-eval-id')).toHaveTextContent('eval-A')

    // Switch to asset B
    const evalsB = [makeSummary({ id: 'eval-B', asset_snapshot: { name: 'catalog-db', tags: {} } })]
    mockUseAssetEvaluations.mockReturnValue({ data: evalsB, isLoading: false })

    rerender(
      <MemoryRouter>
        <TestWrapper>
          <AssetPanel assetName="catalog-db" />
        </TestWrapper>
      </MemoryRouter>,
    )

    // The effective eval ID should now be eval-B (the default for catalog-db)
    expect(screen.getByTestId('heatmap-eval-id')).toHaveTextContent('eval-B')
  })

  it('shows loading state while evaluations and heatmap load', () => {
    mockUseAssetEvaluations.mockReturnValue({ data: [], isLoading: true })
    mockUseMetricHeatmap.mockReturnValue({ data: undefined, isLoading: true })

    renderPanel('catalog-db')

    expect(screen.getByText(/Loading/)).toBeInTheDocument()
    expect(screen.queryByTestId('heatmap-view')).not.toBeInTheDocument()
  })

  it('passes correct asset name to heatmap view', () => {
    const evals = [makeSummary()]
    mockUseAssetEvaluations.mockReturnValue({ data: evals, isLoading: false })

    renderPanel('catalog-db')

    expect(screen.getByTestId('heatmap-asset')).toHaveTextContent('catalog-db')
  })
})
