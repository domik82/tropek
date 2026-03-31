import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { RegistryDetailPanel } from './RegistryDetailPanel'

vi.mock('@/features/registry/details/SloDetailView', () => ({ SloDetailView: () => <div>slo-detail</div> }))
vi.mock('@/features/registry/details/SliDetailView', () => ({ SliDetailView: () => <div>sli-detail</div> }))
vi.mock('@/features/registry/details/DatasourceDetailView', () => ({ DatasourceDetailView: () => <div>ds-detail</div> }))
vi.mock('@/features/registry/details/AssetBindingView', () => ({ AssetBindingView: () => <div>asset-detail</div> }))
vi.mock('@/features/registry/details/TemplateDetailView', () => ({ TemplateDetailView: () => <div>template-detail</div> }))
vi.mock('@/features/registry/details/SloGroupDetailView', () => ({ SloGroupDetailView: () => <div>slo-group-detail</div> }))

describe('RegistryDetailPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('shows empty state when nothing selected', () => {
    render(<RegistryDetailPanel selected={null} onNavigate={vi.fn()} />)
    expect(screen.getByText(/select an item/i)).toBeInTheDocument()
  })

  it('renders TemplateDetailView when type is template', () => {
    render(
      <RegistryDetailPanel
        selected={{ type: 'template', name: 'plugin-tpl' }}
        onNavigate={vi.fn()}
      />,
    )
    expect(screen.getByText('template-detail')).toBeInTheDocument()
  })

  it('renders SloGroupDetailView when type is slo-group', () => {
    render(
      <RegistryDetailPanel
        selected={{ type: 'slo-group', name: 'app-plugins' }}
        onNavigate={vi.fn()}
      />,
    )
    expect(screen.getByText('slo-group-detail')).toBeInTheDocument()
  })
})
