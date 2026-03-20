import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TestWrapper } from '@/test-wrapper'
import { AllAssetsPanel } from './AllAssetsPanel'

vi.mock('@/features/assets/hooks', () => ({
  useAssets: vi.fn(() => ({
    data: [
      {
        id: '1',
        name: 'checkout-api',
        display_name: 'Checkout API',
        type_name: 'service',
        labels: { team: 'payments', env: 'production', region: 'eu-west-1', tier: 'critical' },
      },
      {
        id: '2',
        name: 'orders-db',
        display_name: 'Orders PostgreSQL',
        type_name: 'database',
        labels: { team: 'payments', env: 'production' },
      },
    ],
    isLoading: false,
  })),
  useAssetTypes: vi.fn(() => ({
    data: [
      { name: 'service', is_default: true, asset_count: 1 },
      { name: 'database', is_default: false, asset_count: 1 },
    ],
    isLoading: false,
  })),
  useDeleteAsset: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
}))

describe('AllAssetsPanel', () => {
  it('renders asset names and display names', () => {
    render(<AllAssetsPanel />, { wrapper: TestWrapper })
    expect(screen.getByText('Checkout API')).toBeInTheDocument()
    expect(screen.getByText('Orders PostgreSQL')).toBeInTheDocument()
  })

  it('renders asset type badges', () => {
    render(<AllAssetsPanel />, { wrapper: TestWrapper })
    expect(screen.getByText('service')).toBeInTheDocument()
    expect(screen.getByText('database')).toBeInTheDocument()
  })

  it('renders label chips with overflow', () => {
    render(<AllAssetsPanel />, { wrapper: TestWrapper })
    // checkout-api has 4 labels, default maxVisible=3 → should show +1 more
    expect(screen.getByText('+1 more')).toBeInTheDocument()
  })
})
