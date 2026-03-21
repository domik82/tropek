import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AnnotationSection } from './AnnotationForm'
import type { Annotation } from '../types'

const addAnnotationMutate = vi.fn()
const hideAnnotationMutate = vi.fn()

vi.mock('../hooks', () => ({
  useAddAnnotation: () => ({
    mutate: addAnnotationMutate,
    isPending: false,
  }),
  useHideAnnotation: () => ({
    mutate: hideAnnotationMutate,
    isPending: false,
  }),
}))

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

const annotations: Annotation[] = [
  {
    id: 'ann-1',
    content: 'First note',
    author: 'alice',
    category: 'investigation',
    meta: {},
    hidden_at: null,
    hidden_by: null,
    hidden_reason: null,
    created_at: '2026-03-19T10:00:00Z',
    updated_at: '2026-03-19T10:00:00Z',
  },
  {
    id: 'ann-2',
    content: 'Second note',
    author: 'bob',
    category: null,
    meta: {},
    hidden_at: null,
    hidden_by: null,
    hidden_reason: null,
    created_at: '2026-03-19T11:00:00Z',
    updated_at: '2026-03-19T11:00:00Z',
  },
]

describe('AnnotationSection', () => {
  it('renders Notes heading with annotation count', () => {
    renderWithQuery(<AnnotationSection evalId="e1" annotations={annotations} />)
    expect(screen.getByText('Notes')).toBeInTheDocument()
    expect(screen.getByText('(2)')).toBeInTheDocument()
  })

  it('renders all annotation entries', () => {
    renderWithQuery(<AnnotationSection evalId="e1" annotations={annotations} />)
    expect(screen.getByText('First note')).toBeInTheDocument()
    expect(screen.getByText('Second note')).toBeInTheDocument()
  })

  it('shows "No notes yet." when annotations are empty', () => {
    renderWithQuery(<AnnotationSection evalId="e1" annotations={[]} />)
    expect(screen.getByText('No notes yet.')).toBeInTheDocument()
  })

  it('shows + Note button that toggles the add note form', () => {
    renderWithQuery(<AnnotationSection evalId="e1" annotations={[]} />)
    const addButton = screen.getByText('+ Note')
    expect(addButton).toBeInTheDocument()
    fireEvent.click(addButton)
    expect(screen.getByText('Add Note')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Note content...')).toBeInTheDocument()
  })

  it('changes + Note button to Cancel when form is open', () => {
    renderWithQuery(<AnnotationSection evalId="e1" annotations={[]} />)
    fireEvent.click(screen.getByText('+ Note'))
    // The + Note button text changes to Cancel; AddNoteForm also has a Cancel button
    const cancelButtons = screen.getAllByText('Cancel')
    expect(cancelButtons.length).toBeGreaterThanOrEqual(1)
    expect(screen.queryByText('+ Note')).not.toBeInTheDocument()
  })

  it('hides add form when Cancel is clicked', () => {
    renderWithQuery(<AnnotationSection evalId="e1" annotations={[]} />)
    fireEvent.click(screen.getByText('+ Note'))
    expect(screen.getByPlaceholderText('Note content...')).toBeInTheDocument()
    // Click the toggle button which now says "Cancel"
    fireEvent.click(screen.getAllByText('Cancel')[0])
    expect(screen.queryByPlaceholderText('Note content...')).not.toBeInTheDocument()
  })

  it('shows view mode toggle when annotations exist', () => {
    renderWithQuery(<AnnotationSection evalId="e1" annotations={annotations} />)
    expect(screen.getByText('compact')).toBeInTheDocument()
    expect(screen.getByText('expanded')).toBeInTheDocument()
  })

  it('does not show view mode toggle when no annotations', () => {
    renderWithQuery(<AnnotationSection evalId="e1" annotations={[]} />)
    expect(screen.queryByText('compact')).not.toBeInTheDocument()
    expect(screen.queryByText('expanded')).not.toBeInTheDocument()
  })

  it('shows count of zero in heading when empty', () => {
    renderWithQuery(<AnnotationSection evalId="e1" annotations={[]} />)
    expect(screen.getByText('(0)')).toBeInTheDocument()
  })

  it('calls addAnnotation mutation on form submit', () => {
    addAnnotationMutate.mockClear()
    renderWithQuery(<AnnotationSection evalId="e1" annotations={[]} />)

    // Open form
    fireEvent.click(screen.getByText('+ Note'))
    // Fill content
    fireEvent.change(screen.getByPlaceholderText('Note content...'), {
      target: { value: 'Test annotation' },
    })
    // Submit
    fireEvent.click(screen.getByText('Save note'))
    expect(addAnnotationMutate).toHaveBeenCalled()
  })
})
