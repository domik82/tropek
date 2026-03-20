import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { LabelChips } from './LabelChips'

const LABELS = {
  team: 'payments',
  env: 'production',
  region: 'eu-west-1',
  tier: 'critical',
  os: 'linux',
}

describe('LabelChips', () => {
  it('renders up to maxVisible labels as chips', () => {
    render(<LabelChips labels={LABELS} maxVisible={3} />)
    expect(screen.getByText('team')).toBeInTheDocument()
    expect(screen.getByText('payments')).toBeInTheDocument()
    expect(screen.getByText('env')).toBeInTheDocument()
    expect(screen.getByText('production')).toBeInTheDocument()
    expect(screen.getByText('region')).toBeInTheDocument()
    expect(screen.getByText('eu-west-1')).toBeInTheDocument()
  })

  it('shows +N more badge when labels exceed maxVisible', () => {
    render(<LabelChips labels={LABELS} maxVisible={3} />)
    expect(screen.getByText('+2 more')).toBeInTheDocument()
  })

  it('does not show overflow badge when all labels fit', () => {
    render(<LabelChips labels={{ team: 'payments', env: 'dev' }} maxVisible={3} />)
    expect(screen.queryByText(/\+\d+ more/)).not.toBeInTheDocument()
  })

  it('expands to show all labels when +N badge is clicked', async () => {
    const user = userEvent.setup()
    render(<LabelChips labels={LABELS} maxVisible={3} />)
    await user.click(screen.getByText('+2 more'))
    expect(screen.getByText('tier')).toBeInTheDocument()
    expect(screen.getByText('critical')).toBeInTheDocument()
    expect(screen.getByText('os')).toBeInTheDocument()
    expect(screen.getByText('linux')).toBeInTheDocument()
  })

  it('renders "No labels" when labels is empty', () => {
    render(<LabelChips labels={{}} />)
    expect(screen.getByText(/no labels/i)).toBeInTheDocument()
  })
})
