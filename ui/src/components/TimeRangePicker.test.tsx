// ui/src/components/TimeRangePicker.test.tsx
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { TimeRangePicker } from './TimeRangePicker'
import { TimeRangeProvider, toDateInputValue } from '@/lib/time-range-context'

function renderPicker(initialEntry = '/') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <TimeRangeProvider>
        <TimeRangePicker />
      </TimeRangeProvider>
    </MemoryRouter>,
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

  it('opens dropdown and shows presets and absolute inputs on click', () => {
    renderPicker()
    fireEvent.click(screen.getByRole('button'))
    // Quick presets
    expect(screen.getByText('Last 7 days')).toBeInTheDocument()
    expect(screen.getByText('Last 14 days')).toBeInTheDocument()
    expect(screen.getByText('Last 90 days')).toBeInTheDocument()
    expect(screen.getByText('Last 6 months')).toBeInTheDocument()
    expect(screen.getByText('Last 1 year')).toBeInTheDocument()
    // Absolute date range section
    expect(screen.getByText('Absolute time range')).toBeInTheDocument()
    expect(screen.getByText('Apply time range')).toBeInTheDocument()
  })

  it('selecting a preset updates the displayed label', () => {
    renderPicker()
    fireEvent.click(screen.getByRole('button'))
    fireEvent.click(screen.getByText('Last 7 days'))
    expect(screen.getByRole('button')).toHaveTextContent('Last 7 days')
  })
})

describe('TimeRangePicker calendar initialization', () => {
  it('initializes the absolute inputs from the active context range', () => {
    renderPicker('/?from=2026-04-01T00:00:00.000Z&to=2026-04-25T23:59:59.999Z')
    fireEvent.click(screen.getByRole('button'))
    const expectedFrom = toDateInputValue(new Date('2026-04-01T00:00:00.000Z'))
    const expectedTo = toDateInputValue(new Date('2026-04-25T23:59:59.999Z'))
    expect(screen.getByText(expectedFrom)).toBeInTheDocument()
    expect(screen.getByText(expectedTo)).toBeInTheDocument()
  })
})
