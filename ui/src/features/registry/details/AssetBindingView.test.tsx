// ui/src/features/registry/details/AssetBindingView.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AssetBindingView } from './AssetBindingView'

vi.mock('@/features/slos/hooks', () => ({
  useGroupSloLinks: vi.fn(),
  useDeleteGroupSloLink: vi.fn(() => ({ mutate: vi.fn() })),
  useSloDetail: vi.fn(),
}))

vi.mock('@/features/assets/hooks', () => ({
  useAsset: vi.fn(),
}))

import { useGroupSloLinks, useSloDetail } from '@/features/slos/hooks'
import { useAsset } from '@/features/assets/hooks'

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
    { sli: 'response_time_p99', display_name: 'P99 Latency', pass_criteria: ['<600'], warning_criteria: ['<800'], weight: 2, key_sli: false, sort_order: 0 },
    { sli: 'error_rate', display_name: 'Error Rate', pass_criteria: ['<1%'], warning_criteria: ['<2%'], weight: 3, key_sli: true, sort_order: 1 },
  ],
  total_score_pass_pct: 90,
  total_score_warning_pct: 75,
  comparison: {},
}

const MOCK_LINKS = [
  {
    id: '1',
    link_name: 'checkout-api-http',
    group_id: 'g1',
    slo_name: 'http-availability-slo',
    sli_name: 'http-service-sli',
    data_source_name: 'prometheus-local',
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
    vi.mocked(useGroupSloLinks).mockReturnValue({ data: MOCK_LINKS, isLoading: false } as any)
    vi.mocked(useSloDetail).mockReturnValue({ data: MOCK_SLO, isLoading: false } as any)
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

  it('renders binding count in section header', () => {
    render(
      <AssetBindingView assetName="checkout-api" groupName="core-services"
        onNavigate={vi.fn()} onLinkSlo={vi.fn()} />,
      { wrapper },
    )
    expect(screen.getByText(/SLO Bindings \(1\)/)).toBeInTheDocument()
  })

  it('renders binding chain breadcrumb', () => {
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

  it('renders empty state with Link SLO button', () => {
    vi.mocked(useGroupSloLinks).mockReturnValue({ data: [], isLoading: false } as any)
    render(
      <AssetBindingView assetName="checkout-api" groupName="core-services"
        onNavigate={vi.fn()} onLinkSlo={vi.fn()} />,
      { wrapper },
    )
    expect(screen.getByText(/No SLO bindings/)).toBeInTheDocument()
  })
})
