# Navigator Redesign — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Navigator feature so GroupPanel embeds the shared EvaluationHeatmap + EvaluationTable, AssetPanel mirrors the EvaluationDetailPage layout, and the sidebar gains an "All" entry with recursive member counts.

**Architecture:** Six coordinated changes — remove Evaluations nav link, add "All" tree entry + recursive member count, add `onAssetSelect` to EvaluationHeatmap for second-click navigation, replace GroupHeatmap with shared components, redesign AssetPanel with column-selection heatmap + detail sections, and wire everything through AssetNavigatorPage.

**Tech Stack:** React 19, TypeScript strict, TanStack Query v5, ECharts (echarts-for-react), React Router v7, Vitest

**Spec:** `docs/superpowers/specs/2026-03-15-navigator-redesign.md`

**Tests:** `npx --prefix ui vitest run` (single command, no pipes)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `ui/src/App.tsx` | Modify (line 18) | Remove "Evaluations" from `NAV_ITEMS` |
| `ui/src/features/navigator/components/AssetTreePanel.tsx` | Modify | Add `onClearSelection` prop, "All" entry, `countLeafMembers` helper |
| `ui/src/features/navigator/components/AssetTreePanel.test.ts` | Create | Unit test for `countLeafMembers` |
| `ui/src/features/evaluations/components/EvaluationHeatmap.tsx` | Modify | Add optional `onAssetSelect` prop, three-case click handler |
| `ui/src/features/navigator/components/GroupPanel.tsx` | Modify | Replace GroupHeatmap → EvaluationHeatmap + EvaluationTable; add `onSelectAsset` prop |
| `ui/src/features/navigator/components/GroupHeatmap.tsx` | Delete | Replaced by EvaluationHeatmap |
| `ui/src/features/navigator/components/AssetHeatmap.tsx` | Modify | Add `selectedEvalId`/`onEvalSelect` props; remove `useNavigate`; update tooltip |
| `ui/src/features/evaluations/hooks.ts` | Modify (line 29) | Widen `useEvaluationDetail(id: string)` to `id: string \| undefined` |
| `ui/src/features/navigator/components/AssetPanel.tsx` | Rewrite | Full redesign: Header → Notes → Metric Heatmap → SLI Breakdown → Trend Charts |
| `ui/src/pages/AssetNavigatorPage.tsx` | Modify | Wire `onClearSelection`, `onSelectAsset`; `selectAsset` always clears `?group=` |

---

## Chunk 1: Navigation + Tree Panel + EvaluationHeatmap

### Task 1: Remove "Evaluations" from top nav

**Files:**
- Modify: `ui/src/App.tsx:16-21`

- [ ] **Step 1: Remove the Evaluations entry from NAV_ITEMS**

In `ui/src/App.tsx`, change `NAV_ITEMS` (line 16-21) from:

```typescript
const NAV_ITEMS = [
  { to: '/navigator', label: 'Navigator' },
  { to: '/evaluations', label: 'Evaluations' },
  { to: '/slos', label: 'SLOs' },
  { to: '/assets', label: 'Assets' },
]
```

to:

```typescript
const NAV_ITEMS = [
  { to: '/navigator', label: 'Navigator' },
  { to: '/slos', label: 'SLOs' },
  { to: '/assets', label: 'Assets' },
]
```

The `/evaluations` and `/evaluations/:id` routes remain in the `<Routes>` block (lines 93-94) — they're still reachable via direct URL.

- [ ] **Step 2: Run tests**

Run: `npx --prefix ui vitest run`
Expected: All tests pass (no tests reference NAV_ITEMS)

- [ ] **Step 3: Commit**

```
feat(ui): remove Evaluations tab from top nav

Navigator is now the sole entry point for evaluation data.
The /evaluations route remains accessible via direct URL.
```

---

### Task 2: countLeafMembers — test + implementation

**Files:**
- Create: `ui/src/features/navigator/components/AssetTreePanel.test.ts`
- Modify: `ui/src/features/navigator/components/AssetTreePanel.tsx`

- [ ] **Step 1: Write the failing test for countLeafMembers**

Create `ui/src/features/navigator/components/AssetTreePanel.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { countLeafMembers } from './AssetTreePanel'
import type { AssetGroup, AssetGroupTree } from '@/features/assets/types'

function mkGroup(
  id: string,
  members: number,
  subgroupIds: string[] = [],
): AssetGroup {
  return {
    id,
    name: id,
    members: Array.from({ length: members }, (_, i) => ({
      asset_id: `${id}-asset-${i}`,
      asset_name: `${id}-asset-${i}`,
      weight: 1,
    })),
    subgroups: subgroupIds.map(gid => ({ group_id: gid, weight: 1 })),
  }
}

describe('countLeafMembers', () => {
  it('returns direct member count for a group with no subgroups', () => {
    const group = mkGroup('g1', 3)
    const tree: AssetGroupTree = { top_level: [group], all_groups: [group] }
    expect(countLeafMembers(group, tree)).toBe(3)
  })

  it('sums members recursively through subgroups', () => {
    const child1 = mkGroup('child1', 5)
    const child2 = mkGroup('child2', 6)
    const parent = mkGroup('parent', 0, ['child1', 'child2'])
    const tree: AssetGroupTree = {
      top_level: [parent],
      all_groups: [parent, child1, child2],
    }
    expect(countLeafMembers(parent, tree)).toBe(11)
  })

  it('handles nested subgroups (grandchildren)', () => {
    const grandchild = mkGroup('gc', 4)
    const child = mkGroup('child', 2, ['gc'])
    const root = mkGroup('root', 1, ['child'])
    const tree: AssetGroupTree = {
      top_level: [root],
      all_groups: [root, child, grandchild],
    }
    expect(countLeafMembers(root, tree)).toBe(7)
  })

  it('returns 0 for a group with no members and no subgroups', () => {
    const group = mkGroup('empty', 0)
    const tree: AssetGroupTree = { top_level: [group], all_groups: [group] }
    expect(countLeafMembers(group, tree)).toBe(0)
  })

  it('skips unresolved subgroup IDs', () => {
    const parent = mkGroup('parent', 3, ['nonexistent'])
    const tree: AssetGroupTree = { top_level: [parent], all_groups: [parent] }
    expect(countLeafMembers(parent, tree)).toBe(3)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx --prefix ui vitest run AssetTreePanel.test`
Expected: FAIL — `countLeafMembers` is not exported from `AssetTreePanel`

- [ ] **Step 3: Implement countLeafMembers and export it**

In `ui/src/features/navigator/components/AssetTreePanel.tsx`, add this exported function between the imports (line 4) and the `Props` interface (line 6):

```typescript
export function countLeafMembers(group: AssetGroup, tree: AssetGroupTree): number {
  let count = group.members.length
  for (const sg of group.subgroups) {
    const resolved = tree.all_groups.find(g => g.id === sg.group_id)
    if (resolved) count += countLeafMembers(resolved, tree)
  }
  return count
}
```

Note: `AssetGroup` and `AssetGroupTree` are already imported on line 4.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx --prefix ui vitest run AssetTreePanel.test`
Expected: All 5 tests PASS

- [ ] **Step 5: Replace member count badge in TreeNode**

In `AssetTreePanel.tsx`, in the `TreeNode` component, replace the member count badge (lines 52-54):

Old:
```tsx
        {group.members.length > 0 && (
          <span className="text-xs text-muted-foreground/60 ml-auto shrink-0">{group.members.length}</span>
        )}
```

New:
```tsx
        {(() => {
          const leafCount = countLeafMembers(group, tree)
          return leafCount > 0 ? (
            <span className="text-xs text-muted-foreground/60 ml-auto shrink-0">{leafCount}</span>
          ) : null
        })()}
```

- [ ] **Step 6: Run all tests**

Run: `npx --prefix ui vitest run`
Expected: All tests pass

- [ ] **Step 7: Commit**

```
feat(ui): add countLeafMembers to AssetTreePanel for recursive member count

Groups with subgroups now show the total leaf asset count instead of
only direct members. Fixes Performance Lab showing 0 instead of 11.
```

---

### Task 3: "All" entry in AssetTreePanel

**Files:**
- Modify: `ui/src/features/navigator/components/AssetTreePanel.tsx`

- [ ] **Step 1: Add `onClearSelection` prop to the Props interface**

In `AssetTreePanel.tsx`, update the `Props` interface (lines 6-11):

Old:
```typescript
interface Props {
  selectedGroup?: string
  selectedAsset?: string
  onSelectGroup: (name: string) => void
  onSelectAsset: (name: string) => void
}
```

New:
```typescript
interface Props {
  selectedGroup?: string
  selectedAsset?: string
  onSelectGroup: (name: string) => void
  onSelectAsset: (name: string) => void
  onClearSelection: () => void
}
```

- [ ] **Step 2: Update the component signature to accept `onClearSelection`**

Update the function signature (line 93):

Old:
```typescript
export function AssetTreePanel({ selectedGroup, selectedAsset, onSelectGroup, onSelectAsset }: Props) {
```

New:
```typescript
export function AssetTreePanel({ selectedGroup, selectedAsset, onSelectGroup, onSelectAsset, onClearSelection }: Props) {
```

- [ ] **Step 3: Add "All" entry above the tree nodes**

In `AssetTreePanel`, inside the scrollable `div` (line 108), add the "All" button before the `tree?.top_level.map(...)` block:

Old:
```tsx
      <div className="flex-1 overflow-y-auto py-2">
        {isLoading && <p className="px-3 py-2 text-xs text-muted-foreground">Loading…</p>}
        {tree?.top_level.map(group => (
```

New:
```tsx
      <div className="flex-1 overflow-y-auto py-2">
        {isLoading && <p className="px-3 py-2 text-xs text-muted-foreground">Loading…</p>}
        {!isLoading && (
          <button
            className={`flex items-center w-full text-left py-1.5 text-sm gap-1 hover:bg-muted/50 transition-colors ${
              !selectedGroup && !selectedAsset ? 'bg-muted text-foreground font-medium' : 'text-muted-foreground'
            }`}
            style={{ paddingLeft: '12px', paddingRight: '12px' }}
            onClick={onClearSelection}
          >
            All
          </button>
        )}
        {tree?.top_level.map(group => (
```

- [ ] **Step 4: Run tests**

Run: `npx --prefix ui vitest run`
Expected: All tests pass

- [ ] **Step 5: Commit**

```
feat(ui): add "All" entry and onClearSelection to AssetTreePanel

Clicking "All" clears both group and asset URL params, returning
the main panel to the empty-state message.
```

---

### Task 4: EvaluationHeatmap — add `onAssetSelect` prop

**Files:**
- Modify: `ui/src/features/evaluations/components/EvaluationHeatmap.tsx`

- [ ] **Step 1: Add `onAssetSelect` to the Props interface**

In `EvaluationHeatmap.tsx`, update Props (lines 46-50):

Old:
```typescript
interface Props {
  evaluations: EvaluationSummary[]
  selectedDate: string | null
  onDateSelect: (date: string | null) => void
}
```

New:
```typescript
interface Props {
  evaluations: EvaluationSummary[]
  selectedDate: string | null
  onDateSelect: (date: string | null) => void
  onAssetSelect?: (assetName: string) => void
}
```

- [ ] **Step 2: Update the component signature**

Update the destructuring (line 144):

Old:
```typescript
export function EvaluationHeatmap({ evaluations, selectedDate, onDateSelect }: Props) {
```

New:
```typescript
export function EvaluationHeatmap({ evaluations, selectedDate, onDateSelect, onAssetSelect }: Props) {
```

- [ ] **Step 3: Implement the three-case click handler**

Replace the `onEvents` click handler (lines 252-259):

Old:
```typescript
        onEvents={{
          // Toggle column selection: click same slot again to deselect
          click: (p: { data: CellData }) => {
            if (p?.data?.slot) {
              onDateSelect(selectedDate === p.data.slot ? null : p.data.slot)
            }
          },
        }}
```

New:
```typescript
        onEvents={{
          click: (p: { data: CellData }) => {
            if (!p?.data?.slot) return
            if (selectedDate !== p.data.slot) {
              // Case 1: column not selected → select it
              onDateSelect(p.data.slot)
            } else if (onAssetSelect) {
              // Case 2: column already selected + onAssetSelect → navigate to asset
              const assetName = p.data.row.split(' · ')[0]
              if (assetName.trim()) onAssetSelect(assetName)
            } else {
              // Case 3: column already selected + no onAssetSelect → deselect
              onDateSelect(null)
            }
          },
        }}
```

- [ ] **Step 4: Run tests**

Run: `npx --prefix ui vitest run`
Expected: All tests pass. `EvaluationsPage` does not pass `onAssetSelect`, so it keeps the deselect-on-second-click behaviour (case 3).

- [ ] **Step 5: Commit**

```
feat(ui): add onAssetSelect prop to EvaluationHeatmap

Three-case click handler: first click selects column, second click
with onAssetSelect navigates to asset, second click without deselects.
EvaluationsPage behaviour unchanged.
```

---

## Chunk 2: GroupPanel Redesign + AssetHeatmap Changes

### Task 5: GroupPanel — replace GroupHeatmap with EvaluationHeatmap + EvaluationTable

**Files:**
- Modify: `ui/src/features/navigator/components/GroupPanel.tsx`
- Delete: `ui/src/features/navigator/components/GroupHeatmap.tsx`

- [ ] **Step 1: Rewrite GroupPanel**

Replace the entire contents of `ui/src/features/navigator/components/GroupPanel.tsx`:

```typescript
// ui/src/features/navigator/components/GroupPanel.tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useEvaluations, useColumnVisibility } from '@/features/evaluations/hooks'
import { EvaluationHeatmap } from '@/features/evaluations/components/EvaluationHeatmap'
import { EvaluationTable } from '@/features/evaluations/components/EvaluationTable'
import { GroupScoreChart } from './GroupScoreChart'

type ViewMode = 'heatmap' | 'chart'

interface Props {
  groupName: string
  onSelectAsset: (name: string) => void
}

export function GroupPanel({ groupName, onSelectAsset }: Props) {
  const [mode, setMode] = useState<ViewMode>('heatmap')
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const navigate = useNavigate()

  const { data: evals = [], isLoading } = useEvaluations({ group_name: groupName })

  const colVis = useColumnVisibility([])
  const tableEvals = selectedDate
    ? evals.filter(e => e.period_start === selectedDate)
    : evals

  const latestScore = evals.length
    ? Math.round(
        [...evals].filter(e => !e.invalidated)
          .sort((a, b) => b.period_start.localeCompare(a.period_start))[0]?.score ?? 0
      )
    : null

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">{groupName.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</h2>
          {evals.length > 0 && (
            <p className="text-xs text-muted-foreground mt-0.5">{evals.length} evaluations</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {latestScore != null && (
            <span className="text-2xl font-bold tabular-nums text-foreground">{latestScore}%</span>
          )}
          {/* View toggle */}
          <div className="flex border border-border rounded overflow-hidden text-xs">
            <button
              onClick={() => setMode('heatmap')}
              className={`px-3 py-1.5 transition-colors ${mode === 'heatmap' ? 'bg-muted text-foreground' : 'text-muted-foreground hover:bg-muted/50'}`}
            >
              Heatmap
            </button>
            <button
              onClick={() => setMode('chart')}
              className={`px-3 py-1.5 transition-colors ${mode === 'chart' ? 'bg-muted text-foreground' : 'text-muted-foreground hover:bg-muted/50'}`}
            >
              Chart
            </button>
          </div>
          {/* Explorer icon */}
          <button
            onClick={() => navigate(`/explorer?group=${encodeURIComponent(groupName)}`)}
            className="p-1.5 rounded border border-border text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
            title="Open Metric Explorer"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <rect x="1" y="9" width="3" height="6" rx="0.5"/>
              <rect x="6" y="5" width="3" height="10" rx="0.5"/>
              <rect x="11" y="2" width="3" height="13" rx="0.5"/>
            </svg>
          </button>
        </div>
      </div>

      {/* Content */}
      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {!isLoading && evals.length === 0 && (
        <p className="text-sm text-muted-foreground">No evaluations found for this group.</p>
      )}

      {!isLoading && evals.length > 0 && mode === 'heatmap' && (
        <>
          <div className="rounded-lg border border-border bg-card p-4">
            <EvaluationHeatmap
              evaluations={evals}
              selectedDate={selectedDate}
              onDateSelect={setSelectedDate}
              onAssetSelect={onSelectAsset}
            />
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <EvaluationTable evaluations={tableEvals} dynamicCols={[]} {...colVis} />
          </div>
        </>
      )}

      {!isLoading && evals.length > 0 && mode === 'chart' && (
        <div className="rounded-lg border border-border bg-card p-4">
          <GroupScoreChart evaluations={evals} />
        </div>
      )}
    </div>
  )
}
```

Key changes from the original:
- Added `onSelectAsset` prop (passed to `EvaluationHeatmap.onAssetSelect`)
- Added `selectedDate` state for column selection
- Replaced `GroupHeatmap` with `EvaluationHeatmap` + `EvaluationTable`
- Table is filtered by `selectedDate` via client-side filter on `evals` — shows all evals when no column selected

- [ ] **Step 2: Run tests**

Run: `npx --prefix ui vitest run`
Expected: All tests pass (GroupHeatmap had no tests)

- [ ] **Step 3: Delete GroupHeatmap.tsx**

Delete the file: `ui/src/features/navigator/components/GroupHeatmap.tsx`

- [ ] **Step 4: Run tests again to confirm no breakage**

Run: `npx --prefix ui vitest run`
Expected: All tests pass

- [ ] **Step 5: Commit**

```
feat(ui): replace GroupHeatmap with EvaluationHeatmap + EvaluationTable

GroupPanel now uses the shared EvaluationHeatmap with column selection
and second-click asset navigation. EvaluationTable below shows evals
filtered by the selected time slot. GroupHeatmap.tsx is deleted.
```

---

### Task 6: AssetHeatmap — selectedEvalId, onEvalSelect, remove navigation

**Files:**
- Modify: `ui/src/features/navigator/components/AssetHeatmap.tsx`

- [ ] **Step 1: Update Props interface**

In `AssetHeatmap.tsx`, update the Props interface (lines 11-13):

Old:
```typescript
interface Props {
  data: MetricHeatmapResponse
}
```

New:
```typescript
interface Props {
  data: MetricHeatmapResponse
  selectedEvalId?: string
  onEvalSelect?: (evalId: string) => void
}
```

- [ ] **Step 2: Update component signature and remove useNavigate**

Remove the `useNavigate` import (line 4):
```typescript
import { useNavigate } from 'react-router-dom'
```
→ Delete this line.

Replace the component opening (lines 17-19):

Old:
```typescript
export function AssetHeatmap({ data }: Props) {
  const navigate = useNavigate()
  const { theme } = useTheme()
```

New:
```typescript
export function AssetHeatmap({ data, selectedEvalId, onEvalSelect }: Props) {
  const { theme } = useTheme()
```

- [ ] **Step 3: Add column highlighting based on selectedEvalId**

Replace the `chartCells` useMemo (lines 25-37):

Old:
```typescript
  const chartCells = useMemo(
    () => cells.map(cell => ({
      ...cell,
      itemStyle: {
        color: cell.result === 'none'
          ? ct.bg
          : colours[cell.result as keyof typeof colours] ?? ct.bg,
        borderColor: 'transparent',
        borderWidth: 0,
      },
    })),
    [cells, colours, ct],
  )
```

New:
```typescript
  const chartCells = useMemo(
    () => cells.map(cell => {
      const isSelected = !!selectedEvalId && cell.evalId === selectedEvalId
      return {
        ...cell,
        itemStyle: {
          color: cell.result === 'none'
            ? ct.bg
            : colours[cell.result as keyof typeof colours] ?? ct.bg,
          borderColor: isSelected ? '#ffffff' : 'transparent',
          borderWidth: isSelected ? 2 : 0,
        },
      }
    }),
    [cells, colours, ct, selectedEvalId],
  )
```

- [ ] **Step 4: Update tooltip text**

In the tooltip formatter (line 54), change the hint text:

Old:
```typescript
          d.evalId ? `<span style="color:#888;font-size:10px">Click to open evaluation detail</span>` : '',
```

New:
```typescript
          d.evalId ? `<span style="color:#888;font-size:10px">Click to select this evaluation</span>` : '',
```

- [ ] **Step 5: Replace click handler**

Replace the `onEvents` block (lines 104-110):

Old:
```typescript
      onEvents={{
        click: (p: { data: HeatmapCell }) => {
          if (p?.data?.evalId) {
            navigate(`/evaluations/${p.data.evalId}`)
          }
        },
      }}
```

New:
```typescript
      onEvents={{
        click: (p: { data: HeatmapCell }) => {
          if (p?.data?.evalId && onEvalSelect) {
            onEvalSelect(p.data.evalId)
          }
        },
      }}
```

- [ ] **Step 6: Run tests**

Run: `npx --prefix ui vitest run`
Expected: All tests pass

- [ ] **Step 7: Commit**

```
feat(ui): add selectedEvalId/onEvalSelect to AssetHeatmap, remove navigation

AssetHeatmap now highlights the selected evaluation column with white
borders and calls onEvalSelect on click instead of navigating away.
```

---

## Chunk 3: Hooks, AssetPanel Redesign, Wiring

### Task 7: Widen useEvaluationDetail to accept undefined

**Files:**
- Modify: `ui/src/features/evaluations/hooks.ts:29-35`

- [ ] **Step 1: Update the hook signature**

In `hooks.ts`, replace `useEvaluationDetail` (lines 29-35):

Old:
```typescript
export function useEvaluationDetail(id: string) {
  return useQuery({
    queryKey: evaluationKeys.detail(id),
    queryFn: () => fetchEvaluationDetail(id),
    enabled: !!id,
  })
}
```

New:
```typescript
export function useEvaluationDetail(id: string | undefined) {
  return useQuery({
    queryKey: evaluationKeys.detail(id ?? ''),
    queryFn: () => fetchEvaluationDetail(id!),
    enabled: !!id,
  })
}
```

The `id!` assertion is safe because `enabled: !!id` prevents the query function from running when `id` is undefined.

- [ ] **Step 2: Run tests**

Run: `npx --prefix ui vitest run`
Expected: All tests pass. `EvaluationDetailPage` passes `id!` from `useParams`, so it's unaffected.

- [ ] **Step 3: Commit**

```
feat(ui): widen useEvaluationDetail to accept string | undefined

Enables AssetPanel to call useEvaluationDetail with a selectedEvalId
that starts as undefined while loading.
```

---

### Task 8: AssetPanel — full redesign

**Files:**
- Rewrite: `ui/src/features/navigator/components/AssetPanel.tsx`

This is the largest change. The new AssetPanel mirrors `EvaluationDetailPage`'s layout with the Metric Heatmap inserted between Notes and SLI Breakdown.

- [ ] **Step 1: Rewrite AssetPanel**

Replace the entire contents of `ui/src/features/navigator/components/AssetPanel.tsx`:

```typescript
// ui/src/features/navigator/components/AssetPanel.tsx
import { useState, useMemo } from 'react'
import { useAssetEvaluations, useMetricHeatmap } from '../hooks'
import { useEvaluationDetail, useInvalidateEvaluation } from '@/features/evaluations/hooks'
import { AssetHeatmap } from './AssetHeatmap'
import { MetricTrendBlock } from '@/features/evaluations/components/MetricTrendBlock'
import { SLIBreakdownTable } from '@/features/evaluations/components/SLIBreakdownTable'
import { EvaluationTabs, tabLabel } from '@/features/evaluations/components/EvaluationTabs'
import { AnnotationForm } from '@/features/evaluations/components/AnnotationForm'
import { ResultBadge } from '@/features/evaluations/components/ResultBadge'
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR } from '@/lib/theme'

type ViewMode = 'heatmap' | 'chart'

interface Props {
  assetName: string
}

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

export function AssetPanel({ assetName }: Props) {
  const [mode, setMode] = useState<ViewMode>('heatmap')
  const [selectedEvalId, setSelectedEvalId] = useState<string | undefined>(undefined)
  const [activeTab, setActiveTab] = useState('all')
  const [metricGroupFilter, setMetricGroupFilter] = useState<string>('all')
  const [showInvalidateForm, setShowInvalidateForm] = useState(false)
  const [pendingReason, setPendingReason] = useState('')

  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]

  const { data: evals = [], isLoading: evalsLoading } = useAssetEvaluations(assetName)
  const { data: heatmapData, isLoading: heatmapLoading } = useMetricHeatmap(assetName)

  // Default selection: latest non-invalidated eval, or latest if all invalidated
  const defaultEvalId = useMemo(() => {
    if (!evals.length) return undefined
    const sorted = [...evals].sort((a, b) => b.period_start.localeCompare(a.period_start))
    return (sorted.find(e => !e.invalidated) ?? sorted[0]).id
  }, [evals])

  // Use explicit selection if set, otherwise fall back to default
  const effectiveEvalId = selectedEvalId ?? defaultEvalId

  const { data: ev } = useEvaluationDetail(effectiveEvalId)
  const invalidate = useInvalidateEvaluation(effectiveEvalId ?? '')

  // SLI tab groups from detail
  const availableGroups = useMemo(() =>
    [...new Set(ev?.indicator_results.map(i => i.tab_group).filter(Boolean) as string[])],
    [ev],
  )

  const counts = useMemo(() =>
    Object.fromEntries(
      availableGroups.map(g => [g, ev?.indicator_results.filter(i => i.tab_group === g).length ?? 0]),
    ),
    [ev, availableGroups],
  )

  const resolvedTab = ['all', ...availableGroups].includes(activeTab) ? activeTab : 'all'

  const tabIndicators = useMemo(
    () => resolvedTab === 'all'
      ? (ev?.indicator_results ?? [])
      : (ev?.indicator_results.filter(ind => ind.tab_group === resolvedTab) ?? []),
    [ev, resolvedTab],
  )

  // All indicators for chart mode (from heatmap metric list — stubs for MetricTrendBlock)
  const allIndicators = useMemo(() => {
    if (!heatmapData) return []
    return heatmapData.metrics.map(m => ({
      metric: m.name,
      display_name: m.display_name,
      tab_group: m.tab_group,
      value: 0,
      compared_value: null,
      change_absolute: null,
      change_relative_pct: null,
      aggregation: 'avg' as const,
      status: 'pass' as const,
      score: 0,
      weight: 1,
      key_sli: false,
      pass_targets: null,
      warning_targets: null,
    }))
  }, [heatmapData])

  const metricGroups = useMemo(
    () => Array.from(new Set(allIndicators.map(i => i.tab_group).filter(Boolean) as string[])),
    [allIndicators],
  )

  const chartIndicators = metricGroupFilter === 'all'
    ? allIndicators
    : allIndicators.filter(i => i.tab_group === metricGroupFilter)

  const isLoading = evalsLoading || heatmapLoading
  const displayResult = ev ? (ev.invalidated ? 'invalidated' : ev.result) : undefined
  const score = ev ? Math.round(ev.score) : undefined

  return (
    <div className="p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold font-mono">{assetName}</h2>
          <span
            className="text-2xl font-bold tabular-nums"
            style={{ color: score != null ? (colours[ev!.result as keyof typeof colours] ?? colours.error) : undefined }}
          >
            {score != null ? `${score}%` : '—'}
          </span>
          {displayResult && <ResultBadge result={displayResult} />}
        </div>
        <div className="flex items-center gap-2">
          {/* Invalidate button */}
          {ev && !ev.invalidated && (
            <button
              onClick={() => setShowInvalidateForm(v => !v)}
              className="px-3 py-1 text-xs font-medium rounded border border-red-700/60 text-red-400 bg-red-900/20 hover:bg-red-900/40 transition-colors"
            >
              Invalidate
            </button>
          )}
          {ev?.invalidated && (
            <span className="text-xs text-muted-foreground italic">invalidated</span>
          )}
          {/* View toggle */}
          <div className="flex border border-border rounded overflow-hidden text-xs">
            <button
              onClick={() => setMode('heatmap')}
              className={`px-3 py-1.5 transition-colors ${mode === 'heatmap' ? 'bg-muted text-foreground' : 'text-muted-foreground hover:bg-muted/50'}`}
            >
              Heatmap
            </button>
            <button
              onClick={() => setMode('chart')}
              className={`px-3 py-1.5 transition-colors ${mode === 'chart' ? 'bg-muted text-foreground' : 'text-muted-foreground hover:bg-muted/50'}`}
            >
              Charts
            </button>
          </div>
        </div>
      </div>

      {/* Inline invalidate form */}
      {showInvalidateForm && ev && !ev.invalidated && (
        <div className="rounded-lg border border-red-800/40 bg-card p-4 space-y-3">
          <p className="text-sm font-medium text-red-300">Reason for invalidation</p>
          <textarea
            value={pendingReason}
            onChange={e => setPendingReason(e.target.value)}
            placeholder="Describe why this evaluation result should be discarded…"
            rows={3}
            className="w-full px-3 py-2 bg-muted border border-border rounded text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-red-500 resize-none"
          />
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => { setShowInvalidateForm(false); setPendingReason('') }}
              className="px-3 py-1.5 text-xs rounded border border-border text-muted-foreground hover:text-foreground transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => {
                invalidate.mutate(pendingReason, {
                  onSuccess: () => { setShowInvalidateForm(false); setPendingReason('') },
                })
              }}
              disabled={!pendingReason.trim() || invalidate.isPending}
              className="px-3 py-1.5 text-xs font-medium rounded bg-red-700 text-white hover:bg-red-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {invalidate.isPending ? 'Invalidating…' : 'Confirm invalidation'}
            </button>
          </div>
        </div>
      )}

      {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {/* ── Heatmap mode ── */}
      {!isLoading && mode === 'heatmap' && (
        <>
          {/* Notes */}
          {effectiveEvalId && (
            <AnnotationForm evalId={effectiveEvalId} annotations={ev?.annotations ?? []} />
          )}

          {/* Metric Heatmap */}
          {heatmapData && (
            <div className="rounded-lg border border-border bg-card p-4">
              <AssetHeatmap
                data={heatmapData}
                selectedEvalId={effectiveEvalId}
                onEvalSelect={setSelectedEvalId}
              />
            </div>
          )}

          {/* SLI Breakdown */}
          {ev && (
            <div id="sli-table" className="space-y-0 scroll-mt-4">
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">SLI Breakdown</h2>
              </div>
              <EvaluationTabs
                availableGroups={availableGroups}
                allCount={ev.indicator_results.length}
                counts={counts}
                activeTab={resolvedTab}
                onTabChange={setActiveTab}
              />
              <SLIBreakdownTable
                indicators={tabIndicators}
                onIndicatorClick={(metric, tabGroup) => {
                  if (resolvedTab !== 'all') setActiveTab(tabGroup)
                  setTimeout(() => scrollTo(`trend-${metric}`), 50)
                }}
              />
            </div>
          )}

          {/* Metric Trend Charts */}
          {effectiveEvalId && tabIndicators.length > 0 && (
            <div className="space-y-4">
              <p className="text-xs text-muted-foreground">
                30-day trend for{' '}
                <strong className="text-foreground">{resolvedTab === 'all' ? 'All' : tabLabel(resolvedTab)}</strong>{' '}
                metrics on <strong className="text-foreground">{assetName}</strong>.
              </p>
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                {tabIndicators.map(ind => (
                  <MetricTrendBlock key={ind.metric} evalId={effectiveEvalId} indicator={ind} />
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Charts mode ── */}
      {!isLoading && mode === 'chart' && effectiveEvalId && (
        <div className="space-y-4">
          {/* Metric group filter tabs */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setMetricGroupFilter('all')}
              className={`px-3 py-1.5 rounded text-sm transition-colors ${
                metricGroupFilter === 'all' ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              All ({allIndicators.length})
            </button>
            {metricGroups.map(g => (
              <button
                key={g}
                onClick={() => setMetricGroupFilter(g)}
                className={`px-3 py-1.5 rounded text-sm transition-colors ${
                  metricGroupFilter === g ? 'bg-muted text-foreground' : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {g} ({allIndicators.filter(i => i.tab_group === g).length})
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {chartIndicators.map(ind => (
              <MetricTrendBlock key={ind.metric} evalId={effectiveEvalId} indicator={ind} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
```

Key differences from current `AssetPanel.tsx`:
- **Data:** Uses `useEvaluationDetail(effectiveEvalId)` for selected eval's detail
- **Header:** Shows score + `ResultBadge` + Invalidate button for *selected* evaluation (not latest)
- **Invalidation:** Inline form (same as `EvaluationDetailPage`)
- **Heatmap mode layout:** Notes → Metric Heatmap (with column selection) → SLI Breakdown (tabs + table) → Trend Charts (all indicators from `ev.indicator_results`, no 8-metric cap)
- **Charts mode:** Metric group filter + all filtered trend charts (uses `allIndicators` stubs from heatmap metrics)
- **Removed:** `EvaluationTable` at bottom, `useNavigate`, Explorer button
- **Default eval:** Latest non-invalidated, falls back to latest if all invalidated

- [ ] **Step 2: Run tests**

Run: `npx --prefix ui vitest run`
Expected: All tests pass

- [ ] **Step 3: Commit**

```
feat(ui): redesign AssetPanel to mirror EvaluationDetailPage layout

New layout: Header (name, score, result badge, invalidate) → Notes →
Metric Heatmap (column selection) → SLI Breakdown (tabs + table) →
30-day Trend Charts. Clicking a heatmap column selects that evaluation
and updates all sections. Removes bottom EvaluationTable.
```

---

### Task 9: AssetNavigatorPage — wire onClearSelection and onSelectAsset

**Files:**
- Modify: `ui/src/pages/AssetNavigatorPage.tsx`

- [ ] **Step 1: Rewrite AssetNavigatorPage**

Replace the entire contents of `ui/src/pages/AssetNavigatorPage.tsx`:

```typescript
// ui/src/pages/AssetNavigatorPage.tsx
import { useSearchParams } from 'react-router-dom'
import { AssetTreePanel } from '@/features/navigator/components/AssetTreePanel'
import { GroupPanel } from '@/features/navigator/components/GroupPanel'
import { AssetPanel } from '@/features/navigator/components/AssetPanel'

export function AssetNavigatorPage() {
  const [params, setParams] = useSearchParams()
  const selectedGroup = params.get('group') ?? undefined
  const selectedAsset = params.get('asset') ?? undefined

  function selectGroup(name: string) {
    setParams({ group: name })
  }

  function selectAsset(name: string) {
    setParams({ asset: name })
  }

  function clearSelection() {
    setParams({})
  }

  return (
    <div className="flex h-[calc(100vh-49px)] overflow-hidden">
      <div className="w-64 shrink-0 border-r border-border overflow-y-auto">
        <AssetTreePanel
          selectedGroup={selectedGroup}
          selectedAsset={selectedAsset}
          onSelectGroup={selectGroup}
          onSelectAsset={selectAsset}
          onClearSelection={clearSelection}
        />
      </div>
      <div className="flex-1 overflow-y-auto">
        {selectedAsset && <AssetPanel assetName={selectedAsset} />}
        {!selectedAsset && selectedGroup && (
          <GroupPanel groupName={selectedGroup} onSelectAsset={selectAsset} />
        )}
        {!selectedAsset && !selectedGroup && (
          <div className="p-8 text-muted-foreground text-sm">
            Select a group or asset from the tree to load evaluations.
          </div>
        )}
      </div>
    </div>
  )
}
```

Key changes:
- Added `clearSelection` → `setParams({})` — passed to `AssetTreePanel.onClearSelection`
- Passes `onSelectAsset={selectAsset}` to `GroupPanel`
- `selectAsset` sets `{ asset: name }` which naturally clears `?group=` (only the asset key is set)

- [ ] **Step 2: Run all tests**

Run: `npx --prefix ui vitest run`
Expected: All tests pass

- [ ] **Step 3: Verify TypeScript compilation**

Run: `npx --prefix ui tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```
feat(ui): wire onClearSelection and onSelectAsset in AssetNavigatorPage

AssetTreePanel "All" entry clears both URL params. GroupPanel's
second-click on heatmap navigates to asset view. selectAsset always
clears ?group= to keep URLs clean.
```

---

## Post-Implementation Checklist

- [ ] `GroupHeatmap.tsx` is deleted
- [ ] No remaining imports of `GroupHeatmap` anywhere
- [ ] `npx --prefix ui vitest run` passes all tests
- [ ] TypeScript compilation clean (`npx --prefix ui tsc --noEmit`)
- [ ] EvaluationsPage behaviour unchanged (no `onAssetSelect`, deselect-on-second-click works)
- [ ] `/evaluations` and `/evaluations/:id` routes still work via direct URL
- [ ] Manual smoke test: Nav → tree "All" → group selection → heatmap second-click → asset panel
