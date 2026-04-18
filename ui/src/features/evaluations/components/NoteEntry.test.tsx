import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { NoteEntry } from './NoteEntry'
import type { Annotation } from '../domain'

const annotation: Annotation = {
  id: 'ann-1',
  sloEvaluationId: null,
  evaluationRunId: 'run-1',
  content: 'test note',
  author: 'tester',
  categoryId: 'cat-investigation',
  category: {
    id: 'cat-investigation',
    name: 'investigation',
    label: 'Investigation',
    color: 'amber',
    showOnGraph: true,
    isSystem: false,
    createdAt: new Date('2026-01-01T00:00:00Z'),
    updatedAt: null,
  },
  tags: {},
  noteGroupId: null,
  noteGroupName: null,
  hiddenAt: null,
  hiddenBy: null,
  hiddenReason: null,
  createdAt: new Date('2026-03-19T10:00:00Z'),
  updatedAt: new Date('2026-03-19T10:00:00Z'),
}

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

describe('NoteEntry', () => {
  it('renders content and author in expanded mode', () => {
    renderWithQuery(<NoteEntry runId="e1" annotation={annotation} />)
    expect(screen.getByText('test note')).toBeInTheDocument()
    expect(screen.getByText('tester')).toBeInTheDocument()
    expect(screen.getByText('Investigation')).toBeInTheDocument()
  })

  it('renders content in compact mode', () => {
    renderWithQuery(<NoteEntry runId="e1" annotation={annotation} compact />)
    expect(screen.getByText('test note')).toBeInTheDocument()
  })

  it('shows delete form when ✕ is clicked in expanded mode', () => {
    renderWithQuery(<NoteEntry runId="e1" annotation={annotation} />)
    fireEvent.click(screen.getByTitle('Delete note'))
    expect(screen.getByText('Delete this note?')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Reason\u2026')).toBeInTheDocument()
  })

  it('shows delete form when ✕ is clicked in compact mode', () => {
    renderWithQuery(<NoteEntry runId="e1" annotation={annotation} compact />)
    fireEvent.click(screen.getByTitle('Delete note'))
    expect(screen.getByText('Delete this note?')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Reason\u2026')).toBeInTheDocument()
  })

  it('hides delete form when Cancel is clicked', () => {
    renderWithQuery(<NoteEntry runId="e1" annotation={annotation} />)
    fireEvent.click(screen.getByTitle('Delete note'))
    expect(screen.getByText('Delete this note?')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Cancel'))
    expect(screen.queryByText('Delete this note?')).not.toBeInTheDocument()
  })

  it('disables Delete button when reason is empty', () => {
    renderWithQuery(<NoteEntry runId="e1" annotation={annotation} />)
    fireEvent.click(screen.getByTitle('Delete note'))
    expect(screen.getByText('Delete note')).toBeDisabled()
  })

  it('enables Delete button when reason and author are provided', () => {
    renderWithQuery(<NoteEntry runId="e1" annotation={annotation} />)
    fireEvent.click(screen.getByTitle('Delete note'))
    fireEvent.change(screen.getByPlaceholderText('Reason\u2026'), {
      target: { value: 'wrong note' },
    })
    fireEvent.change(screen.getByPlaceholderText('Your name'), {
      target: { value: 'tester' },
    })
    expect(screen.getByText('Delete note')).toBeEnabled()
  })
})
