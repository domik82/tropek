import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AggregatedModeFields } from './AggregatedModeFields'

const defaultProps = {
  queryTemplate: '',
  interval: '1m',
  methods: [] as string[],
  onQueryTemplateChange: vi.fn(),
  onIntervalChange: vi.fn(),
  onMethodsChange: vi.fn(),
}

describe('AggregatedModeFields', () => {
  it('renders query template input', () => {
    render(<AggregatedModeFields {...defaultProps} />)
    expect(screen.getByLabelText('Query Template')).toBeInTheDocument()
  })

  it('renders interval selector with presets', () => {
    render(<AggregatedModeFields {...defaultProps} />)
    expect(screen.getByLabelText('Interval')).toBeInTheDocument()
    expect(screen.getByText('1m')).toBeInTheDocument()
    expect(screen.getByText('5m')).toBeInTheDocument()
    expect(screen.getByText('15m')).toBeInTheDocument()
  })

  it('renders method checkboxes', () => {
    render(<AggregatedModeFields {...defaultProps} />)
    expect(screen.getByLabelText('Mean')).toBeInTheDocument()
    expect(screen.getByLabelText('P99')).toBeInTheDocument()
    expect(screen.getByLabelText('Max')).toBeInTheDocument()
  })

  it('calls onQueryTemplateChange when template is typed', () => {
    const onChange = vi.fn()
    render(<AggregatedModeFields {...defaultProps} onQueryTemplateChange={onChange} />)
    fireEvent.change(screen.getByLabelText('Query Template'), {
      target: { value: 'rate(cpu[$interval])' },
    })
    expect(onChange).toHaveBeenCalledWith('rate(cpu[$interval])')
  })

  it('calls onMethodsChange when a method is toggled on', () => {
    const onChange = vi.fn()
    render(<AggregatedModeFields {...defaultProps} onMethodsChange={onChange} />)
    fireEvent.click(screen.getByLabelText('Mean'))
    expect(onChange).toHaveBeenCalledWith(['mean'])
  })

  it('calls onMethodsChange when a method is toggled off', () => {
    const onChange = vi.fn()
    render(
      <AggregatedModeFields
        {...defaultProps}
        methods={['mean', 'p99']}
        onMethodsChange={onChange}
      />,
    )
    fireEvent.click(screen.getByLabelText('Mean'))
    expect(onChange).toHaveBeenCalledWith(['p99'])
  })

  it('shows pre-selected methods as checked', () => {
    render(<AggregatedModeFields {...defaultProps} methods={['mean', 'max']} />)
    expect(screen.getByLabelText('Mean')).toBeChecked()
    expect(screen.getByLabelText('Max')).toBeChecked()
    expect(screen.getByLabelText('P99')).not.toBeChecked()
  })

  it('interval preset buttons update the interval value', () => {
    const onChange = vi.fn()
    render(<AggregatedModeFields {...defaultProps} onIntervalChange={onChange} />)
    fireEvent.click(screen.getByText('5m'))
    expect(onChange).toHaveBeenCalledWith('5m')
  })

  it('supports custom interval via text input', () => {
    const onChange = vi.fn()
    render(<AggregatedModeFields {...defaultProps} onIntervalChange={onChange} />)
    fireEvent.change(screen.getByLabelText('Interval'), {
      target: { value: '30s' },
    })
    expect(onChange).toHaveBeenCalledWith('30s')
  })
})
