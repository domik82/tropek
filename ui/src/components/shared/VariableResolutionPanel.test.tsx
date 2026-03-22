import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { VariableResolutionPanel } from './VariableResolutionPanel'

describe('VariableResolutionPanel', () => {
  it('renders variable sources in priority order', () => {
    render(
      <VariableResolutionPanel
        assetVariables={{ job: 'checkout', namespace: 'prod' }}
        sloVariables={{ aggregation_window: '5m' }}
        reserved={{ asset_name: 'checkout-api' }}
      />
    )
    expect(screen.getByText('asset.variables:')).toBeInTheDocument()
    expect(screen.getByText(/\$job/)).toBeInTheDocument()
    expect(screen.getByText('slo.variables:')).toBeInTheDocument()
    expect(screen.getByText('reserved:')).toBeInTheDocument()
  })

  it('hides empty sections', () => {
    render(
      <VariableResolutionPanel
        assetVariables={{}} sloVariables={{ window: '5m' }} reserved={{}}
      />
    )
    expect(screen.queryByText('asset.variables:')).not.toBeInTheDocument()
    expect(screen.getByText('slo.variables:')).toBeInTheDocument()
  })

  it('returns null when all sections are empty', () => {
    const { container } = render(
      <VariableResolutionPanel assetVariables={{}} sloVariables={{}} reserved={{}} />
    )
    expect(container.firstChild).toBeNull()
  })
})
