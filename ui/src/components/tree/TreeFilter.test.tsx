import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TreeFilter } from './TreeFilter'

describe('TreeFilter', () => {
  it('renders with placeholder', () => {
    render(<TreeFilter value="" onChange={vi.fn()} placeholder="Filter..." />)
    expect(screen.getByPlaceholderText('Filter...')).toBeInTheDocument()
  })

  it('calls onChange when typing', () => {
    const onChange = vi.fn()
    render(<TreeFilter value="" onChange={onChange} placeholder="Filter..." />)
    fireEvent.change(screen.getByPlaceholderText('Filter...'), { target: { value: 'test' } })
    expect(onChange).toHaveBeenCalledWith('test')
  })

  it('shows clear button when value is present', () => {
    render(<TreeFilter value="hello" onChange={vi.fn()} placeholder="Filter..." />)
    expect(screen.getByLabelText('Clear filter')).toBeInTheDocument()
  })

  it('does not show clear button when value is empty', () => {
    render(<TreeFilter value="" onChange={vi.fn()} placeholder="Filter..." />)
    expect(screen.queryByLabelText('Clear filter')).not.toBeInTheDocument()
  })

  it('clears value on X click', () => {
    const onChange = vi.fn()
    render(<TreeFilter value="hello" onChange={onChange} placeholder="Filter..." />)
    fireEvent.click(screen.getByLabelText('Clear filter'))
    expect(onChange).toHaveBeenCalledWith('')
  })

  it('shows result count when filtering and resultCount is provided', () => {
    render(<TreeFilter value="check" onChange={vi.fn()} placeholder="Filter..." resultCount={3} />)
    expect(screen.getByText('3 results')).toBeInTheDocument()
  })

  it('does not show result count when value is empty', () => {
    render(<TreeFilter value="" onChange={vi.fn()} placeholder="Filter..." resultCount={5} />)
    expect(screen.queryByText('5 results')).not.toBeInTheDocument()
  })

  it('shows singular "result" when count is 1', () => {
    render(<TreeFilter value="x" onChange={vi.fn()} placeholder="Filter..." resultCount={1} />)
    expect(screen.getByText('1 result')).toBeInTheDocument()
  })
})
