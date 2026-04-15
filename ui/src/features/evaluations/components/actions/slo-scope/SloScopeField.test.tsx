import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SloScopeField } from './SloScopeField'
import type { SloScopeResult } from './types'

afterEach(() => cleanup())

function makeScope(overrides: Partial<SloScopeResult> = {}): SloScopeResult {
  return {
    availableSlos: [
      { sloName: 'a', displayName: 'A', sloEvaluationId: 'eid-a', currentResult: 'pass' },
      { sloName: 'b', displayName: 'B', sloEvaluationId: 'eid-b', currentResult: 'fail' },
      { sloName: 'c', displayName: 'C', sloEvaluationId: 'eid-c', currentResult: 'warning' },
    ],
    selected: new Set(['a', 'b', 'c']),
    setSelected: vi.fn(),
    reset: vi.fn(),
    lookupEvalId: vi.fn(),
    ...overrides,
  }
}

describe('SloScopeField', () => {
  it('renders N of M SLOs summary', () => {
    render(<SloScopeField scope={makeScope()} onOpenPicker={vi.fn()} />)
    expect(screen.getByText(/3 of 3 SLOs/i)).toBeInTheDocument()
  })

  it('renders a partial count when some are deselected', () => {
    const scope = makeScope({ selected: new Set(['a']) })
    render(<SloScopeField scope={scope} onOpenPicker={vi.fn()} />)
    expect(screen.getByText(/1 of 3 SLOs/i)).toBeInTheDocument()
  })

  it('clicking the summary row invokes onOpenPicker', async () => {
    const onOpenPicker = vi.fn()
    render(<SloScopeField scope={makeScope()} onOpenPicker={onOpenPicker} />)
    await userEvent.click(screen.getByRole('button', { name: /change scope/i }))
    expect(onOpenPicker).toHaveBeenCalledOnce()
  })

  it('clicking reset invokes scope.reset and does not open the picker', async () => {
    const onOpenPicker = vi.fn()
    const scope = makeScope({ selected: new Set(['a']) })
    render(<SloScopeField scope={scope} onOpenPicker={onOpenPicker} />)
    await userEvent.click(screen.getByRole('button', { name: /reset to all/i }))
    expect(scope.reset).toHaveBeenCalledOnce()
    expect(onOpenPicker).not.toHaveBeenCalled()
  })
})
