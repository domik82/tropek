import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SloScopeModal } from './SloScopeModal'
import type { SloScopeOption } from './types'

afterEach(() => cleanup())

const slos: SloScopeOption[] = [
  { sloName: 'latency-slo', displayName: 'Latency', sloEvaluationId: 'e1', currentResult: 'fail' },
  { sloName: 'avail-slo', displayName: 'Availability', sloEvaluationId: 'e2', currentResult: 'pass' },
  { sloName: 'err-slo', displayName: 'Error Rate', sloEvaluationId: 'e3', currentResult: 'warning' },
]

describe('SloScopeModal', () => {
  it('renders all SLOs with current result badges', () => {
    render(
      <SloScopeModal
        open
        availableSlos={slos}
        initialSelected={new Set(['latency-slo'])}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    expect(screen.getByText('Latency')).toBeInTheDocument()
    expect(screen.getByText('Availability')).toBeInTheDocument()
    expect(screen.getByText('Error Rate')).toBeInTheDocument()
    expect(screen.getAllByRole('checkbox')).toHaveLength(3)
  })

  it('search filters by display name', async () => {
    render(
      <SloScopeModal
        open
        availableSlos={slos}
        initialSelected={new Set()}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    await userEvent.type(screen.getByPlaceholderText(/search/i), 'latency')
    expect(screen.getByText('Latency')).toBeInTheDocument()
    expect(screen.queryByText('Availability')).not.toBeInTheDocument()
  })

  it('Select all checks every row', async () => {
    const onConfirm = vi.fn()
    render(
      <SloScopeModal
        open
        availableSlos={slos}
        initialSelected={new Set()}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: /select all/i }))
    await userEvent.click(screen.getByRole('button', { name: /confirm/i }))
    expect(onConfirm).toHaveBeenCalledWith(new Set(['latency-slo', 'avail-slo', 'err-slo']))
  })

  it('Clear unchecks every row', async () => {
    const onConfirm = vi.fn()
    render(
      <SloScopeModal
        open
        availableSlos={slos}
        initialSelected={new Set(['latency-slo', 'avail-slo'])}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: /clear/i }))
    await userEvent.click(screen.getByRole('button', { name: /confirm/i }))
    expect(onConfirm).toHaveBeenCalledWith(new Set())
  })

  it('cancel discards changes and invokes onCancel', async () => {
    const onCancel = vi.fn()
    const onConfirm = vi.fn()
    render(
      <SloScopeModal
        open
        availableSlos={slos}
        initialSelected={new Set()}
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: /select all/i }))
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(onCancel).toHaveBeenCalledOnce()
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('returns null when open=false', () => {
    const { container } = render(
      <SloScopeModal
        open={false}
        availableSlos={slos}
        initialSelected={new Set()}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    expect(container.firstChild).toBeNull()
  })
})
