import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { StructuredCriteriaInput } from './StructuredCriteriaInput'
import type { CriteriaParts } from '@/features/registry/forms/criteriaUtils'

describe('StructuredCriteriaInput', () => {
  const defaultParts: CriteriaParts = { operator: '<', sign: null, value: 600, percent: false }

  it('renders operator select, value input, and % toggle', () => {
    render(<StructuredCriteriaInput value={defaultParts} onChange={vi.fn()} />)
    expect(screen.getByDisplayValue('<')).toBeInTheDocument()
    expect(screen.getByDisplayValue('600')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /%/i })).toBeInTheDocument()
  })

  it('shows preview string in preview cell', () => {
    render(<StructuredCriteriaInput value={defaultParts} onChange={vi.fn()} showPreview />)
    expect(screen.getByText('<600')).toBeInTheDocument()
  })

  it('calls onChange when value changes', () => {
    const onChange = vi.fn()
    render(<StructuredCriteriaInput value={defaultParts} onChange={onChange} />)
    fireEvent.change(screen.getByDisplayValue('600'), { target: { value: '800' } })
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ value: 800 }))
  })

  it('toggles percent mode', () => {
    const onChange = vi.fn()
    render(<StructuredCriteriaInput value={defaultParts} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: /%/i }))
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ percent: true }))
  })

  it('renders relative percent preview', () => {
    const parts: CriteriaParts = { operator: '<=', sign: '+', value: 10, percent: true }
    render(<StructuredCriteriaInput value={parts} onChange={vi.fn()} showPreview />)
    expect(screen.getByText('<=+10%')).toBeInTheDocument()
  })
})
