# SLO Registry UI Phase 4 — Sidebar with STANDARD / TEMPLATES / GROUPS

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the SLO mode sidebar to show three sections (STANDARD, TEMPLATES, GROUPS) matching the design mockup, add SLO group detail/create views, and extend the Create dropdown with template-aware options.

**Architecture:** The current `buildSloTree()` produces a flat list of all SLOs. We split it into three builders — one per section — using the existing `kind` field (`standard` vs `template`) and a new SLO groups API hook. Each section is a collapsible group in the existing `RegistryTree`. Detail panel gains new views for template SLOs and SLO groups. The Create dropdown adds "SLO Template" and "SLO Group" options.

**Tech Stack:** React 19, TypeScript 5.9, React Query, Vitest + React Testing Library, Tailwind v4, lucide-react icons.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `ui/src/features/slo-groups/types.ts` | SLO group TypeScript types |
| Create | `ui/src/features/slo-groups/api.ts` | SLO group API functions |
| Create | `ui/src/features/slo-groups/hooks.ts` | React Query hooks for SLO groups |
| Modify | `ui/src/lib/queryKeys.ts` | Add `sloGroupKeys` factory |
| Modify | `ui/src/lib/entity-colors.ts` | Add `template` and `sloGroup` colors |
| Modify | `ui/src/features/registry/types.ts` | Add `'template' \| 'slo-group'` to `NodeType` |
| Modify | `ui/src/features/registry/useRegistryTree.ts` | Split `buildSloTree` into 3 section builders |
| Modify | `ui/src/features/registry/RegistrySidebar.tsx` | Render 3 sections when `mode === 'slo'` |
| Modify | `ui/src/features/registry/RegistryTree.tsx` | Support section headers with collapse |
| Create | `ui/src/features/registry/details/SloGroupDetailView.tsx` | SLO group detail panel |
| Create | `ui/src/features/registry/details/TemplateDetailView.tsx` | Template SLO detail (read-only, shows group count) |
| Modify | `ui/src/features/registry/RegistryDetailPanel.tsx` | Route `template` and `slo-group` to new views |
| Modify | `ui/src/features/registry/RegistrySidebar.tsx` | Extend Create dropdown with Template + Group |
| Create | `ui/src/features/registry/forms/SloGroupForm.tsx` | SLO group creation form |
| Test | `ui/src/features/registry/useRegistryTree.test.ts` | Update tree builder tests |
| Test | `ui/src/features/registry/RegistrySidebar.test.tsx` | Test 3-section rendering |
| Test | `ui/src/features/registry/details/SloGroupDetailView.test.tsx` | Group detail panel |
| Test | `ui/src/features/registry/details/TemplateDetailView.test.tsx` | Template detail panel |
| Test | `ui/src/features/slo-groups/hooks.test.ts` | Hook tests |

---

### Task 1: SLO Group Types, API, and Hooks

**Files:**
- Create: `ui/src/features/slo-groups/types.ts`
- Create: `ui/src/features/slo-groups/api.ts`
- Create: `ui/src/features/slo-groups/hooks.ts`
- Modify: `ui/src/lib/queryKeys.ts`
- Test: `ui/src/features/slo-groups/hooks.test.ts`

- [ ] **Step 1: Create SLO group types**

```typescript
// ui/src/features/slo-groups/types.ts
export interface SloGroup {
  id: string
  name: string
  display_name: string | null
  template_slo_name: string
  template_slo_version: number
  gen_variables: Record<string, string[]>
  tags: Record<string, string>
  author: string | null
  version: number
  active: boolean
  created_at: string
  updated_at: string
  generated_slo_count: number
}

export interface SloGroupCreate {
  name: string
  display_name?: string
  template_slo_name: string
  template_slo_version: number
  gen_variables: Record<string, string[]>
  tags?: Record<string, string>
  author?: string
}
```

- [ ] **Step 2: Create SLO group API functions**

```typescript
// ui/src/features/slo-groups/api.ts
import type { SloGroup, SloGroupCreate } from './types'

const BASE = '/api'

export async function fetchSloGroups(): Promise<SloGroup[]> {
  const res = await fetch(`${BASE}/slo-groups`)
  if (!res.ok) throw new Error(`fetchSloGroups: ${res.status}`)
  const data: { items: SloGroup[]; total: number } = await res.json()
  return data.items
}

export async function fetchSloGroupDetail(name: string): Promise<SloGroup> {
  const res = await fetch(`${BASE}/slo-groups/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`fetchSloGroupDetail: ${res.status}`)
  return res.json()
}

export async function createSloGroup(body: SloGroupCreate): Promise<SloGroup> {
  const res = await fetch(`${BASE}/slo-groups`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`createSloGroup: ${res.status}`)
  return res.json()
}

export async function deleteSloGroup(name: string): Promise<void> {
  const res = await fetch(`${BASE}/slo-groups/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`deleteSloGroup: ${res.status}`)
}
```

- [ ] **Step 3: Add query key factory**

Add to `ui/src/lib/queryKeys.ts`:

```typescript
export const sloGroupKeys = {
  all: ['slo-groups'] as const,
  detail: (name: string) => [...sloGroupKeys.all, name] as const,
}
```

- [ ] **Step 4: Create React Query hooks**

```typescript
// ui/src/features/slo-groups/hooks.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { sloGroupKeys, sloKeys } from '@/lib/queryKeys'
import { fetchSloGroups, fetchSloGroupDetail, createSloGroup, deleteSloGroup } from './api'
import type { SloGroupCreate } from './types'

export function useSloGroups() {
  return useQuery({
    queryKey: sloGroupKeys.all,
    queryFn: fetchSloGroups,
  })
}

export function useSloGroupDetail(name: string) {
  return useQuery({
    queryKey: sloGroupKeys.detail(name),
    queryFn: () => fetchSloGroupDetail(name),
    enabled: !!name,
  })
}

export function useCreateSloGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: SloGroupCreate) => createSloGroup(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: sloGroupKeys.all })
      void qc.invalidateQueries({ queryKey: sloKeys.all })
    },
  })
}

export function useDeleteSloGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteSloGroup,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: sloGroupKeys.all })
      void qc.invalidateQueries({ queryKey: sloKeys.all })
    },
  })
}
```

- [ ] **Step 5: Write hook test**

```typescript
// ui/src/features/slo-groups/hooks.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useSloGroups } from './hooks'
import * as api from './api'

vi.mock('./api')

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('useSloGroups', () => {
  beforeEach(() => { vi.resetAllMocks() })

  it('returns SLO groups from API', async () => {
    const groups = [
      { id: '1', name: 'g1', display_name: null, template_slo_name: 'tpl',
        template_slo_version: 1, gen_variables: { x: ['a'] }, tags: {},
        author: null, version: 1, active: true, created_at: '', updated_at: '',
        generated_slo_count: 3 },
    ]
    vi.mocked(api.fetchSloGroups).mockResolvedValue(groups)

    const { result } = renderHook(() => useSloGroups(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(groups)
  })
})
```

- [ ] **Step 6: Run test to verify it passes**

Run: `./scripts/ui-test.sh --tail 10 src/features/slo-groups/hooks.test.ts`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git -C /path/to/worktree add ui/src/features/slo-groups/ ui/src/lib/queryKeys.ts
git -C /path/to/worktree commit -m "feat(ui): add SLO group types, API, and hooks"
```

---

### Task 2: Extend Entity Colors and NodeType for Templates + Groups

**Files:**
- Modify: `ui/src/lib/entity-colors.ts`
- Modify: `ui/src/features/registry/types.ts`

- [ ] **Step 1: Add template and sloGroup colors**

In `ui/src/lib/entity-colors.ts`, add to `ENTITY_COLORS`:

```typescript
export const ENTITY_COLORS = {
  slo: '#7dc540',
  sli: '#A371F7',
  ds: '#58A6FF',
  group: '#8B949E',
  template: '#F0B429',   // yellow/amber for template SLOs (matches mockup)
  sloGroup: '#8B949E',   // gray for SLO groups (matches mockup)
} as const
```

And add to `NODE_TYPE_COLORS`:

```typescript
export const NODE_TYPE_COLORS: Record<string, string> = {
  slo: ENTITY_COLORS.slo,
  sli: ENTITY_COLORS.sli,
  datasource: ENTITY_COLORS.ds,
  group: ENTITY_COLORS.group,
  asset: '#c9d1d9',
  binding: ENTITY_COLORS.slo,
  template: ENTITY_COLORS.template,
  'slo-group': ENTITY_COLORS.sloGroup,
}
```

- [ ] **Step 2: Extend NodeType in types.ts**

In `ui/src/features/registry/types.ts`:

```typescript
export type NodeType = 'group' | 'asset' | 'slo' | 'sli' | 'datasource' | 'binding' | 'template' | 'slo-group'
```

- [ ] **Step 3: Commit**

```bash
git -C /path/to/worktree add ui/src/lib/entity-colors.ts ui/src/features/registry/types.ts
git -C /path/to/worktree commit -m "feat(ui): add template/slo-group colors and node types"
```

---

### Task 3: Split SLO Tree into 3-Section Builder

**Files:**
- Modify: `ui/src/features/registry/useRegistryTree.ts`
- Modify: `ui/src/features/registry/useRegistryTree.test.ts`

The design mockup shows three sections in SLO mode:
- **STANDARD**: `kind === 'standard'` and NOT generated by a group (no `group_id`)
- **TEMPLATES**: `kind === 'template'`
- **GROUPS**: SLO groups (from `/slo-groups` API)

- [ ] **Step 1: Add `subtitle` to TreeNode and `kind` to MinSlo**

These type changes are prerequisites for the test and implementation that follow.

In `ui/src/features/registry/types.ts`, add `subtitle?: string` to `TreeNode`:

```typescript
export interface TreeNode {
  id: string
  name: string
  displayName?: string
  type: NodeType
  badge?: string
  subtitle?: string  // Secondary line (e.g., "via template-name", "2 groups")
  children?: TreeNode[]
  bindingChain?: { sloName: string; sliName: string; dsName: string }
  groupName?: string
}
```

In `ui/src/features/registry/useRegistryTree.ts`, add `kind?: string` to the **existing** `MinSlo` interface (do NOT redeclare the entire interface — just add the field):

```typescript
export interface MinSlo {
  name: string
  display_name?: string | null
  version: number
  active: boolean
  sli_name?: string | null
  sli_version?: number | null
  kind?: string                    // ← add this line
}
```

- [ ] **Step 2: Write failing tests for new tree builders**

Add to `ui/src/features/registry/useRegistryTree.test.ts`:

```typescript
import { buildSloSections } from './useRegistryTree'
import type { SloGroup } from '@/features/slo-groups/types'

describe('buildSloSections', () => {
  const slis = [
    { name: 'http-sli', display_name: null, adapter_type: 'prometheus', active: true, indicators: { latency: 'q' } },
  ]
  const datasources = [{ name: 'prom', display_name: null, adapter_type: 'prometheus' }]
  const bindings = [{ slo_name: 'web-perf', data_source_name: 'prom' }]

  it('separates standard SLOs from templates', () => {
    const slos = [
      { name: 'web-perf', display_name: null, version: 3, active: true, sli_name: 'http-sli', sli_version: 1, kind: 'standard' },
      { name: 'plugin-tpl', display_name: null, version: 1, active: true, sli_name: 'http-sli', sli_version: 1, kind: 'template' },
    ]
    const groups: SloGroup[] = []
    const { standard, templates, groupNodes } = buildSloSections(slos, slis, datasources, bindings, groups)
    expect(standard).toHaveLength(1)
    expect(standard[0].name).toBe('web-perf')
    expect(templates).toHaveLength(1)
    expect(templates[0].name).toBe('plugin-tpl')
    expect(templates[0].type).toBe('template')
    expect(groupNodes).toHaveLength(0)
  })

  it('builds group nodes with badge and subtitle', () => {
    const slos = [
      { name: 'web-perf', display_name: null, version: 1, active: true, sli_name: null, sli_version: null, kind: 'standard' },
    ]
    const groups: SloGroup[] = [
      { id: '1', name: 'app-plugins', display_name: 'App Plugins', template_slo_name: 'plugin-tpl',
        template_slo_version: 1, gen_variables: {}, tags: {}, author: null, version: 1,
        active: true, created_at: '', updated_at: '', generated_slo_count: 30 },
    ]
    const { groupNodes } = buildSloSections(slos, slis, datasources, bindings, groups)
    expect(groupNodes).toHaveLength(1)
    expect(groupNodes[0].name).toBe('app-plugins')
    expect(groupNodes[0].type).toBe('slo-group')
    expect(groupNodes[0].badge).toBe('30 SLOs')
    expect(groupNodes[0].subtitle).toBe('via plugin-tpl')
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `./scripts/ui-test.sh --tail 10 src/features/registry/useRegistryTree.test.ts`
Expected: FAIL — `buildSloSections` not exported

- [ ] **Step 4: Implement `buildSloSections`**

Add to `useRegistryTree.ts` — the `MinSlo` interface already has `kind` from Step 1:

```typescript
import type { SloGroup } from '@/features/slo-groups/types'

export function buildSloSections(
  slos: MinSlo[],
  slis: MinSli[],
  datasources: MinDs[],
  bindings: MinBinding[],
  groups: SloGroup[],
): { standard: TreeNode[]; templates: TreeNode[]; groupNodes: TreeNode[] } {
  const sliByName = new Map(slis.map(s => [s.name, s]))
  const dsByName = new Map(datasources.map(d => [d.name, d]))

  const activeSlos = slos.filter(s => s.active)
  const standardSlos = activeSlos.filter(s => (s.kind ?? 'standard') === 'standard')
  const templateSlos = activeSlos.filter(s => s.kind === 'template')

  // Build standard SLO nodes (same as current buildSloTree for standard kind)
  const standard: TreeNode[] = standardSlos.map(slo => {
    const sloBindings = bindings.filter(b => b.slo_name === slo.name)
    const dsNames = [...new Set(sloBindings.map(b => b.data_source_name))]
    const dsChildren: TreeNode[] = dsNames.map(dsName => ({
      id: `ds:${dsName}`,
      name: dsName,
      displayName: dsByName.get(dsName)?.display_name ?? undefined,
      type: 'datasource' as const,
    }))
    const sliChildren: TreeNode[] = []
    if (slo.sli_name) {
      const sli = sliByName.get(slo.sli_name)
      const indicatorCount = sli?.indicators ? Object.keys(sli.indicators).length : 0
      sliChildren.push({
        id: `sli:${slo.sli_name}`,
        name: slo.sli_name,
        displayName: sli?.display_name ?? undefined,
        type: 'sli' as const,
        badge: `${indicatorCount} indicators`,
        children: dsChildren,
      })
    }
    return {
      id: `slo:${slo.name}`,
      name: slo.name,
      displayName: slo.display_name ?? undefined,
      type: 'slo' as const,
      badge: `v${slo.version}`,
      children: sliChildren.length > 0 ? sliChildren : dsChildren,
    }
  })

  // Build template nodes
  const templates: TreeNode[] = templateSlos.map(slo => {
    // Count how many groups reference this template
    const refGroups = groups.filter(g => g.template_slo_name === slo.name)
    return {
      id: `template:${slo.name}`,
      name: slo.name,
      displayName: slo.display_name ?? undefined,
      type: 'template' as const,
      badge: `v${slo.version}`,
      subtitle: `${refGroups.length} group${refGroups.length !== 1 ? 's' : ''}`,
    }
  })

  // Build group nodes
  const groupNodes: TreeNode[] = groups.filter(g => g.active).map(g => ({
    id: `slo-group:${g.name}`,
    name: g.name,
    displayName: g.display_name ?? undefined,
    type: 'slo-group' as const,
    badge: `${g.generated_slo_count} SLOs`,
    subtitle: `via ${g.template_slo_name}`,
  }))

  return { standard, templates, groupNodes }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./scripts/ui-test.sh --tail 10 src/features/registry/useRegistryTree.test.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git -C /path/to/worktree add ui/src/features/registry/useRegistryTree.ts ui/src/features/registry/useRegistryTree.test.ts ui/src/features/registry/types.ts
git -C /path/to/worktree commit -m "feat(ui): split SLO tree into standard/templates/groups sections"
```

---

### Task 4: Update RegistryTree to Render Subtitles and Section Headers

**Files:**
- Modify: `ui/src/features/registry/RegistryTree.tsx`
- Modify: `ui/src/features/registry/RegistryTree.test.tsx`

The mockup shows section headers ("STANDARD", "TEMPLATES", "GROUPS") as small gray uppercase labels with a thin divider line. Template nodes show a subtitle line below the name (e.g., "2 groups"). Group nodes show a subtitle (e.g., "via plugin-health-tpl").

- [ ] **Step 1: Write failing test for subtitle rendering**

Add to `ui/src/features/registry/RegistryTree.test.tsx`:

```typescript
it('renders subtitle text below the node name', () => {
  const nodes: TreeNode[] = [
    { id: 'slo-group:g1', name: 'app-plugins', type: 'slo-group', badge: '30 SLOs', subtitle: 'via plugin-tpl' },
  ]
  render(<RegistryTree nodes={nodes} selected={null} onSelect={vi.fn()} />)
  expect(screen.getByText('app-plugins')).toBeInTheDocument()
  expect(screen.getByText('via plugin-tpl')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./scripts/ui-test.sh --tail 10 src/features/registry/RegistryTree.test.tsx`
Expected: FAIL — subtitle text not rendered

- [ ] **Step 3: Add subtitle rendering to TreeNodeRow**

In `RegistryTree.tsx`, modify `TreeNodeRow` to render the subtitle below the name when present:

```tsx
{/* Replace the name button with a flex column when subtitle exists */}
<button
  onClick={() => onSelect({ type: node.type, name: node.name, groupName: groupContext })}
  className="flex-1 text-left text-xs truncate"
  style={{ color }}
>
  <span className="truncate">{node.displayName ?? node.name}</span>
  {node.subtitle && (
    <span className="block text-[10px] text-muted-foreground truncate mt-0.5">
      {node.subtitle}
    </span>
  )}
</button>
```

- [ ] **Step 4: Add SectionHeader component**

Add to `RegistryTree.tsx` a section header component that can be used by the sidebar:

```tsx
export function SectionHeader({ label }: { label: string }) {
  return (
    <div className="px-3 pt-3 pb-1">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <div className="border-b border-border/50 mt-1" />
    </div>
  )
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./scripts/ui-test.sh --tail 10 src/features/registry/RegistryTree.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git -C /path/to/worktree add ui/src/features/registry/RegistryTree.tsx ui/src/features/registry/RegistryTree.test.tsx
git -C /path/to/worktree commit -m "feat(ui): add subtitle rendering and section headers to tree"
```

---

### Task 5: Rewire RegistrySidebar for 3-Section SLO Mode

**Files:**
- Modify: `ui/src/features/registry/RegistrySidebar.tsx`
- Modify: `ui/src/features/registry/RegistrySidebar.test.tsx`

When `mode === 'slo'`, instead of calling `buildSloTree()` and rendering a flat list, the sidebar calls `buildSloSections()` and renders three sections with `SectionHeader` + `RegistryTree` for each.

- [ ] **Step 1: Write failing test for 3-section rendering**

Add to `ui/src/features/registry/RegistrySidebar.test.tsx`:

```typescript
it('renders STANDARD, TEMPLATES, GROUPS section headers in SLO mode', async () => {
  // Mock useSlos to return both standard + template SLOs
  // Mock useSloGroups to return groups
  // Render with mode='slo'
  expect(screen.getByText('STANDARD')).toBeInTheDocument()
  expect(screen.getByText('TEMPLATES')).toBeInTheDocument()
  expect(screen.getByText('GROUPS')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./scripts/ui-test.sh --tail 10 src/features/registry/RegistrySidebar.test.tsx`
Expected: FAIL

- [ ] **Step 3: Modify RegistrySidebar to use sections**

Import `useSloGroups` from `@/features/slo-groups/hooks` and `buildSloSections` from `./useRegistryTree`. Import `SectionHeader` from `./RegistryTree`.

When `mode === 'slo'`, compute sections:

```typescript
const { data: sloGroups } = useSloGroups()

const sloSections = useMemo(() => {
  if (mode !== 'slo') return null
  return buildSloSections(slos ?? [], slis ?? [], datasources ?? [], allBindings, sloGroups ?? [])
}, [mode, slos, slis, datasources, allBindings, sloGroups])
```

Replace the tree rendering section with conditional logic:

```tsx
{mode === 'slo' && sloSections ? (
  <div className="flex-1 overflow-y-auto">
    <SectionHeader label="STANDARD" />
    <RegistryTree
      nodes={filterTree(sloSections.standard, search)}
      selected={selected}
      onSelect={onSelect}
    />
    <SectionHeader label="TEMPLATES" />
    <RegistryTree
      nodes={filterTree(sloSections.templates, search)}
      selected={selected}
      onSelect={onSelect}
    />
    <SectionHeader label="GROUPS" />
    <RegistryTree
      nodes={filterTree(sloSections.groupNodes, search)}
      selected={selected}
      onSelect={onSelect}
    />
  </div>
) : (
  <RegistryTree nodes={filteredNodes} selected={selected} onSelect={onSelect} />
)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/ui-test.sh --tail 10 src/features/registry/RegistrySidebar.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /path/to/worktree add ui/src/features/registry/RegistrySidebar.tsx ui/src/features/registry/RegistrySidebar.test.tsx
git -C /path/to/worktree commit -m "feat(ui): render 3-section SLO sidebar (standard/templates/groups)"
```

---

### Task 6: Template SLO Detail View

**Files:**
- Create: `ui/src/features/registry/details/TemplateDetailView.tsx`
- Create: `ui/src/features/registry/details/TemplateDetailView.test.tsx`
- Modify: `ui/src/features/registry/RegistryDetailPanel.tsx`

When a template node is selected in the sidebar, the detail panel shows the template SLO definition with:
- Amber accent strip (template color)
- Name + version + "template" badge
- Objectives table (reuse `SloObjectiveTable`)
- Variables list (highlighting `$__gen_*` placeholders)
- List of groups referencing this template
- Read-only indicator (templates are edited via the SLO wizard)

- [ ] **Step 1: Write failing test**

```typescript
// ui/src/features/registry/details/TemplateDetailView.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { TemplateDetailView } from './TemplateDetailView'

vi.mock('@/features/slos/hooks', () => ({
  useSloDetail: () => ({
    data: {
      name: 'plugin-tpl', version: 1, kind: 'template', active: true,
      display_name: 'Plugin Health', objectives: [], tags: {},
      variables: { process_name: '$__gen_process_name', AGGREGATION_WINDOW: '5m' },
      comparison: {}, notes: null, author: null,
      total_score_pass_pct: 90, total_score_warning_pct: 75,
      sli_name: 'plugin-sli', sli_version: 1, created_at: '2026-01-01',
      comparable_from_version: 1, id: '1',
    },
    isLoading: false,
  }),
}))

vi.mock('@/features/slo-groups/hooks', () => ({
  useSloGroups: () => ({
    data: [
      { name: 'app-x-plugins', template_slo_name: 'plugin-tpl', generated_slo_count: 3, active: true },
    ],
  }),
}))

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('TemplateDetailView', () => {
  it('renders template name and template badge', () => {
    render(<TemplateDetailView name="plugin-tpl" onNavigate={vi.fn()} />, { wrapper })
    expect(screen.getByText('Plugin Health')).toBeInTheDocument()
    expect(screen.getByText('template')).toBeInTheDocument()
  })

  it('shows groups referencing this template', () => {
    render(<TemplateDetailView name="plugin-tpl" onNavigate={vi.fn()} />, { wrapper })
    expect(screen.getByText('app-x-plugins')).toBeInTheDocument()
  })

  it('highlights gen variables', () => {
    render(<TemplateDetailView name="plugin-tpl" onNavigate={vi.fn()} />, { wrapper })
    expect(screen.getByText('$__gen_process_name')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./scripts/ui-test.sh --tail 10 src/features/registry/details/TemplateDetailView.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Implement TemplateDetailView**

```tsx
// ui/src/features/registry/details/TemplateDetailView.tsx
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import { SloObjectiveTable } from '@/features/slos/components/SloObjectiveTable'
import { useSloDetail } from '@/features/slos/hooks'
import { useSloGroups } from '@/features/slo-groups/hooks'
import type { SelectedNode } from '@/features/registry/types'

interface Props {
  name: string
  onNavigate: (node: SelectedNode) => void
}

export function TemplateDetailView({ name, onNavigate }: Props) {
  const { data: slo, isLoading } = useSloDetail(name)
  const { data: groups } = useSloGroups()

  if (isLoading || !slo) {
    return (
      <div className="p-4 text-sm text-muted-foreground" style={{ fontFamily: SANS_SERIF }}>
        Loading...
      </div>
    )
  }

  const referencingGroups = (groups ?? []).filter(
    g => g.template_slo_name === slo.name && g.active,
  )

  return (
    <div className="overflow-auto h-full" style={{ fontFamily: SANS_SERIF }}>
      <div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.template }} />
      <div className="p-6 space-y-6">
        {/* Header */}
        <div>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h2 className="text-xl font-semibold text-foreground truncate">
                {slo.display_name ?? slo.name}
              </h2>
              <p className="text-xs font-mono text-muted-foreground mt-0.5">{slo.name}</p>
            </div>
            <div className="flex shrink-0 gap-1.5 items-center">
              <span className="px-2 py-0.5 text-xs rounded-full border border-border bg-muted/40 text-muted-foreground">
                v{slo.version}
              </span>
              <span
                className="px-2 py-0.5 text-xs rounded-full border"
                style={{
                  borderColor: `${ENTITY_COLORS.template}40`,
                  backgroundColor: `${ENTITY_COLORS.template}15`,
                  color: ENTITY_COLORS.template,
                }}
              >
                template
              </span>
            </div>
          </div>
        </div>

        {/* SLI link */}
        {slo.sli_name && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">SLI Definition</p>
            <button
              className="text-sm text-primary hover:underline"
              onClick={() => onNavigate({ type: 'sli', name: slo.sli_name! })}
            >
              {slo.sli_name} v{slo.sli_version}
            </button>
          </div>
        )}

        {/* Objectives */}
        {slo.objectives.length > 0 && (
          <div>
            <SloObjectiveTable slo={slo} />
          </div>
        )}

        {/* Variables — highlight $__gen_ placeholders */}
        {Object.keys(slo.variables).length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2">Variables</p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(slo.variables).map(([k, v]) => {
                const isGen = v.includes('$__gen_')
                return (
                  <span
                    key={k}
                    className={`px-2 py-0.5 text-xs rounded-full border ${
                      isGen
                        ? 'border-amber-600/30 bg-amber-950/20 text-amber-400'
                        : 'border-border bg-muted/40 text-muted-foreground'
                    }`}
                  >
                    {k}={v}
                  </span>
                )
              })}
            </div>
          </div>
        )}

        {/* Referencing groups */}
        <div>
          <p className="text-xs text-muted-foreground mb-2">
            Groups ({referencingGroups.length})
          </p>
          {referencingGroups.length === 0 ? (
            <p className="text-xs text-muted-foreground">No groups use this template</p>
          ) : (
            <ul className="space-y-1">
              {referencingGroups.map(g => (
                <li key={g.name}>
                  <button
                    className="text-sm text-primary hover:underline"
                    onClick={() => onNavigate({ type: 'slo-group', name: g.name })}
                  >
                    {g.display_name ?? g.name}
                  </button>
                  <span className="text-xs text-muted-foreground ml-2">
                    {g.generated_slo_count} SLOs
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Tags */}
        {Object.keys(slo.tags).length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2">Tags</p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(slo.tags).map(([k, v]) => (
                <span
                  key={k}
                  className="px-2 py-0.5 text-xs rounded-full bg-primary/10 text-primary border border-primary/20"
                >
                  {k}: {v}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./scripts/ui-test.sh --tail 10 src/features/registry/details/TemplateDetailView.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /path/to/worktree add ui/src/features/registry/details/TemplateDetailView.tsx ui/src/features/registry/details/TemplateDetailView.test.tsx
git -C /path/to/worktree commit -m "feat(ui): add template SLO detail view with gen-var highlighting"
```

---

### Task 7: SLO Group Detail View

**Files:**
- Create: `ui/src/features/registry/details/SloGroupDetailView.tsx`
- Create: `ui/src/features/registry/details/SloGroupDetailView.test.tsx`

When an SLO group node is selected, the detail panel shows:
- Gray accent strip
- Group name + display_name
- Template SLO link (clickable → navigates to template detail)
- `gen_variables` table
- Generated SLO count
- Tags
- Delete button

- [ ] **Step 1: Write failing test**

```typescript
// ui/src/features/registry/details/SloGroupDetailView.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { SloGroupDetailView } from './SloGroupDetailView'

vi.mock('@/features/slo-groups/hooks', () => ({
  useSloGroupDetail: () => ({
    data: {
      id: '1', name: 'app-x-plugins', display_name: 'App-X Plugins',
      template_slo_name: 'plugin-tpl', template_slo_version: 1,
      gen_variables: { process_name: ['auth', 'cache', 'db'] },
      tags: { app: 'app-x' }, author: 'admin', version: 1,
      active: true, created_at: '2026-01-01', updated_at: '2026-01-01',
      generated_slo_count: 3,
    },
    isLoading: false,
  }),
  useDeleteSloGroup: () => ({ mutate: vi.fn(), isPending: false }),
}))

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('SloGroupDetailView', () => {
  it('renders group name and template link', () => {
    render(<SloGroupDetailView name="app-x-plugins" onNavigate={vi.fn()} />, { wrapper })
    expect(screen.getByText('App-X Plugins')).toBeInTheDocument()
    expect(screen.getByText('plugin-tpl v1')).toBeInTheDocument()
  })

  it('shows gen_variables as a table', () => {
    render(<SloGroupDetailView name="app-x-plugins" onNavigate={vi.fn()} />, { wrapper })
    expect(screen.getByText('process_name')).toBeInTheDocument()
    expect(screen.getByText('auth')).toBeInTheDocument()
    expect(screen.getByText('cache')).toBeInTheDocument()
    expect(screen.getByText('db')).toBeInTheDocument()
  })

  it('shows generated SLO count', () => {
    render(<SloGroupDetailView name="app-x-plugins" onNavigate={vi.fn()} />, { wrapper })
    expect(screen.getByText('3 SLOs generated')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./scripts/ui-test.sh --tail 10 src/features/registry/details/SloGroupDetailView.test.tsx`
Expected: FAIL

- [ ] **Step 3: Implement SloGroupDetailView**

```tsx
// ui/src/features/registry/details/SloGroupDetailView.tsx
import { useState } from 'react'
import { Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { DeletionConfirmForm } from '@/components/DeletionConfirmForm'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import { useSloGroupDetail, useDeleteSloGroup } from '@/features/slo-groups/hooks'
import type { SelectedNode } from '@/features/registry/types'

interface Props {
  name: string
  onNavigate: (node: SelectedNode) => void
}

export function SloGroupDetailView({ name, onNavigate }: Props) {
  const [showDelete, setShowDelete] = useState(false)
  const { data: group, isLoading } = useSloGroupDetail(name)
  const deleteMutation = useDeleteSloGroup()

  if (isLoading || !group) {
    return (
      <div className="p-4 text-sm text-muted-foreground" style={{ fontFamily: SANS_SERIF }}>
        Loading...
      </div>
    )
  }

  function handleDelete() {
    deleteMutation.mutate(group!.name)
    setShowDelete(false)
  }

  // Compute variable rows: transpose gen_variables map into row-oriented data
  const varKeys = Object.keys(group.gen_variables)
  const rowCount = Math.max(0, ...varKeys.map(k => group.gen_variables[k].length))
  const rows = Array.from({ length: rowCount }, (_, i) =>
    varKeys.map(k => group.gen_variables[k][i] ?? ''),
  )

  return (
    <div className="overflow-auto h-full" style={{ fontFamily: SANS_SERIF }}>
      <div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.sloGroup }} />
      <div className="p-6 space-y-6">
        {/* Header */}
        <div>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h2 className="text-xl font-semibold text-foreground truncate">
                {group.display_name ?? group.name}
              </h2>
              <p className="text-xs font-mono text-muted-foreground mt-0.5">{group.name}</p>
            </div>
            <span className="px-2 py-0.5 text-xs rounded-full border border-border bg-muted/40 text-muted-foreground shrink-0">
              v{group.version}
            </span>
          </div>

          <div className="flex gap-2 mt-3">
            <Button
              size="xs"
              variant="outline"
              className="text-red-400 border-red-700/40 hover:bg-red-950/20"
              onClick={() => setShowDelete(true)}
            >
              <Trash2 className="size-3" />
              Delete Group
            </Button>
          </div>

          {showDelete && (
            <div className="mt-3">
              <DeletionConfirmForm
                title={`Delete group "${group.name}"?`}
                onConfirm={handleDelete}
                onCancel={() => setShowDelete(false)}
                confirmLabel="Delete"
                pendingLabel="Deleting…"
                isPending={deleteMutation.isPending}
                requireReason={false}
              />
            </div>
          )}
        </div>

        {/* Template link */}
        <div>
          <p className="text-xs text-muted-foreground mb-1">Template SLO</p>
          <button
            className="text-sm text-primary hover:underline"
            onClick={() => onNavigate({ type: 'template', name: group.template_slo_name })}
          >
            {group.template_slo_name} v{group.template_slo_version}
          </button>
        </div>

        {/* Generated count */}
        <div>
          <p className="text-sm text-foreground">{group.generated_slo_count} SLOs generated</p>
        </div>

        {/* Gen variables table */}
        {varKeys.length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2">Generator Variables</p>
            <div className="border border-border rounded overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-muted/30">
                    {varKeys.map(k => (
                      <th key={k} className="text-left px-3 py-1.5 text-muted-foreground font-medium">
                        {k}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr key={i} className="border-t border-border/50">
                      {row.map((val, j) => (
                        <td key={j} className="px-3 py-1.5 text-foreground font-mono">{val}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tags */}
        {Object.keys(group.tags).length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2">Tags</p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(group.tags).map(([k, v]) => (
                <span
                  key={k}
                  className="px-2 py-0.5 text-xs rounded-full bg-primary/10 text-primary border border-primary/20"
                >
                  {k}: {v}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Author */}
        {group.author && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">Author</p>
            <p className="text-sm text-foreground">{group.author}</p>
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./scripts/ui-test.sh --tail 10 src/features/registry/details/SloGroupDetailView.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /path/to/worktree add ui/src/features/registry/details/SloGroupDetailView.tsx ui/src/features/registry/details/SloGroupDetailView.test.tsx
git -C /path/to/worktree commit -m "feat(ui): add SLO group detail view with gen_variables table"
```

---

### Task 8: Wire Detail Panel to Template + Group Views

**Files:**
- Modify: `ui/src/features/registry/RegistryDetailPanel.tsx`
- Modify: `ui/src/features/registry/RegistryDetailPanel.test.tsx`

- [ ] **Step 1: Write failing test**

```typescript
it('renders TemplateDetailView for template node', () => {
  render(
    <RegistryDetailPanel
      selected={{ type: 'template', name: 'plugin-tpl' }}
      onNavigate={vi.fn()}
    />,
    { wrapper },
  )
  // TemplateDetailView renders the template name
  expect(screen.getByText(/loading/i)).toBeInTheDocument()
})

it('renders SloGroupDetailView for slo-group node', () => {
  render(
    <RegistryDetailPanel
      selected={{ type: 'slo-group', name: 'app-plugins' }}
      onNavigate={vi.fn()}
    />,
    { wrapper },
  )
  expect(screen.getByText(/loading/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./scripts/ui-test.sh --tail 10 src/features/registry/RegistryDetailPanel.test.tsx`
Expected: FAIL

- [ ] **Step 3: Add template and slo-group cases to RegistryDetailPanel**

```tsx
import { TemplateDetailView } from './details/TemplateDetailView'
import { SloGroupDetailView } from './details/SloGroupDetailView'

// Add before the asset/group fallback:
if (selected.type === 'template') {
  return <TemplateDetailView name={selected.name} onNavigate={onNavigate} />
}

if (selected.type === 'slo-group') {
  return <SloGroupDetailView name={selected.name} onNavigate={onNavigate} />
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/ui-test.sh --tail 10 src/features/registry/RegistryDetailPanel.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /path/to/worktree add ui/src/features/registry/RegistryDetailPanel.tsx ui/src/features/registry/RegistryDetailPanel.test.tsx
git -C /path/to/worktree commit -m "feat(ui): route template and slo-group selection to detail views"
```

---

### Task 9: Extend Create Dropdown with Template + Group Options

**Files:**
- Modify: `ui/src/features/registry/RegistrySidebar.tsx`

The mockup shows the Create dropdown with 5 items (colored accent bars):
1. **SLO Definition** (green) — Standard SLO with criteria
2. **SLO Template** (amber) — Reusable template for groups
3. **SLO Group** (gray) — Generate SLOs from template
4. **SLI Definition** (purple) — Query templates for metrics
5. **Datasource** (blue) — Connection to data backend

- [ ] **Step 1: Extend onCreateAction type**

Update the `Props` interface and `CreateDropdown` items:

```typescript
onCreateAction: (type: 'datasource' | 'sli' | 'slo' | 'group' | 'slo-template' | 'slo-group', context?: { adapterType?: string }) => void
```

- [ ] **Step 2: Update CreateDropdown items array**

```typescript
const items = [
  { type: 'slo' as const, label: 'SLO Definition', desc: 'Standard SLO with criteria', color: ENTITY_COLORS.slo },
  { type: 'slo-template' as const, label: 'SLO Template', desc: 'Reusable template for groups', color: ENTITY_COLORS.template },
  { type: 'slo-group' as const, label: 'SLO Group', desc: 'Generate SLOs from template', color: ENTITY_COLORS.sloGroup },
  { type: 'sli' as const, label: 'SLI Definition', desc: 'Query templates for metrics', color: ENTITY_COLORS.sli },
  { type: 'datasource' as const, label: 'Datasource', desc: 'Connection to data backend', color: ENTITY_COLORS.ds },
]
```

- [ ] **Step 3: Commit**

```bash
git -C /path/to/worktree add ui/src/features/registry/RegistrySidebar.tsx
git -C /path/to/worktree commit -m "feat(ui): add SLO Template and SLO Group to Create dropdown"
```

---

### Task 10: SLO Group Creation Form (Stub)

**Files:**
- Create: `ui/src/features/registry/forms/SloGroupForm.tsx`
- Create: `ui/src/features/registry/forms/SloGroupForm.test.tsx`

This task creates a basic creation form for SLO groups. The form matches the "New SLO Group" mockup:
- Name + display name fields
- Template SLO selector (dropdown from template SLOs)
- Gen variables editor (key + values table)
- Tags
- Generate button

This is a stub that captures the form layout and creates the group via the API. The full gen_variables editor (interactive table from the mockup) can be refined iteratively.

- [ ] **Step 1: Write failing test**

```typescript
// ui/src/features/registry/forms/SloGroupForm.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { SloGroupForm } from './SloGroupForm'

vi.mock('@/features/slos/hooks', () => ({
  useSlos: () => ({
    data: [
      { name: 'plugin-tpl', kind: 'template', version: 1, active: true },
    ],
  }),
}))

vi.mock('@/features/slo-groups/hooks', () => ({
  useCreateSloGroup: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('SloGroupForm', () => {
  it('renders name field and template selector', () => {
    render(<SloGroupForm onClose={vi.fn()} />, { wrapper })
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument()
    expect(screen.getByText(/template slo/i)).toBeInTheDocument()
  })

  it('shows generate button', () => {
    render(<SloGroupForm onClose={vi.fn()} />, { wrapper })
    expect(screen.getByRole('button', { name: /generate/i })).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./scripts/ui-test.sh --tail 10 src/features/registry/forms/SloGroupForm.test.tsx`
Expected: FAIL

- [ ] **Step 3: Implement SloGroupForm**

```tsx
// ui/src/features/registry/forms/SloGroupForm.tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import { useSlos } from '@/features/slos/hooks'
import { useCreateSloGroup } from '@/features/slo-groups/hooks'

interface Props {
  onClose: () => void
}

export function SloGroupForm({ onClose }: Props) {
  const { data: slos } = useSlos()
  const createMutation = useCreateSloGroup()

  const [name, setName] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [templateSloName, setTemplateSloName] = useState('')
  const [genVarsText, setGenVarsText] = useState('')

  const templateSlos = (slos ?? []).filter(s => s.kind === 'template' && s.active)
  const selectedTemplate = templateSlos.find(t => t.name === templateSloName)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name || !templateSloName || !selectedTemplate) return

    // Parse gen_variables from simple text format: key=val1,val2,val3 (one per line)
    const genVariables: Record<string, string[]> = {}
    for (const line of genVarsText.split('\n').filter(l => l.trim())) {
      const [key, ...rest] = line.split('=')
      if (key && rest.length > 0) {
        genVariables[key.trim()] = rest.join('=').split(',').map(v => v.trim())
      }
    }

    await createMutation.mutateAsync({
      name,
      display_name: displayName || undefined,
      template_slo_name: templateSloName,
      template_slo_version: selectedTemplate.version,
      gen_variables: genVariables,
    })
    onClose()
  }

  return (
    <div className="overflow-auto h-full" style={{ fontFamily: SANS_SERIF }}>
      <div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.sloGroup }} />
      <form onSubmit={handleSubmit} className="p-6 space-y-4">
        <h2 className="text-lg font-semibold text-foreground">New SLO Group</h2>

        <div>
          <label htmlFor="group-name" className="block text-xs text-muted-foreground mb-1">
            Name
          </label>
          <input
            id="group-name"
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            className="w-full px-3 py-1.5 text-sm bg-muted/30 border border-border rounded text-foreground"
            placeholder="app-x-plugins"
          />
        </div>

        <div>
          <label htmlFor="group-display" className="block text-xs text-muted-foreground mb-1">
            Display Name
          </label>
          <input
            id="group-display"
            type="text"
            value={displayName}
            onChange={e => setDisplayName(e.target.value)}
            className="w-full px-3 py-1.5 text-sm bg-muted/30 border border-border rounded text-foreground"
            placeholder="App-X Plugin Monitoring"
          />
        </div>

        <div>
          <p className="text-xs text-muted-foreground mb-1">Template SLO</p>
          <select
            value={templateSloName}
            onChange={e => setTemplateSloName(e.target.value)}
            className="w-full px-3 py-1.5 text-sm bg-muted/30 border border-border rounded text-foreground"
          >
            <option value="">Select a template...</option>
            {templateSlos.map(t => (
              <option key={t.name} value={t.name}>
                {t.display_name ?? t.name} (v{t.version})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="gen-vars" className="block text-xs text-muted-foreground mb-1">
            Generator Variables (key=val1,val2 per line)
          </label>
          <textarea
            id="gen-vars"
            value={genVarsText}
            onChange={e => setGenVarsText(e.target.value)}
            rows={4}
            className="w-full px-3 py-1.5 text-sm bg-muted/30 border border-border rounded text-foreground font-mono"
            placeholder={`process_name=auth,cache,db`}
          />
        </div>

        <div className="flex gap-2 justify-end pt-2">
          <Button type="button" size="sm" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            size="sm"
            disabled={!name || !templateSloName || createMutation.isPending}
          >
            {createMutation.isPending ? 'Generating…' : 'Generate'}
          </Button>
        </div>
      </form>
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./scripts/ui-test.sh --tail 10 src/features/registry/forms/SloGroupForm.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /path/to/worktree add ui/src/features/registry/forms/SloGroupForm.tsx ui/src/features/registry/forms/SloGroupForm.test.tsx
git -C /path/to/worktree commit -m "feat(ui): add SLO group creation form"
```

---

### Task 11: Wire Create Actions to Forms in Registry Page

**Files:**
- Modify: `ui/src/pages/SloRegistryPage.tsx`
- Modify: `ui/src/features/registry/forms/SloWizard.tsx`

The registry page is at `ui/src/pages/SloRegistryPage.tsx`. It hosts `RegistrySidebar` and `RegistryDetailPanel` and handles the `onCreateAction` callback. The current `handleCreateAction` union type is `'datasource' | 'sli' | 'slo' | 'group'`. We need to handle two new cases: `'slo-template'` and `'slo-group'`.

**How each new action works:**
- `'slo-template'`: Opens the existing SLO wizard with a `defaultKind` prop set to `'template'`
- `'slo-group'`: Shows the `SloGroupForm` in the detail panel area (same pattern as `wizardOpen`)

- [ ] **Step 1: Add `defaultKind` prop to SloWizard**

In `ui/src/features/registry/forms/SloWizard.tsx`:

```typescript
interface SloWizardProps {
  editSlo?: SloDefinition
  defaultKind?: 'standard' | 'template'  // ← add this
  onClose?: () => void
}
```

In the `SloWizard` component, use `defaultKind` when building the initial state. The wizard currently doesn't track `kind` — add it alongside the `createMutation.mutate` call (line ~184):

```typescript
export function SloWizard({ editSlo, defaultKind, onClose }: SloWizardProps) {
  // ...existing state...

  // Track kind for the submission
  const kind = editSlo?.kind ?? defaultKind ?? 'standard'
```

In the submit handler (`createMutation.mutate` call around line 184), add `kind` to the payload:

```typescript
createMutation.mutate(
  {
    name: identity.name,
    // ...existing fields...
    kind,  // ← add this field
  },
  { onSuccess: () => onClose?.() },
)
```

Also update the title to reflect template mode:

```typescript
const title = isEdit
  ? `${editSlo!.name} · New Version`
  : kind === 'template'
    ? 'New SLO Template'
    : 'New SLO Definition'
```

- [ ] **Step 2: Add SLO group form state to SloRegistryPage**

In `ui/src/pages/SloRegistryPage.tsx`, add:

```typescript
import { SloGroupForm } from '@/features/registry/forms/SloGroupForm'

// Add state (alongside existing wizardOpen state):
const [sloGroupFormOpen, setSloGroupFormOpen] = useState(false)
const [wizardDefaultKind, setWizardDefaultKind] = useState<'standard' | 'template'>('standard')
```

- [ ] **Step 3: Extend handleCreateAction with new cases**

```typescript
const handleCreateAction = useCallback(
  (type: 'datasource' | 'sli' | 'slo' | 'group' | 'slo-template' | 'slo-group', context?: { adapterType?: string }) => {
    switch (type) {
      case 'slo':
        setWizardDefaultKind('standard')
        setWizardEditSlo(undefined)
        setWizardOpen(true)
        setSloGroupFormOpen(false)
        break
      case 'slo-template':
        setWizardDefaultKind('template')
        setWizardEditSlo(undefined)
        setWizardOpen(true)
        setSloGroupFormOpen(false)
        break
      case 'slo-group':
        setSloGroupFormOpen(true)
        setWizardOpen(false)
        break
      case 'sli':
        setSliDefaultAdapter(context?.adapterType)
        setSliFormOpen(true)
        break
      case 'datasource':
        setDsEditName(undefined)
        setDsFormOpen(true)
        break
      case 'group':
        setGroupName('')
        setGroupDialogOpen(true)
        break
    }
  },
  [],
)
```

- [ ] **Step 4: Wire SloGroupForm into the detail panel area**

In the JSX of `SloRegistryPage.tsx`, extend the detail area to handle the group form (around line 177):

```tsx
<div className="flex-1 overflow-y-auto">
  {wizardOpen ? (
    <SloWizard
      editSlo={wizardEditSlo}
      defaultKind={wizardDefaultKind}
      onClose={handleWizardClose}
    />
  ) : sloGroupFormOpen ? (
    <SloGroupForm onClose={() => setSloGroupFormOpen(false)} />
  ) : (
    <RegistryDetailPanel
      selected={selected}
      onNavigate={handleNavigate}
      onEditDatasource={handleEditDatasource}
      onNewSloVersion={handleNewSloVersion}
      onNewSliVersion={handleNewSliVersion}
      onLinkSlo={handleLinkSlo}
    />
  )}
</div>
```

Also close the group form when the user selects a sidebar item — update `handleSelect`:

```typescript
const handleSelect = useCallback(
  (node: SelectedNode) => {
    updateParams({ selected: node.name, type: node.type, group: node.groupName ?? null })
    setWizardOpen(false)
    setSloGroupFormOpen(false)  // ← add this
  },
  [updateParams],
)
```

- [ ] **Step 5: Run type check**

Run: `pnpm exec tsc --noEmit -p tsconfig.app.json` from `ui/`
Expected: No errors

- [ ] **Step 6: Manual verification**

Start the dev server and verify:
1. Create → "SLO Definition" opens wizard with title "New SLO Definition"
2. Create → "SLO Template" opens wizard with title "New SLO Template"
3. Create → "SLO Group" shows the SloGroupForm in the detail area
4. Clicking any sidebar item dismisses the form/wizard

- [ ] **Step 7: Commit**

```bash
git -C /path/to/worktree add ui/src/pages/SloRegistryPage.tsx ui/src/features/registry/forms/SloWizard.tsx
git -C /path/to/worktree commit -m "feat(ui): wire template/group create actions to forms and detail views"
```

---

### Task 12: Template Validation Warning (Kind=Template Without Gen Vars)

**Files:**
- Modify: `ui/src/features/registry/forms/SloWizard.tsx` or relevant wizard step

The mockup `warn.png` shows a warning dialog when saving an SLO as template but it has no `$__gen_*` variables. This is a validation UX hint, not a blocker.

- [ ] **Step 1: Add template validation check**

In the SLO wizard's submit handler, when `kind === 'template'`:
- Check if any variable value contains `$__gen_`
- If not, show a warning dialog with "Go Back & Fix" and "Save Anyway" buttons
- The warning text: "This template has no $__gen_ variables. Templates are designed to be used with SLO Groups, which expand $__gen_ placeholders into multiple SLOs."

- [ ] **Step 2: Implement warning dialog**

```tsx
{showTemplateWarning && (
  <div className="p-4 border border-amber-600/30 bg-amber-950/20 rounded-lg space-y-3">
    <p className="text-sm font-semibold text-amber-400">Template Validation Warning</p>
    <p className="text-sm text-foreground">
      This template has no <code className="text-amber-400">$__gen_</code> variables.
    </p>
    <p className="text-xs text-muted-foreground">
      Templates are designed to be used with SLO Groups, which expand $__gen_ placeholders
      into multiple SLOs. Without any $__gen_ variables, this template will generate identical
      copies with no variation.
    </p>
    <div className="flex gap-2 justify-end">
      <Button size="sm" variant="outline" onClick={() => setShowTemplateWarning(false)}>
        Go Back & Fix
      </Button>
      <Button size="sm" onClick={handleSaveAnyway}>
        Save Anyway
      </Button>
    </div>
  </div>
)}
```

- [ ] **Step 3: Commit**

```bash
git -C /path/to/worktree add ui/src/features/registry/forms/
git -C /path/to/worktree commit -m "feat(ui): add template validation warning for missing gen vars"
```

---

### Task 13: Final Integration Test and Cleanup

- [ ] **Step 1: Run all UI tests**

Run: `./scripts/ui-test.sh --tail 20`
Expected: All tests pass

- [ ] **Step 2: Run TypeScript type check**

Run: `pnpm exec tsc --noEmit -p tsconfig.app.json` from `ui/`
Expected: No errors

- [ ] **Step 3: Visual verification**

Start the dev server and verify against the design mockups:
1. SLO sidebar matches `tree-view-with-groups-and-templates.png` layout
2. Create dropdown matches `action-options.png`
3. Template detail shows amber accent + gen var highlighting
4. Group detail shows gen_variables table
5. Section headers (STANDARD, TEMPLATES, GROUPS) are visible and collapsible

- [ ] **Step 4: Commit any final adjustments**

Stage only the specific files modified during cleanup, then commit:

```bash
git -C /path/to/worktree add <specific-files-changed>
git -C /path/to/worktree commit -m "fix(ui): final adjustments for SLO registry phase 4"
```
