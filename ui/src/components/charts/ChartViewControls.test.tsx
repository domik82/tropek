import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ChartViewControls } from './ChartViewControls'
import { ChartPreferencesProvider } from '@/lib/chart-preferences-context'

function renderControls() {
  return render(
    <ChartPreferencesProvider>
      <ChartViewControls />
    </ChartPreferencesProvider>,
  )
}

describe('ChartViewControls', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('sets columns to 1 when the "1 / row" option is clicked', () => {
    renderControls()
    fireEvent.click(screen.getByRole('button', { name: '1 / row' }))
    expect(localStorage.getItem('tropek.chartColumns')).toBe('1')
  })

  it('toggles the master notes switch', () => {
    renderControls()
    fireEvent.click(screen.getByRole('button', { name: 'Toggle notes on all charts' }))
    expect(localStorage.getItem('tropek.notesMaster')).toBe('false')
  })

  it('switches the master chart type to bar', () => {
    renderControls()
    fireEvent.click(screen.getByRole('button', { name: 'Show all charts as bars' }))
    expect(localStorage.getItem('tropek.chartType')).toBe('bar')
  })
})
