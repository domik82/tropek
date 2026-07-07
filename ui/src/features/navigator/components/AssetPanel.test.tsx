/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { TestWrapper } from '@/test-wrapper'
import { AssetPanel } from './AssetPanel'
import type { Evaluation } from '@/features/evaluations'
import type { TimeSlotSelection } from './AssetHeatmap'

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
      {props.toolbar}
      {props.actions}
    </div>
  ),
}))

// The header toolbar renders a real TimeRangePicker; stub it so these tests don't
// need the TimeRangeProvider (the real ChartViewControls is exercised, not this).
vi.mock('@/components/TimeRangePicker', () => ({
  TimeRangePicker: () => <div data-testid="time-range-picker" />,
}))

vi.mock('@/features/evaluations/components/AnnotationForm', () => ({
  AnnotationSection: () => null,
}))

vi.mock('@/features/evaluations/components/EvaluationActions', () => ({
  EvaluationActionsButton: (props: any) => (
    <button
      data-testid="actions-button"
      data-all-invalidated={String(props.allRowsInvalidated)}
      data-no-invalidated={String(props.noRowsInvalidated)}
      onClick={() => props.onSelectAction('override')}
    >
      Actions
    </button>
  ),
  NoteIconButton: () => null,
}))

vi.mock('@/features/evaluations/components/ActionPopover', () => ({
  ActionPopover: ({ open, children }: { open: boolean; children: React.ReactNode }) =>
    open ? <div data-testid="action-popover">{children}</div> : null,
}))

vi.mock('@/features/evaluations/components/actions/OverrideForm', () => ({
  OverrideForm: ({ scope }: any) => (
    <div data-testid="override-form">
      <span data-testid="scope-selected-count">{scope.selected.size}</span>
      <span data-testid="scope-selected-names">{[...scope.selected].sort().join(',')}</span>
    </div>
  ),
}))
vi.mock('@/features/evaluations/components/actions/InvalidateForm', () => ({
  InvalidateForm: () => <div data-testid="invalidate-form" />,
}))
vi.mock('@/features/evaluations/components/actions/RestoreForm', () => ({
  RestoreForm: () => <div data-testid="restore-form" />,
}))
vi.mock('@/features/evaluations/components/actions/BaselineForm', () => ({
  BaselineForm: () => <div data-testid="baseline-form" />,
}))
vi.mock('@/features/evaluations/components/actions/ReEvaluateForm', () => ({
  ReEvaluateForm: () => <div data-testid="reevaluate-form" />,
}))

// Capture the onSlotSelect callback so tests can drive cell vs column clicks.
let lastOnSlotSelect: ((slot: TimeSlotSelection) => void) | undefined
vi.mock('./AssetPanelHeatmapView', () => ({
  AssetPanelHeatmapView: (props: any) => {
    lastOnSlotSelect = props.onSlotSelect
    return (
      <div data-testid="heatmap-view">
        <span data-testid="heatmap-asset">{props.assetName}</span>
        <span data-testid="heatmap-eval-id">{props.effectiveEvalId ?? 'none'}</span>
      </div>
    )
  },
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

function makeSummary(overrides: Partial<Evaluation> = {}): Evaluation {
  return {
    id: 'eval-1',
    evaluationId: 'run-1',
    evaluationName: 'nightly',
    status: 'completed',
    outcome: 'pass',
    score: 95,
    period: { from: '2026-03-15T10:00:00Z', to: '2026-03-15T10:30:00Z' },
    sloName: 'latency-slo',
    sloVersion: 1,
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
    assetSnapshot: { assetId: null, name: 'catalog-db', displayName: null, tags: {}, primaryVersion: null, buildRef: null },
    variables: {},
    baselinePin: null,
    latestAnnotation: null,
    annotationCount: 0,
    createdAt: new Date('2026-03-15T10:30:00Z'),
    topFailures: [],
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

// Build a minimal GroupedMetricHeatmapResponse DTO with two SLOs and one
// column. Useful for exercising scope-initialization behaviour.
function makeHeatmapDto() {
  return {
    asset_name: 'catalog-db',
    columns: [
      {
        evaluation_id: 'col-1',
        period_start: '2026-03-15T10:00:00Z',
        period_end: '2026-03-15T10:30:00Z',
        eval_name: 'nightly',
        has_notes: false,
      },
    ],
    groups: [
      {
        slo_name: 'latency-slo',
        slo_display_name: 'Latency SLO',
        metrics: [{ name: 'latency-p95', display_name: 'Latency p95' }],
        cells: [
          {
            evaluation_id: 'col-1',
            slo_evaluation_id: 'sloeval-latency',
            period_start: '2026-03-15T10:00:00Z',
            metric: 'latency-p95',
            display_name: 'Latency p95',
            result: 'pass',
            score: 100,
            value: 150,
            compared_value: null,
            change_relative_pct: null,
            weight: 1,
            key_sli: false,
            pass_targets: null,
            warning_targets: null,
            tab_group: null,
            aggregation: null,
          },
        ],
        summary: [
          {
            evaluation_id: 'col-1',
            period_start: '2026-03-15T10:00:00Z',
            result: 'pass',
            score: 100,
            total_score_pass_threshold: 90,
            total_score_warning_threshold: 75,
            invalidated: false,
            sli_metadata: null,
            invalidation_note: null,
          },
        ],
      },
      {
        slo_name: 'avail-slo',
        slo_display_name: 'Availability SLO',
        metrics: [{ name: 'availability', display_name: 'Availability' }],
        cells: [
          {
            evaluation_id: 'col-1',
            slo_evaluation_id: 'sloeval-avail',
            period_start: '2026-03-15T10:00:00Z',
            metric: 'availability',
            display_name: 'Availability',
            result: 'pass',
            score: 100,
            value: 99.9,
            compared_value: null,
            change_relative_pct: null,
            weight: 1,
            key_sli: false,
            pass_targets: null,
            warning_targets: null,
            tab_group: null,
            aggregation: null,
          },
        ],
        summary: [
          {
            evaluation_id: 'col-1',
            period_start: '2026-03-15T10:00:00Z',
            result: 'pass',
            score: 100,
            total_score_pass_threshold: 90,
            total_score_warning_threshold: 75,
            invalidated: false,
            sli_metadata: null,
            invalidation_note: null,
          },
        ],
      },
    ],
    composite: [
      {
        evaluation_id: 'col-1',
        period_start: '2026-03-15T10:00:00Z',
        result: 'pass',
        score: 100,
        total_score_pass_threshold: 90,
        total_score_warning_threshold: 75,
        invalidated: false,
        sli_metadata: null,
        invalidation_note: null,
      },
    ],
  }
}

// ── Setup ──────────────────────────────────────────────────────────────────────

beforeEach(() => {
  mockUseAssetEvaluations.mockReset()
  mockUseMetricHeatmap.mockReset()
  mockUseColumnAnnotations.mockReset()
  lastOnSlotSelect = undefined

  mockUseMetricHeatmap.mockReturnValue({ data: undefined, isLoading: false })
  mockUseColumnAnnotations.mockReturnValue({ data: [] })
  localStorage.clear() // ChartPreferencesProvider (via TestWrapper) reads persisted prefs on mount
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
      makeSummary({ id: 'old', period: { from: '2026-03-14T10:00:00Z', to: '2026-03-14T10:30:00Z' } }),
      makeSummary({ id: 'newest-invalidated', period: { from: '2026-03-16T10:00:00Z', to: '2026-03-16T10:30:00Z' }, invalidated: true }),
      makeSummary({ id: 'newest-valid', period: { from: '2026-03-15T10:00:00Z', to: '2026-03-15T10:30:00Z' } }),
    ]
    mockUseAssetEvaluations.mockReturnValue({ data: evals, isLoading: false })

    renderPanel('catalog-db')

    // The heatmap view should receive the newest non-invalidated eval
    expect(screen.getByTestId('heatmap-eval-id')).toHaveTextContent('newest-valid')
  })

  it('resets selectedEvalId when assetName prop changes', () => {
    // Asset A: user had selected eval-A
    const evalsA = [makeSummary({ id: 'eval-A', assetSnapshot: { assetId: null, name: 'api-gateway', displayName: null, tags: {}, primaryVersion: null, buildRef: null } })]
    mockUseAssetEvaluations.mockReturnValue({ data: evalsA, isLoading: false })

    const { rerender } = renderPanel('api-gateway', 'eval-A')

    // Verify eval-A is active
    expect(screen.getByTestId('heatmap-eval-id')).toHaveTextContent('eval-A')

    // Switch to asset B
    const evalsB = [makeSummary({ id: 'eval-B', assetSnapshot: { assetId: null, name: 'catalog-db', displayName: null, tags: {}, primaryVersion: null, buildRef: null } })]
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

  describe('graphs toolbar controls', () => {
    // The panel-variant ChartViewControls lives in the header toolbar, gated on
    // `!isLoading && evals.length > 0`. It calls useChartPreferences(), so this also
    // asserts the shared ChartPreferencesProvider is wired into TestWrapper.
    const notesButtonName = 'Toggle notes on all charts'

    it('renders the graphs controls when evaluations are loaded', () => {
      mockUseAssetEvaluations.mockReturnValue({ data: [makeSummary()], isLoading: false })

      renderPanel('catalog-db')

      expect(screen.getByRole('button', { name: notesButtonName })).toBeInTheDocument()
      expect(screen.getByText('Graphs')).toBeInTheDocument()
    })

    it('hides the graphs controls while data is loading', () => {
      // Evaluations are present but the heatmap is still loading → isLoading is true.
      mockUseAssetEvaluations.mockReturnValue({ data: [makeSummary()], isLoading: false })
      mockUseMetricHeatmap.mockReturnValue({ data: undefined, isLoading: true })

      renderPanel('catalog-db')

      expect(screen.queryByRole('button', { name: notesButtonName })).not.toBeInTheDocument()
    })

    it('hides the graphs controls when there are no evaluations', () => {
      mockUseAssetEvaluations.mockReturnValue({ data: [], isLoading: false })

      renderPanel('catalog-db')

      expect(screen.queryByRole('button', { name: notesButtonName })).not.toBeInTheDocument()
    })
  })

  describe('SLO scope defaults', () => {
    function setupPanelWithHeatmap() {
      const evals = [
        makeSummary({
          id: 'sloeval-latency',
          evaluationId: 'col-1',
          sloName: 'latency-slo',
          period: { from: '2026-03-15T10:00:00Z', to: '2026-03-15T10:30:00Z' },
        }),
      ]
      mockUseAssetEvaluations.mockReturnValue({ data: evals, isLoading: false })
      mockUseMetricHeatmap.mockReturnValue({ data: makeHeatmapDto(), isLoading: false })
      renderPanel('catalog-db')
    }

    it('defaults to ALL SLOs selected after a column-level selection', () => {
      setupPanelWithHeatmap()

      // Simulate a column click (composite cell): no specificSloEvalId set.
      expect(lastOnSlotSelect).toBeDefined()
      lastOnSlotSelect!({
        periodStart: '2026-03-15T10:00:00Z',
        evalIds: ['sloeval-latency', 'sloeval-avail'],
        columnEvalId: 'col-1',
      })

      // Open the Override action popover.
      fireEvent.click(screen.getByTestId('actions-button'))

      // Scope picker should default to BOTH SLOs.
      expect(screen.getByTestId('scope-selected-count')).toHaveTextContent('2')
      expect(screen.getByTestId('scope-selected-names')).toHaveTextContent('avail-slo,latency-slo')
    })

    it('defaults to a single SLO when a per-SLO indicator cell is clicked', () => {
      setupPanelWithHeatmap()

      // Simulate a per-SLO indicator click — specificSloEvalId carries the
      // clicked cell's slo_evaluation_id.
      expect(lastOnSlotSelect).toBeDefined()
      lastOnSlotSelect!({
        periodStart: '2026-03-15T10:00:00Z',
        evalIds: ['sloeval-latency', 'sloeval-avail'],
        columnEvalId: 'col-1',
        specificSloEvalId: 'sloeval-latency',
      })

      fireEvent.click(screen.getByTestId('actions-button'))

      expect(screen.getByTestId('scope-selected-count')).toHaveTextContent('1')
      expect(screen.getByTestId('scope-selected-names')).toHaveTextContent('latency-slo')
    })

    it('re-widens to ALL when a column click follows a single-SLO cell click', () => {
      setupPanelWithHeatmap()

      // First click: a specific latency cell → single SLO default.
      expect(lastOnSlotSelect).toBeDefined()
      lastOnSlotSelect!({
        periodStart: '2026-03-15T10:00:00Z',
        evalIds: ['sloeval-latency', 'sloeval-avail'],
        columnEvalId: 'col-1',
        specificSloEvalId: 'sloeval-latency',
      })

      // Second click: the overall-score row → no specificSloEvalId.
      lastOnSlotSelect!({
        periodStart: '2026-03-15T10:00:00Z',
        evalIds: ['sloeval-latency', 'sloeval-avail'],
        columnEvalId: 'col-1',
      })

      fireEvent.click(screen.getByTestId('actions-button'))

      expect(screen.getByTestId('scope-selected-count')).toHaveTextContent('2')
    })

    it('forwards menu availability flags from the column summary rows', () => {
      setupPanelWithHeatmap()

      // Column-level click to ensure the button is mounted.
      expect(lastOnSlotSelect).toBeDefined()
      lastOnSlotSelect!({
        periodStart: '2026-03-15T10:00:00Z',
        evalIds: ['sloeval-latency', 'sloeval-avail'],
        columnEvalId: 'col-1',
      })

      const button = screen.getByTestId('actions-button')
      // All rows in fixture are non-invalidated:
      // allRowsInvalidated=false, noRowsInvalidated=true.
      expect(button).toHaveAttribute('data-all-invalidated', 'false')
      expect(button).toHaveAttribute('data-no-invalidated', 'true')
    })
  })
})
