import { cleanup, render, screen, fireEvent } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MetaTimelineSection } from './MetaTimelineSection'

// Mock hooks — return controlled data
const mockUseMetaTimelineSummary = vi.fn()
const mockUseMetaTimeline = vi.fn()

vi.mock('../hooks', () => ({
  useMetaTimelineSummary: (...args: unknown[]) => mockUseMetaTimelineSummary(...args),
  useMetaTimeline: (...args: unknown[]) => mockUseMetaTimeline(...args),
}))

// Mock MetaTimeline (vis-timeline wrapper) to avoid DOM issues
vi.mock('./MetaTimeline', () => ({
  MetaTimeline: () => <div data-testid="meta-timeline-chart">Timeline rendered</div>,
}))

const focusEval = { id: 'eval-1', periodEnd: new Date('2026-04-16T10:00:00Z') }

describe('MetaTimelineSection', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    // Default: summary returns some count, timeline not yet fetched
    mockUseMetaTimelineSummary.mockReturnValue({ data: { itemCount: 3 } })
    mockUseMetaTimeline.mockReturnValue({ data: undefined, isLoading: false, error: null })
  })

  afterEach(() => {
    queryClient.cancelQueries()
    queryClient.clear()
    cleanup()
    vi.clearAllMocks()
  })

  function renderSection() {
    return render(
      <QueryClientProvider client={queryClient}>
        <MetaTimelineSection assetId="asset-123" focusEval={focusEval} />
      </QueryClientProvider>,
    )
  }

  it('shows collapsed strip with item count from summary', () => {
    renderSection()
    expect(screen.getByText(/3 items tracked/)).toBeInTheDocument()
  })

  it('does not render timeline when collapsed', () => {
    renderSection()
    expect(screen.queryByTestId('meta-timeline-chart')).not.toBeInTheDocument()
  })

  it('renders timeline when expanded with data', () => {
    mockUseMetaTimeline.mockReturnValue({
      data: {
        groups: [{ id: '["app"]', content: 'app' }],
        items: [
          {
            id: 's0',
            group: '["app"]',
            content: '1.0',
            start: new Date(),
            end: new Date(),
            type: 'range',
            className: 'meta-span',
            source: 'cicd',
          },
        ],
      },
      isLoading: false,
      error: null,
    })
    renderSection()
    fireEvent.click(screen.getByRole('button'))
    expect(screen.getByTestId('meta-timeline-chart')).toBeInTheDocument()
  })

  it('shows loading state when expanded and loading', () => {
    mockUseMetaTimeline.mockReturnValue({ data: undefined, isLoading: true, error: null })
    renderSection()
    fireEvent.click(screen.getByRole('button'))
    expect(screen.getByText(/Loading timeline/)).toBeInTheDocument()
  })

  it('shows error state when expanded and errored', () => {
    mockUseMetaTimeline.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Network error'),
    })
    renderSection()
    fireEvent.click(screen.getByRole('button'))
    expect(screen.getByText(/Failed to load timeline/)).toBeInTheDocument()
  })

  it('shows empty state when expanded with zero items', () => {
    mockUseMetaTimeline.mockReturnValue({
      data: { groups: [], items: [] },
      isLoading: false,
      error: null,
    })
    renderSection()
    fireEvent.click(screen.getByRole('button'))
    expect(screen.getByText(/No meta data recorded/)).toBeInTheDocument()
  })

  it('collapses back when strip is clicked again', () => {
    mockUseMetaTimeline.mockReturnValue({
      data: {
        groups: [{ id: '["app"]', content: 'app' }],
        items: [
          {
            id: 's0',
            group: '["app"]',
            content: '1.0',
            start: new Date(),
            end: new Date(),
            type: 'range',
            className: 'meta-span',
            source: 'cicd',
          },
        ],
      },
      isLoading: false,
      error: null,
    })
    renderSection()
    fireEvent.click(screen.getByRole('button')) // expand
    expect(screen.getByTestId('meta-timeline-chart')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button')) // collapse
    expect(screen.queryByTestId('meta-timeline-chart')).not.toBeInTheDocument()
  })

  it('shows "no items tracked" when summary returns zero', () => {
    mockUseMetaTimelineSummary.mockReturnValue({ data: { itemCount: 0 } })
    renderSection()
    expect(screen.getByText(/no items tracked/)).toBeInTheDocument()
  })
})
