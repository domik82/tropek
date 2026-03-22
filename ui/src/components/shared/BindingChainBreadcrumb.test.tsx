import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { BindingChainBreadcrumb } from './BindingChainBreadcrumb'

describe('BindingChainBreadcrumb', () => {
  it('renders SLO → SLI → DS chain', () => {
    render(
      <BindingChainBreadcrumb
        sloName="http-availability-slo" sloVersion="3.1"
        sliName="http-service-sli" dsName="prometheus-local"
        onClickSlo={vi.fn()} onClickSli={vi.fn()} onClickDs={vi.fn()}
      />
    )
    expect(screen.getByText(/http-availability-slo/)).toBeInTheDocument()
    expect(screen.getByText(/http-service-sli/)).toBeInTheDocument()
    expect(screen.getByText(/prometheus-local/)).toBeInTheDocument()
  })

  it('calls onClickSli when SLI badge clicked', () => {
    const onClickSli = vi.fn()
    render(
      <BindingChainBreadcrumb
        sloName="slo" sliName="sli" dsName="ds"
        onClickSlo={vi.fn()} onClickSli={onClickSli} onClickDs={vi.fn()}
      />
    )
    fireEvent.click(screen.getByText('sli'))
    expect(onClickSli).toHaveBeenCalled()
  })

  it('shows version badge when sloVersion provided', () => {
    render(
      <BindingChainBreadcrumb
        sloName="slo" sloVersion="3.1" sliName="sli" dsName="ds"
        onClickSlo={vi.fn()} onClickSli={vi.fn()} onClickDs={vi.fn()}
      />
    )
    expect(screen.getByText('v3.1')).toBeInTheDocument()
  })

  it('calls onClickDs when DS badge clicked', () => {
    const onClickDs = vi.fn()
    render(
      <BindingChainBreadcrumb
        sloName="slo" sliName="sli" dsName="ds"
        onClickSlo={vi.fn()} onClickSli={vi.fn()} onClickDs={onClickDs}
      />
    )
    fireEvent.click(screen.getByText('ds'))
    expect(onClickDs).toHaveBeenCalled()
  })
})
