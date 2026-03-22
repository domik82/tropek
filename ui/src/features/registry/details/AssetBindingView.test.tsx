import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AssetBindingView } from './AssetBindingView'
import type { AssetGroupSLOLink } from '@/features/slos/types'

vi.mock('@/features/slos/hooks', () => ({
  useGroupSloLinks: vi.fn(),
  useDeleteGroupSloLink: vi.fn(),
}))

import { useGroupSloLinks, useDeleteGroupSloLink } from '@/features/slos/hooks'

const mockLinks: AssetGroupSLOLink[] = [
  {
    id: 'link-1',
    link_name: 'api-availability-link',
    group_id: 'group-uuid-1',
    slo_name: 'api-availability',
    sli_name: 'error-rate',
    data_source_name: 'prom-main',
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'link-2',
    link_name: 'latency-link',
    group_id: 'group-uuid-1',
    slo_name: 'latency-slo',
    sli_name: 'p99-latency',
    data_source_name: 'prom-secondary',
    created_at: '2024-01-02T00:00:00Z',
  },
]

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
}

describe('AssetBindingView', () => {
  beforeEach(() => {
    vi.mocked(useGroupSloLinks).mockReturnValue({
      data: mockLinks,
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useGroupSloLinks>)

    vi.mocked(useDeleteGroupSloLink).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useDeleteGroupSloLink>)
  })

  it('renders asset name in header', () => {
    render(
      <AssetBindingView
        assetName="my-asset"
        groupName="my-group"
        onNavigate={vi.fn()}
        onLinkSlo={vi.fn()}
      />,
      { wrapper: Wrapper }
    )
    expect(screen.getByText('my-asset')).toBeInTheDocument()
  })

  it('empty state shows "Link an SLO" when no bindings', () => {
    vi.mocked(useGroupSloLinks).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useGroupSloLinks>)

    render(
      <AssetBindingView
        assetName="my-asset"
        groupName="my-group"
        onNavigate={vi.fn()}
        onLinkSlo={vi.fn()}
      />,
      { wrapper: Wrapper }
    )
    expect(screen.getByText(/No SLO bindings/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /link an slo/i })).toBeInTheDocument()
  })

  it('renders binding cards with chain info', () => {
    render(
      <AssetBindingView
        assetName="my-asset"
        groupName="my-group"
        onNavigate={vi.fn()}
        onLinkSlo={vi.fn()}
      />,
      { wrapper: Wrapper }
    )
    expect(screen.getByText('api-availability')).toBeInTheDocument()
    expect(screen.getByText('error-rate')).toBeInTheDocument()
    expect(screen.getByText('prom-main')).toBeInTheDocument()
    expect(screen.getByText('latency-slo')).toBeInTheDocument()
    expect(screen.getByText('p99-latency')).toBeInTheDocument()
    expect(screen.getByText('prom-secondary')).toBeInTheDocument()
  })

  it('clicking chain entities fires onNavigate', () => {
    const onNavigate = vi.fn()
    render(
      <AssetBindingView
        assetName="my-asset"
        groupName="my-group"
        onNavigate={onNavigate}
        onLinkSlo={vi.fn()}
      />,
      { wrapper: Wrapper }
    )
    fireEvent.click(screen.getByText('api-availability'))
    expect(onNavigate).toHaveBeenCalledWith({ type: 'slo', name: 'api-availability' })

    fireEvent.click(screen.getByText('error-rate'))
    expect(onNavigate).toHaveBeenCalledWith({ type: 'sli', name: 'error-rate' })

    fireEvent.click(screen.getByText('prom-main'))
    expect(onNavigate).toHaveBeenCalledWith({ type: 'datasource', name: 'prom-main' })
  })
})
