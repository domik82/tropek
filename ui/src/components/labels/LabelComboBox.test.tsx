import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { LabelComboBox } from './LabelComboBox'

describe('LabelComboBox', () => {
  it('renders input with placeholder', () => {
    render(
      <LabelComboBox
        value=""
        onChange={vi.fn()}
        suggestions={[]}
        placeholder="Pick a key"
      />
    )
    expect(screen.getByPlaceholderText('Pick a key')).toBeInTheDocument()
  })

  it('typing filters suggestions', async () => {
    const user = userEvent.setup()
    const suggestions = [
      { value: 'env', count: 1 },
      { value: 'team', count: 2 },
      { value: 'region', count: 3 },
    ]
    const onChange = vi.fn()
    const { rerender } = render(
      <LabelComboBox value="" onChange={onChange} suggestions={suggestions} />
    )

    const input = screen.getByRole('textbox')
    await user.click(input)
    await user.type(input, 'te')

    // Simulate controlled component: update value prop as user types
    rerender(
      <LabelComboBox value="te" onChange={onChange} suggestions={suggestions} />
    )

    expect(screen.getByText('team')).toBeInTheDocument()
    expect(screen.queryByText('region')).not.toBeInTheDocument()
  })

  it('clicking suggestion calls onChange', async () => {
    const user = userEvent.setup()
    const suggestions = [
      { value: 'env', count: 5 },
      { value: 'team', count: 3 },
    ]
    const onChange = vi.fn()
    render(
      <LabelComboBox value="" onChange={onChange} suggestions={suggestions} />
    )

    const input = screen.getByRole('textbox')
    await user.click(input)

    const envButton = screen.getByText('env')
    await user.pointer({ keys: '[MouseLeft>]', target: envButton })

    expect(onChange).toHaveBeenCalledWith('env')
  })

  it('shows "Create new" option for novel input', async () => {
    const user = userEvent.setup()
    const suggestions = [
      { value: 'env', count: 1 },
      { value: 'team', count: 2 },
    ]
    const onChange = vi.fn()
    const { rerender } = render(
      <LabelComboBox value="" onChange={onChange} suggestions={suggestions} />
    )

    const input = screen.getByRole('textbox')
    await user.click(input)
    await user.type(input, 'custom')

    rerender(
      <LabelComboBox value="custom" onChange={onChange} suggestions={suggestions} />
    )

    expect(screen.getByText(/create.*custom/i)).toBeInTheDocument()
  })
})
