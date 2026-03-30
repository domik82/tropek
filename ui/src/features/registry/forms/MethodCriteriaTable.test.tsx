import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MethodCriteriaTable } from './MethodCriteriaTable'
import type { MethodCriteriaOverride } from '@/features/slos/types'

const methods = ['mean', 'p99', 'max']
const defaultBlueprintPass = ['<10']
const defaultBlueprintWeight = 1

describe('MethodCriteriaTable', () => {
  it('renders a row for each method', () => {
    render(
      <MethodCriteriaTable
        methods={methods}
        criteria={{}}
        blueprintPassCriteria={defaultBlueprintPass}
        blueprintWeight={defaultBlueprintWeight}
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByText('mean')).toBeInTheDocument()
    expect(screen.getByText('p99')).toBeInTheDocument()
    expect(screen.getByText('max')).toBeInTheDocument()
  })

  it('shows inherited values in muted style when no override exists', () => {
    render(
      <MethodCriteriaTable
        methods={methods}
        criteria={{}}
        blueprintPassCriteria={defaultBlueprintPass}
        blueprintWeight={defaultBlueprintWeight}
        onChange={vi.fn()}
      />,
    )
    const passInputs = screen.getAllByDisplayValue('<10')
    expect(passInputs.length).toBe(3)
    passInputs.forEach(input => {
      expect(input).toHaveClass('italic')
    })
  })

  it('shows override values without muted style', () => {
    const criteria: Record<string, MethodCriteriaOverride> = {
      p99: { pass_criteria: ['<25'], weight: 2 },
    }
    render(
      <MethodCriteriaTable
        methods={methods}
        criteria={criteria}
        blueprintPassCriteria={defaultBlueprintPass}
        blueprintWeight={defaultBlueprintWeight}
        onChange={vi.fn()}
      />,
    )
    const p99Input = screen.getByDisplayValue('<25')
    expect(p99Input).not.toHaveClass('italic')
  })

  it('calls onChange when pass criteria is edited', () => {
    const onChange = vi.fn()
    render(
      <MethodCriteriaTable
        methods={methods}
        criteria={{}}
        blueprintPassCriteria={defaultBlueprintPass}
        blueprintWeight={defaultBlueprintWeight}
        onChange={onChange}
      />,
    )
    const passInputs = screen.getAllByDisplayValue('<10')
    fireEvent.change(passInputs[1], { target: { value: '<25' } })
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        p99: expect.objectContaining({ pass_criteria: ['<25'] }),
      }),
    )
  })

  it('calls onChange when weight is edited', () => {
    const onChange = vi.fn()
    render(
      <MethodCriteriaTable
        methods={methods}
        criteria={{}}
        blueprintPassCriteria={defaultBlueprintPass}
        blueprintWeight={defaultBlueprintWeight}
        onChange={onChange}
      />,
    )
    const weightInputs = screen.getAllByDisplayValue('1')
    fireEvent.change(weightInputs[1], { target: { value: '3' } })
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        p99: expect.objectContaining({ weight: 3 }),
      }),
    )
  })

  it('calls onChange when key_sli is toggled', () => {
    const onChange = vi.fn()
    render(
      <MethodCriteriaTable
        methods={methods}
        criteria={{}}
        blueprintPassCriteria={defaultBlueprintPass}
        blueprintWeight={defaultBlueprintWeight}
        onChange={onChange}
      />,
    )
    const checkboxes = screen.getAllByRole('checkbox')
    fireEvent.click(checkboxes[0])
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        mean: expect.objectContaining({ key_sli: true }),
      }),
    )
  })

  it('removes override when value is reset to blueprint default', () => {
    const criteria: Record<string, MethodCriteriaOverride> = {
      p99: { pass_criteria: ['<25'], weight: 2 },
    }
    const onChange = vi.fn()
    render(
      <MethodCriteriaTable
        methods={methods}
        criteria={criteria}
        blueprintPassCriteria={defaultBlueprintPass}
        blueprintWeight={defaultBlueprintWeight}
        onChange={onChange}
      />,
    )
    const p99Input = screen.getByDisplayValue('<25')
    fireEvent.change(p99Input, { target: { value: '<10' } })
    const call = onChange.mock.calls[0][0]
    expect(call.p99.pass_criteria).toBeUndefined()
    expect(call.p99.weight).toBe(2)
  })
})
