import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { RegistryTree } from './RegistryTree'
import type { TreeNode, SelectedNode } from './types'

describe('RegistryTree', () => {
  const nodes: TreeNode[] = [
    {
      id: 'slo:http-slo', name: 'http-slo', type: 'slo', badge: 'v3.1',
      children: [
        { id: 'sli:http-sli', name: 'http-sli', type: 'sli', badge: '3 indicators' },
      ],
    },
    { id: 'slo:db-slo', name: 'db-slo', type: 'slo', badge: 'v1.0' },
  ]

  it('renders root nodes', () => {
    render(<RegistryTree nodes={nodes} selected={null} onSelect={vi.fn()} />)
    expect(screen.getByText('http-slo')).toBeInTheDocument()
    expect(screen.getByText('db-slo')).toBeInTheDocument()
  })

  it('expands node on toggle click to show children', () => {
    render(<RegistryTree nodes={nodes} selected={null} onSelect={vi.fn()} />)
    fireEvent.click(screen.getByTestId('toggle-slo:http-slo'))
    expect(screen.getByText('http-sli')).toBeInTheDocument()
  })

  it('calls onSelect with node info on name click', () => {
    const onSelect = vi.fn()
    render(<RegistryTree nodes={nodes} selected={null} onSelect={onSelect} />)
    fireEvent.click(screen.getByText('http-slo'))
    expect(onSelect).toHaveBeenCalledWith({ type: 'slo', name: 'http-slo' })
  })

  it('highlights selected node', () => {
    const selected: SelectedNode = { type: 'slo', name: 'db-slo' }
    render(<RegistryTree nodes={nodes} selected={selected} onSelect={vi.fn()} />)
    const node = screen.getByTestId('node-slo:db-slo')
    expect(node).toHaveAttribute('data-selected', 'true')
  })

  it('shows badges', () => {
    render(<RegistryTree nodes={nodes} selected={null} onSelect={vi.fn()} />)
    expect(screen.getByText('v3.1')).toBeInTheDocument()
  })

  it('renders subtitle text below the node name', () => {
    const subtitleNodes: TreeNode[] = [
      { id: 'slo-group:g1', name: 'app-plugins', type: 'slo-group', badge: '30 SLOs', subtitle: 'via plugin-tpl' },
    ]
    render(<RegistryTree nodes={subtitleNodes} selected={null} onSelect={vi.fn()} />)
    expect(screen.getByText('app-plugins')).toBeInTheDocument()
    expect(screen.getByText('via plugin-tpl')).toBeInTheDocument()
  })
})
