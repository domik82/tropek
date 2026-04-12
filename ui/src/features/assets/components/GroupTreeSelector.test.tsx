import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { GroupTreeSelector } from './GroupTreeSelector'
import type { AssetGroup, AssetGroupTree } from '@/features/assets'

const TS = new Date('2026-01-01T00:00:00Z')

const INFRA_GROUP: AssetGroup = {
  id: 'g1',
  name: 'infrastructure',
  displayName: 'Infrastructure',
  description: null,
  color: null,
  members: [],
  subgroups: [{ groupId: 'g2', groupName: 'production', weight: 1 }],
  createdAt: TS,
  updatedAt: TS,
}

const PRODUCTION_GROUP: AssetGroup = {
  id: 'g2',
  name: 'production',
  displayName: 'Production',
  description: null,
  color: null,
  members: [],
  subgroups: [],
  createdAt: TS,
  updatedAt: TS,
}

const TREE: AssetGroupTree = {
  topLevel: [INFRA_GROUP],
  allGroups: [INFRA_GROUP, PRODUCTION_GROUP],
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
      <GroupTreeSelector tree={TREE} value={null} onChange={() => {}} excludeName="infrastructure" />,
    )
    expect(screen.queryByText('Infrastructure')).not.toBeInTheDocument()
  })
})
