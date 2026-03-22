import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SearchableComboBox } from './SearchableComboBox'

describe('SearchableComboBox', () => {
  const items = [
    { value: 'http-service-sli', label: 'HTTP Service SLI', badge: 'prometheus' },
    { value: 'db-sli', label: 'DB SLI', badge: 'prometheus' },
    { value: 'k8s-pod-sli', label: 'K8s Pod SLI', badge: 'mock' },
  ]

  it('shows placeholder when no value selected', () => {
    render(<SearchableComboBox value="" items={items} onSelect={vi.fn()} placeholder="Select SLI..." />)
    expect(screen.getByText('Select SLI...')).toBeInTheDocument()
  })

  it('shows selected value label', () => {
    render(<SearchableComboBox value="db-sli" items={items} onSelect={vi.fn()} />)
    expect(screen.getByText('DB SLI')).toBeInTheDocument()
  })

  it('opens dropdown on click and shows all items', () => {
    render(<SearchableComboBox value="" items={items} onSelect={vi.fn()} placeholder="Pick..." />)
    fireEvent.click(screen.getByText('Pick...'))
    expect(screen.getByText('HTTP Service SLI')).toBeInTheDocument()
    expect(screen.getByText('DB SLI')).toBeInTheDocument()
  })

  it('calls onSelect when item clicked', () => {
    const onSelect = vi.fn()
    render(<SearchableComboBox value="" items={items} onSelect={onSelect} placeholder="Pick..." />)
    fireEvent.click(screen.getByText('Pick...'))
    fireEvent.click(screen.getByText('DB SLI'))
    expect(onSelect).toHaveBeenCalledWith('db-sli')
  })

  it('filters items by search text', () => {
    render(<SearchableComboBox value="" items={items} onSelect={vi.fn()} placeholder="Pick..." />)
    fireEvent.click(screen.getByText('Pick...'))
    const searchInput = screen.getByPlaceholderText('Search...')
    fireEvent.change(searchInput, { target: { value: 'k8s' } })
    expect(screen.getByText('K8s Pod SLI')).toBeInTheDocument()
    expect(screen.queryByText('HTTP Service SLI')).not.toBeInTheDocument()
    expect(screen.queryByText('DB SLI')).not.toBeInTheDocument()
  })

  it('displays badges when provided', () => {
    render(<SearchableComboBox value="" items={items} onSelect={vi.fn()} placeholder="Pick..." />)
    fireEvent.click(screen.getByText('Pick...'))
    expect(screen.getAllByText('prometheus')).toHaveLength(2)
    expect(screen.getByText('mock')).toBeInTheDocument()
  })
})
