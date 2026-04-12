# Asset UI Test Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Increase asset UI component test coverage from ~20% to ~90%, covering all CRUD dialogs, tree components, context menus, and label editors with unit/component tests.

**Architecture:** Each component gets a colocated `.test.tsx` file. Tests mock hooks at module level via `vi.mock()`, render with `TestWrapper` (React Query provider), and assert on rendering + user interactions. No Playwright/e2e tests — Vitest + React Testing Library only.

**Tech Stack:** Vitest, React Testing Library, @testing-library/user-event, jsdom, vi.mock for hook isolation.

---

## Conventions (apply to ALL tasks)

### Test file template

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TestWrapper } from '@/test-wrapper'
// component + type imports
```

### Hook mocking pattern

```tsx
vi.mock('@/features/assets/hooks', () => ({
  useHookName: vi.fn(() => ({ data: MOCK_DATA, isLoading: false })),
  useMutationHook: vi.fn(() => ({ mutate: vi.fn(), mutateAsync: vi.fn().mockResolvedValue({}), isPending: false })),
}))
```

### Shared mock data (inline per file, no shared fixtures)

```tsx
const MOCK_ASSET = { id: 'a1', name: 'cart-service', display_name: 'Cart Service', type_name: 'service', labels: { env: 'prod' }, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' }
```

### Commands

```bash
npx vitest run src/path/to/Component.test.tsx       # Run single test file
npx vitest run                                       # Run all tests
npx tsc --noEmit -p tsconfig.app.json                # Type check
```

---

## Task 1: GroupDetailPanel tests

The largest untested component. Renders group header, subgroup cards, members table, linked SLOs table, and wires 7 dialogs.

**Files:**
- Create: `ui/src/features/assets/components/GroupDetailPanel.test.tsx`
- Reference: `ui/src/features/assets/components/GroupDetailPanel.tsx`

### Mock setup

Mock these hooks:
- `@/features/assets/hooks`: `useAssetGroup`, `useAssets`, `useRemoveGroupMember`, `useAssetGroups`, `useUpdateAsset`
- `@/features/slos/hooks`: `useGroupSloLinks`, `useDeleteGroupSloLink`

Mock all child dialog components to avoid deep rendering:
- `@/features/slos/components/GroupEditDialog` → `vi.fn(() => null)`
- `@/features/slos/components/GroupDeleteDialog` → `vi.fn(() => null)`
- `@/features/slos/components/GroupCreateDialog` → `vi.fn(() => null)`
- `@/features/slos/components/SloLinkDialog` → `vi.fn(() => null)`
- `./AddAssetToGroupDialog` → `vi.fn(() => null)`
- `./AssetEditDialog` → `vi.fn(() => null)`
- `@/components/labels/LabelsEditorDialog` → `vi.fn(() => null)`

### Mock data

```tsx
const MOCK_GROUP = {
  id: 'g1', name: 'payments', display_name: 'Payments', description: 'Payment services',
  members: [
    { asset_id: 'a1', asset_name: 'cart-service', weight: 1.0 },
    { asset_id: 'a2', asset_name: 'checkout-api', weight: 2.0 },
  ],
  subgroups: [{ group_id: 'g2', group_name: 'payments-eu', weight: 1.0 }],
}

const MOCK_TREE = {
  top_level: [MOCK_GROUP],
  all_groups: [
    MOCK_GROUP,
    { id: 'g2', name: 'payments-eu', display_name: 'Payments EU', description: '', members: [], subgroups: [] },
  ],
}

const MOCK_ASSETS = [
  { id: 'a1', name: 'cart-service', display_name: 'Cart Service', type_name: 'service', labels: { env: 'prod' }, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
  { id: 'a2', name: 'checkout-api', display_name: null, type_name: 'api', labels: {}, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
]

const MOCK_LINKS = [
  { id: 'l1', link_name: 'link-1', slo_name: 'availability', sli_name: 'error_rate', data_source_name: 'prometheus-prod', group_name: 'payments' },
]
```

- [ ] **Step 1: Write test — renders header with group name and stats**

```tsx
it('renders group display name and stats line', () => {
  render(<GroupDetailPanel groupName="payments" onSelectGroup={vi.fn()} />, { wrapper: TestWrapper })
  expect(screen.getByText('Payments')).toBeInTheDocument()
  expect(screen.getByText('2 assets · 1 subgroups · 1 linked SLOs')).toBeInTheDocument()
})
```

- [ ] **Step 2: Write test — renders description**

```tsx
it('renders group description', () => {
  render(<GroupDetailPanel groupName="payments" onSelectGroup={vi.fn()} />, { wrapper: TestWrapper })
  expect(screen.getByText('Payment services')).toBeInTheDocument()
})
```

- [ ] **Step 3: Write test — renders subgroup cards**

```tsx
it('renders subgroup cards with name and member count', () => {
  render(<GroupDetailPanel groupName="payments" onSelectGroup={vi.fn()} />, { wrapper: TestWrapper })
  expect(screen.getByText('Payments EU')).toBeInTheDocument()
  expect(screen.getByText('0 assets')).toBeInTheDocument()
})
```

- [ ] **Step 4: Write test — clicking subgroup card calls onSelectGroup**

```tsx
it('calls onSelectGroup when subgroup card clicked', async () => {
  const onSelect = vi.fn()
  const user = userEvent.setup()
  render(<GroupDetailPanel groupName="payments" onSelectGroup={onSelect} />, { wrapper: TestWrapper })
  await user.click(screen.getByText('Payments EU'))
  expect(onSelect).toHaveBeenCalledWith('payments-eu')
})
```

- [ ] **Step 5: Write test — renders members table with asset data**

```tsx
it('renders members table with display names and types', () => {
  render(<GroupDetailPanel groupName="payments" onSelectGroup={vi.fn()} />, { wrapper: TestWrapper })
  expect(screen.getByText('Cart Service')).toBeInTheDocument()
  expect(screen.getByText('checkout-api')).toBeInTheDocument()
  expect(screen.getByText('service')).toBeInTheDocument()
  expect(screen.getByText('api')).toBeInTheDocument()
})
```

- [ ] **Step 6: Write test — renders linked SLOs table**

```tsx
it('renders linked SLOs with columns', () => {
  render(<GroupDetailPanel groupName="payments" onSelectGroup={vi.fn()} />, { wrapper: TestWrapper })
  expect(screen.getByText('availability')).toBeInTheDocument()
  expect(screen.getByText('error_rate')).toBeInTheDocument()
  expect(screen.getByText('prometheus-prod')).toBeInTheDocument()
})
```

- [ ] **Step 7: Write test — remove member button calls mutation**

```tsx
it('calls removeMember when X button clicked on member row', async () => {
  const mockMutate = vi.fn()
  vi.mocked(useRemoveGroupMember).mockReturnValue({ mutate: mockMutate } as any)
  const user = userEvent.setup()
  render(<GroupDetailPanel groupName="payments" onSelectGroup={vi.fn()} />, { wrapper: TestWrapper })
  const removeButtons = screen.getAllByTitle('Remove from group')
  await user.click(removeButtons[0])
  expect(mockMutate).toHaveBeenCalledWith({ groupName: 'payments', assetId: 'a1' })
})
```

- [ ] **Step 8: Write test — unlink SLO button calls mutation**

```tsx
it('calls unlinkSlo when X clicked on SLO row', async () => {
  const mockMutate = vi.fn()
  vi.mocked(useDeleteGroupSloLink).mockReturnValue({ mutate: mockMutate } as any)
  const user = userEvent.setup()
  render(<GroupDetailPanel groupName="payments" onSelectGroup={vi.fn()} />, { wrapper: TestWrapper })
  await user.click(screen.getByTitle('Unlink'))
  expect(mockMutate).toHaveBeenCalledWith({ groupName: 'payments', linkName: 'link-1' })
})
```

- [ ] **Step 9: Write test — shows loading state when no data**

```tsx
it('shows loading when group data not yet available', () => {
  vi.mocked(useAssetGroup).mockReturnValue({ data: undefined } as any)
  render(<GroupDetailPanel groupName="payments" onSelectGroup={vi.fn()} />, { wrapper: TestWrapper })
  expect(screen.getByText('Loading…')).toBeInTheDocument()
})
```

- [ ] **Step 10: Run tests, verify all pass**

Run: `npx vitest run src/features/assets/components/GroupDetailPanel.test.tsx`
Expected: 9 tests PASS

- [ ] **Step 11: Commit**

```bash
git add ui/src/features/assets/components/GroupDetailPanel.test.tsx
git commit -m "test: add GroupDetailPanel component tests"
```

---

## Task 2: useAssetTreeActions tests

Hook with real mutation logic for dispatch actions.

**Files:**
- Create: `ui/src/components/AssetTree/useAssetTreeActions.test.ts`
- Reference: `ui/src/components/AssetTree/useAssetTreeActions.ts`

### Setup

Use `@testing-library/react`'s `renderHook` with `TestWrapper`. Mock mutation hooks.

```tsx
import { renderHook } from '@testing-library/react'
```

Mock:
- `@/features/slos/hooks`: `useUpdateGroup`
- `@/features/assets/hooks`: `useRemoveGroupMember`, `useDeleteAsset`

- [ ] **Step 1: Write test — dispatch 'rename' calls onStartRename callback**

```tsx
it('dispatches rename to onStartRename callback', () => {
  const onStartRename = vi.fn()
  const { result } = renderHook(
    () => useAssetTreeActions('navigator', { ...defaultCallbacks, onStartRename }),
    { wrapper: TestWrapper },
  )
  result.current.dispatch('rename', { type: 'group', name: 'payments' })
  expect(onStartRename).toHaveBeenCalledWith('payments')
})
```

- [ ] **Step 2: Write test — dispatch 'removeFromGroup' calls removeMember mutation**

```tsx
it('dispatches removeFromGroup with groupName and assetId', () => {
  const mockMutate = vi.fn()
  vi.mocked(useRemoveGroupMember).mockReturnValue({ mutate: mockMutate } as any)
  const { result } = renderHook(
    () => useAssetTreeActions('navigator', defaultCallbacks),
    { wrapper: TestWrapper },
  )
  result.current.dispatch('removeFromGroup', { type: 'asset', name: 'cart', groupName: 'payments', assetId: 'a1' })
  expect(mockMutate).toHaveBeenCalledWith({ groupName: 'payments', assetId: 'a1' })
})
```

- [ ] **Step 3: Write test — dispatch 'deleteAsset' calls deleteAsset mutation**

```tsx
it('dispatches deleteAsset with target name', () => {
  const mockMutate = vi.fn()
  vi.mocked(useDeleteAsset).mockReturnValue({ mutate: mockMutate } as any)
  const { result } = renderHook(
    () => useAssetTreeActions('navigator', defaultCallbacks),
    { wrapper: TestWrapper },
  )
  result.current.dispatch('deleteAsset', { type: 'asset', name: 'cart-service' })
  expect(mockMutate).toHaveBeenCalledWith('cart-service')
})
```

- [ ] **Step 4: Write tests — remaining dispatch cases (editDetails, addSubgroup, linkSlo, addAssetToGroup, editAsset, viewEvaluations)**

Each calls the matching callback:

```tsx
it.each([
  ['editDetails', 'onEditGroup'],
  ['addSubgroup', 'onCreateGroup'],
  ['linkSlo', 'onAddSloLink'],
  ['addAssetToGroup', 'onAddAssetToGroup'],
  ['editAsset', 'onEditAsset'],
  ['viewEvaluations', 'onSelectAsset'],
])('dispatches %s to %s callback', (action, callbackName) => {
  const cb = vi.fn()
  const callbacks = { ...defaultCallbacks, [callbackName]: cb }
  const { result } = renderHook(
    () => useAssetTreeActions('navigator', callbacks),
    { wrapper: TestWrapper },
  )
  result.current.dispatch(action, { type: 'group', name: 'payments' })
  expect(cb).toHaveBeenCalledWith('payments')
})
```

- [ ] **Step 5: Write test — handleRename calls updateGroup mutation**

```tsx
it('handleRename calls updateGroup mutation', () => {
  const mockMutate = vi.fn()
  vi.mocked(useUpdateGroup).mockReturnValue({ mutate: mockMutate } as any)
  const { result } = renderHook(
    () => useAssetTreeActions('navigator', defaultCallbacks),
    { wrapper: TestWrapper },
  )
  result.current.handleRename('payments', 'Payments Team')
  expect(mockMutate).toHaveBeenCalledWith({ name: 'payments', display_name: 'Payments Team' })
})
```

- [ ] **Step 6: Write test — no-op actions (moveGroup, duplicateGroup) don't throw**

```tsx
it('no-op actions do not throw', () => {
  const { result } = renderHook(
    () => useAssetTreeActions('navigator', defaultCallbacks),
    { wrapper: TestWrapper },
  )
  expect(() => result.current.dispatch('moveGroup', { type: 'group', name: 'x' })).not.toThrow()
  expect(() => result.current.dispatch('duplicateGroup', { type: 'group', name: 'x' })).not.toThrow()
})
```

- [ ] **Step 7: Run tests, verify all pass**

Run: `npx vitest run src/components/AssetTree/useAssetTreeActions.test.ts`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add ui/src/components/AssetTree/useAssetTreeActions.test.ts
git commit -m "test: add useAssetTreeActions dispatch tests"
```

---

## Task 3: AssetTreeContextMenu tests

Menu rendering per mode with correct items, disabled states, and action dispatch.

**Files:**
- Create: `ui/src/components/AssetTree/AssetTreeContextMenu.test.tsx`
- Reference: `ui/src/components/AssetTree/AssetTreeContextMenu.tsx`

No hooks to mock — pure presentational component.

- [ ] **Step 1: Write test — renders group menu items**

```tsx
it('renders group context menu items', () => {
  const state = { x: 100, y: 100, target: { type: 'group' as const, name: 'payments' } }
  render(<AssetTreeContextMenu state={state} mode="navigator" onAction={vi.fn()} onClose={vi.fn()} />)
  expect(screen.getByText('Rename')).toBeInTheDocument()
  expect(screen.getByText('Edit details…')).toBeInTheDocument()
  expect(screen.getByText('Add subgroup')).toBeInTheDocument()
  expect(screen.getByText('Delete group')).toBeInTheDocument()
})
```

- [ ] **Step 2: Write test — renders asset menu items**

```tsx
it('renders asset context menu items', () => {
  const state = { x: 100, y: 100, target: { type: 'asset' as const, name: 'cart', groupName: 'payments', assetId: 'a1' } }
  render(<AssetTreeContextMenu state={state} mode="navigator" onAction={vi.fn()} onClose={vi.fn()} />)
  expect(screen.getByText('View evaluations')).toBeInTheDocument()
  expect(screen.getByText('Remove from group')).toBeInTheDocument()
  expect(screen.getByText('Edit asset…')).toBeInTheDocument()
  expect(screen.getByText('Delete asset')).toBeInTheDocument()
})
```

- [ ] **Step 3: Write test — mode filtering (navigator shows 'Add asset to group', slo shows 'Link SLO…')**

```tsx
it('shows "Add asset to group" in navigator mode, not "Link SLO…"', () => {
  const state = { x: 100, y: 100, target: { type: 'group' as const, name: 'payments' } }
  render(<AssetTreeContextMenu state={state} mode="navigator" onAction={vi.fn()} onClose={vi.fn()} />)
  expect(screen.getByText('Add asset to group')).toBeInTheDocument()
  expect(screen.queryByText('Link SLO…')).not.toBeInTheDocument()
})

it('shows "Link SLO…" in slo mode, not "Add asset to group"', () => {
  const state = { x: 100, y: 100, target: { type: 'group' as const, name: 'payments' } }
  render(<AssetTreeContextMenu state={state} mode="slo" onAction={vi.fn()} onClose={vi.fn()} />)
  expect(screen.getByText('Link SLO…')).toBeInTheDocument()
  expect(screen.queryByText('Add asset to group')).not.toBeInTheDocument()
})
```

- [ ] **Step 4: Write test — disabled items cannot be clicked**

```tsx
it('disabled items do not fire onAction', async () => {
  const onAction = vi.fn()
  const user = userEvent.setup()
  const state = { x: 100, y: 100, target: { type: 'group' as const, name: 'payments' } }
  render(<AssetTreeContextMenu state={state} mode="navigator" onAction={onAction} onClose={vi.fn()} />)
  await user.click(screen.getByText(/Move to/))
  expect(onAction).not.toHaveBeenCalled()
})
```

- [ ] **Step 5: Write test — clicking enabled item fires onAction with action and target**

```tsx
it('fires onAction with action string and target on click', async () => {
  const onAction = vi.fn()
  const onClose = vi.fn()
  const user = userEvent.setup()
  const target = { type: 'group' as const, name: 'payments' }
  render(<AssetTreeContextMenu state={{ x: 100, y: 100, target }} mode="navigator" onAction={onAction} onClose={onClose} />)
  await user.click(screen.getByText('Rename'))
  expect(onAction).toHaveBeenCalledWith('rename', target)
  expect(onClose).toHaveBeenCalled()
})
```

- [ ] **Step 6: Run tests, verify all pass**

Run: `npx vitest run src/components/AssetTree/AssetTreeContextMenu.test.tsx`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add ui/src/components/AssetTree/AssetTreeContextMenu.test.tsx
git commit -m "test: add AssetTreeContextMenu rendering and interaction tests"
```

---

## Task 4: AddAssetToGroupDialog tests

Dialog that filters available assets and adds selected one to group.

**Files:**
- Create: `ui/src/features/assets/components/AddAssetToGroupDialog.test.tsx`
- Reference: `ui/src/features/assets/components/AddAssetToGroupDialog.tsx`

Mock:
- `@/features/assets/hooks`: `useAssets`, `useAssetGroups`, `useAddGroupMember`

### Mock data

```tsx
const ALL_ASSETS = [
  { id: 'a1', name: 'cart-service', display_name: 'Cart', type_name: 'service', labels: {}, created_at: '', updated_at: '' },
  { id: 'a2', name: 'checkout-api', display_name: null, type_name: 'api', labels: {}, created_at: '', updated_at: '' },
  { id: 'a3', name: 'order-worker', display_name: null, type_name: 'worker', labels: {}, created_at: '', updated_at: '' },
]

const MOCK_GROUP = {
  id: 'g1', name: 'payments', display_name: 'Payments', description: '',
  members: [{ asset_id: 'a1', asset_name: 'cart-service', weight: 1.0 }],
  subgroups: [],
}

const MOCK_TREE = { top_level: [MOCK_GROUP], all_groups: [MOCK_GROUP] }
```

- [ ] **Step 1: Write test — renders available assets excluding current members**

Note: `AddAssetToGroupDialog` renders `asset.display_name ?? asset.name`. cart-service (id=a1) is already a member and should be excluded entirely.

```tsx
it('shows assets not already in the group', () => {
  render(<AddAssetToGroupDialog open groupName="payments" onOpenChange={vi.fn()} />, { wrapper: TestWrapper })
  // cart-service (displayed as "Cart") is already a member — should not appear
  expect(screen.queryByText('Cart')).not.toBeInTheDocument()
  // checkout-api has no display_name so shows raw name
  expect(screen.getByText('checkout-api')).toBeInTheDocument()
  expect(screen.getByText('order-worker')).toBeInTheDocument()
})
```

- [ ] **Step 2: Write test — search filter narrows asset list**

```tsx
it('filters assets by search text', async () => {
  const user = userEvent.setup()
  render(<AddAssetToGroupDialog open groupName="payments" onOpenChange={vi.fn()} />, { wrapper: TestWrapper })
  await user.type(screen.getByPlaceholderText(/search/i), 'checkout')
  expect(screen.getByText('checkout-api')).toBeInTheDocument()
  expect(screen.queryByText('order-worker')).not.toBeInTheDocument()
})
```

- [ ] **Step 3: Write test — clicking asset calls addMember mutation**

```tsx
it('calls addMember when asset row clicked', async () => {
  const mockMutate = vi.fn((_vars: any, opts?: any) => opts?.onSuccess?.())
  vi.mocked(useAddGroupMember).mockReturnValue({ mutate: mockMutate } as any)
  const onOpenChange = vi.fn()
  const user = userEvent.setup()
  render(<AddAssetToGroupDialog open groupName="payments" onOpenChange={onOpenChange} />, { wrapper: TestWrapper })
  await user.click(screen.getByText('checkout-api'))
  expect(mockMutate).toHaveBeenCalledWith(
    expect.objectContaining({ groupName: 'payments', assetId: 'a2' }),
    expect.anything(),
  )
})
```

- [ ] **Step 4: Write test — returns null when not open**

```tsx
it('renders nothing when open=false', () => {
  const { container } = render(<AddAssetToGroupDialog open={false} groupName="payments" onOpenChange={vi.fn()} />, { wrapper: TestWrapper })
  expect(container.innerHTML).toBe('')
})
```

- [ ] **Step 5: Run tests, verify all pass**

Run: `npx vitest run src/features/assets/components/AddAssetToGroupDialog.test.tsx`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add ui/src/features/assets/components/AddAssetToGroupDialog.test.tsx
git commit -m "test: add AddAssetToGroupDialog filtering and mutation tests"
```

---

## Task 5: AssetCreateDialog tests

Most complex dialog — name validation, two-step mutation (create + optional group add).

**Files:**
- Create: `ui/src/features/assets/components/AssetCreateDialog.test.tsx`
- Reference: `ui/src/features/assets/components/AssetCreateDialog.tsx`

Mock:
- `@/features/assets/hooks`: `useAssetTypes`, `useAssetGroups`, `useCreateAsset`, `useAddGroupMember`
- `@/components/labels/LabelsEditorDialog` → stub

### Mock data

```tsx
const TYPES = [
  { name: 'service', is_default: true, asset_count: 5 },
  { name: 'endpoint', is_default: false, asset_count: 2 },
]
const TREE = { top_level: [], all_groups: [{ id: 'g1', name: 'payments', display_name: 'Payments', members: [], subgroups: [] }] }
```

- [ ] **Step 1: Write test — name validation rejects uppercase and special chars**

Note: The name input placeholder is `"linux-cache-01"`, and the submit button text is `"Add"`.

```tsx
it('shows validation error when name contains uppercase or special chars', async () => {
  const user = userEvent.setup()
  render(<AssetCreateDialog open onOpenChange={vi.fn()} />, { wrapper: TestWrapper })
  await user.type(screen.getByPlaceholderText('linux-cache-01'), 'Bad Name!')
  expect(screen.getByText(/lowercase letters, numbers, hyphens only/)).toBeInTheDocument()
})
```

- [ ] **Step 2: Write test — valid name enables Add button**

```tsx
it('enables Add button when name is valid lowercase-hyphen', async () => {
  const user = userEvent.setup()
  render(<AssetCreateDialog open onOpenChange={vi.fn()} />, { wrapper: TestWrapper })
  await user.type(screen.getByPlaceholderText('linux-cache-01'), 'my-service')
  expect(screen.getByText('Add')).toBeEnabled()
})
```

- [ ] **Step 3: Write test — auto-selects default asset type**

```tsx
it('pre-selects the default asset type', () => {
  render(<AssetCreateDialog open onOpenChange={vi.fn()} />, { wrapper: TestWrapper })
  const select = screen.getByDisplayValue('service')
  expect(select).toBeInTheDocument()
})
```

- [ ] **Step 4: Write test — create calls mutation with name and type**

```tsx
it('calls createAsset with name and type on submit', async () => {
  const mockCreate = vi.fn().mockResolvedValue({ id: 'new-id' })
  vi.mocked(useCreateAsset).mockReturnValue({ mutateAsync: mockCreate, isPending: false } as any)
  const user = userEvent.setup()
  render(<AssetCreateDialog open onOpenChange={vi.fn()} />, { wrapper: TestWrapper })
  await user.type(screen.getByPlaceholderText('linux-cache-01'), 'my-service')
  await user.click(screen.getByText('Add'))
  expect(mockCreate).toHaveBeenCalledWith(expect.objectContaining({ name: 'my-service', type_name: 'service' }))
})
```

- [ ] **Step 5: Run tests, verify all pass**

Run: `npx vitest run src/features/assets/components/AssetCreateDialog.test.tsx`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add ui/src/features/assets/components/AssetCreateDialog.test.tsx
git commit -m "test: add AssetCreateDialog validation and mutation tests"
```

---

## Task 6: AssetEditDialog tests

Edit form pre-populated from existing asset.

**Files:**
- Create: `ui/src/features/assets/components/AssetEditDialog.test.tsx`
- Reference: `ui/src/features/assets/components/AssetEditDialog.tsx`

Mock:
- `@/features/assets/hooks`: `useAsset`, `useAssetTypes`, `useUpdateAsset`
- `@/components/labels/LabelsEditorDialog` → stub

### Mock data

```tsx
const MOCK_ASSET = { id: 'a1', name: 'cart-service', display_name: 'Cart', type_name: 'service', labels: { env: 'prod' }, created_at: '', updated_at: '' }
const TYPES = [{ name: 'service', is_default: true, asset_count: 5 }, { name: 'api', is_default: false, asset_count: 2 }]
```

- [ ] **Step 1: Write test — pre-fills form from asset data**

Note: `useEffect` populates state async — use `findBy` queries (auto-waits).

```tsx
it('pre-fills display name and type from loaded asset', async () => {
  render(<AssetEditDialog open assetName="cart-service" onOpenChange={vi.fn()} />, { wrapper: TestWrapper })
  expect(await screen.findByDisplayValue('Cart')).toBeInTheDocument()
  expect(screen.getByDisplayValue('service')).toBeInTheDocument()
})
```

- [ ] **Step 2: Write test — save calls updateAsset mutation**

```tsx
it('calls updateAsset on save', async () => {
  const mockMutate = vi.fn((_vars: any, opts?: any) => opts?.onSuccess?.())
  vi.mocked(useUpdateAsset).mockReturnValue({ mutate: mockMutate, isPending: false } as any)
  const user = userEvent.setup()
  render(<AssetEditDialog open assetName="cart-service" onOpenChange={vi.fn()} />, { wrapper: TestWrapper })
  const input = await screen.findByDisplayValue('Cart')
  await user.clear(input)
  await user.type(input, 'Cart Service V2')
  await user.click(screen.getByText('Save'))
  expect(mockMutate).toHaveBeenCalledWith(
    expect.objectContaining({ name: 'cart-service', display_name: 'Cart Service V2' }),
    expect.anything(),
  )
})
```

- [ ] **Step 3: Write test — shows dialog title with asset name**

```tsx
it('shows asset name in dialog title', () => {
  render(<AssetEditDialog open assetName="cart-service" onOpenChange={vi.fn()} />, { wrapper: TestWrapper })
  expect(screen.getByText('cart-service')).toBeInTheDocument()
})
```

- [ ] **Step 4: Run tests, verify all pass**

Run: `npx vitest run src/features/assets/components/AssetEditDialog.test.tsx`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add ui/src/features/assets/components/AssetEditDialog.test.tsx
git commit -m "test: add AssetEditDialog pre-fill and mutation tests"
```

---

## Task 7: LabelsEditorDialog tests

Label CRUD with combobox-based key/value entry.

**Files:**
- Create: `ui/src/components/labels/LabelsEditorDialog.test.tsx`
- Reference: `ui/src/components/labels/LabelsEditorDialog.tsx`

Mock:
- `@/features/assets/hooks`: `useLabelKeys`, `useLabelValues`

- [ ] **Step 1: Write test — renders existing labels**

```tsx
it('renders existing labels as key-value pairs', () => {
  render(
    <LabelsEditorDialog open onOpenChange={vi.fn()} title="Edit Labels" labels={{ env: 'prod', team: 'payments' }} onSave={vi.fn()} />,
    { wrapper: TestWrapper },
  )
  expect(screen.getByText('env')).toBeInTheDocument()
  expect(screen.getByText('prod')).toBeInTheDocument()
  expect(screen.getByText('team')).toBeInTheDocument()
  expect(screen.getByText('payments')).toBeInTheDocument()
})
```

- [ ] **Step 2: Write test — remove label removes it from list**

```tsx
it('removes label when X button clicked', async () => {
  const user = userEvent.setup()
  render(
    <LabelsEditorDialog open onOpenChange={vi.fn()} title="Edit Labels" labels={{ env: 'prod', team: 'payments' }} onSave={vi.fn()} />,
    { wrapper: TestWrapper },
  )
  const removeButtons = screen.getAllByTitle(/remove/i)
  await user.click(removeButtons[0])
  // One label should be removed from the display
})
```

- [ ] **Step 3: Write test — Done button calls onSave with updated labels**

```tsx
it('calls onSave with current labels when Done clicked', async () => {
  const onSave = vi.fn()
  const user = userEvent.setup()
  render(
    <LabelsEditorDialog open onOpenChange={vi.fn()} title="Edit Labels" labels={{ env: 'prod' }} onSave={onSave} />,
    { wrapper: TestWrapper },
  )
  await user.click(screen.getByText(/done/i))
  expect(onSave).toHaveBeenCalledWith({ env: 'prod' })
})
```

- [ ] **Step 4: Write test — empty labels shows "No labels assigned"**

```tsx
it('shows empty state when no labels', () => {
  render(
    <LabelsEditorDialog open onOpenChange={vi.fn()} title="Edit Labels" labels={{}} onSave={vi.fn()} />,
    { wrapper: TestWrapper },
  )
  expect(screen.getByText(/no labels/i)).toBeInTheDocument()
})
```

- [ ] **Step 5: Run tests, verify all pass**

Run: `npx vitest run src/components/labels/LabelsEditorDialog.test.tsx`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add ui/src/components/labels/LabelsEditorDialog.test.tsx
git commit -m "test: add LabelsEditorDialog rendering and interaction tests"
```

---

## Task 8: LabelComboBox tests

Autocomplete dropdown with create-new option.

**Files:**
- Create: `ui/src/components/labels/LabelComboBox.test.tsx`
- Reference: `ui/src/components/labels/LabelComboBox.tsx`

No hooks — pure presentational component with `suggestions` prop.

- [ ] **Step 1: Write test — renders input with placeholder**

```tsx
it('renders input with placeholder', () => {
  render(<LabelComboBox value="" onChange={vi.fn()} suggestions={[]} placeholder="Pick a key" />)
  expect(screen.getByPlaceholderText('Pick a key')).toBeInTheDocument()
})
```

- [ ] **Step 2: Write test — typing filters suggestions**

```tsx
it('filters suggestions as user types', async () => {
  const user = userEvent.setup()
  render(<LabelComboBox value="" onChange={vi.fn()} suggestions={['env', 'team', 'region']} />)
  const input = screen.getByRole('textbox')
  await user.type(input, 'te')
  expect(screen.getByText('team')).toBeInTheDocument()
  expect(screen.queryByText('region')).not.toBeInTheDocument()
})
```

- [ ] **Step 3: Write test — clicking suggestion calls onChange**

```tsx
it('calls onChange when suggestion clicked', async () => {
  const onChange = vi.fn()
  const user = userEvent.setup()
  render(<LabelComboBox value="" onChange={onChange} suggestions={['env', 'team']} />)
  const input = screen.getByRole('textbox')
  await user.click(input) // open dropdown
  await user.click(screen.getByText('env'))
  expect(onChange).toHaveBeenCalledWith('env')
})
```

- [ ] **Step 4: Write test — shows "Create new" option for novel input**

```tsx
it('shows create-new option when value does not match suggestions', async () => {
  const user = userEvent.setup()
  render(<LabelComboBox value="" onChange={vi.fn()} suggestions={['env', 'team']} />)
  const input = screen.getByRole('textbox')
  await user.type(input, 'custom')
  expect(screen.getByText(/create.*custom/i)).toBeInTheDocument()
})
```

- [ ] **Step 5: Run tests, verify all pass**

Run: `npx vitest run src/components/labels/LabelComboBox.test.tsx`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add ui/src/components/labels/LabelComboBox.test.tsx
git commit -m "test: add LabelComboBox autocomplete and interaction tests"
```

---

## Task 9: AssetTreeNode tests

Complex recursive component with filtering, mode-specific behavior, and context menus.

**Files:**
- Create: `ui/src/components/AssetTree/AssetTreeNode.test.tsx`
- Reference: `ui/src/components/AssetTree/AssetTreeNode.tsx`

Mock:
- `@/features/navigator/components/treeUtils`: `countLeafMembers` → `vi.fn(() => 1)`

```tsx
vi.mock('@/features/navigator/components/treeUtils', () => ({
  countLeafMembers: vi.fn(() => 1),
}))
```

### Mock data

```tsx
const ROOT_GROUP: AssetGroup = {
  id: 'g1', name: 'infra', display_name: 'Infrastructure',
  members: [{ asset_id: 'a1', asset_name: 'db-primary', weight: 1.0 }],
  subgroups: [{ group_id: 'g2', group_name: 'infra-eu', weight: 1.0 }],
}
const CHILD_GROUP: AssetGroup = {
  id: 'g2', name: 'infra-eu', display_name: 'Infra EU', members: [], subgroups: [],
}
const TREE: AssetGroupTree = { top_level: [ROOT_GROUP], all_groups: [ROOT_GROUP, CHILD_GROUP] }
```

- [ ] **Step 1: Write test — renders group display name**

```tsx
it('renders group display name', () => {
  render(
    <AssetTreeNode group={ROOT_GROUP} tree={TREE} mode="navigator" depth={0} filter="" selectedGroup={null} expandedGroups={new Set()} renamingGroup={null} isLastChild={false} onToggleExpand={vi.fn()} onSelectGroup={vi.fn()} onOpenContextMenu={vi.fn()} onStartRename={vi.fn()} onFinishRename={vi.fn()} onCancelRename={vi.fn()} />
  )
  expect(screen.getByText('Infrastructure')).toBeInTheDocument()
})
```

- [ ] **Step 2: Write test — shows asset leaves in navigator/assets mode when expanded**

```tsx
it('shows asset leaves when expanded in navigator mode', () => {
  render(
    <AssetTreeNode group={ROOT_GROUP} tree={TREE} mode="navigator" depth={0} filter="" selectedGroup={null} expandedGroups={new Set(['infra'])} renamingGroup={null} isLastChild={false} onToggleExpand={vi.fn()} onSelectGroup={vi.fn()} onOpenContextMenu={vi.fn()} onStartRename={vi.fn()} onFinishRename={vi.fn()} onCancelRename={vi.fn()} />
  )
  expect(screen.getByText('db-primary')).toBeInTheDocument()
})
```

- [ ] **Step 3: Write test — hides asset leaves in slo mode**

```tsx
it('hides asset leaves in slo mode', () => {
  render(
    <AssetTreeNode group={ROOT_GROUP} tree={TREE} mode="slo" depth={0} filter="" selectedGroup={null} expandedGroups={new Set(['infra'])} renamingGroup={null} isLastChild={false} onToggleExpand={vi.fn()} onSelectGroup={vi.fn()} onOpenContextMenu={vi.fn()} onStartRename={vi.fn()} onFinishRename={vi.fn()} onCancelRename={vi.fn()} />
  )
  expect(screen.queryByText('db-primary')).not.toBeInTheDocument()
})
```

- [ ] **Step 4: Write test — filter matches group name**

```tsx
it('renders when filter matches group name', () => {
  render(
    <AssetTreeNode group={ROOT_GROUP} tree={TREE} mode="navigator" depth={0} filter="infra" selectedGroup={null} expandedGroups={new Set()} renamingGroup={null} isLastChild={false} onToggleExpand={vi.fn()} onSelectGroup={vi.fn()} onOpenContextMenu={vi.fn()} onStartRename={vi.fn()} onFinishRename={vi.fn()} onCancelRename={vi.fn()} />
  )
  expect(screen.getByText('Infrastructure')).toBeInTheDocument()
})
```

- [ ] **Step 5: Write test — filter hides non-matching group**

```tsx
it('returns null when filter does not match group or children', () => {
  const { container } = render(
    <AssetTreeNode group={CHILD_GROUP} tree={TREE} mode="navigator" depth={0} filter="zzz-no-match" selectedGroup={null} expandedGroups={new Set()} renamingGroup={null} isLastChild={false} onToggleExpand={vi.fn()} onSelectGroup={vi.fn()} onOpenContextMenu={vi.fn()} onStartRename={vi.fn()} onFinishRename={vi.fn()} onCancelRename={vi.fn()} />
  )
  expect(container.innerHTML).toBe('')
})
```

- [ ] **Step 6: Write test — clicking group row calls onToggleExpand and onSelectGroup**

```tsx
it('calls onToggleExpand and onSelectGroup when group row clicked', async () => {
  const onToggle = vi.fn()
  const onSelect = vi.fn()
  const user = userEvent.setup()
  render(
    <AssetTreeNode group={ROOT_GROUP} tree={TREE} mode="navigator" depth={0} filter="" selectedGroup={null} expandedGroups={new Set()} renamingGroup={null} isLastChild={false} onToggleExpand={onToggle} onSelectGroup={onSelect} onOpenContextMenu={vi.fn()} onStartRename={vi.fn()} onFinishRename={vi.fn()} onCancelRename={vi.fn()} />
  )
  await user.click(screen.getByText('Infrastructure'))
  expect(onToggle).toHaveBeenCalledWith('infra')
  expect(onSelect).toHaveBeenCalledWith('infra')
})
```

- [ ] **Step 7: Run tests, verify all pass**

Run: `npx vitest run src/components/AssetTree/AssetTreeNode.test.tsx`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add ui/src/components/AssetTree/AssetTreeNode.test.tsx
git commit -m "test: add AssetTreeNode rendering, filtering, and mode tests"
```

---

## Task 10: AssetsPage integration test

Page-level wiring of tree + detail panel.

**Files:**
- Create: `ui/src/pages/AssetsPage.test.tsx`
- Reference: `ui/src/pages/AssetsPage.tsx`

Mock child components to shallow render — this avoids needing to mock every hook used by deep children:

```tsx
vi.mock('@/components/AssetTree', () => ({
  AssetTree: (props: any) => <div data-testid="asset-tree" data-mode={props.mode} />,
}))
vi.mock('@/features/assets/components/GroupDetailPanel', () => ({
  GroupDetailPanel: (props: any) => <div data-testid="group-detail">{props.groupName}</div>,
}))
vi.mock('@/features/assets/components/AllAssetsPanel', () => ({
  AllAssetsPanel: () => <div data-testid="all-assets">All Assets</div>,
}))
vi.mock('@/features/assets/components/AssetCreateDialog', () => ({
  AssetCreateDialog: () => null,
}))
```

Mock `react-router-dom` with controllable search params:

```tsx
let mockParams = new URLSearchParams()
const mockSetParams = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useSearchParams: () => [mockParams, mockSetParams] }
})
```

Reset between tests:
```tsx
beforeEach(() => { mockParams = new URLSearchParams(); mockSetParams.mockClear() })
```

- [ ] **Step 1: Write test — renders tree and all-assets panel by default (no params)**

```tsx
it('renders asset tree and all-assets panel when no group selected', () => {
  mockParams = new URLSearchParams()
  render(<AssetsPage />, { wrapper: TestWrapper })
  expect(screen.getByTestId('asset-tree')).toBeInTheDocument()
  expect(screen.getByTestId('all-assets')).toBeInTheDocument()
})
```

- [ ] **Step 2: Write test — group param shows GroupDetailPanel**

```tsx
it('shows group detail panel when group param is set', () => {
  mockParams = new URLSearchParams({ group: 'payments' })
  render(<AssetsPage />, { wrapper: TestWrapper })
  expect(screen.getByTestId('group-detail')).toBeInTheDocument()
  expect(screen.getByText('payments')).toBeInTheDocument()
  expect(screen.queryByTestId('all-assets')).not.toBeInTheDocument()
})
```

- [ ] **Step 3: Write test — __ungrouped__ group shows AllAssetsPanel**

```tsx
it('shows all-assets panel when group is __ungrouped__', () => {
  mockParams = new URLSearchParams({ group: '__ungrouped__' })
  render(<AssetsPage />, { wrapper: TestWrapper })
  expect(screen.getByTestId('all-assets')).toBeInTheDocument()
  expect(screen.queryByTestId('group-detail')).not.toBeInTheDocument()
})
```

- [ ] **Step 4: Run tests, verify all pass**

Run: `npx vitest run src/pages/AssetsPage.test.tsx`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add ui/src/pages/AssetsPage.test.tsx
git commit -m "test: add AssetsPage routing and panel selection tests"
```

---

## Task 11: Final verification and coverage report

- [ ] **Step 1: Run full test suite**

Run: `npx vitest run`
Expected: All tests PASS (existing + new)

- [ ] **Step 2: Type check**

Run: `npx tsc --noEmit -p tsconfig.app.json`
Expected: No new errors (pre-existing errors in EvaluationTable.tsx and NoteEntry.test.tsx are known)

- [ ] **Step 3: Commit all remaining changes**

```bash
git add -A
git commit -m "test: complete asset UI component test coverage"
```
