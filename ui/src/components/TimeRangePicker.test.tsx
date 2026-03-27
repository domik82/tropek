// ui/src/components/TimeRangePicker.test.tsx
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TimeRangePicker } from './TimeRangePicker'
import { TimeRangeProvider } from '@/lib/time-range-context'

function renderPicker() {
  return render(
    <TimeRangeProvider>
      <TimeRangePicker />
    </TimeRangeProvider>,
  )
}

describe('TimeRangePicker', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('renders the default preset label', () => {
    renderPicker()
    expect(screen.getByText('Last 30 days')).toBeInTheDocument()
  })

  it('opens dropdown and shows all presets on click', () => {
    renderPicker()
    fireEvent.click(screen.getByRole('button'))
    expect(screen.getByText('Last 7 days')).toBeInTheDocument()
    expect(screen.getByText('Last 14 days')).toBeInTheDocument()
    expect(screen.getByText('Last 90 days')).toBeInTheDocument()
    expect(screen.getByText('Last 6 months')).toBeInTheDocument()
    expect(screen.getByText('Last 1 year')).toBeInTheDocument()
  })

  it('selecting a preset updates the displayed label', () => {
    renderPicker()
    fireEvent.click(screen.getByRole('button'))
    fireEvent.click(screen.getByText('Last 7 days'))
    expect(screen.getByRole('button')).toHaveTextContent('Last 7 days')
  })
})
