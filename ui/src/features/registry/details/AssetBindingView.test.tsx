// ui/src/features/registry/details/AssetBindingView.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AssetBindingView } from './AssetBindingView'

vi.mock('@/features/slos/hooks', () => ({
  useAssetSloAssignments: vi.fn(),
  useAssetSloGroupAssignments: vi.fn(),
  useGroupSloAssignments: vi.fn(),
  useDeleteGroupSloAssignment: vi.fn(() => ({ mutate: vi.fn() })),
  useSloDetail: vi.fn(),
}))

vi.mock('@/features/assets/hooks', () => ({
  useAsset: vi.fn(),
}))

vi.mock('@/features/slis/hooks', () => ({
  useSliDetail: vi.fn(),
}))

import { useAssetSloAssignments, useAssetSloGroupAssignments, useGroupSloAssignments, useSloDetail } from '@/features/slos/hooks'
import { useAsset } from '@/features/assets/hooks'
import { useSliDetail } from '@/features/slis/hooks'

const MOCK_ASSET = {
  id: '1',
  name: 'checkout-api',
  display_name: 'Checkout API',
  type_name: 'service',
  tags: { env: 'production', team: 'payments', tier: 'critical' },
  variables: { job: 'checkout-api', namespace: 'ecommerce' },
  created_at: '2026-03-15T00:00:00Z',
  updated_at: '2026-03-15T00:00:00Z',
}

const MOCK_SLO = {
  id: 's1',
  name: 'http-availability-slo',
  version: 1,
  comparable_from_version: 1,
  display_name: 'HTTP Availability SLO',
  author: 'bootstrap',
  notes: null,
  tags: {},
  variables: { aggregation_window: '5m' },
  created_at: '2026-03-15T00:00:00Z',
  active: true,
  objectives: [
    { sli: 'response_time_p99', display_name: 'P99 Latency', pass_threshold: ['<600'], warning_threshold: ['<800'], weight: 2, key_sli: false, sort_order: 0 },
    { sli: 'error_rate', display_name: 'Error Rate', pass_threshold: ['<1%'], warning_threshold: ['<2%'], weight: 3, key_sli: true, sort_order: 1 },
  ],
  total_score_pass_threshold: 90,
  total_score_warning_threshold: 75,
  comparison: {},
  sli_name: 'http-service-sli',
  sli_version: 1,
}

const MOCK_ASSIGNMENTS = [
  {
    id: '1',
    asset_id: null,
    asset_group_id: 'g1',
    slo_definition_id: 's1',
    slo_name: 'http-availability-slo',
    slo_version: 1,
    data_source_id: 'ds1',
    data_source_name: 'prometheus-local',
    comparison_rules: null,
    created_at: '2026-03-15T00:00:00Z',
  },
]

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('AssetBindingView', () => {
  beforeEach(() => {
    vi.mocked(useAsset).mockReturnValue({ data: MOCK_ASSET, isLoading: false } as any)
    vi.mocked(useAssetSloAssignments).mockReturnValue({ data: MOCK_ASSIGNMENTS, isLoading: false } as any)
    vi.mocked(useAssetSloGroupAssignments).mockReturnValue({ data: [], isLoading: false } as any)
    vi.mocked(useGroupSloAssignments).mockReturnValue({ data: [], isLoading: false } as any)
    vi.mocked(useSloDetail).mockReturnValue({ data: MOCK_SLO, isLoading: false } as any)
    vi.mocked(useSliDetail).mockReturnValue({ data: {
      id: 'sli1', name: 'http-service-sli', display_name: null, adapter_type: 'prometheus',
      version: 1, comparable_from_version: 1, mode: 'raw' as const, query_template: null,
      interval: null, methods: null, notes: null, author: null, tags: {}, active: true,
      created_at: '2026-03-15T00:00:00Z',
      indicators: {
        response_time_p99: 'histogram_quantile(0.99, rate(http_duration_bucket{job="$job"}[5m]))',
        error_rate: 'sum(rate(http_requests_total{status=~"5..",job="$job"}[5m]))',
      },
    }, isLoading: false } as any)
  })

  it('renders asset name and type', () => {
    render(
      <AssetBindingView assetName="checkout-api" groupName="core-services"
        onNavigate={vi.fn()} onLinkSlo={vi.fn()} />,
      { wrapper },
    )
    expect(screen.getByText('Checkout API')).toBeInTheDocument()
    expect(screen.getByText(/service · /)).toBeInTheDocument()
  })

  it('renders asset tags as chips', () => {
    render(
      <AssetBindingView assetName="checkout-api" groupName="core-services"
        onNavigate={vi.fn()} onLinkSlo={vi.fn()} />,
      { wrapper },
    )
    expect(screen.getByText(/env: production/)).toBeInTheDocument()
    expect(screen.getByText(/team: payments/)).toBeInTheDocument()
  })

  it('renders asset variables', () => {
    render(
      <AssetBindingView assetName="checkout-api" groupName="core-services"
        onNavigate={vi.fn()} onLinkSlo={vi.fn()} />,
      { wrapper },
    )
    expect(screen.getAllByText('$job').length).toBeGreaterThan(0)
    expect(screen.getAllByText('$namespace').length).toBeGreaterThan(0)
  })

  it('renders assignment count in section header', () => {
    render(
      <AssetBindingView assetName="checkout-api" groupName="core-services"
        onNavigate={vi.fn()} onLinkSlo={vi.fn()} />,
      { wrapper },
    )
    expect(screen.getByText(/SLO Assignments \(1\)/)).toBeInTheDocument()
  })

  it('renders assignment chain breadcrumb', () => {
    render(
      <AssetBindingView assetName="checkout-api" groupName="core-services"
        onNavigate={vi.fn()} onLinkSlo={vi.fn()} />,
      { wrapper },
    )
    expect(screen.getByText('http-availability-slo')).toBeInTheDocument()
    expect(screen.getByText('http-service-sli')).toBeInTheDocument()
    expect(screen.getByText('prometheus-local')).toBeInTheDocument()
  })

  it('renders objectives table with pass/warn criteria', () => {
    render(
      <AssetBindingView assetName="checkout-api" groupName="core-services"
        onNavigate={vi.fn()} onLinkSlo={vi.fn()} />,
      { wrapper },
    )
    expect(screen.getByText('response_time_p99')).toBeInTheDocument()
    expect(screen.getByText('<600')).toBeInTheDocument()
    expect(screen.getByText('<800')).toBeInTheDocument()
    expect(screen.getByText('error_rate')).toBeInTheDocument()
  })

  it('renders empty state with Assign SLO button', () => {
    vi.mocked(useAssetSloAssignments).mockReturnValue({ data: [], isLoading: false } as any)
    vi.mocked(useGroupSloAssignments).mockReturnValue({ data: [], isLoading: false } as any)
    render(
      <AssetBindingView assetName="checkout-api" groupName="core-services"
        onNavigate={vi.fn()} onLinkSlo={vi.fn()} />,
      { wrapper },
    )
    expect(screen.getByText(/No SLO assignments/)).toBeInTheDocument()
  })
})
