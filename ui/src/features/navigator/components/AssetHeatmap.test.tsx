import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AssetHeatmap } from './AssetHeatmap'
import type { MetricHeatmapResponse } from '../types'

// Mock theme context
vi.mock('@/lib/theme-context', () => ({
  useTheme: () => ({ theme: 'dark' }),
}))

// Mock the chart component to inspect what data AssetHeatmap passes to it
vi.mock('@/components/charts/HeatmapChart', () => ({
  HeatmapChart: (props: any) => (
    <div data-testid="heatmap-chart">{JSON.stringify(props.cells)}</div>
  ),
}))

vi.mock('@/components/charts/NoteIndicatorRow', () => ({
  NoteIndicatorRow: () => null,
}))

const EVAL_ID_1 = 'aaaaaaaa-0000-0000-0000-000000000001'
const SLO_EVAL_ID_1 = 'bbbbbbbb-0000-0000-0000-000000000001'

const baseMockData: MetricHeatmapResponse = {
  asset_name: 'test-asset',
  columns: [
    { evaluation_id: EVAL_ID_1, period_start: '2026-03-15T10:00:00Z', period_end: '2026-03-15T10:59:59Z', eval_name: 'load-test' },
  ],
  groups: [
    {
      slo_name: 'cpu-slo',
      metrics: [{ name: 'cpu_usage', display_name: 'CPU Usage' }],
      cells: [
        {
          evaluation_id: EVAL_ID_1,
          slo_evaluation_id: SLO_EVAL_ID_1,
          period_start: '2026-03-15T10:00:00Z',
          metric: 'cpu_usage',
          display_name: 'CPU Usage',
          result: 'pass',
          score: 100,
        },
      ],
      summary: [
        { evaluation_id: EVAL_ID_1, period_start: '2026-03-15T10:00:00Z', result: 'pass', score: 100 },
      ],
    },
  ],
  composite: [
    { evaluation_id: EVAL_ID_1, period_start: '2026-03-15T10:00:00Z', result: 'pass', score: 100 },
  ],
}

describe('AssetHeatmap', () => {
  it('renders heatmap chart with provided data', () => {
    render(<AssetHeatmap data={baseMockData} />)
    expect(screen.getByTestId('heatmap-chart')).toBeInTheDocument()
  })

  it('passes invalidated result through to chart', () => {
    const data: MetricHeatmapResponse = {
      ...baseMockData,
      composite: [{ ...baseMockData.composite[0], result: 'invalidated' }],
    }
    render(<AssetHeatmap data={data} />)
    const chart = screen.getByTestId('heatmap-chart')
    expect(chart.textContent).toContain('invalidated')
  })

  it('handles empty cells array', () => {
    const data: MetricHeatmapResponse = {
      ...baseMockData,
      columns: [],
      groups: [],
      composite: [],
    }
    render(<AssetHeatmap data={data} />)
    expect(screen.getByTestId('heatmap-chart')).toBeInTheDocument()
  })
})
