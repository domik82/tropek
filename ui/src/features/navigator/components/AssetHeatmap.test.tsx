import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AssetHeatmap } from './AssetHeatmap'
import type { MetricHeatmapResponse } from '../types'

const EVAL_ID_1 = 'aaaaaaaa-0000-0000-0000-000000000001'
const SLO_EVAL_ID_1 = 'bbbbbbbb-0000-0000-0000-000000000001'

const RESP: MetricHeatmapResponse = {
  asset_name: 'test-asset',
  columns: [
    { evaluation_id: EVAL_ID_1, period_start: '2026-01-15T00:00:00Z', period_end: '2026-01-15T23:59:59Z', eval_name: 'daily' },
  ],
  groups: [
    {
      slo_name: 'nginx',
      metrics: [{ name: 'error_rate', display_name: 'Error Rate' }],
      cells: [{ evaluation_id: EVAL_ID_1, slo_evaluation_id: SLO_EVAL_ID_1, period_start: '2026-01-15T00:00:00Z', metric: 'error_rate', display_name: 'Error Rate', result: 'pass', score: 100 }],
      summary: [{ evaluation_id: EVAL_ID_1, period_start: '2026-01-15T00:00:00Z', result: 'pass', score: 100 }],
    },
  ],
  composite: [{ evaluation_id: EVAL_ID_1, period_start: '2026-01-15T00:00:00Z', result: 'pass', score: 100 }],
}

let queryClient: QueryClient
beforeEach(() => {
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
})
afterEach(() => {
  queryClient.cancelQueries()
  queryClient.clear()
  cleanup()
})

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
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
})
