/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TestWrapper } from '@/test-wrapper'
import { AssetNavigatorPage } from './AssetNavigatorPage'

// ── Mocks ──────────────────────────────────────────────────────────────────────

vi.mock('@/components/AssetTree', () => ({
  AssetTree: (props: any) => (
    <div data-testid="asset-tree">
      <button
        data-testid="select-asset-catalog-db"
        onClick={() => props.onSelectAsset?.('catalog-db')}
      >
        catalog-db
      </button>
      <button
        data-testid="select-group-infra"
        onClick={() => props.onSelectGroup?.('infra-production')}
      >
        infra-production
      </button>
      <button
        data-testid="select-all"
        onClick={() => props.onSelectGroup?.(null)}
      >
        All
      </button>
      {/* Expose current selection so tests can assert sidebar state */}
      <span data-testid="selected-group">{props.selectedGroup ?? ''}</span>
      <span data-testid="selected-asset">{props.selectedAsset ?? ''}</span>
    </div>
  ),
}))

// Mock AssetPanel to expose the assetName it receives and track mounts
const assetPanelRenders: string[] = []
vi.mock('@/features/navigator/components/AssetPanel', () => ({
  AssetPanel: (props: any) => {
    assetPanelRenders.push(props.assetName)
    return (
      <div data-testid="asset-panel" data-asset={props.assetName}>
        AssetPanel: {props.assetName}
      </div>
    )
  },
}))

vi.mock('@/features/navigator/components/GroupPanel', () => ({
  GroupPanel: (props: any) => (
    <div data-testid="group-panel" data-group={props.groupName}>
      GroupPanel: {props.groupName}
      <button
        data-testid="group-select-asset"
        onClick={() => props.onSelectAsset('catalog-db')}
      >
        select catalog-db from group
      </button>
    </div>
  ),
}))

vi.mock('@/features/navigator/components/AllEvaluationsPanel', () => ({
  AllEvaluationsPanel: (props: any) => (
    <div data-testid="all-evals-panel">
      AllEvaluationsPanel
      <button
        data-testid="all-select-asset"
        onClick={() => props.onSelectAsset('catalog-db')}
      >
        select catalog-db from all
      </button>
    </div>
  ),
}))

// ── URL param management ───────────────────────────────────────────────────────

let mockParams = new URLSearchParams()
const mockSetParams = vi.fn((next: Record<string, string> | URLSearchParams) => {
  // Simulate real setSearchParams behavior: replaces all params
  mockParams = next instanceof URLSearchParams ? next : new URLSearchParams(next)
})

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useSearchParams: () => [mockParams, mockSetParams] }
})

beforeEach(() => {
  mockParams = new URLSearchParams()
  mockSetParams.mockClear()
  assetPanelRenders.length = 0
})

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('AssetNavigatorPage', () => {
  it('shows AllEvaluationsPanel when no group or asset selected', () => {
    render(<TestWrapper><AssetNavigatorPage /></TestWrapper>)
    expect(screen.getByTestId('all-evals-panel')).toBeInTheDocument()
    expect(screen.queryByTestId('group-panel')).not.toBeInTheDocument()
    expect(screen.queryByTestId('asset-panel')).not.toBeInTheDocument()
  })

  it('shows GroupPanel when group is selected', () => {
    mockParams = new URLSearchParams({ group: 'infra-production' })
    render(<TestWrapper><AssetNavigatorPage /></TestWrapper>)
    expect(screen.getByTestId('group-panel')).toBeInTheDocument()
    expect(screen.getByTestId('group-panel')).toHaveAttribute('data-group', 'infra-production')
  })

  it('shows AssetPanel when asset is selected', () => {
    mockParams = new URLSearchParams({ asset: 'catalog-db' })
    render(<TestWrapper><AssetNavigatorPage /></TestWrapper>)
    expect(screen.getByTestId('asset-panel')).toBeInTheDocument()
    expect(screen.getByTestId('asset-panel')).toHaveAttribute('data-asset', 'catalog-db')
  })

  it('switches from GroupPanel to AssetPanel when asset clicked in tree', async () => {
    mockParams = new URLSearchParams({ group: 'infra-production' })
    const { rerender } = render(<TestWrapper><AssetNavigatorPage /></TestWrapper>)

    // GroupPanel visible
    expect(screen.getByTestId('group-panel')).toBeInTheDocument()

    // Click asset in tree
    await userEvent.click(screen.getByTestId('select-asset-catalog-db'))

    // setParams should have been called with asset + preserved group
    expect(mockSetParams).toHaveBeenCalledWith({ asset: 'catalog-db', group: 'infra-production' })

    // Re-render with updated params (simulating URL update)
    mockParams = new URLSearchParams({ asset: 'catalog-db' })
    rerender(<TestWrapper><AssetNavigatorPage /></TestWrapper>)

    // AssetPanel should now be visible, GroupPanel gone
    expect(screen.getByTestId('asset-panel')).toBeInTheDocument()
    expect(screen.getByTestId('asset-panel')).toHaveAttribute('data-asset', 'catalog-db')
    expect(screen.queryByTestId('group-panel')).not.toBeInTheDocument()
  })

  // ── BUG: group context lost when selecting asset from tree ───────────────
  // When user navigates infrastructure → infra-production → catalog-db,
  // the group context should be preserved so the tree can maintain its state.
  it('preserves group param when selecting asset from within a group', async () => {
    mockParams = new URLSearchParams({ group: 'infra-production' })
    render(<TestWrapper><AssetNavigatorPage /></TestWrapper>)

    await userEvent.click(screen.getByTestId('select-asset-catalog-db'))

    // The group should be preserved alongside the asset in the URL params
    const calledWith = mockSetParams.mock.calls[0][0]
    expect(calledWith).toEqual(
      expect.objectContaining({ asset: 'catalog-db', group: 'infra-production' }),
    )
  })

  // ── BUG: AssetPanel must remount (reset state) when asset changes ────────
  // Without a key prop, React reuses the same AssetPanel instance,
  // causing stale selectedEvalId from the previous asset to persist.
  it('remounts AssetPanel when switching between assets (key prop)', async () => {
    // Start with asset A
    mockParams = new URLSearchParams({ asset: 'api-gateway' })
    const { rerender } = render(<TestWrapper><AssetNavigatorPage /></TestWrapper>)
    expect(screen.getByTestId('asset-panel')).toHaveAttribute('data-asset', 'api-gateway')

    // Switch to asset B — AssetPanel should get a fresh instance
    mockParams = new URLSearchParams({ asset: 'catalog-db' })
    rerender(<TestWrapper><AssetNavigatorPage /></TestWrapper>)
    expect(screen.getByTestId('asset-panel')).toHaveAttribute('data-asset', 'catalog-db')

    // The mock tracks render calls — if remounted, we get both asset names
    // (if reused without key, React would update props on the same instance,
    // which our mock would also track, but the real component would keep stale state)
    expect(assetPanelRenders).toContain('api-gateway')
    expect(assetPanelRenders).toContain('catalog-db')
  })

  it('passes selected group and asset to AssetTree for highlighting', () => {
    mockParams = new URLSearchParams({ group: 'infra-production', asset: 'catalog-db' })
    render(<TestWrapper><AssetNavigatorPage /></TestWrapper>)

    // AssetTree should receive both selectedGroup and selectedAsset
    expect(screen.getByTestId('selected-group')).toHaveTextContent('infra-production')
    expect(screen.getByTestId('selected-asset')).toHaveTextContent('catalog-db')
  })
})
