import { cleanup, render, screen, fireEvent } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CollapsedStrip } from './CollapsedStrip'

describe('CollapsedStrip', () => {
  afterEach(() => cleanup())

  it('renders "no items tracked" when itemCount is 0', () => {
    render(<CollapsedStrip itemCount={0} expanded={false} onToggle={() => {}} />)
    expect(screen.getByText(/no items tracked/)).toBeInTheDocument()
  })

  it('renders "1 item tracked" (singular) when itemCount is 1', () => {
    render(<CollapsedStrip itemCount={1} expanded={false} onToggle={() => {}} />)
    expect(screen.getByText(/1 item tracked/)).toBeInTheDocument()
  })

  it('renders "5 items tracked" when itemCount is 5', () => {
    render(<CollapsedStrip itemCount={5} expanded={false} onToggle={() => {}} />)
    expect(screen.getByText(/5 items tracked/)).toBeInTheDocument()
  })

  it('sets aria-expanded to match the expanded prop', () => {
    const { rerender } = render(<CollapsedStrip itemCount={3} expanded={false} onToggle={() => {}} />)
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'false')
    rerender(<CollapsedStrip itemCount={3} expanded={true} onToggle={() => {}} />)
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'true')
  })

  it('fires onToggle when clicked', () => {
    const handleToggle = vi.fn()
    render(<CollapsedStrip itemCount={3} expanded={false} onToggle={handleToggle} />)
    fireEvent.click(screen.getByRole('button'))
    expect(handleToggle).toHaveBeenCalledOnce()
  })

  it('shows investigation hint when collapsed, hides when expanded', () => {
    const { rerender } = render(<CollapsedStrip itemCount={3} expanded={false} onToggle={() => {}} />)
    expect(screen.getByText(/click to investigate/)).toBeInTheDocument()
    rerender(<CollapsedStrip itemCount={3} expanded={true} onToggle={() => {}} />)
    expect(screen.queryByText(/click to investigate/)).not.toBeInTheDocument()
  })
})
