import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '@/lib/theme-context'
import { AssetHeatmap } from './AssetHeatmap'
import type { GroupedMetricHeatmapResponseDto } from '../mappers'
import type { MiniHeatmapView } from '../domain'

const renderedViews: MiniHeatmapView[] = []

vi.mock('./SloMiniHeatmap', () => ({
  SloMiniHeatmap: (props: { view: MiniHeatmapView }) => {
    renderedViews.push(props.view)
    return <div data-testid="slo-mini-heatmap" />
  },
}))

vi.mock('@/components/charts/HeatmapChart', () => ({
  HeatmapChart: () => <div data-testid="heatmap-chart" />,
  HEATMAP_GRID_LEFT: 210,
  HEATMAP_GRID_RIGHT: 20,
}))

const EVAL_ID_1 = 'aaaaaaaa-0000-0000-0000-000000000001'
const SLO_EVAL_ID_1 = 'bbbbbbbb-0000-0000-0000-000000000001'

function makeSloGroup(sloName: string, evalId: string, sloEvalId: string) {
  return {
    slo_name: sloName,
    slo_display_name: null,
    metrics: [{ name: 'metric_a', display_name: `${sloName} metric` }],
    cells: [{ evaluation_id: evalId, slo_evaluation_id: sloEvalId, period_start: '2026-01-15T00:00:00Z', metric: 'metric_a', display_name: `${sloName} metric`, result: 'pass', score: 100, key_sli: false, weight: 1 }],
    summary: [{ evaluation_id: evalId, period_start: '2026-01-15T00:00:00Z', result: 'pass', score: 100, invalidated: false }],
  }
}

const RESP: GroupedMetricHeatmapResponseDto = {
  asset_name: 'test-asset',
  columns: [
    { evaluation_id: EVAL_ID_1, period_start: '2026-01-15T00:00:00Z', period_end: '2026-01-15T23:59:59Z', eval_name: 'daily', has_notes: false },
  ],
  groups: [
    makeSloGroup('nginx', EVAL_ID_1, SLO_EVAL_ID_1),
  ],
  composite: [{ evaluation_id: EVAL_ID_1, period_start: '2026-01-15T00:00:00Z', result: 'pass', score: 100, invalidated: false }],
}

let queryClient: QueryClient
beforeEach(() => {
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  renderedViews.length = 0
})
afterEach(() => {
  queryClient.cancelQueries()
  queryClient.clear()
  cleanup()
})

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ThemeProvider>
  )
}

describe('AssetHeatmap', () => {
  it('renders without crashing', () => {
    render(
      <Wrapper>
        <AssetHeatmap
          data={RESP}
          expandState={new Map([['nginx', false]])}
          onSloToggle={vi.fn()}
        />
      </Wrapper>
    )
    expect(document.body).toBeTruthy()
  })

  it('renders SLO groups in alphabetical order regardless of input order', () => {
    const data: GroupedMetricHeatmapResponseDto = {
      ...RESP,
      groups: [
        makeSloGroup('zulu', EVAL_ID_1, 'slo-z'),
        makeSloGroup('alpha', EVAL_ID_1, 'slo-a'),
        makeSloGroup('mike', EVAL_ID_1, 'slo-m'),
      ],
    }

    render(
      <Wrapper>
        <AssetHeatmap
          data={data}
          expandState={new Map()}
          onSloToggle={vi.fn()}
        />
      </Wrapper>
    )

    // First rendered view is Overall Score, then SLO groups in alphabetical order
    const sloGroupRows = renderedViews.slice(1).map(view => view.rows[0])
    expect(sloGroupRows).toEqual(['alpha', 'mike', 'zulu'])
  })
})
