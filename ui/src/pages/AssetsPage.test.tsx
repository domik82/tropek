/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TestWrapper } from '@/test-wrapper'
import { AssetsPage } from './AssetsPage'

let capturedTreeProps: any = {}
vi.mock('@/components/AssetTree', () => ({
  AssetTree: (props: any) => {
    capturedTreeProps = props
    return <div data-testid="asset-tree" data-mode={props.mode} />
  },
}))
vi.mock('@/features/assets/components/GroupDetailPanel', () => ({
  GroupDetailPanel: (props: any) => <div data-testid="group-detail">{props.groupName}</div>,
}))
vi.mock('@/features/assets/components/AllAssetsPanel', () => ({
  AllAssetsPanel: () => <div data-testid="all-assets">All Assets</div>,
}))
vi.mock('@/features/assets/components/AssetCreateDialog', () => ({
  AssetCreateDialog: () => null,
}))

let mockParams = new URLSearchParams()
const mockSetParams = vi.fn(
  (next: ((prev: URLSearchParams) => URLSearchParams) | Record<string, string> | URLSearchParams) => {
    if (typeof next === 'function') mockParams = next(mockParams)
    else mockParams = next instanceof URLSearchParams ? next : new URLSearchParams(next)
  },
)
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useSearchParams: () => [mockParams, mockSetParams] }
})

beforeEach(() => {
  mockParams = new URLSearchParams()
  mockSetParams.mockClear()
  capturedTreeProps = {}
})

describe('AssetsPage', () => {
  it('renders asset tree and all-assets panel when no group selected', () => {
    render(
      <TestWrapper>
        <AssetsPage />
      </TestWrapper>,
    )
    expect(screen.getByTestId('asset-tree')).toBeInTheDocument()
    expect(screen.getByTestId('all-assets')).toBeInTheDocument()
  })

  it('shows group detail panel when group param is set', () => {
    mockParams = new URLSearchParams({ group: 'payments' })
    render(
      <TestWrapper>
        <AssetsPage />
      </TestWrapper>,
    )
    expect(screen.getByTestId('group-detail')).toBeInTheDocument()
    expect(screen.getByText('payments')).toBeInTheDocument()
    expect(screen.queryByTestId('all-assets')).not.toBeInTheDocument()
  })

  it('shows all-assets panel when group is __ungrouped__', () => {
    mockParams = new URLSearchParams({ group: '__ungrouped__' })
    render(
      <TestWrapper>
        <AssetsPage />
      </TestWrapper>,
    )
    expect(screen.getByTestId('all-assets')).toBeInTheDocument()
    expect(screen.queryByTestId('group-detail')).not.toBeInTheDocument()
  })

  // --- Bug fix: clicking leaf asset must select parent group, not show AllAssetsPanel ---

  it('shows group detail panel (not all-assets) when asset is selected with a group', () => {
    // When a leaf asset is clicked, both group and asset should be in the URL
    mockParams = new URLSearchParams({ group: 'data-tier', asset: 'orders-db' })
    render(
      <TestWrapper>
        <AssetsPage />
      </TestWrapper>,
    )
    expect(screen.getByTestId('group-detail')).toBeInTheDocument()
    expect(screen.getByText('data-tier')).toBeInTheDocument()
    expect(screen.queryByTestId('all-assets')).not.toBeInTheDocument()
  })

  it('onSelectAsset sets both group and asset params (not asset alone)', () => {
    // The onSelectAsset callback receives (assetName, groupName) from the tree.
    // It should call setParams with BOTH group and asset.
    render(
      <TestWrapper>
        <AssetsPage />
      </TestWrapper>,
    )

    // Simulate clicking a leaf asset — the tree passes (name, groupName)
    capturedTreeProps.onSelectAsset('orders-db', 'data-tier')

    expect(mockParams.get('group')).toBe('data-tier')
    expect(mockParams.get('asset')).toBe('orders-db')
  })

  it('preserves an existing from param when selecting an asset', () => {
    mockParams = new URLSearchParams({ from: 'now-7d' })
    render(
      <TestWrapper>
        <AssetsPage />
      </TestWrapper>,
    )

    capturedTreeProps.onSelectAsset('orders-db', 'data-tier')

    expect(mockParams.get('from')).toBe('now-7d')
    expect(mockParams.get('asset')).toBe('orders-db')
    expect(mockParams.get('group')).toBe('data-tier')
  })

  it('keeps from/to as the last two params after selecting an asset', () => {
    mockParams = new URLSearchParams('from=now-7d&to=20260101')
    render(
      <TestWrapper>
        <AssetsPage />
      </TestWrapper>,
    )
    capturedTreeProps.onSelectAsset('orders-db', 'data-tier')
    const keys = [...mockParams.keys()]
    expect(keys.slice(-2)).toEqual(['from', 'to'])
  })
})
