import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EvaluationNameFilter } from './EvaluationNameFilter'

const NAMES = [
  { name: 'load-test', count: 42, last_run: '2026-03-27T08:00:00Z' },
  { name: 'ad-hoc-run', count: 3, last_run: '2026-03-26T14:00:00Z' },
]

describe('EvaluationNameFilter', () => {
  it('renders chips for each name plus All', () => {
    render(
      <EvaluationNameFilter
        names={NAMES}
        selected={['load-test']}
        onChange={vi.fn()}
      />
    )
    expect(screen.getByText('All')).toBeInTheDocument()
    expect(screen.getByText(/load-test/)).toBeInTheDocument()
    expect(screen.getByText(/ad-hoc-run/)).toBeInTheDocument()
  })

  it('shows count on each chip', () => {
    render(
      <EvaluationNameFilter
        names={NAMES}
        selected={['load-test']}
        onChange={vi.fn()}
      />
    )
    expect(screen.getByText(/42/)).toBeInTheDocument()
    expect(screen.getByText(/3/)).toBeInTheDocument()
  })

  it('selects a name when clicked', async () => {
    const onChange = vi.fn()
    render(
      <EvaluationNameFilter
        names={NAMES}
        selected={['load-test']}
        onChange={onChange}
      />
    )
    await userEvent.click(screen.getByText(/ad-hoc-run/))
    // Selecting all individual chips collapses to All (undefined)
    expect(onChange).toHaveBeenCalledWith(undefined)
  })

  it('deselects a name when clicked again (if others remain)', async () => {
    const onChange = vi.fn()
    render(
      <EvaluationNameFilter
        names={NAMES}
        selected={['load-test', 'ad-hoc-run']}
        onChange={onChange}
      />
    )
    await userEvent.click(screen.getByText(/load-test/))
    expect(onChange).toHaveBeenCalledWith(['ad-hoc-run'])
  })

  it('deselecting the last name returns to All', async () => {
    const onChange = vi.fn()
    render(
      <EvaluationNameFilter
        names={NAMES}
        selected={['load-test']}
        onChange={onChange}
      />
    )
    await userEvent.click(screen.getByText(/load-test/))
    expect(onChange).toHaveBeenCalledWith(undefined)
  })

  it('clicking a chip when All is active deselects that name', async () => {
    const onChange = vi.fn()
    render(
      <EvaluationNameFilter
        names={NAMES}
        selected={undefined}
        onChange={onChange}
      />
    )
    await userEvent.click(screen.getByText(/ad-hoc-run/))
    // Deselects ad-hoc-run, keeps load-test
    expect(onChange).toHaveBeenCalledWith(['load-test'])
  })

  it('All selects undefined (no filter)', async () => {
    const onChange = vi.fn()
    render(
      <EvaluationNameFilter
        names={NAMES}
        selected={['load-test']}
        onChange={onChange}
      />
    )
    await userEvent.click(screen.getByText('All'))
    expect(onChange).toHaveBeenCalledWith(undefined)
  })
})
