import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { TestWrapper } from '@/test-wrapper'
import { useAssetTreeActions } from './useAssetTreeActions'
import { useRemoveGroupMember, useDeleteAsset } from '@/features/assets/hooks'
import { useUpdateGroup } from '@/features/slos/hooks'

vi.mock('@/features/assets/hooks', () => ({
  useRemoveGroupMember: vi.fn(() => ({ mutate: vi.fn() })),
  useDeleteAsset: vi.fn(() => ({ mutate: vi.fn() })),
}))

vi.mock('@/features/slos/hooks', () => ({
  useUpdateGroup: vi.fn(() => ({ mutate: vi.fn() })),
}))

const defaultCallbacks = {
  onCreateGroup: vi.fn(),
  onEditGroup: vi.fn(),
  onDeleteGroup: vi.fn(),
  onAddSloLink: vi.fn(),
  onAddAssetToGroup: vi.fn(),
  onEditAsset: vi.fn(),
  onStartRename: vi.fn(),
  onSelectAsset: vi.fn(),
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useRemoveGroupMember).mockReturnValue({ mutate: vi.fn() } as any)
  vi.mocked(useDeleteAsset).mockReturnValue({ mutate: vi.fn() } as any)
  vi.mocked(useUpdateGroup).mockReturnValue({ mutate: vi.fn() } as any)
})

describe('useAssetTreeActions', () => {
  it("dispatch 'rename' calls onStartRename with target name", () => {
    const { result } = renderHook(
      () => useAssetTreeActions('navigator', defaultCallbacks),
      { wrapper: TestWrapper },
    )
    result.current.dispatch('rename', { type: 'group', name: 'payments' })
    expect(defaultCallbacks.onStartRename).toHaveBeenCalledWith('payments')
  })

  it("dispatch 'removeFromGroup' calls removeMember.mutate with { groupName, assetId }", () => {
    const mockMutate = vi.fn()
    vi.mocked(useRemoveGroupMember).mockReturnValue({ mutate: mockMutate } as any)

    const { result } = renderHook(
      () => useAssetTreeActions('navigator', defaultCallbacks),
      { wrapper: TestWrapper },
    )
    result.current.dispatch('removeFromGroup', {
      type: 'asset',
      name: 'cart',
      groupName: 'payments',
      assetId: 'a1',
    })
    expect(mockMutate).toHaveBeenCalledWith({ groupName: 'payments', assetId: 'a1' })
  })

  it("dispatch 'deleteAsset' calls deleteAsset.mutate with target name", () => {
    const mockMutate = vi.fn()
    vi.mocked(useDeleteAsset).mockReturnValue({ mutate: mockMutate } as any)

    const { result } = renderHook(
      () => useAssetTreeActions('navigator', defaultCallbacks),
      { wrapper: TestWrapper },
    )
    result.current.dispatch('deleteAsset', { type: 'asset', name: 'cart-service' })
    expect(mockMutate).toHaveBeenCalledWith('cart-service')
  })

  it.each([
    ['editDetails', 'onEditGroup', 'group', 'payments'],
    ['addSubgroup', 'onCreateGroup', 'group', 'payments'],
    ['linkSlo', 'onAddSloLink', 'group', 'payments'],
    ['addAssetToGroup', 'onAddAssetToGroup', 'group', 'payments'],
    ['editAsset', 'onEditAsset', 'asset', 'cart-service'],
  ] as const)(
    "dispatch '%s' calls %s with target name",
    (action, callbackKey, nodeType, name) => {
      const { result } = renderHook(
        () => useAssetTreeActions('navigator', defaultCallbacks),
        { wrapper: TestWrapper },
      )
      result.current.dispatch(action, { type: nodeType, name })
      expect(defaultCallbacks[callbackKey]).toHaveBeenCalledWith(name)
    },
  )

  it("dispatch 'viewEvaluations' calls onSelectAsset with target name and group name", () => {
    const { result } = renderHook(
      () => useAssetTreeActions('navigator', defaultCallbacks),
      { wrapper: TestWrapper },
    )
    result.current.dispatch('viewEvaluations', { type: 'asset', name: 'cart-service', groupName: 'payments' })
    expect(defaultCallbacks.onSelectAsset).toHaveBeenCalledWith('cart-service', 'payments')
  })

  it('handleRename calls updateGroup.mutate with { name, display_name }', () => {
    const mockMutate = vi.fn()
    vi.mocked(useUpdateGroup).mockReturnValue({ mutate: mockMutate } as any)

    const { result } = renderHook(
      () => useAssetTreeActions('navigator', defaultCallbacks),
      { wrapper: TestWrapper },
    )
    result.current.handleRename('payments', 'Payments Team')
    expect(mockMutate).toHaveBeenCalledWith({ name: 'payments', display_name: 'Payments Team' })
  })

  it.each(['moveGroup', 'duplicateGroup'])(
    "dispatch '%s' does not throw (no-op)",
    (action) => {
      const { result } = renderHook(
        () => useAssetTreeActions('navigator', defaultCallbacks),
        { wrapper: TestWrapper },
      )
      expect(() =>
        result.current.dispatch(action, { type: 'group', name: 'payments' }),
      ).not.toThrow()
    },
  )
})
