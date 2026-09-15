// ui/src/features/navigator/components/AssetPanelHeatmapView.test.tsx
import { describe, it, expect, vi, beforeAll, afterAll, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'
import { TimeRangeProvider } from '@/lib/time-range-context'
import { ChartPreferencesProvider } from '@/lib/chart-preferences-context'
import { ThemeProvider } from '@/lib/theme-context'
import { AssetPanelHeatmapView } from './AssetPanelHeatmapView'
import type { GroupedMetricHeatmapResponseDto } from '../mappers'

// The trend chart itself is exercised elsewhere (ECharts rendering isn't the
// concern of this test) — stub it so we can assert on the props it receives
// (trend / isLoading) without mounting a real chart.
vi.mock('@/features/evaluations/components/MetricTrendBlock', () => ({
  MetricTrendBlock: (props: { indicator: { metric: string }; trend?: unknown[]; isLoading?: boolean }) => (
    <div
      data-testid={`trend-block-${props.indicator.metric}`}
      data-loading={String(props.isLoading)}
      data-point-count={String(props.trend?.length ?? 'undefined')}
    />
  ),
}))

// Note categories / trend annotations are unrelated to the viewport-gated
// batched-trend fetch under test — mock them away rather than adding more
// MSW handlers that would only add noise to this test.
vi.mock('@/features/note-categories', () => ({
  useNoteCategories: () => ({ data: [] }),
}))

vi.mock('@/features/evaluations/hooks', async () => {
  const actual = await vi.importActual<typeof import('@/features/evaluations/hooks')>(
    '@/features/evaluations/hooks',
  )
  return {
    ...actual,
    useTrendAnnotations: () => ({ data: undefined }),
  }
})

class MockIntersectionObserver {
  static instances: MockIntersectionObserver[] = []
  callback: IntersectionObserverCallback
  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback
    MockIntersectionObserver.instances.push(this)
  }
  observe() {}
  disconnect() {}
  trigger(isIntersecting: boolean) {
    this.callback([{ isIntersecting } as IntersectionObserverEntry], this as unknown as IntersectionObserver)
  }
}

let trendsRequestCount = 0

const server = setupServer(
  http.get('/api/assets/:assetName/slos/:sloName/trends', ({ params }) => {
    trendsRequestCount += 1
    return HttpResponse.json({
      [params.sloName as string === 'latency-slo' ? 'latency-p95' : 'unknown']: [
        {
          timestamp: '2026-03-15T10:00:00Z',
          value: 150,
          score: 100,
          eval_id: 'sloeval-latency',
          result: 'pass',
          baseline: null,
          evaluation_name: 'nightly',
          targets: null,
          change_point: null,
        },
      ],
    })
  }),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterAll(() => server.close())

beforeEach(() => {
  trendsRequestCount = 0
  MockIntersectionObserver.instances = []
  vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)
})

afterEach(() => {
  server.resetHandlers()
  cleanup()
  vi.unstubAllGlobals()
})

function makeHeatmapData(): GroupedMetricHeatmapResponseDto {
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
  } as unknown as GroupedMetricHeatmapResponseDto
}

function renderHeatmapView(
  heatmapData: GroupedMetricHeatmapResponseDto = makeHeatmapData(),
  sloExpandState: Map<string, boolean> = new Map([['latency-slo', true]]),
) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <TimeRangeProvider>
          <ThemeProvider>
            <ChartPreferencesProvider>
              <AssetPanelHeatmapView
                assetName="catalog-db"
                heatmapData={heatmapData}
                selectedColumnEvalId="col-1"
                effectiveEvalId="sloeval-latency"
                selectedColumnSloEvalIds={new Set(['sloeval-latency'])}
                selectedPeriodStart="2026-03-15T10:00:00Z"
                notedSlots={new Map()}
                onEvalSelect={() => {}}
                mode="heatmap"
                setMode={() => {}}
                explorerButton={null}
                sloExpandState={sloExpandState}
                onSloToggle={() => {}}
                assetId={undefined}
                focusPeriodEnd={undefined}
                focusEvalId={undefined}
              />
            </ChartPreferencesProvider>
          </ThemeProvider>
        </TimeRangeProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('AssetPanelHeatmapView — lazy per-SLO trend fetch', () => {
  it("does not fetch a group's trends until the group scrolls into view", async () => {
    renderHeatmapView()

    // Trend block for the expanded group should be present (expanded by
    // default in this test), but its batched-trends fetch must not have
    // fired yet — the group's viewport ref has not intersected.
    const trendBlock = await screen.findByTestId('trend-block-latency-p95')
    expect(trendBlock).toBeInTheDocument()
    expect(trendsRequestCount).toBe(0)
    // No data yet: the block receives an undefined trend until the batch arrives.
    expect(trendBlock).toHaveAttribute('data-point-count', 'undefined')

    // Simulate the group's container entering the viewport.
    expect(MockIntersectionObserver.instances.length).toBeGreaterThan(0)
    await act(async () => {
      MockIntersectionObserver.instances[0].trigger(true)
    })

    // The fetch should now have fired exactly once for this (asset, slo).
    await vi.waitFor(() => expect(trendsRequestCount).toBe(1))

    // The batched response's per-metric slice must actually reach the block:
    // the 1-point series keyed 'latency-p95' flows through useSloTrends →
    // trendsByMetric[indicator.metric] into the block's `trend` prop.
    await vi.waitFor(() =>
      expect(screen.getByTestId('trend-block-latency-p95')).toHaveAttribute('data-point-count', '1'),
    )

    // Triggering intersection again (e.g. a second observer callback) must
    // not cause a second network request — useSloTrends caches with
    // staleTime: Infinity and `enabled` only flips true→true here.
    await act(async () => {
      MockIntersectionObserver.instances[0].trigger(true)
    })
    expect(trendsRequestCount).toBe(1)
  })
})

// Every SLO on an asset is evaluated under one shared `evaluation_id`, and
// indicator names are unique only within an SLO, so two SLOs on the same asset
// may declare the same one. Sample metadata must therefore stay scoped to the
// SLO it was measured for; a flat metric-name map lets the last group in the
// response overwrite every other group's counts.
function makeSharedMetricHeatmapData(): GroupedMetricHeatmapResponseDto {
  const cell = (sloEvalId: string) => ({
    evaluation_id: 'col-1',
    slo_evaluation_id: sloEvalId,
    period_start: '2026-03-15T10:00:00Z',
    metric: 'memory_bytes.mean',
    display_name: 'memory_bytes.mean',
    result: 'pass',
    score: 100,
    value: 23_990_000,
    compared_value: null,
    change_relative_pct: null,
    weight: 1,
    key_sli: false,
    pass_targets: null,
    warning_targets: null,
    tab_group: null,
    aggregation: null,
  })
  const summary = (sampleMetadata: Record<string, unknown>) => ({
    evaluation_id: 'col-1',
    period_start: '2026-03-15T10:00:00Z',
    result: 'pass',
    score: 100,
    total_score_pass_threshold: 90,
    total_score_warning_threshold: 75,
    invalidated: false,
    sli_metadata: sampleMetadata,
    invalidation_note: null,
  })
  const metadata = (actual: number, missingPct: number) => ({
    memory_bytes: {
      mode: 'aggregated',
      expected_samples: 27,
      actual_samples: actual,
      missing_pct: missingPct,
      chunks_failed: 0,
    },
  })

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
        slo_name: 'web-tier',
        slo_display_name: 'Web tier',
        metrics: [{ name: 'memory_bytes.mean', display_name: 'memory_bytes.mean' }],
        cells: [cell('sloeval-cx-dec')],
        summary: [summary(metadata(27, 0.0))],
      },
      {
        // Listed last, so a flat map keyed only by metric name ends up
        // showing this group's "no data" counts for every group above it.
        slo_name: 'worker-tier',
        slo_display_name: 'Worker tier',
        metrics: [{ name: 'memory_bytes.mean', display_name: 'memory_bytes.mean' }],
        cells: [cell('sloeval-python')],
        summary: [summary(metadata(0, 100.0))],
      },
    ],
    composite: [summary(metadata(27, 0.0))],
  } as unknown as GroupedMetricHeatmapResponseDto
}

describe('AssetPanelHeatmapView — SLI sample metadata scoping', () => {
  it('shows each SLO its own sample counts when two SLOs share an indicator name', async () => {
    const { container } = renderHeatmapView(
      makeSharedMetricHeatmapData(),
      new Map([['web-tier', true], ['worker-tier', true]]),
    )

    await screen.findAllByText('Web tier')

    expect(container.textContent).toContain('27/27 samples (0.0% missing)')
    expect(container.textContent).toContain('0/27 samples (100.0% missing)')
    // Only the group that really had no data is flagged.
    expect(screen.getAllByText('low confidence')).toHaveLength(1)
  })
})
