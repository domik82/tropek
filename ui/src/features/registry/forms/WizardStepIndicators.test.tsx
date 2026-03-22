import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { WizardStepIndicators } from './WizardStepIndicators'
import type { CriteriaParts } from './criteriaUtils'

const indicators = ['error_rate', 'latency_p95', 'throughput']

const defaultCriteria: CriteriaParts = {
  operator: '<',
  sign: null,
  value: 0,
  percent: false,
}

interface IndicatorRow {
  sli: string
  checked: boolean
  weight: number
  key_sli: boolean
  passCriteria: CriteriaParts[]
  warnCriteria: CriteriaParts[]
}

function makeRows(overrides?: Partial<Record<string, Partial<IndicatorRow>>>): IndicatorRow[] {
  return indicators.map((name) => ({
    sli: name,
    checked: false,
    weight: 1,
    key_sli: false,
    passCriteria: [{ ...defaultCriteria }],
    warnCriteria: [{ ...defaultCriteria }],
    ...overrides?.[name],
  }))
}

describe('WizardStepIndicators', () => {
  it('renders all indicators as checkable rows', () => {
    const rows = makeRows()
    render(<WizardStepIndicators rows={rows} onChange={vi.fn()} />)

    for (const name of indicators) {
      expect(screen.getByText(name)).toBeInTheDocument()
    }

    const checkboxes = screen.getAllByRole('checkbox')
    expect(checkboxes).toHaveLength(indicators.length)
  })

  it('unchecked indicators are dimmed with "(unchecked — will not be included)"', () => {
    const rows = makeRows({ error_rate: { checked: true } })
    render(<WizardStepIndicators rows={rows} onChange={vi.fn()} />)

    const dimmedTexts = screen.getAllByText('(unchecked — will not be included)')
    expect(dimmedTexts).toHaveLength(2) // latency_p95 and throughput are unchecked
  })

  it('shows pass AND warn criteria columns when indicator checked', () => {
    const rows = makeRows({
      error_rate: {
        checked: true,
        passCriteria: [{ operator: '<', sign: null, value: 600, percent: false }],
        warnCriteria: [{ operator: '<', sign: null, value: 800, percent: false }],
      },
    })
    render(<WizardStepIndicators rows={rows} onChange={vi.fn()} />)

    // Should show PASS and WARNING column headers
    expect(screen.getByText('PASS CRITERIA')).toBeInTheDocument()
    expect(screen.getByText('WARNING CRITERIA')).toBeInTheDocument()
  })

  it('supports multiple criteria rows per indicator (AND logic)', () => {
    const rows = makeRows({
      error_rate: {
        checked: true,
        passCriteria: [
          { operator: '<', sign: null, value: 600, percent: false },
          { operator: '>', sign: null, value: 100, percent: false },
        ],
        warnCriteria: [
          { operator: '<', sign: null, value: 800, percent: false },
          { operator: '>', sign: null, value: 50, percent: false },
        ],
      },
    })
    render(<WizardStepIndicators rows={rows} onChange={vi.fn()} />)

    // Each checked indicator with 2 criteria should show 2 rows of inputs
    // We look for the serialized previews
    expect(screen.getByText('<600')).toBeInTheDocument()
    expect(screen.getByText('>100')).toBeInTheDocument()
    expect(screen.getByText('<800')).toBeInTheDocument()
    expect(screen.getByText('>50')).toBeInTheDocument()
  })

  it('shows AND label between multi-criteria rows', () => {
    const rows = makeRows({
      error_rate: {
        checked: true,
        passCriteria: [
          { operator: '<', sign: null, value: 600, percent: false },
          { operator: '>', sign: null, value: 100, percent: false },
        ],
        warnCriteria: [
          { operator: '<', sign: null, value: 800, percent: false },
          { operator: '>', sign: null, value: 50, percent: false },
        ],
      },
    })
    render(<WizardStepIndicators rows={rows} onChange={vi.fn()} />)

    const andLabels = screen.getAllByText('AND')
    expect(andLabels.length).toBeGreaterThanOrEqual(1)
  })

  it('shows preview for both pass and warn criteria', () => {
    const rows = makeRows({
      error_rate: {
        checked: true,
        passCriteria: [{ operator: '<=', sign: '+', value: 10, percent: true }],
        warnCriteria: [{ operator: '<=', sign: '+', value: 15, percent: true }],
      },
    })
    render(<WizardStepIndicators rows={rows} onChange={vi.fn()} />)

    expect(screen.getByText('<=+10%')).toBeInTheDocument()
    expect(screen.getByText('<=+15%')).toBeInTheDocument()
  })

  it('calls onChange when add criterion button is clicked', () => {
    const onChange = vi.fn()
    const rows = makeRows({
      error_rate: {
        checked: true,
        passCriteria: [{ operator: '<', sign: null, value: 600, percent: false }],
        warnCriteria: [{ operator: '<', sign: null, value: 800, percent: false }],
      },
    })
    render(<WizardStepIndicators rows={rows} onChange={onChange} />)

    const addButtons = screen.getAllByRole('button', { name: /add criterion/i })
    fireEvent.click(addButtons[0])
    expect(onChange).toHaveBeenCalled()
  })

  it('calls onChange when checkbox is toggled', () => {
    const onChange = vi.fn()
    const rows = makeRows()
    render(<WizardStepIndicators rows={rows} onChange={onChange} />)

    const checkboxes = screen.getAllByRole('checkbox')
    fireEvent.click(checkboxes[0])
    expect(onChange).toHaveBeenCalled()
  })
})
