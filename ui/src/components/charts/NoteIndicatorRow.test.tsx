import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { Annotation } from '@/features/evaluations/domain'
import { NoteIndicatorRow } from './NoteIndicatorRow'

const mockUseColumnAnnotations = vi.fn()
vi.mock('@/features/evaluations/hooks', () => ({
  useColumnAnnotations: (...args: unknown[]) => mockUseColumnAnnotations(...args),
}))

let queryClient: QueryClient
beforeEach(() => {
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  mockUseColumnAnnotations.mockReset()
})
afterEach(() => {
  queryClient.cancelQueries()
  queryClient.clear()
  cleanup()
})

function wrap(ui: React.ReactNode) {
  return <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
}

function makeAnnotation(partial: Partial<Annotation>): Annotation {
  return {
    id: 'id-' + Math.random(),
    content: '',
    author: null,
    category: null,
    tags: {},
    noteGroupId: null,
    noteGroupName: null,
    hiddenAt: null,
    hiddenBy: null,
    hiddenReason: null,
    createdAt: new Date('2026-04-14T17:00:00Z'),
    updatedAt: null,
    ...partial,
  }
}

describe('NoteIndicatorRow tooltip', () => {
  it('renders a standalone annotation (noteGroupId=null) in the tooltip', async () => {
    const annotations: Annotation[] = [
      makeAnnotation({
        id: 'group-1',
        content: 'plugin/auth: pass → pass, score 100.0 → 100.0',
        category: 're-evaluation',
        noteGroupId: 'group-a',
        noteGroupName: 're-evaluation — 5 SLOs',
      }),
      makeAnnotation({
        id: 'standalone-1',
        content: 'this is really long text that I would like to render in the tooltip',
        category: 'error',
        author: 'd',
        noteGroupId: null,
      }),
    ]
    mockUseColumnAnnotations.mockReturnValue({
      data: annotations,
      isFetching: false,
      refetch: vi.fn(),
    })

    render(
      wrap(
        <NoteIndicatorRow
          columns={['run-1']}
          notedColumns={new Map([['run-1', { evalId: 'run-1', count: 2 }]])}
          columnPositions={[{ x: 0, width: 20 }]}
        />,
      ),
    )

    // Force tooltip open by hovering the parent wrapper (mouseenter doesn't bubble)
    const wrapper = screen.getByRole('button').parentElement!
    fireEvent.mouseEnter(wrapper)

    expect(
      await screen.findByText(/plugin\/auth: pass → pass/),
    ).toBeInTheDocument()
    expect(
      await screen.findByText(/this is really long text/),
    ).toBeInTheDocument()
  })
})
