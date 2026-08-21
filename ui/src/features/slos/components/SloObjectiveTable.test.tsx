import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SloObjectiveTable } from './SloObjectiveTable'
import type { Slo } from '../domain'

const baseSlo: Slo = {
  id: 'slo-1',
  name: 'file-io-centos7/cpu',
  version: 1,
  comparableFromVersion: 1,
  displayName: null,
  author: null,
  notes: null,
  tags: {},
  variables: {},
  kind: 'standard',
  sliDefinitionId: null,
  sliName: 'loadtest-linux-cpu-sli',
  sliVersion: 1,
  createdAt: new Date('2024-01-01T00:00:00Z'),
  active: true,
  objectives: [],
  totalScorePassThreshold: 95,
  totalScoreWarningThreshold: 75,
  comparison: {},
  methodCriteria: null,
}

describe('SloObjectiveTable', () => {
  it('shows the expand button and query for a raw-mode objective keyed by indicator name', () => {
    const slo: Slo = {
      ...baseSlo,
      objectives: [
        { sli: 'cpu_time', displayName: 'cpu_time', passThreshold: ['>=0'], warningThreshold: [], weight: 1, keySli: false, sortOrder: 0 },
      ],
    }
    render(<SloObjectiveTable slo={slo} indicators={{ cpu_time: "SELECT mean FROM tanium_summary WHERE metric_name = 'cpu_time'" }} />)

    const expandButton = screen.getByRole('button')
    expect(expandButton).toBeInTheDocument()
    fireEvent.click(expandButton)
    expect(screen.getByText(/SELECT mean FROM tanium_summary/)).toBeInTheDocument()
  })

  it('shows the expand button and query for a multi-indicator aggregated objective keyed as <indicator>.<method>', () => {
    const slo: Slo = {
      ...baseSlo,
      objectives: [
        { sli: 'usage_percent.mean', displayName: 'cpu.usage_percent', passThreshold: ['>=0'], warningThreshold: [], weight: 1, keySli: false, sortOrder: 0 },
        { sli: 'total_time.mean', displayName: 'cpu.total_time', passThreshold: ['>=0'], warningThreshold: [], weight: 1, keySli: false, sortOrder: 1 },
      ],
    }
    render(
      <SloObjectiveTable
        slo={slo}
        indicators={{
          usage_percent: 'round(sum(rate(tanium_cx_core_system_cpu_seconds_total[$interval])) * 100, .01)',
          total_time: 'rate(tanium_cx_core_system_cpu_seconds_total[$interval]) > -Inf',
        }}
      />
    )

    const expandButtons = screen.getAllByRole('button')
    expect(expandButtons).toHaveLength(2)

    fireEvent.click(expandButtons[0])
    expect(screen.getByText(/round\(sum\(rate/)).toBeInTheDocument()
  })

  it('does not render an expand button when no indicator query resolves for the objective', () => {
    const slo: Slo = {
      ...baseSlo,
      objectives: [
        { sli: 'unknown_metric.mean', displayName: 'unknown', passThreshold: ['>=0'], warningThreshold: [], weight: 1, keySli: false, sortOrder: 0 },
      ],
    }
    render(<SloObjectiveTable slo={slo} indicators={{ cpu_time: 'SELECT 1' }} />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
