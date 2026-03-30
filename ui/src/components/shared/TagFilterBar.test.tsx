import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TagFilterBar } from './TagFilterBar'
import type { TagFilter } from '@/features/registry'

describe('TagFilterBar', () => {
  const defaultProps = {
    search: '',
    onSearchChange: vi.fn(),
    tags: [] as TagFilter[],
    onTagsChange: vi.fn(),
    tagKeySuggestions: [
      { key: 'env', count: 5 },
      { key: 'team', count: 3 },
    ],
    tagValueSuggestions: [{ value: 'prod', count: 4 }],
    onTagKeySelected: vi.fn(),
    isLoadingKeys: false,
    isLoadingValues: false,
  }

  it('renders search input with placeholder', () => {
    render(<TagFilterBar {...defaultProps} />)
    expect(screen.getByPlaceholderText('Filter...')).toBeInTheDocument()
  })

  it('calls onSearchChange when typing', () => {
    render(<TagFilterBar {...defaultProps} />)
    fireEvent.change(screen.getByPlaceholderText('Filter...'), { target: { value: 'http' } })
    expect(defaultProps.onSearchChange).toHaveBeenCalledWith('http')
  })

  it('renders active tag pills with remove button', () => {
    const tags = [{ key: 'env', value: 'prod' }]
    render(<TagFilterBar {...defaultProps} tags={tags} />)
    expect(screen.getByText('env')).toBeInTheDocument()
    expect(screen.getByText('prod')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /remove/i })).toBeInTheDocument()
  })

  it('removes tag when x clicked', () => {
    const tags = [
      { key: 'env', value: 'prod' },
      { key: 'team', value: 'core' },
    ]
    const onChange = vi.fn()
    render(<TagFilterBar {...defaultProps} tags={tags} onTagsChange={onChange} />)
    const removeButtons = screen.getAllByRole('button', { name: /remove/i })
    fireEvent.click(removeButtons[0])
    expect(onChange).toHaveBeenCalledWith([{ key: 'team', value: 'core' }])
  })

  it('clicking Add tag filter shows key suggestions', () => {
    render(<TagFilterBar {...defaultProps} />)
    fireEvent.click(screen.getByText('Add tag filter'))
    expect(screen.getByText('Select tag key:')).toBeInTheDocument()
    expect(screen.getByText('env')).toBeInTheDocument()
    expect(screen.getByText('team')).toBeInTheDocument()
  })

  it('clicking a key suggestion calls onTagKeySelected and advances to value step', () => {
    const onTagKeySelected = vi.fn()
    render(<TagFilterBar {...defaultProps} onTagKeySelected={onTagKeySelected} />)
    fireEvent.click(screen.getByText('Add tag filter'))
    fireEvent.click(screen.getByText('env'))
    expect(onTagKeySelected).toHaveBeenCalledWith('env')
    expect(screen.getByText(/Select value for/)).toBeInTheDocument()
  })

  it('clicking a value suggestion adds a pill and returns to idle', () => {
    const onTagsChange = vi.fn()
    const onTagKeySelected = vi.fn()
    render(
      <TagFilterBar
        {...defaultProps}
        onTagsChange={onTagsChange}
        onTagKeySelected={onTagKeySelected}
      />,
    )
    fireEvent.click(screen.getByText('Add tag filter'))
    fireEvent.click(screen.getByText('env'))
    fireEvent.click(screen.getByText('prod'))
    expect(onTagsChange).toHaveBeenCalledWith([{ key: 'env', value: 'prod' }])
    expect(screen.getByText('Add tag filter')).toBeInTheDocument()
  })

  it('pressing Escape during add flow resets to idle', () => {
    render(<TagFilterBar {...defaultProps} />)
    fireEvent.click(screen.getByText('Add tag filter'))
    expect(screen.getByText('Select tag key:')).toBeInTheDocument()
    fireEvent.keyDown(screen.getByText('Select tag key:'), { key: 'Escape' })
    expect(screen.getByText('Add tag filter')).toBeInTheDocument()
  })

  it('does not add duplicate tag', () => {
    const existingTags = [{ key: 'env', value: 'prod' }]
    const onTagsChange = vi.fn()
    const onTagKeySelected = vi.fn()
    render(
      <TagFilterBar
        {...defaultProps}
        tags={existingTags}
        onTagsChange={onTagsChange}
        onTagKeySelected={onTagKeySelected}
      />,
    )
    fireEvent.click(screen.getByText('Add tag filter'))
    // Key suggestion button contains "env" + "(5)" as children
    fireEvent.click(screen.getByRole('button', { name: /env/ }))
    // Value suggestion button contains "prod" + "(4)" as children
    fireEvent.click(screen.getByRole('button', { name: /prod/ }))
    expect(onTagsChange).not.toHaveBeenCalled()
    expect(screen.getByText('Add tag filter')).toBeInTheDocument()
  })
})
