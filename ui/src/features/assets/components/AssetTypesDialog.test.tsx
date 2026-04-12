import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TestWrapper } from '@/test-wrapper'
import { AssetTypesDialog } from './AssetTypesDialog'

// Mock the hooks to avoid real API calls
vi.mock('@/features/assets/hooks', () => ({
  useAssetTypes: vi.fn(() => ({
    data: [
      { id: 't1', name: 'service', isDefault: true, assetCount: 5 },
      { id: 't2', name: 'database', isDefault: false, assetCount: 2 },
      { id: 't3', name: 'vm', isDefault: false, assetCount: 0 },
    ],
    isLoading: false,
  })),
  useCreateAssetType: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useRenameAssetType: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useSetDefaultAssetType: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  useDeleteAssetType: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
}))

describe('AssetTypesDialog', () => {
  it('renders all asset types', () => {
    render(<AssetTypesDialog open onOpenChange={() => {}} />, { wrapper: TestWrapper })
    expect(screen.getByText('service')).toBeInTheDocument()
    expect(screen.getByText('database')).toBeInTheDocument()
    expect(screen.getByText('vm')).toBeInTheDocument()
  })

  it('shows default badge on the default type', () => {
    render(<AssetTypesDialog open onOpenChange={() => {}} />, { wrapper: TestWrapper })
    expect(screen.getByText('default')).toBeInTheDocument()
  })

  it('shows asset count for each type', () => {
    render(<AssetTypesDialog open onOpenChange={() => {}} />, { wrapper: TestWrapper })
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('0')).toBeInTheDocument()
  })
})
