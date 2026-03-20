import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { GroupTreeSelector } from './GroupTreeSelector'
import type { AssetGroupTree } from '@/features/assets/types'

const TREE: AssetGroupTree = {
  top_level: [
    {
      id: 'g1',
      name: 'infrastructure',
      display_name: 'Infrastructure',
      members: [],
      subgroups: [{ group_id: 'g2', group_name: 'production', weight: 1 }],
    },
  ],
  all_groups: [
    {
      id: 'g1',
      name: 'infrastructure',
      display_name: 'Infrastructure',
      members: [],
      subgroups: [{ group_id: 'g2', group_name: 'production', weight: 1 }],
    },
    {
      id: 'g2',
      name: 'production',
      display_name: 'Production',
      members: [],
      subgroups: [],
    },
  ],
}

describe('GroupTreeSelector', () => {
  it('renders "(top level)" option', () => {
    render(<GroupTreeSelector tree={TREE} value={null} onChange={() => {}} />)
    expect(screen.getByText(/top.level/i)).toBeInTheDocument()
  })

  it('renders group hierarchy', () => {
    render(<GroupTreeSelector tree={TREE} value={null} onChange={() => {}} />)
    expect(screen.getByText('Infrastructure')).toBeInTheDocument()
    expect(screen.getByText('Production')).toBeInTheDocument()
  })

  it('calls onChange with group name when clicked', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<GroupTreeSelector tree={TREE} value={null} onChange={onChange} />)
    await user.click(screen.getByText('Production'))
    expect(onChange).toHaveBeenCalledWith('production')
  })

  it('calls onChange with null when top-level is clicked', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<GroupTreeSelector tree={TREE} value="infrastructure" onChange={onChange} />)
    await user.click(screen.getByText(/top.level/i))
    expect(onChange).toHaveBeenCalledWith(null)
  })

  it('does not render excluded group', () => {
    render(
      <GroupTreeSelector tree={TREE} value={null} onChange={() => {}} excludeName="infrastructure" />
    )
    expect(screen.queryByText('Infrastructure')).not.toBeInTheDocument()
  })
})
