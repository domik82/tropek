# Tree View Consistency Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify all tree views (Navigator, Assets, SLO Registry) with consistent dimensions, icons, colors, selection states, and filter behavior.

**Architecture:** Three layers of change: (1) Backend — add `color` columns to `asset_groups` and `assets` tables, add `load-test` asset type seed, extend member schema with `asset_type_name`; (2) Shared UI components — new `TreeNode`, `TreeFilter`, and icon resolver; (3) Integration — rewire `AssetTree` and `RegistryTree` to use the shared components.

**Tech Stack:** Python 3.13, SQLAlchemy, Alembic, React 19, TypeScript, Tailwind CSS, Lucide icons, Vitest

**Spec:** `docs/superpowers/specs/2026-03-28-tree-view-consistency-design.md`

---

## File Structure

### New files

| File | Responsibility |
|---|---|
| `ui/src/components/tree/TreeNode.tsx` | Unified tree node renderer — icon, label, badge, chevron, selection |
| `ui/src/components/tree/TreeNode.test.tsx` | Tests for TreeNode rendering, selection, chevron, badges |
| `ui/src/components/tree/TreeFilter.tsx` | Unified filter input with search icon, clear X, result count |
| `ui/src/components/tree/TreeFilter.test.tsx` | Tests for TreeFilter input behavior |
| `ui/src/components/tree/tree-icons.ts` | Icon resolver — maps entity/asset types to Lucide icons + colors |
| `ui/src/components/tree/tree-icons.test.ts` | Tests for icon resolver |
| `ui/src/components/tree/index.ts` | Barrel export |

### Modified files

| File | Change |
|---|---|
| `api/app/db/models.py` | Add `color` column to `AssetGroup` and `Asset` |
| `api/app/modules/assets/schemas.py` | Add `color` to read/create/update schemas; add `asset_type_name` to `AssetGroupMemberRead` |
| `api/app/modules/assets/repository.py` | Include `asset_type_name` in `_build_read()`; auto-assign color on group creation |
| `api/alembic/versions/002_timescaledb_hypertable_and_seed_data.py` | Add `load-test` to seeded types |
| `ui/src/features/assets/types.ts` | Add `color` to `AssetGroup`, `Asset`; add `asset_type_name` to `AssetGroupMember` |
| `ui/src/lib/entity-colors.ts` | Add `GROUP_PALETTE` constant |
| `ui/src/components/AssetTree/AssetTree.tsx` | Replace inline filter with `TreeFilter`; replace inline "All"/"Ungrouped" rows with `TreeNode` |
| `ui/src/components/AssetTree/AssetTreeNode.tsx` | Replace inline node rendering with `TreeNode`; update indentation from `depth*16+8` to `depth*24`; add icons |
| `ui/src/features/registry/RegistryTree.tsx` | Replace `TreeNodeRow` with shared `TreeNode`; update dimensions |
| `ui/src/features/registry/RegistrySidebar.tsx` | Replace `TagFilterBar` search with `TreeFilter` for search portion |

---

## Task 1: Backend — Add `color` columns and `load-test` seed

**Files:**
- Modify: `api/app/db/models.py:58-73` (Asset) and `api/app/db/models.py:76-94` (AssetGroup)
- Modify: `api/app/modules/assets/schemas.py`
- Modify: `api/app/modules/assets/repository.py:267-358`
- Modify: `api/alembic/versions/002_timescaledb_hypertable_and_seed_data.py:30-38`

- [ ] **Step 1: Add `color` column to `AssetGroup` model**

In `api/app/db/models.py`, add after the `description` field in `AssetGroup`:

```python
color:        Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 2: Add `color` column to `Asset` model**

In `api/app/db/models.py`, add after `heatmap_config` in `Asset`:

```python
color:          Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 3: Update schemas — group color + asset color + member type_name**

In `api/app/modules/assets/schemas.py`:

Add `color` to `AssetGroupCreate`:
```python
class AssetGroupCreate(BaseModel):
    name: str
    display_name: str | None = None
    description: str | None = None
    color: str | None = None
    members: list[AssetGroupMemberCreate] = []
    subgroups: list[AssetGroupSubgroupCreate] = []
```

Add `color` to `AssetGroupUpdate`:
```python
class AssetGroupUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    color: str | None = None
```

Add `color` to `AssetGroupRead`:
```python
class AssetGroupRead(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str | None
    description: str | None
    color: str | None
    members: list[AssetGroupMemberRead]
    subgroups: list[AssetGroupSubgroupRead]
    created_at: datetime
    updated_at: datetime
```

Add `asset_type_name` to `AssetGroupMemberRead`:
```python
class AssetGroupMemberRead(BaseModel):
    asset_id: uuid.UUID
    asset_name: str
    asset_display_name: str | None = None
    asset_type_name: str = "vm"
    weight: float
```

Add `color` to `AssetCreate`:
```python
class AssetCreate(BaseModel):
    name: str
    display_name: str | None = None
    type_name: str
    tags: dict[str, str] = {}
    variables: dict[str, str] = {}
    color: str | None = None
```

Add `color` to `AssetUpdate`:
```python
class AssetUpdate(BaseModel):
    display_name: str | None = None
    type_name: str | None = None
    tags: dict[str, str] | None = None
    variables: dict[str, str] | None = None
    heatmap_config: dict[str, Any] | None = None
    color: str | None = None
```

Add `color` to `AssetRead`:
```python
class AssetRead(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str | None
    type_name: str
    tags: dict[str, Any]
    variables: dict[str, Any]
    heatmap_config: dict[str, Any] | None = None
    color: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 4: Update repository — include `asset_type_name` in `_build_read`, auto-assign color on create**

In `api/app/modules/assets/repository.py`, update `AssetGroupRepository._build_read()` to join `Asset.type_name`:

Change the member query select to include `Asset.type_name`:
```python
member_rows = await self._session.execute(
    select(
        AssetGroupMember,
        Asset.name.label("asset_name"),
        Asset.display_name.label("asset_display_name"),
        Asset.type_name.label("asset_type_name"),
    )
    .join(Asset, AssetGroupMember.asset_id == Asset.id)
    .where(AssetGroupMember.group_id == group.id)
)
members = [
    AssetGroupMemberRead(
        asset_id=row.AssetGroupMember.asset_id,
        asset_name=row.asset_name,
        asset_display_name=row.asset_display_name,
        asset_type_name=row.asset_type_name,
        weight=row.AssetGroupMember.weight,
    )
    for row in member_rows
]
```

Include `color` in the return:
```python
return AssetGroupRead(
    id=group.id,
    name=group.name,
    display_name=group.display_name,
    description=group.description,
    color=group.color,
    members=members,
    subgroups=subgroups,
    created_at=group.created_at,
    updated_at=group.updated_at,
)
```

Add auto-assign color on group creation. At the top of `repository.py`, add the palette constant:
```python
import random

GROUP_COLOR_PALETTE = [
    "#6897BB", "#E8915A", "#A371F7", "#7DC540", "#F85149",
    "#58A6FF", "#D4A032", "#2DD4A0", "#DB61A2", "#8B949E",
]
```

In the `create()` method, auto-assign a color if none provided:
```python
group = AssetGroup(
    id=uuid.uuid4(),
    name=name,
    display_name=display_name,
    description=description,
    color=color if color is not None else random.choice(GROUP_COLOR_PALETTE),
)
```

Add `color` parameter to the `create()` method signature:
```python
async def create(
    self,
    name: str,
    *,
    display_name: str | None = None,
    description: str | None = None,
    color: str | None = None,
    members: list[AssetGroupMemberCreate] | None = None,
    subgroups: list[AssetGroupSubgroupCreate] | None = None,
) -> AssetGroupRead:
```

Also update the `update()` method to accept `color`:
```python
async def update(self, name: str, *, display_name: str | None = None, description: str | None = None, color: str | None = None) -> AssetGroupRead | None:
```
And include `color` in the filtered kwargs dict that gets applied.

- [ ] **Step 5: Update router to pass `color` through**

In the router's group create endpoint, pass `color=body.color` to `repo.create()`.
In the update endpoint, pass `color=body.color` to `repo.update()`.

- [ ] **Step 6: Add `load-test` to seed data**

In `api/alembic/versions/002_timescaledb_hypertable_and_seed_data.py`, update the INSERT to include `load-test`:

```python
op.execute("""
    INSERT INTO asset_types (id, name, is_default) VALUES
        (gen_random_uuid(), 'vm',        true),
        (gen_random_uuid(), 'service',   false),
        (gen_random_uuid(), 'database',  false),
        (gen_random_uuid(), 'container', false),
        (gen_random_uuid(), 'endpoint',  false),
        (gen_random_uuid(), 'load-test', false)
    ON CONFLICT (name) DO NOTHING
""")
```

Also update the downgrade:
```python
op.execute("""
    DELETE FROM asset_types
    WHERE name IN ('vm', 'service', 'database', 'container', 'endpoint', 'load-test')
""")
```

- [ ] **Step 7: Regenerate migrations**

Run the migration regeneration script to squash:
```bash
./scripts/db-regen-migrations.sh
```

- [ ] **Step 8: Run integration tests**

```bash
./scripts/api-test.sh --tail 20 -m integration -v
```

Expected: All pass. The new `color` and `asset_type_name` fields should flow through existing tests because they're nullable/have defaults.

- [ ] **Step 9: Commit**

```bash
git add api/app/db/models.py api/app/modules/assets/schemas.py api/app/modules/assets/repository.py api/app/modules/assets/router.py api/alembic/versions/
git commit -m "feat(api): add color columns to asset_groups/assets, load-test seed, member type_name"
```

---

## Task 2: Frontend types — extend TS interfaces

**Files:**
- Modify: `ui/src/features/assets/types.ts`
- Modify: `ui/src/lib/entity-colors.ts`

- [ ] **Step 1: Add `color` to TS types and `asset_type_name` to member**

In `ui/src/features/assets/types.ts`:

Add `color` to `AssetGroup`:
```typescript
export interface AssetGroup {
  id: string
  name: string
  display_name?: string
  description?: string
  color?: string | null
  members: AssetGroupMember[]
  subgroups: AssetGroupSubgroup[]
}
```

Add `asset_type_name` to `AssetGroupMember`:
```typescript
export interface AssetGroupMember {
  asset_id: string
  asset_name: string
  asset_display_name?: string | null
  asset_type_name?: string
  weight: number
}
```

Add `color` to `Asset`:
```typescript
export interface Asset {
  id: string
  name: string
  display_name?: string
  type_name: string
  tags: Record<string, string>
  variables: Record<string, string>
  color?: string | null
  created_at: string
  updated_at: string
}
```

- [ ] **Step 2: Add `GROUP_PALETTE` to entity-colors**

In `ui/src/lib/entity-colors.ts`, add:

```typescript
export const GROUP_PALETTE = [
  '#6897BB', '#E8915A', '#A371F7', '#7DC540', '#F85149',
  '#58A6FF', '#D4A032', '#2DD4A0', '#DB61A2', '#8B949E',
] as const
```

- [ ] **Step 3: Commit**

```bash
git add ui/src/features/assets/types.ts ui/src/lib/entity-colors.ts
git commit -m "feat(ui): extend TS types with color, asset_type_name, group palette"
```

---

## Task 3: Icon resolver — `tree-icons.ts`

**Files:**
- Create: `ui/src/components/tree/tree-icons.ts`
- Create: `ui/src/components/tree/tree-icons.test.ts`

- [ ] **Step 1: Write the failing test**

Create `ui/src/components/tree/tree-icons.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { Server, Component, Database, Container, Laptop, Gauge, CircuitBoard, ShieldCheck, Braces, Folder, LayoutGrid } from 'lucide-react'
import { getAssetTypeIcon, getEntityIcon, FALLBACK_ASSET_ICON } from './tree-icons'

describe('getAssetTypeIcon', () => {
  it('maps vm to Server', () => {
    expect(getAssetTypeIcon('vm')).toBe(Server)
  })

  it('maps service to Component', () => {
    expect(getAssetTypeIcon('service')).toBe(Component)
  })

  it('maps database to Database', () => {
    expect(getAssetTypeIcon('database')).toBe(Database)
  })

  it('maps container to Container', () => {
    expect(getAssetTypeIcon('container')).toBe(Container)
  })

  it('maps endpoint to Laptop', () => {
    expect(getAssetTypeIcon('endpoint')).toBe(Laptop)
  })

  it('maps load-test to Gauge', () => {
    expect(getAssetTypeIcon('load-test')).toBe(Gauge)
  })

  it('returns CircuitBoard for unknown types', () => {
    expect(getAssetTypeIcon('unknown-thing')).toBe(CircuitBoard)
  })

  it('exports FALLBACK_ASSET_ICON as CircuitBoard', () => {
    expect(FALLBACK_ASSET_ICON).toBe(CircuitBoard)
  })
})

describe('getEntityIcon', () => {
  it('maps slo to ShieldCheck', () => {
    expect(getEntityIcon('slo')).toBe(ShieldCheck)
  })

  it('maps sli to Braces', () => {
    expect(getEntityIcon('sli')).toBe(Braces)
  })

  it('maps datasource to Database', () => {
    expect(getEntityIcon('datasource')).toBe(Database)
  })

  it('maps group to Folder', () => {
    expect(getEntityIcon('group')).toBe(Folder)
  })

  it('maps all to LayoutGrid', () => {
    expect(getEntityIcon('all')).toBe(LayoutGrid)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
./scripts/ui-test.sh --tail 10 src/components/tree/tree-icons.test.ts
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement the icon resolver**

Create `ui/src/components/tree/tree-icons.ts`:

```typescript
import type { LucideIcon } from 'lucide-react'
import {
  Server, Component, Database, Container, Laptop, Gauge, CircuitBoard,
  ShieldCheck, Braces, Folder, LayoutGrid,
} from 'lucide-react'

const ASSET_TYPE_ICONS: Record<string, LucideIcon> = {
  vm: Server,
  service: Component,
  database: Database,
  container: Container,
  endpoint: Laptop,
  'load-test': Gauge,
}

export const FALLBACK_ASSET_ICON: LucideIcon = CircuitBoard

const ENTITY_ICONS: Record<string, LucideIcon> = {
  slo: ShieldCheck,
  sli: Braces,
  datasource: Database,
  group: Folder,
  all: LayoutGrid,
}

/** Get the Lucide icon for an asset type. Falls back to CircuitBoard. */
export function getAssetTypeIcon(typeName: string): LucideIcon {
  return ASSET_TYPE_ICONS[typeName] ?? FALLBACK_ASSET_ICON
}

/** Get the Lucide icon for an entity type (slo, sli, datasource, group, all). */
export function getEntityIcon(entityType: string): LucideIcon {
  return ENTITY_ICONS[entityType] ?? FALLBACK_ASSET_ICON
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
./scripts/ui-test.sh --tail 10 src/components/tree/tree-icons.test.ts
```

Expected: All 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/tree/tree-icons.ts ui/src/components/tree/tree-icons.test.ts
git commit -m "feat(ui): add tree icon resolver for asset types and entity types"
```

---

## Task 4: `TreeFilter` component

**Files:**
- Create: `ui/src/components/tree/TreeFilter.tsx`
- Create: `ui/src/components/tree/TreeFilter.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `ui/src/components/tree/TreeFilter.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TreeFilter } from './TreeFilter'

describe('TreeFilter', () => {
  it('renders with placeholder', () => {
    render(<TreeFilter value="" onChange={vi.fn()} placeholder="Filter..." />)
    expect(screen.getByPlaceholderText('Filter...')).toBeInTheDocument()
  })

  it('calls onChange when typing', () => {
    const onChange = vi.fn()
    render(<TreeFilter value="" onChange={onChange} placeholder="Filter..." />)
    fireEvent.change(screen.getByPlaceholderText('Filter...'), { target: { value: 'test' } })
    expect(onChange).toHaveBeenCalledWith('test')
  })

  it('shows clear button when value is present', () => {
    render(<TreeFilter value="hello" onChange={vi.fn()} placeholder="Filter..." />)
    expect(screen.getByLabelText('Clear filter')).toBeInTheDocument()
  })

  it('does not show clear button when value is empty', () => {
    render(<TreeFilter value="" onChange={vi.fn()} placeholder="Filter..." />)
    expect(screen.queryByLabelText('Clear filter')).not.toBeInTheDocument()
  })

  it('clears value on X click', () => {
    const onChange = vi.fn()
    render(<TreeFilter value="hello" onChange={onChange} placeholder="Filter..." />)
    fireEvent.click(screen.getByLabelText('Clear filter'))
    expect(onChange).toHaveBeenCalledWith('')
  })

  it('shows result count when filtering and resultCount is provided', () => {
    render(<TreeFilter value="check" onChange={vi.fn()} placeholder="Filter..." resultCount={3} />)
    expect(screen.getByText('3 results')).toBeInTheDocument()
  })

  it('does not show result count when value is empty', () => {
    render(<TreeFilter value="" onChange={vi.fn()} placeholder="Filter..." resultCount={5} />)
    expect(screen.queryByText('5 results')).not.toBeInTheDocument()
  })

  it('shows singular "result" when count is 1', () => {
    render(<TreeFilter value="x" onChange={vi.fn()} placeholder="Filter..." resultCount={1} />)
    expect(screen.getByText('1 result')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
./scripts/ui-test.sh --tail 10 src/components/tree/TreeFilter.test.tsx
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement TreeFilter**

Create `ui/src/components/tree/TreeFilter.tsx`:

```tsx
import { Search, X } from 'lucide-react'

interface TreeFilterProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  resultCount?: number
}

export function TreeFilter({ value, onChange, placeholder = 'Filter...', resultCount }: TreeFilterProps) {
  return (
    <div>
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
        <input
          type="text"
          placeholder={placeholder}
          value={value}
          onChange={e => onChange(e.target.value)}
          className="w-full bg-input border border-border rounded-md py-1.5 pl-8 pr-7 text-[13px] text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:border-primary/50"
        />
        {value && (
          <button
            onClick={() => onChange('')}
            aria-label="Clear filter"
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
      {value && resultCount !== undefined && (
        <div className="text-[11px] text-muted-foreground px-1 pt-1">
          {resultCount} {resultCount === 1 ? 'result' : 'results'}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
./scripts/ui-test.sh --tail 10 src/components/tree/TreeFilter.test.tsx
```

Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/tree/TreeFilter.tsx ui/src/components/tree/TreeFilter.test.tsx
git commit -m "feat(ui): add shared TreeFilter component with clear button and result count"
```

---

## Task 5: `TreeNode` component

**Files:**
- Create: `ui/src/components/tree/TreeNode.tsx`
- Create: `ui/src/components/tree/TreeNode.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `ui/src/components/tree/TreeNode.test.tsx`:

```tsx
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

  it('renders icon with correct color', () => {
    const { container } = render(<TreeNode {...defaults} />)
    const svg = container.querySelector('svg')
    expect(svg).toBeTruthy()
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

  it('applies selection background with selectionColor at 12% opacity', () => {
    const { container } = render(
      <TreeNode {...defaults} isSelected selectionColor="#6897BB" />
    )
    const row = container.firstChild as HTMLElement
    expect(row.style.backgroundColor).toContain('#6897BB')
  })

  it('indents by depth * 24px', () => {
    const { container } = render(<TreeNode {...defaults} depth={2} />)
    const row = container.firstChild as HTMLElement
    expect(row.style.paddingLeft).toBe('48px')
  })

  it('uses font-weight 600 when isGroup', () => {
    render(<TreeNode {...defaults} icon={Folder} isGroup />)
    const label = screen.getByText('web-server-01')
    expect(label.className).toContain('font-semibold')
  })

  it('uses font-weight 400 when not isGroup', () => {
    render(<TreeNode {...defaults} />)
    const label = screen.getByText('web-server-01')
    expect(label.className).not.toContain('font-semibold')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
./scripts/ui-test.sh --tail 10 src/components/tree/TreeNode.test.tsx
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement TreeNode**

Create `ui/src/components/tree/TreeNode.tsx`:

```tsx
import { ChevronRight } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export interface TreeNodeBadge {
  type: 'count' | 'version'
  value: string | number
}

export interface TreeNodeProps {
  icon: LucideIcon
  iconColor: string
  label: string
  depth: number
  isExpandable: boolean
  isExpanded: boolean
  isSelected: boolean
  selectionColor?: string
  isGroup?: boolean
  badge?: TreeNodeBadge
  onClick?: () => void
  onToggle?: () => void
  onContextMenu?: (e: React.MouseEvent) => void
  onDoubleClick?: () => void
  trailingAction?: React.ReactNode
  testId?: string
}

export function TreeNode({
  icon: Icon,
  iconColor,
  label,
  depth,
  isExpandable,
  isExpanded,
  isSelected,
  selectionColor,
  isGroup,
  badge,
  onClick,
  onToggle,
  onContextMenu,
  onDoubleClick,
  trailingAction,
  testId,
}: TreeNodeProps) {
  const paddingLeft = depth * 24
  const selectedPaddingLeft = isSelected ? paddingLeft - 2 : paddingLeft

  return (
    <div
      data-testid={testId}
      data-selected={isSelected ? 'true' : 'false'}
      className={`flex items-center gap-1.5 cursor-pointer transition-colors h-8 group ${
        isSelected ? '' : 'hover:bg-muted/50'
      }`}
      style={{
        paddingLeft: selectedPaddingLeft,
        paddingRight: 8,
        ...(isSelected && selectionColor
          ? { backgroundColor: `${selectionColor}1f`, borderLeft: `2px solid ${selectionColor}` }
          : {}),
      }}
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={e => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick?.() }
      }}
      onContextMenu={onContextMenu}
      onDoubleClick={onDoubleClick}
    >
      {/* Chevron zone */}
      {isExpandable ? (
        <button
          data-testid="chevron"
          aria-label={`Toggle ${label}`}
          className={`shrink-0 p-0.5 text-muted-foreground hover:text-foreground transition-transform ${
            isExpanded ? 'rotate-90' : ''
          }`}
          onClick={e => { e.stopPropagation(); onToggle?.() }}
        >
          <ChevronRight className="w-3 h-3" />
        </button>
      ) : (
        <span className="shrink-0 w-4" />
      )}

      {/* Icon */}
      <Icon className="w-4 h-4 shrink-0" style={{ color: iconColor }} strokeWidth={2} />

      {/* Label */}
      <span
        className={`text-[14px] truncate flex-1 leading-4 ${
          isGroup ? 'font-semibold' : 'font-normal'
        }`}
        style={{ color: isSelected ? selectionColor : undefined }}
      >
        {label}
      </span>

      {/* Badge */}
      {badge && (
        badge.type === 'count' ? (
          <span
            className="shrink-0 text-[10px] font-semibold min-w-[18px] h-[18px] inline-flex items-center justify-center rounded-full px-1.5"
            style={{
              backgroundColor: isSelected && selectionColor ? `${selectionColor}33` : '#30363d',
              color: isSelected && selectionColor ? selectionColor : '#c9d1d9',
            }}
          >
            {badge.value}
          </span>
        ) : (
          <span className="shrink-0 text-[10px] text-muted-foreground border border-border rounded px-1.5 py-px">
            {badge.value}
          </span>
        )
      )}

      {/* Trailing action (e.g., more button) */}
      {trailingAction}
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
./scripts/ui-test.sh --tail 10 src/components/tree/TreeNode.test.tsx
```

Expected: All 15 tests PASS.

- [ ] **Step 5: Create barrel export**

Create `ui/src/components/tree/index.ts`:

```typescript
export { TreeNode } from './TreeNode'
export type { TreeNodeProps, TreeNodeBadge } from './TreeNode'
export { TreeFilter } from './TreeFilter'
export { getAssetTypeIcon, getEntityIcon, FALLBACK_ASSET_ICON } from './tree-icons'
```

- [ ] **Step 6: Commit**

```bash
git add ui/src/components/tree/
git commit -m "feat(ui): add shared TreeNode component with icon, badge, selection, chevron"
```

---

## Task 6: Integrate `TreeFilter` into AssetTree

**Files:**
- Modify: `ui/src/components/AssetTree/AssetTree.tsx:188-208`

- [ ] **Step 1: Replace inline filter with TreeFilter**

In `ui/src/components/AssetTree/AssetTree.tsx`:

Add import at top:
```typescript
import { TreeFilter } from '@/components/tree'
```

Remove `Search` and `X` from the lucide-react import (keep `Plus, MoreHorizontal, FolderTree, Settings`).

Replace the filter section (lines 188-208, the `{/* Filter */}` div):

```tsx
{/* Filter */}
<div className="px-3 py-2">
  <TreeFilter
    value={filter}
    onChange={setFilter}
    placeholder="Filter groups & assets..."
  />
</div>
```

- [ ] **Step 2: Run existing AssetTree tests**

```bash
./scripts/ui-test.sh --tail 10 src/components/AssetTree/
```

Expected: All existing tests pass (filter behavior is internal to TreeFilter now, but the filter state variable is unchanged).

- [ ] **Step 3: Commit**

```bash
git add ui/src/components/AssetTree/AssetTree.tsx
git commit -m "refactor(ui): replace AssetTree inline filter with shared TreeFilter"
```

---

## Task 7: Integrate `TreeFilter` into RegistrySidebar

**Files:**
- Modify: `ui/src/features/registry/RegistrySidebar.tsx:130-143`

- [ ] **Step 1: Add TreeFilter for the search portion**

In `ui/src/features/registry/RegistrySidebar.tsx`:

Add import:
```typescript
import { TreeFilter } from '@/components/tree'
```

Replace the search + tag filter section. The `TagFilterBar` handles both search and tag filtering. Since we want to keep tag filtering but unify the search input look, we need to replace just the search portion.

Looking at the current code, `TagFilterBar` is a combined component. The simplest approach: add `TreeFilter` above the `TagFilterBar` and remove the search prop from `TagFilterBar`, or replace the `TagFilterBar`'s internal search input styling.

The cleanest approach is to keep `TagFilterBar` for tags but replace the search text input inside it with our `TreeFilter`. However, since `TagFilterBar` is a shared component, the better path is: place `TreeFilter` above and pass `search` / `onSearchChange` to it, then only show `TagFilterBar` for tag pills (no search).

If `TagFilterBar` requires search as a mandatory prop, we can pass the same state to both. Check what `TagFilterBar` does with `search`:

Read `TagFilterBar` to determine integration approach. The key insight: `RegistrySidebar` already has `search` state that gets passed to both `TagFilterBar` (for display) and `filterTree()` (for filtering). We can:

1. Replace the `{/* Search + tag filter */}` section with `TreeFilter` + tag pills only
2. OR keep `TagFilterBar` as-is and just update its search input styling to match

The safest approach that doesn't break `TagFilterBar` is option 2 — leave `TagFilterBar` alone and add a `TreeFilter` if/when the tag filter doesn't need a search input. But the spec says "identical filter component on all pages", so let's add `TreeFilter` and keep `TagFilterBar` for tags only:

```tsx
{/* Search filter */}
<div className="px-3 pt-2">
  <TreeFilter
    value={search}
    onChange={setSearch}
    placeholder="Filter..."
    resultCount={search ? filteredNodes.length : undefined}
  />
</div>

{/* Tag filter */}
<div className="mt-1">
  <TagFilterBar
    search=""
    onSearchChange={() => {}}
    tags={tags}
    onTagsChange={setTags}
    tagKeySuggestions={tagKeySuggestions}
    tagValueSuggestions={tagValueSuggestions}
    onTagKeySelected={setPendingTagKey}
    isLoadingKeys={isLoadingKeys}
    isLoadingValues={isLoadingValues}
  />
</div>
```

Note: Passing empty `search=""` to `TagFilterBar` disables its internal search display. If `TagFilterBar` renders a search input when `search` is empty string, we may need to hide it or add a `hideSearch` prop. Verify by reading the component — if it always renders a search input, add a CSS `hidden` class or a prop. This is an integration detail to handle during implementation.

- [ ] **Step 2: Run RegistrySidebar tests**

```bash
./scripts/ui-test.sh --tail 10 src/features/registry/RegistrySidebar.test.tsx
```

Expected: Pass (or update test expectations if they target the old search input).

- [ ] **Step 3: Commit**

```bash
git add ui/src/features/registry/RegistrySidebar.tsx
git commit -m "refactor(ui): replace RegistrySidebar search with shared TreeFilter"
```

---

## Task 8: Integrate `TreeNode` into AssetTree — "All" and "Ungrouped" rows

**Files:**
- Modify: `ui/src/components/AssetTree/AssetTree.tsx:218-290`

- [ ] **Step 1: Replace inline "All" row with TreeNode**

Add imports at top of `AssetTree.tsx`:
```typescript
import { TreeNode } from '@/components/tree'
import { getEntityIcon } from '@/components/tree'
```

Replace the "All" button (lines 219-244) with:

```tsx
<TreeNode
  icon={getEntityIcon('all')}
  iconColor={selectedGroup === null ? 'var(--primary)' : '#8b949e'}
  label="All"
  depth={0}
  isExpandable={false}
  isExpanded={false}
  isSelected={selectedGroup === null}
  selectionColor="var(--primary)"
  isGroup
  badge={totalCount > 0 ? { type: 'count', value: totalCount } : undefined}
  onClick={() => onSelectGroup(null)}
/>
```

- [ ] **Step 2: Replace inline "Ungrouped" row with TreeNode**

Replace the "Ungrouped" button (lines 276-288) with:

```tsx
<TreeNode
  icon={getEntityIcon('group')}
  iconColor="#8b949e80"
  label="Ungrouped"
  depth={0}
  isExpandable={false}
  isExpanded={false}
  isSelected={selectedGroup === '__ungrouped__'}
  selectionColor="var(--primary)"
  onClick={() => onSelectGroup('__ungrouped__')}
/>
```

Remove the `FolderTree` import from lucide-react (no longer used).

- [ ] **Step 3: Run AssetTree tests**

```bash
./scripts/ui-test.sh --tail 10 src/components/AssetTree/
```

Expected: Pass. The "All" and "Ungrouped" rows now render via TreeNode but behavior is the same.

- [ ] **Step 4: Commit**

```bash
git add ui/src/components/AssetTree/AssetTree.tsx
git commit -m "refactor(ui): replace AssetTree All/Ungrouped rows with shared TreeNode"
```

---

## Task 9: Integrate `TreeNode` into AssetTreeNode — group rows and asset leaves

**Files:**
- Modify: `ui/src/components/AssetTree/AssetTreeNode.tsx`

This is the largest integration task. The `AssetTreeNode` component currently renders group rows and asset leaf rows inline. We replace both with `TreeNode`.

- [ ] **Step 1: Add imports**

```typescript
import { MoreHorizontal } from 'lucide-react'
import { TreeNode } from '@/components/tree'
import { getAssetTypeIcon, getEntityIcon } from '@/components/tree'
import { NODE_TYPE_COLORS } from '@/lib/entity-colors'
```

Remove `ChevronRight` from the lucide-react import (TreeNode handles it internally).

- [ ] **Step 2: Replace group row rendering**

Replace the group row `<div>` (lines 138-212) with:

```tsx
<TreeNode
  icon={getEntityIcon('group')}
  iconColor={group.color ?? '#8b949e'}
  label={isRenaming ? '' : (group.display_name ?? group.name)}
  depth={depth}
  isExpandable={subgroups.length > 0 || filteredMembers.length > 0}
  isExpanded={isExpanded}
  isSelected={isSelected}
  selectionColor={group.color ?? 'var(--primary)'}
  isGroup
  badge={count > 0 && !isRenaming ? { type: 'count', value: count } : undefined}
  onClick={() => { onToggleExpand(group.name); onSelectGroup(group.name) }}
  onToggle={() => onToggleExpand(group.name)}
  onContextMenu={e => { e.preventDefault(); openGroupMenu(e.clientX, e.clientY) }}
  onDoubleClick={() => onStartRename(group.name)}
  trailingAction={!isRenaming ? (
    <button
      className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-muted/80 shrink-0"
      aria-label={`Actions for ${group.display_name ?? group.name}`}
      onClick={e => {
        e.stopPropagation()
        const rect = e.currentTarget.getBoundingClientRect()
        openGroupMenu(rect.left, rect.bottom + 2)
      }}
    >
      <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
    </button>
  ) : undefined}
/>
```

Note: When `isRenaming` is true, we need to show the inline rename input instead of the label. This requires either:
- Rendering the rename input separately below the TreeNode
- Or adding a `children` slot to TreeNode for custom label content

The simplest approach: when renaming, render the `AssetTreeInlineRename` component in a wrapper div with the same indentation, instead of TreeNode. This keeps TreeNode simple:

```tsx
{isRenaming ? (
  <div className="flex items-center h-8" style={{ paddingLeft: depth * 24 + 20 }}>
    <AssetTreeInlineRename
      currentName={group.display_name ?? group.name}
      onSave={newName => onFinishRename(group.name, newName)}
      onCancel={onCancelRename}
    />
  </div>
) : (
  <TreeNode ... />
)}
```

- [ ] **Step 3: Replace asset leaf rendering**

Replace the asset leaf rows (lines 241-283) with:

```tsx
{(mode === 'navigator' || mode === 'assets') && filteredMembers.map(m => {
  const isAssetSelected = selectedAsset === m.asset_name && selectedGroup === group.name
  const assetColor = m.asset_color ?? '#8b949e'
  return (
    <div key={m.asset_id} className="group relative">
      <TreeNode
        icon={getAssetTypeIcon(m.asset_type_name ?? 'vm')}
        iconColor={assetColor}
        label={m.asset_display_name ?? m.asset_name}
        depth={depth + 1}
        isExpandable={false}
        isExpanded={false}
        isSelected={isAssetSelected}
        selectionColor="var(--primary)"
        onClick={() => onSelectAsset?.(m.asset_name, group.name)}
        onContextMenu={e => {
          e.preventDefault()
          openAssetMenu(e.clientX, e.clientY, m.asset_name, m.asset_id)
        }}
        trailingAction={
          <button
            className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-muted/80 shrink-0"
            aria-label={`Actions for ${m.asset_display_name ?? m.asset_name}`}
            onClick={e => {
              e.stopPropagation()
              const rect = e.currentTarget.getBoundingClientRect()
              openAssetMenu(rect.left, rect.bottom + 2, m.asset_name, m.asset_id)
            }}
          >
            <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
          </button>
        }
      />
    </div>
  )
})}
```

Note: `m.asset_type_name` comes from the extended `AssetGroupMember` type (Task 2). `m.asset_color` is not in the member schema — asset color is only on the full `Asset` model. For the tree view, we show the default muted gray for all assets. If an asset has a custom color, it would need to be fetched separately or added to `AssetGroupMemberRead`. For now, use `'#8b949e'` as default since asset color assignment is manual and rare. This can be extended later by adding `asset_color` to the member read schema.

- [ ] **Step 4: Update indentation — remove tree connector lines**

The spec says indent per level = 24px. Remove the tree connector lines block (lines 88-135) entirely — the spec lists "Tree connecting lines / indent guides" as out of scope (future). The old connector lines used `depth * 16` math which no longer applies.

- [ ] **Step 5: Run AssetTreeNode tests**

```bash
./scripts/ui-test.sh --tail 10 src/components/AssetTree/AssetTreeNode.test.tsx
```

Expected: Tests may need updates since the DOM structure changed. Key behaviors to verify:
- Filter matching still works (unchanged — `matchesFilter` function is untouched)
- Selection still works (TreeNode handles visuals, parent handles state)
- Asset click passes parent group name (unchanged — callback wiring is the same)

Update test expectations if they query for DOM elements that moved (e.g., looking for specific class names that are now inside TreeNode).

- [ ] **Step 6: Commit**

```bash
git add ui/src/components/AssetTree/AssetTreeNode.tsx
git commit -m "refactor(ui): replace AssetTreeNode inline rendering with shared TreeNode + icons"
```

---

## Task 10: Integrate `TreeNode` into RegistryTree

**Files:**
- Modify: `ui/src/features/registry/RegistryTree.tsx`

- [ ] **Step 1: Add "All" row to RegistrySidebar**

In `ui/src/features/registry/RegistrySidebar.tsx`, add a `TreeNode` "All" row above the `RegistryTree`. This row shows "All SLOs", "All Datasources", or "All Assets" depending on active mode:

Add imports:
```typescript
import { TreeNode } from '@/components/tree'
import { getEntityIcon } from '@/components/tree'
```

Before `<RegistryTree .../>`, add:

```tsx
{/* "All" row */}
<TreeNode
  icon={getEntityIcon('all')}
  iconColor={!selected ? 'var(--primary)' : '#8b949e'}
  label={mode === 'slo' ? 'All SLOs' : mode === 'datasource' ? 'All Datasources' : 'All Assets'}
  depth={0}
  isExpandable={false}
  isExpanded={false}
  isSelected={!selected}
  selectionColor="var(--primary)"
  isGroup
  onClick={() => onSelect(null as unknown as SelectedNode)}
/>
<div className="mx-3 my-1 border-t border-border/50" />
```

Note: The "All" row deselects the current selection. The parent `SloRegistryPage` should handle `null` selection to show an overview panel. If the current `onSelect` signature doesn't accept null, this can be handled by adding a separate `onSelectAll` prop or by checking for a sentinel value. During implementation, check how `SloRegistryPage` handles the `selected` state and adapt accordingly.

- [ ] **Step 2: Replace TreeNodeRow with shared TreeNode**

Rewrite `ui/src/features/registry/RegistryTree.tsx`:

```tsx
import { useState } from 'react'
import { TreeNode } from '@/components/tree'
import { getEntityIcon, getAssetTypeIcon } from '@/components/tree'
import { NODE_TYPE_COLORS } from '@/lib/entity-colors'
import type { TreeNode as TreeNodeData, SelectedNode } from './types'

interface Props {
  nodes: TreeNodeData[]
  selected: SelectedNode | null
  onSelect: (node: SelectedNode) => void
}

export function RegistryTree({ nodes, selected, onSelect }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const toggle = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div
      className="flex-1 overflow-y-auto py-1"
      style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}
    >
      {nodes.map(node => (
        <RegistryNodeRow
          key={node.id}
          node={node}
          depth={0}
          expanded={expanded}
          onToggle={toggle}
          selected={selected}
          onSelect={onSelect}
        />
      ))}
      {nodes.length === 0 && (
        <div className="px-4 py-3 text-xs text-muted-foreground italic">No items</div>
      )}
    </div>
  )
}

function getIconForNode(node: TreeNodeData) {
  if (node.type === 'group' || node.type === 'asset') {
    return node.type === 'group' ? getEntityIcon('group') : getAssetTypeIcon('vm')
  }
  return getEntityIcon(node.type)
}

function getColorForNode(node: TreeNodeData) {
  return NODE_TYPE_COLORS[node.type] ?? '#c9d1d9'
}

function getBadgeForNode(node: TreeNodeData): { type: 'count' | 'version'; value: string | number } | undefined {
  if (!node.badge) return undefined
  if (node.badge.startsWith('v')) return { type: 'version', value: node.badge }
  return { type: 'count', value: node.badge }
}

function RegistryNodeRow({
  node,
  depth,
  expanded,
  onToggle,
  selected,
  onSelect,
  parentGroupName,
}: {
  node: TreeNodeData
  depth: number
  expanded: Set<string>
  onToggle: (id: string) => void
  selected: SelectedNode | null
  onSelect: (node: SelectedNode) => void
  parentGroupName?: string
}) {
  const hasChildren = node.children && node.children.length > 0
  const isExpanded = expanded.has(node.id)
  const isSelected = selected?.type === node.type && selected?.name === node.name
  const color = getColorForNode(node)
  const groupContext = node.type === 'group' ? node.name : parentGroupName

  return (
    <>
      <TreeNode
        testId={`node-${node.id}`}
        icon={getIconForNode(node)}
        iconColor={color}
        label={node.displayName ?? node.name}
        depth={depth}
        isExpandable={!!hasChildren}
        isExpanded={isExpanded}
        isSelected={isSelected}
        selectionColor={color}
        isGroup={node.type === 'group'}
        badge={getBadgeForNode(node)}
        onClick={() => onSelect({ type: node.type, name: node.name, groupName: groupContext })}
        onToggle={() => onToggle(node.id)}
      />
      {hasChildren && isExpanded && node.children!.map(child => (
        <RegistryNodeRow
          key={child.id}
          node={child}
          depth={depth + 1}
          expanded={expanded}
          onToggle={onToggle}
          selected={selected}
          onSelect={onSelect}
          parentGroupName={groupContext}
        />
      ))}
    </>
  )
}
```

- [ ] **Step 3: Run RegistryTree tests**

```bash
./scripts/ui-test.sh --tail 10 src/features/registry/RegistryTree.test.tsx
```

Expected: Tests should pass. The test queries `data-testid="node-..."` and `data-selected` which are preserved in the new TreeNode. The `data-testid="toggle-..."` query needs updating since TreeNode uses `aria-label="Toggle ..."` for the chevron button. Update tests:

Replace:
```typescript
fireEvent.click(screen.getByTestId('toggle-slo:http-slo'))
```
With:
```typescript
fireEvent.click(screen.getByLabelText('Toggle http-slo'))
```

Also update the `onSelect` expectation — with the new component, `groupName` will be `undefined` for top-level nodes:
```typescript
expect(onSelect).toHaveBeenCalledWith({ type: 'slo', name: 'http-slo', groupName: undefined })
```

- [ ] **Step 4: Commit**

```bash
git add ui/src/features/registry/RegistryTree.tsx ui/src/features/registry/RegistryTree.test.tsx ui/src/features/registry/RegistrySidebar.tsx
git commit -m "refactor(ui): replace RegistryTree inline rows with shared TreeNode + entity icons + All row"
```

---

## Task 11: Run all tests and fix regressions

**Files:**
- Various test files may need updates

- [ ] **Step 1: Run all UI tests**

```bash
./scripts/ui-test.sh --tail 30
```

- [ ] **Step 2: Fix any failing tests**

Common issues to watch for:
- Tests querying for old class names (`font-mono text-[13px]` on assets → now `text-[14px] font-normal` via TreeNode)
- Tests querying for `ChevronDown` (removed — TreeNode only uses `ChevronRight` with rotation)
- Tests checking `text-xs` (old RegistryTree font → now `text-[14px]` via TreeNode)
- Tests checking specific padding values (16px indent → 24px indent)

- [ ] **Step 3: Run API tests**

```bash
./scripts/api-test.sh --tail 10
```

- [ ] **Step 4: Run typecheck**

```bash
cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json
```

- [ ] **Step 5: Commit any test fixes**

```bash
git add -u
git commit -m "test: fix tree view test expectations after TreeNode integration"
```

---

## Task 12: Visual verification

**Files:** None (manual check)

- [ ] **Step 1: Start dev environment**

```bash
just dev
```

- [ ] **Step 2: Verify Navigator page**

Open Navigator. Check:
- All groups show `Folder` icon with color
- Asset leaves show type-specific icons (Server for VMs, etc.)
- 14px font, 32px row height, 24px indentation
- Filter input has Search icon, X clear button
- Chevron rotates on expand
- Selection uses group color for groups, primary for assets
- Count badges are filled pills

- [ ] **Step 3: Verify Assets page**

Open Assets page. Same checks as Navigator.

- [ ] **Step 4: Verify SLO Registry page**

Open Registry. Check:
- SLOs show `ShieldCheck` icon in green
- SLIs show `Braces` icon in purple
- Datasources show `Database` icon in blue
- Groups show `Folder` icon
- 14px font (was 12px), 32px row height (was ~24px)
- Version badges show as outlined tags (`v2`)
- Filter input matches Navigator/Assets style
- Chevron rotates (no more icon swap)

- [ ] **Step 5: Commit if any visual fixes needed**

---

## Spec Coverage Check

| Spec Section | Task |
|---|---|
| §1 Unified Dimensions (font, row height, indent, sidebar width) | Tasks 5, 8, 9, 10 |
| §2 Entity Icon Mapping | Task 3, 9, 10 |
| §3 Group Colors (DB + auto-assign) | Task 1 |
| §4 Asset Colors (DB column) | Task 1 |
| §5 load-test asset type | Task 1 |
| §6 Selection State (group-aware) | Task 5, 9, 10 |
| §7 Unified Filter Input | Tasks 4, 6, 7 |
| §8 Badge Format (count pill vs version tag) | Task 5, 10 |
| §9 "All" Row in Registry | Task 10 (add during integration) |
| §10 Chevron Behavior | Task 5 |
| Component Architecture — TreeNode | Task 5 |
| Component Architecture — TreeFilter | Task 4 |
| Component Architecture — Icon resolver | Task 3 |
