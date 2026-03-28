import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Server, Folder } from 'lucide-react'
import { TreeNode } from './TreeNode'

describe('TreeNode', () => {
  const defaults = {
    icon: Server,
    iconColor: '#8b949e',
    label: 'web-server-01',
    depth: 0,
    isExpandable: false,
    isExpanded: false,
    isSelected: false,
    onClick: vi.fn(),
  }

  it('renders label text', () => {
    render(<TreeNode {...defaults} />)
    expect(screen.getByText('web-server-01')).toBeInTheDocument()
  })

  it('renders icon', () => {
    const { container } = render(<TreeNode {...defaults} />)
    expect(container.querySelector('svg')).toBeTruthy()
  })

  it('shows chevron when expandable', () => {
    render(<TreeNode {...defaults} isExpandable />)
    expect(screen.getByLabelText('Toggle web-server-01')).toBeInTheDocument()
  })

  it('does not show chevron when not expandable', () => {
    render(<TreeNode {...defaults} />)
    expect(screen.queryByLabelText('Toggle web-server-01')).not.toBeInTheDocument()
  })

  it('rotates chevron when expanded', () => {
    const { container } = render(<TreeNode {...defaults} isExpandable isExpanded />)
    const chevron = container.querySelector('[data-testid="chevron"]')
    expect(chevron?.className).toContain('rotate-90')
  })

  it('calls onClick when label clicked', () => {
    const onClick = vi.fn()
    render(<TreeNode {...defaults} onClick={onClick} />)
    fireEvent.click(screen.getByText('web-server-01'))
    expect(onClick).toHaveBeenCalled()
  })

  it('calls onToggle when chevron clicked', () => {
    const onToggle = vi.fn()
    render(<TreeNode {...defaults} isExpandable onToggle={onToggle} />)
    fireEvent.click(screen.getByLabelText('Toggle web-server-01'))
    expect(onToggle).toHaveBeenCalled()
  })

  it('does not call onClick when chevron clicked', () => {
    const onClick = vi.fn()
    const onToggle = vi.fn()
    render(<TreeNode {...defaults} isExpandable onClick={onClick} onToggle={onToggle} />)
    fireEvent.click(screen.getByLabelText('Toggle web-server-01'))
    expect(onToggle).toHaveBeenCalled()
    expect(onClick).not.toHaveBeenCalled()
  })

  it('renders count badge', () => {
    render(<TreeNode {...defaults} badge={{ type: 'count', value: 7 }} />)
    expect(screen.getByText('7')).toBeInTheDocument()
  })

  it('renders version badge', () => {
    render(<TreeNode {...defaults} badge={{ type: 'version', value: 'v2' }} />)
    expect(screen.getByText('v2')).toBeInTheDocument()
  })

  it('applies selection border with selectionColor', () => {
    const { container } = render(
      <TreeNode {...defaults} isSelected selectionColor="#6897BB" />
    )
    const row = container.firstChild as HTMLElement
    expect(row.style.borderLeft).toBe('2px solid #6897BB')
  })

  it('indents by depth * 24px', () => {
    const { container } = render(<TreeNode {...defaults} depth={2} />)
    const row = container.firstChild as HTMLElement
    expect(row.style.paddingLeft).toBe('48px')
  })

  it('uses font-semibold when isGroup', () => {
    render(<TreeNode {...defaults} icon={Folder} isGroup />)
    const label = screen.getByText('web-server-01')
    expect(label.className).toContain('font-semibold')
  })

  it('uses font-normal when not isGroup', () => {
    render(<TreeNode {...defaults} />)
    const label = screen.getByText('web-server-01')
    expect(label.className).toContain('font-normal')
  })
})
