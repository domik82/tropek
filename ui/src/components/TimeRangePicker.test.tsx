// ui/src/components/TimeRangePicker.test.tsx
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { TimeRangePicker } from './TimeRangePicker'
import { TimeRangeProvider, toDateInputValue, isoToCalendarDate } from '@/lib/time-range-context'

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
    const fromEpoch = Date.UTC(2026, 3, 1, 0, 0, 0)
    const toEpoch = Date.UTC(2026, 3, 25, 23, 59, 59)
    renderPicker(`/?from=${fromEpoch}&to=${toEpoch}`)
    fireEvent.click(screen.getByRole('button'))
    const expectedFrom = toDateInputValue(isoToCalendarDate(new Date(fromEpoch).toISOString()))
    const expectedTo = toDateInputValue(isoToCalendarDate(new Date(toEpoch).toISOString()))
    expect(screen.getByText(expectedFrom)).toBeInTheDocument()
    expect(screen.getByText(expectedTo)).toBeInTheDocument()
  })
})
