import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { Annotation } from '@/features/evaluations/domain'
import { NoteIndicatorRow } from './NoteIndicatorRow'

const mockFetch = vi.fn()
vi.mock('@/features/evaluations/api', () => ({
  fetchColumnAnnotations: (...args: unknown[]) => mockFetch(...args),
}))

let queryClient: QueryClient
beforeEach(() => {
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  mockFetch.mockReset()
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
    mockFetch.mockResolvedValue([
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
    ])

    render(
      wrap(
        <NoteIndicatorRow
          columns={['col-1']}
          notedColumns={new Map([['col-1', { evalIds: ['eval-1'], count: 2 }]])}
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

  it('merges annotations from multiple runs sharing one slot (original + re-eval)', async () => {
    // Two runs at the same period_start. The manual note is on the first
    // run; the second run only has re-eval annotations. The tooltip must
    // surface both sets — dropping either silently hides the user's note.
    mockFetch.mockImplementation((evalId: string) => {
      if (evalId === 'run-with-note') {
        return Promise.resolve([
          makeAnnotation({
            id: 'manual',
            content: 'THE MANUAL NOTE CONTENT',
            category: 'error',
            author: 'd',
            noteGroupId: null,
          }),
        ])
      }
      if (evalId === 'run-reeval-only') {
        return Promise.resolve([
          makeAnnotation({
            id: 'reeval',
            content: 'plugin/auth: pass → pass, score 100.0 → 100.0',
            category: 're-evaluation',
            noteGroupId: 'g1',
            noteGroupName: 're-evaluation — 5 SLOs',
          }),
        ])
      }
      return Promise.resolve([])
    })

    render(
      wrap(
        <NoteIndicatorRow
          columns={['slot-1']}
          notedColumns={new Map([[
            'slot-1',
            { evalIds: ['run-with-note', 'run-reeval-only'], count: 2 },
          ]])}
          columnPositions={[{ x: 0, width: 20 }]}
        />,
      ),
    )

    const wrapper = screen.getByRole('button').parentElement!
    fireEvent.mouseEnter(wrapper)

    expect(await screen.findByText(/THE MANUAL NOTE CONTENT/)).toBeInTheDocument()
    expect(
      await screen.findByText(/plugin\/auth: pass → pass/),
    ).toBeInTheDocument()
    expect(mockFetch).toHaveBeenCalledWith('run-with-note')
    expect(mockFetch).toHaveBeenCalledWith('run-reeval-only')
  })
})
