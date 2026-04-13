import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ResultBadge } from './ResultBadge'

describe('ResultBadge', () => {
  it('renders pass badge with result text', () => {
    render(<ResultBadge result="pass" />)
    expect(screen.getByText('pass')).toBeInTheDocument()
  })

  it('renders warning badge with result text', () => {
    render(<ResultBadge result="warning" />)
    expect(screen.getByText('warning')).toBeInTheDocument()
  })

  it('renders fail badge with result text', () => {
    render(<ResultBadge result="fail" />)
    expect(screen.getByText('fail')).toBeInTheDocument()
  })

  it('renders invalidated badge with result text', () => {
    render(<ResultBadge result="invalidated" />)
    expect(screen.getByText('invalidated')).toBeInTheDocument()
  })

  it('renders error result gracefully', () => {
    render(<ResultBadge result="error" />)
    expect(screen.getByText('error')).toBeInTheDocument()
  })

  it('renders as an inline span element', () => {
    render(<ResultBadge result="pass" />)
    const badge = screen.getByText('pass')
    expect(badge.tagName).toBe('SPAN')
  })
})
