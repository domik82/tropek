import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AssetHeatmap } from './AssetHeatmap'
import type { MetricHeatmapResponse } from '../types'

// Mock theme context
vi.mock('@/lib/theme-context', () => ({
  useTheme: () => ({ theme: 'forest' }),
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

const baseMockData: MetricHeatmapResponse = {
  asset_name: 'test-asset',
  slots: ['2026-03-15T10:00:00Z'],
  metrics: [{ name: 'cpu_usage', display_name: 'CPU Usage' }],
  cells: [
    {
      slot: '2026-03-15T10:00:00Z',
      metric: 'cpu_usage',
      display_name: 'CPU Usage',
      result: 'pass',
      score: 1.0,
      eval_id: 'e1',
      evaluation_name: 'load-test',
    },
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
      cells: [{ ...baseMockData.cells[0], result: 'invalidated' }],
    }
    render(<AssetHeatmap data={data} />)
    const chart = screen.getByTestId('heatmap-chart')
    expect(chart.textContent).toContain('invalidated')
  })

  it('handles empty cells array', () => {
    const data: MetricHeatmapResponse = {
      ...baseMockData,
      cells: [],
      slots: [],
      metrics: [],
    }
    render(<AssetHeatmap data={data} />)
    expect(screen.getByTestId('heatmap-chart')).toBeInTheDocument()
  })
})
