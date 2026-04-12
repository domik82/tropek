# Asset Navigator Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Asset Navigator — a persistent split-pane default landing page with a collapsible group/subgroup/asset tree on the left and contextual evaluation views on the right (group view: heatmap + stacked score chart; asset view: metric heatmap + trend charts + score table); plus a full-screen Metric Explorer page.

**Architecture:** New `/navigator` route (default redirect from `/`) with `AssetNavigatorPage` managing tree selection via URL search params (`?group=name` or `?asset=name`). New `ui/src/features/navigator/` folder owns all navigator-specific components, hooks, and pure utilities. MSW mock is extended with `asset_name` filter and a new `GET /api/evaluations/metric-heatmap` endpoint that returns pre-computed metric×evaluation grid data.

**Tech Stack:** React 19, ECharts (echarts-for-react), TanStack Query v5, React Router v7, MSW v2, Vitest, TypeScript strict.

---

## File Map

### New files

| File | Responsibility |
|------|---------------|
| `ui/src/pages/AssetNavigatorPage.tsx` | Split-pane shell; reads/writes `?group=` / `?asset=` URL params; renders `AssetTreePanel` + `GroupPanel` / `AssetPanel` |
| `ui/src/pages/MetricExplorerPage.tsx` | Full-screen metric explorer; all metrics as line charts; `?metric_group=` filter; accessed via icon button |
| `ui/src/features/navigator/types.ts` | `NavSelection`, `MetricHeatmapResponse`, `MetricHeatmapCell`, `AssetScorePoint` |
| `ui/src/features/navigator/hooks.ts` | `useAssetEvaluations(assetName)`, `useMetricHeatmap(assetName)` |
| `ui/src/features/navigator/utils.ts` | Pure fns: `buildGroupHeatmapData`, `buildGroupScoreChartData`, `buildAssetHeatmapData` |
| `ui/src/features/navigator/utils.test.ts` | Unit tests for all pure fns |
| `ui/src/features/navigator/components/AssetTreePanel.tsx` | Collapsible tree (groups → subgroups → assets) + filter input + selection highlight |
| `ui/src/features/navigator/components/GroupPanel.tsx` | Group view: header (group name + score) + Heatmap/Chart/Explorer toggle + content area |
| `ui/src/features/navigator/components/AssetPanel.tsx` | Asset view: header (asset name + latest score) + same toggle + heatmap + trend charts + table |
| `ui/src/features/navigator/components/GroupHeatmap.tsx` | ECharts custom heatmap: rows=assets, cols=time slots, click cell → navigate to Evaluations |
| `ui/src/features/navigator/components/AssetHeatmap.tsx` | ECharts custom heatmap: rows=metrics, cols=evaluations, click cell → navigate to EvaluationDetail |
| `ui/src/features/navigator/components/GroupScoreChart.tsx` | ECharts stacked bar: per-asset colored segments, absolute/normalized toggle |

### Modified files

| File | Change |
|------|--------|
| `ui/src/App.tsx` | Add `/navigator` + `/explorer` routes; add "Navigator" to nav; redirect `/` → `/navigator` |
| `ui/src/features/evaluations/types.ts` | Add `asset_name?` to `EvaluationFilters` |
| `ui/src/features/evaluations/api.ts` | Pass `asset_name` in `toParams` |
| `ui/src/mocks/generate.ts` | Add `asset_name` filter in `getEvaluations`; add nested subgroups to `getAssetGroupTree`; add `getMetricHeatmap(assetName)` |
| `ui/src/mocks/handlers/evaluations.ts` | Forward `asset_name` param; add `GET /api/evaluations/metric-heatmap` handler |

---

## Chunk 1: Routing & Layout Shell

**Files:**
- Modify: `ui/src/App.tsx`
- Create: `ui/src/pages/AssetNavigatorPage.tsx`
- Create: `ui/src/pages/MetricExplorerPage.tsx`

- [ ] **Step 1.1: Add routes and nav items to App.tsx**

  Import new pages and add routes. The nav gains "Navigator" as first item; `/` now redirects to `/navigator` instead of `/evaluations`.

  ```tsx
  // App.tsx — update NAV_ITEMS and Routes
  import { AssetNavigatorPage } from './pages/AssetNavigatorPage'
  import { MetricExplorerPage } from './pages/MetricExplorerPage'

  const NAV_ITEMS = [
    { to: '/navigator', label: 'Navigator' },
    { to: '/evaluations', label: 'Evaluations' },
    { to: '/slos', label: 'SLOs' },
    { to: '/assets', label: 'Assets' },
  ]

  // In Routes:
  <Route path="/" element={<Navigate to="/navigator" replace />} />
  <Route path="/navigator" element={<AssetNavigatorPage />} />
  <Route path="/explorer" element={<MetricExplorerPage />} />
  ```

- [ ] **Step 1.2: Create AssetNavigatorPage shell**

  Split-pane layout: fixed-width left sidebar + flex-grow right content. Selection state lives in URL params.

  ```tsx
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

    return (
      <div className="flex h-[calc(100vh-49px)] overflow-hidden">
        {/* Left: fixed-width tree */}
        <div className="w-64 shrink-0 border-r border-border overflow-y-auto">
          <AssetTreePanel
            selectedGroup={selectedGroup}
            selectedAsset={selectedAsset}
            onSelectGroup={selectGroup}
            onSelectAsset={selectAsset}
          />
        </div>
        {/* Right: contextual content */}
        <div className="flex-1 overflow-y-auto">
          {selectedAsset && <AssetPanel assetName={selectedAsset} />}
          {!selectedAsset && selectedGroup && <GroupPanel groupName={selectedGroup} />}
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

- [ ] **Step 1.3: Create MetricExplorerPage shell**

  ```tsx
  // ui/src/pages/MetricExplorerPage.tsx
  export function MetricExplorerPage() {
    return (
      <div className="p-6">
        <h1 className="text-xl font-semibold mb-4">Metric Explorer</h1>
        <p className="text-muted-foreground text-sm">Coming soon — full-screen metric trend analysis.</p>
      </div>
    )
  }
  ```

- [ ] **Step 1.4: Create stub components so the app compiles**

  Create these files with minimal stub exports:
  - `ui/src/features/navigator/components/AssetTreePanel.tsx` — renders `<div>Tree</div>`
  - `ui/src/features/navigator/components/GroupPanel.tsx` — renders `<div>Group: {props.groupName}</div>`
  - `ui/src/features/navigator/components/AssetPanel.tsx` — renders `<div>Asset: {props.assetName}</div>`

- [ ] **Step 1.5: Verify app compiles and Navigator nav item works**

  ```bash
  npm --prefix /mnt/d/DEV/keptn_rewrite/tropek/ui run build 2>&1 | tail -5
  ```
  Expected: no TypeScript errors, build succeeds.

- [ ] **Step 1.6: Commit**

  ```bash
  git -C /mnt/d/DEV/keptn_rewrite/tropek add ui/src/App.tsx ui/src/pages/AssetNavigatorPage.tsx ui/src/pages/MetricExplorerPage.tsx ui/src/features/navigator/
  git -C /mnt/d/DEV/keptn_rewrite/tropek commit -m "feat(ui): add Asset Navigator and Metric Explorer route shells"
  ```

---

## Chunk 2: Asset Tree Sidebar

**Files:**
- Create: `ui/src/features/navigator/components/AssetTreePanel.tsx`
- Modify: `ui/src/mocks/generate.ts` (add nested subgroups)

- [ ] **Step 2.1: Add subgroups to mock `getAssetGroupTree`**

  The current mock returns flat groups with no subgroups. Update it so Performance Lab 1 contains two subgroups ("Linux" and "Windows") to demonstrate nesting. This is pure mock data; the API contract already supports subgroups.

  In `ui/src/mocks/generate.ts`, update `getAssetGroupTree`:

  ```ts
  // Performance Lab 1 gets Linux and Windows subgroups
  // Assets prefixed 'centos/rocky/ubuntu' → linux subgroup
  // Assets prefixed 'win/winsrv' → windows subgroup

  export function getAssetGroupTree(): AssetGroupTree {
    // ... existing code until allGroups construction ...

    // For 'performance-lab-1': split members into two subgroups
    const pl1 = allGroups.find(g => g.name === 'performance-lab-1')
    if (pl1) {
      const linuxMembers = pl1.members.filter(m => !m.asset_name.startsWith('win'))
      const winMembers   = pl1.members.filter(m =>  m.asset_name.startsWith('win'))

      const linuxGroup: AssetGroup = {
        id: 'group-pl1-linux',
        name: 'performance-lab-1-linux',
        display_name: 'Linux',
        description: 'Linux assets in Performance Lab 1',
        members: linuxMembers,
        subgroups: [],
      }
      const winGroup: AssetGroup = {
        id: 'group-pl1-windows',
        name: 'performance-lab-1-windows',
        display_name: 'Windows',
        description: 'Windows assets in Performance Lab 1',
        members: winMembers,
        subgroups: [],
      }

      // Remove members from parent — parent only holds subgroup references
      pl1.members = []
      pl1.subgroups = [
        { group_id: 'group-pl1-linux', weight: 1 },
        { group_id: 'group-pl1-windows', weight: 1 },
      ]

      allGroups.push(linuxGroup, winGroup)
    }

    return { top_level: topLevel, all_groups: allGroups }
  }
  ```

  Note: `AssetGroupTree` shape has `top_level` (top-level groups only) and `all_groups` (everything including subgroups). The existing `AssetGroupCard` recursive renderer already handles this correctly.

- [ ] **Step 2.2: Implement `AssetTreePanel`**

  The panel renders a collapsible tree recursively. Groups can be expanded/collapsed. Clicking a group selects it (highlights it, loads group view on the right). Clicking a leaf asset selects it. A filter input at the top narrows visible nodes by name.

  ```tsx
  // ui/src/features/navigator/components/AssetTreePanel.tsx
  import { useState } from 'react'
  import { useAssetGroups } from '@/features/assets/hooks'
  import type { AssetGroup, AssetGroupTree } from '@/features/assets/types'

  interface Props {
    selectedGroup?: string
    selectedAsset?: string
    onSelectGroup: (name: string) => void
    onSelectAsset: (name: string) => void
  }

  interface NodeProps {
    group: AssetGroup
    tree: AssetGroupTree
    depth: number
    filter: string
    selectedGroup?: string
    selectedAsset?: string
    onSelectGroup: (name: string) => void
    onSelectAsset: (name: string) => void
  }

  function TreeNode({ group, tree, depth, filter, selectedGroup, selectedAsset, onSelectGroup, onSelectAsset }: NodeProps) {
    const [open, setOpen] = useState(depth === 0)

    const subgroups = group.subgroups
      .map(sg => tree.all_groups.find(g => g.id === sg.group_id))
      .filter(Boolean) as AssetGroup[]

    const filteredMembers = filter
      ? group.members.filter(m => m.asset_name.toLowerCase().includes(filter.toLowerCase()))
      : group.members

    const isGroupSelected = selectedGroup === group.name
    const indent = depth * 12

    return (
      <div>
        {/* Group row */}
        <button
          className={`flex items-center w-full text-left px-3 py-1.5 text-sm gap-1 hover:bg-muted/50 transition-colors ${
            isGroupSelected ? 'bg-muted text-foreground font-medium' : 'text-muted-foreground'
          }`}
          style={{ paddingLeft: `${indent + 12}px` }}
          onClick={() => {
            setOpen(v => !v)
            onSelectGroup(group.name)
          }}
        >
          <span className="text-xs w-3 shrink-0">{open ? '▾' : '▸'}</span>
          <span className="truncate">{group.display_name ?? group.name}</span>
          {group.members.length > 0 && (
            <span className="text-xs text-muted-foreground/60 ml-auto shrink-0">{group.members.length}</span>
          )}
        </button>

        {/* Children */}
        {open && (
          <div>
            {subgroups.map(sg => (
              <TreeNode
                key={sg.id}
                group={sg}
                tree={tree}
                depth={depth + 1}
                filter={filter}
                selectedGroup={selectedGroup}
                selectedAsset={selectedAsset}
                onSelectGroup={onSelectGroup}
                onSelectAsset={onSelectAsset}
              />
            ))}
            {filteredMembers.map(m => {
              const isAssetSelected = selectedAsset === m.asset_name
              return (
                <button
                  key={m.asset_id}
                  className={`flex items-center w-full text-left px-3 py-1 text-xs transition-colors hover:bg-muted/50 ${
                    isAssetSelected ? 'bg-muted text-foreground font-medium' : 'text-muted-foreground'
                  }`}
                  style={{ paddingLeft: `${indent + 28}px` }}
                  onClick={() => onSelectAsset(m.asset_name)}
                >
                  <span className="font-mono truncate">{m.asset_name}</span>
                </button>
              )
            })}
          </div>
        )}
      </div>
    )
  }

  export function AssetTreePanel({ selectedGroup, selectedAsset, onSelectGroup, onSelectAsset }: Props) {
    const { data: tree, isLoading } = useAssetGroups()
    const [filter, setFilter] = useState('')

    return (
      <div className="flex flex-col h-full">
        <div className="p-3 border-b border-border">
          <input
            type="text"
            placeholder="Filter…"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            className="w-full px-2 py-1 text-xs rounded border border-border bg-muted/30 text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary"
          />
        </div>
        <div className="flex-1 overflow-y-auto py-2">
          {isLoading && <p className="px-3 py-2 text-xs text-muted-foreground">Loading…</p>}
          {tree?.top_level.map(group => (
            <TreeNode
              key={group.id}
              group={group}
              tree={tree}
              depth={0}
              filter={filter}
              selectedGroup={selectedGroup}
              selectedAsset={selectedAsset}
              onSelectGroup={onSelectGroup}
              onSelectAsset={onSelectAsset}
            />
          ))}
        </div>
      </div>
    )
  }
  ```

- [ ] **Step 2.3: Build and verify tree renders**

  ```bash
  npm --prefix /mnt/d/DEV/keptn_rewrite/tropek/ui run build 2>&1 | tail -5
  ```

  Also verify in the browser dev server that Performance Lab 1 shows two subgroups ("Linux" and "Windows"), each with members. If either subgroup is empty, the `startsWith('win')` filter needs adjusting to match actual asset name prefixes in the mock data (`winsrv`, `win7`, `win10`, `win11`).

- [ ] **Step 2.4: Commit**

  ```bash
  git -C /mnt/d/DEV/keptn_rewrite/tropek add ui/src/features/navigator/components/AssetTreePanel.tsx ui/src/mocks/generate.ts
  git -C /mnt/d/DEV/keptn_rewrite/tropek commit -m "feat(ui): add AssetTreePanel with nested group/subgroup/asset tree"
  ```

---

## Chunk 3: Pure Data Utilities + Tests

Pure transformation functions that power the heatmaps and stacked chart. These are the only logic that gets unit-tested.

**Files:**
- Create: `ui/src/features/navigator/types.ts`
- Create: `ui/src/features/navigator/utils.ts`
- Create: `ui/src/features/navigator/utils.test.ts`

- [ ] **Step 3.1: Create navigator types**

  ```ts
  // ui/src/features/navigator/types.ts

  import type { EvaluationSummary } from '@/features/evaluations/types'

  // Grid cell for both group and asset heatmaps
  export interface HeatmapCell {
    value: [number, number]       // [xIndex (slot), yIndex (row)]
    result: string                // pass | warning | fail | error | invalidated | none
    score: number
    slot: string                  // ISO timestamp for column
    rowLabel: string              // asset name (group view) or metric display name (asset view)
    evalId?: string               // defined in asset view — for click navigation
  }

  // Pre-computed group heatmap: rows=assets, cols=slots
  export interface GroupHeatmapData {
    slots: string[]               // unique ISO timestamps, sorted
    rows: string[]                // unique asset names
    cells: HeatmapCell[]
  }

  // One data point in the stacked bar chart
  export interface AssetScorePoint {
    slot: string
    assetName: string
    score: number                 // 0–100
    result: string
    maxScore: number              // always 100 (per asset)
  }

  // Grouped by slot for stacked bar rendering
  export interface SlotScoreData {
    slot: string
    assets: AssetScorePoint[]
    totalAchieved: number
    totalMax: number
  }

  // API response for GET /api/evaluations/metric-heatmap?asset_name=X
  export interface MetricHeatmapCell {
    slot: string
    metric: string
    display_name: string
    result: string
    score: number
    eval_id: string
  }

  export interface MetricHeatmapResponse {
    asset_name: string
    slots: string[]
    metrics: Array<{ name: string; display_name: string; tab_group?: string }>
    cells: MetricHeatmapCell[]
  }

  // Pre-computed asset heatmap: rows=metrics, cols=evaluations
  export interface AssetHeatmapData {
    slots: string[]
    rows: string[]                // display_names in metric order
    cells: HeatmapCell[]
  }
  ```

- [ ] **Step 3.2: Write failing tests for `buildGroupHeatmapData`**

  ```ts
  // ui/src/features/navigator/utils.test.ts
  import { describe, it, expect } from 'vitest'
  import { buildGroupHeatmapData, buildGroupScoreData, buildAssetHeatmapData } from './utils'
  import type { EvaluationSummary } from '@/features/evaluations/types'
  import type { MetricHeatmapResponse } from './types'

  function mkEval(asset: string, slot: string, result: 'pass' | 'warning' | 'fail', score: number): EvaluationSummary {
    return {
      id: `${asset}-${slot}`,
      name: 'test',
      status: 'completed',
      result,
      score,
      period_start: slot,
      period_end: slot,
      slo_name: null, slo_version: null, sli_name: null, sli_version: null,
      data_source_name: null, ingestion_mode: 'pull', adapter_used: null,
      invalidated: false,
      asset_snapshot: { name: asset, tags: {} },
      evaluation_metadata: {},
      created_at: slot,
    }
  }

  describe('buildGroupHeatmapData', () => {
    it('builds correct slots and rows from evaluations', () => {
      const evals = [
        mkEval('asset-a', '2026-01-01T06:00:00Z', 'pass', 95),
        mkEval('asset-b', '2026-01-01T06:00:00Z', 'fail', 40),
        mkEval('asset-a', '2026-01-02T06:00:00Z', 'pass', 98),
      ]
      const { slots, rows } = buildGroupHeatmapData(evals)
      expect(slots).toEqual(['2026-01-01T06:00:00Z', '2026-01-02T06:00:00Z'])
      expect(rows).toEqual(['asset-a', 'asset-b'])
    })

    it('produces a cell for every (slot × row) combination', () => {
      const evals = [
        mkEval('asset-a', '2026-01-01T06:00:00Z', 'pass', 95),
        mkEval('asset-b', '2026-01-01T06:00:00Z', 'fail', 40),
      ]
      const { cells } = buildGroupHeatmapData(evals)
      // 1 slot × 2 rows = 2 cells
      expect(cells).toHaveLength(2)
    })

    it('uses result=none for empty cells', () => {
      const evals = [
        mkEval('asset-a', '2026-01-01T06:00:00Z', 'pass', 95),
        mkEval('asset-b', '2026-01-02T06:00:00Z', 'pass', 90), // different slot
      ]
      const { cells } = buildGroupHeatmapData(evals)
      // 2 slots × 2 rows = 4 cells; 2 of them are empty
      const emptyCells = cells.filter(c => c.result === 'none')
      expect(emptyCells).toHaveLength(2)
    })

    it('picks worst result when two evaluations share the same cell', () => {
      const evals = [
        mkEval('asset-a', '2026-01-01T06:00:00Z', 'pass', 90),
        mkEval('asset-a', '2026-01-01T06:00:00Z', 'fail', 40), // same cell
      ]
      const { cells } = buildGroupHeatmapData(evals)
      const cell = cells.find(c => c.result !== 'none')!
      expect(cell.result).toBe('fail')
    })
  })

  describe('buildGroupScoreData', () => {
    it('groups scores by slot with one entry per asset', () => {
      const evals = [
        mkEval('asset-a', '2026-01-01T06:00:00Z', 'pass', 90),
        mkEval('asset-b', '2026-01-01T06:00:00Z', 'fail', 40),
      ]
      const data = buildGroupScoreData(evals)
      expect(data).toHaveLength(1)
      expect(data[0].assets).toHaveLength(2)
      expect(data[0].totalAchieved).toBeCloseTo(130)
      expect(data[0].totalMax).toBe(200)
    })
  })

  describe('buildAssetHeatmapData', () => {
    it('maps metric-heatmap API response to grid data', () => {
      const resp: MetricHeatmapResponse = {
        asset_name: 'asset-a',
        slots: ['2026-01-01T06:00:00Z', '2026-01-02T06:00:00Z'],
        metrics: [{ name: 'error_rate', display_name: 'Error Rate' }],
        cells: [
          { slot: '2026-01-01T06:00:00Z', metric: 'error_rate', display_name: 'Error Rate', result: 'pass', score: 100, eval_id: 'e1' },
          { slot: '2026-01-02T06:00:00Z', metric: 'error_rate', display_name: 'Error Rate', result: 'fail', score: 0, eval_id: 'e2' },
        ],
      }
      const { slots, rows, cells } = buildAssetHeatmapData(resp)
      expect(slots).toHaveLength(2)
      expect(rows).toHaveLength(1)
      expect(cells).toHaveLength(2)
      expect(cells[1].result).toBe('fail')
      expect(cells[1].evalId).toBe('e2')
    })
  })
  ```

- [ ] **Step 3.3: Run tests to confirm they fail**

  ```bash
  npm --prefix /mnt/d/DEV/keptn_rewrite/tropek/ui test 2>&1 | tail -20
  ```
  Expected: all three describe blocks fail with "cannot find module './utils'".

- [ ] **Step 3.4: Implement `utils.ts`**

  ```ts
  // ui/src/features/navigator/utils.ts
  import type { EvaluationSummary } from '@/features/evaluations/types'
  import type { HeatmapCell, GroupHeatmapData, SlotScoreData, AssetHeatmapData, MetricHeatmapResponse } from './types'

  const RESULT_RANK: Record<string, number> = { pass: 0, warning: 1, fail: 2, error: 3, invalidated: 4 }

  export function buildGroupHeatmapData(evals: EvaluationSummary[]): GroupHeatmapData {
    const slots = Array.from(new Set(evals.map(e => e.period_start))).sort()
    const rows  = Array.from(new Set(evals.map(e => e.asset_snapshot.name))).sort()

    // Merge duplicates: worst result, averaged score
    const cellMap = new Map<string, { result: string; score: number; count: number }>()
    for (const e of evals) {
      const key = `${e.asset_snapshot.name}::${e.period_start}`
      const effectiveResult = e.invalidated ? 'invalidated' : e.result
      const existing = cellMap.get(key)
      if (!existing) {
        cellMap.set(key, { result: effectiveResult, score: e.score, count: 1 })
      } else {
        cellMap.set(key, {
          result: (RESULT_RANK[effectiveResult] ?? 0) > (RESULT_RANK[existing.result] ?? 0)
            ? effectiveResult : existing.result,
          score: (existing.score * existing.count + e.score) / (existing.count + 1),
          count: existing.count + 1,
        })
      }
    }

    const cells: HeatmapCell[] = []
    for (let xi = 0; xi < slots.length; xi++) {
      for (let yi = 0; yi < rows.length; yi++) {
        const key = `${rows[yi]}::${slots[xi]}`
        const cell = cellMap.get(key)
        cells.push({
          value: [xi, yi],
          result: cell?.result ?? 'none',
          score: cell ? Math.round(cell.score) : 0,
          slot: slots[xi],
          rowLabel: rows[yi],
        })
      }
    }

    return { slots, rows, cells }
  }

  export function buildGroupScoreData(evals: EvaluationSummary[]): SlotScoreData[] {
    const slots = Array.from(new Set(evals.map(e => e.period_start))).sort()

    return slots.map(slot => {
      const slotEvals = evals.filter(e => e.period_start === slot)
      const assets = slotEvals.map(e => ({
        slot,
        assetName: e.asset_snapshot.name,
        score: e.score,
        result: e.invalidated ? 'invalidated' : e.result,
        maxScore: 100,
      }))
      return {
        slot,
        assets,
        totalAchieved: assets.reduce((s, a) => s + a.score, 0),
        totalMax: assets.length * 100,
      }
    })
  }

  export function buildAssetHeatmapData(resp: MetricHeatmapResponse): AssetHeatmapData {
    const { slots, metrics, cells } = resp

    const cellMap = new Map<string, MetricHeatmapResponse['cells'][0]>()
    for (const c of cells) {
      cellMap.set(`${c.metric}::${c.slot}`, c)
    }

    const rows = metrics.map(m => m.display_name)

    const gridCells: HeatmapCell[] = []
    for (let xi = 0; xi < slots.length; xi++) {
      for (let yi = 0; yi < metrics.length; yi++) {
        const key = `${metrics[yi].name}::${slots[xi]}`
        const c = cellMap.get(key)
        gridCells.push({
          value: [xi, yi],
          result: c?.result ?? 'none',
          score: c ? Math.round(c.score) : 0,
          slot: slots[xi],
          rowLabel: metrics[yi].display_name,
          evalId: c?.eval_id,
        })
      }
    }

    return { slots, rows, cells: gridCells }
  }
  ```

- [ ] **Step 3.5: Run tests to confirm they pass**

  ```bash
  npm --prefix /mnt/d/DEV/keptn_rewrite/tropek/ui test 2>&1 | tail -10
  ```
  Expected: all tests PASS.

- [ ] **Step 3.6: Commit**

  ```bash
  git -C /mnt/d/DEV/keptn_rewrite/tropek add ui/src/features/navigator/types.ts ui/src/features/navigator/utils.ts ui/src/features/navigator/utils.test.ts
  git -C /mnt/d/DEV/keptn_rewrite/tropek commit -m "feat(ui): add navigator pure utils with unit tests"
  ```

---

## Chunk 4: API Extension + Mock Endpoint

**Files:**
- Modify: `ui/src/features/evaluations/types.ts`
- Modify: `ui/src/features/evaluations/api.ts`
- Create: `ui/src/features/navigator/hooks.ts`
- Modify: `ui/src/mocks/generate.ts`
- Modify: `ui/src/mocks/handlers/evaluations.ts`

- [ ] **Step 4.1: Add `asset_name` to `EvaluationFilters`**

  In `ui/src/features/evaluations/types.ts`:
  ```ts
  export interface EvaluationFilters {
    group_name?: string
    asset_name?: string   // ← add this
    date?: string
    from?: string
    to?: string
  }
  ```

- [ ] **Step 4.2: Pass `asset_name` in `toParams`**

  In `ui/src/features/evaluations/api.ts`, update `toParams`:
  ```ts
  function toParams(filters: EvaluationFilters): string {
    const p = new URLSearchParams()
    if (filters.group_name) p.set('group_name', filters.group_name)
    if (filters.asset_name) p.set('asset_name', filters.asset_name)  // ← add
    if (filters.date)       p.set('date', filters.date)
    if (filters.from)       p.set('from', filters.from)
    if (filters.to)         p.set('to', filters.to)
    return p.toString()
  }
  ```

- [ ] **Step 4.3: Add `fetchMetricHeatmap` to api.ts**

  ```ts
  // In ui/src/features/evaluations/api.ts — add at bottom
  import type { MetricHeatmapResponse } from '@/features/navigator/types'

  export async function fetchMetricHeatmap(assetName: string): Promise<MetricHeatmapResponse> {
    const res = await fetch(`/api/evaluations/metric-heatmap?asset_name=${encodeURIComponent(assetName)}`)
    if (!res.ok) throw new Error(`fetchMetricHeatmap: ${res.status}`)
    return res.json()
  }
  ```

- [ ] **Step 4.4: Create navigator hooks**

  ```ts
  // ui/src/features/navigator/hooks.ts
  import { useQuery } from '@tanstack/react-query'
  import { fetchEvaluations, fetchMetricHeatmap } from '@/features/evaluations/api'

  export function useAssetEvaluations(assetName: string | undefined) {
    return useQuery({
      queryKey: ['evaluations', { asset_name: assetName }],
      queryFn: () => fetchEvaluations({ asset_name: assetName }),
      enabled: !!assetName,
    })
  }

  export function useMetricHeatmap(assetName: string | undefined) {
    return useQuery({
      queryKey: ['metric-heatmap', assetName],
      queryFn: () => fetchMetricHeatmap(assetName!),
      enabled: !!assetName,
    })
  }
  ```

- [ ] **Step 4.5: Add `asset_name` filter in mock `getEvaluations`**

  In `ui/src/mocks/generate.ts`, update:
  ```ts
  export function getEvaluations(filters: EvaluationListFilters = {}): EvaluationSummary[] {
    let evals = allEvals()
    if (filters.group_name) evals = evals.filter(e => e.asset_snapshot.tags?.['lab'] === filters.group_name)
    if (filters.asset_name) evals = evals.filter(e => e.asset_snapshot.name === filters.asset_name)  // ← add
    if (filters.date)       evals = evals.filter(e => e.period_start.startsWith(filters.date!))
    if (filters.from)       evals = evals.filter(e => e.period_start >= filters.from!)
    if (filters.to)         evals = evals.filter(e => e.period_start <= filters.to!)
    return evals
  }
  ```

  Also add `asset_name?` to `EvaluationListFilters`:
  ```ts
  export interface EvaluationListFilters {
    group_name?: string
    asset_name?: string  // ← add
    date?: string
    from?: string
    to?: string
  }
  ```

- [ ] **Step 4.6: Add `getMetricHeatmap` to mock generator**

  This generates metric×slot grid data for a single asset by calling `generateEvaluationDetail` for each of the asset's evaluations. Add at the bottom of `ui/src/mocks/generate.ts`:

  ```ts
  import type { MetricHeatmapResponse } from '../features/navigator/types'

  export function getMetricHeatmap(assetName: string): MetricHeatmapResponse {
    const assetEvals = allEvals()
      .filter(e => e.asset_snapshot.name === assetName)
      .sort((a, b) => a.period_start.localeCompare(b.period_start))

    if (!assetEvals.length) {
      return { asset_name: assetName, slots: [], metrics: [], cells: [] }
    }

    const slots = Array.from(new Set(assetEvals.map(e => e.period_start))).sort()

    // Use the first evaluation's detail to get the metric list
    const sampleDetail = generateEvaluationDetail(assetEvals[0].id, allEvals())
    const metrics = sampleDetail.indicator_results.map(ind => ({
      name: ind.metric,
      display_name: ind.display_name,
      tab_group: ind.tab_group,   // preserve metric group for chart-mode filter in AssetPanel
    }))

    const cells: MetricHeatmapResponse['cells'] = []
    for (const slot of slots) {
      const ev = assetEvals.find(e => e.period_start === slot)
      if (!ev) continue
      const detail = generateEvaluationDetail(ev.id, allEvals())
      for (const ind of detail.indicator_results) {
        cells.push({
          slot,
          metric: ind.metric,
          display_name: ind.display_name,
          result: ind.status,
          score: ind.score,
          eval_id: ev.id,
        })
      }
    }

    return { asset_name: assetName, slots, metrics, cells }
  }
  ```

- [ ] **Step 4.7: Add MSW handler for `asset_name` + metric-heatmap endpoint**

  In `ui/src/mocks/handlers/evaluations.ts`:

  ```ts
  // Update GET /api/evaluations to forward asset_name:
  http.get('/api/evaluations', async ({ request }) => {
    const url = new URL(request.url)
    const group_name = url.searchParams.get('group_name') ?? undefined
    const asset_name = url.searchParams.get('asset_name') ?? undefined  // ← add
    const date  = url.searchParams.get('date') ?? undefined
    const from  = url.searchParams.get('from') ?? undefined
    const to    = url.searchParams.get('to')   ?? undefined
    const { getEvaluations } = await gen()
    const items = getEvaluations({ group_name, asset_name, date, from, to })
    return HttpResponse.json({ items, total: items.length })
  }),

  // Add new handler (insert before the closing bracket):
  http.get('/api/evaluations/metric-heatmap', async ({ request }) => {
    const url = new URL(request.url)
    const assetName = url.searchParams.get('asset_name') ?? ''
    const { getMetricHeatmap } = await gen()
    return HttpResponse.json(getMetricHeatmap(assetName))
  }),
  ```

  **Important:** the `metric-heatmap` route must be registered **before** the `evaluations/:id` route in the handlers array, otherwise MSW will match `:id = 'metric-heatmap'` first.

- [ ] **Step 4.8: Build + run tests**

  ```bash
  npm --prefix /mnt/d/DEV/keptn_rewrite/tropek/ui run build 2>&1 | tail -5
  ```
  ```bash
  npm --prefix /mnt/d/DEV/keptn_rewrite/tropek/ui test 2>&1 | tail -10
  ```
  Expected: build succeeds, all tests pass.

- [ ] **Step 4.9: Commit**

  ```bash
  git -C /mnt/d/DEV/keptn_rewrite/tropek add ui/src/features/evaluations/types.ts ui/src/features/evaluations/api.ts ui/src/features/navigator/hooks.ts ui/src/mocks/generate.ts ui/src/mocks/handlers/evaluations.ts
  git -C /mnt/d/DEV/keptn_rewrite/tropek commit -m "feat(ui): extend evaluations API with asset_name filter and metric-heatmap endpoint"
  ```

---

## Chunk 5: Group Panel

The group panel loads evaluations for the selected group, renders a toggle bar (Heatmap / Chart / Explorer icon), and delegates to `GroupHeatmap` or `GroupScoreChart`.

**Files:**
- Create: `ui/src/features/navigator/components/GroupHeatmap.tsx`
- Create: `ui/src/features/navigator/components/GroupScoreChart.tsx`
- Modify: `ui/src/features/navigator/components/GroupPanel.tsx` (replace stub)

- [ ] **Step 5.1: Implement `GroupHeatmap`**

  Heavily based on `EvaluationHeatmap.tsx` but with rows=assets instead of rows="asset · eval name". Click navigates to `/evaluations?group_name=X&from=slot&to=slot` (single click, no double-click).

  ```tsx
  // ui/src/features/navigator/components/GroupHeatmap.tsx
  import ReactECharts from 'echarts-for-react'
  import { useMemo } from 'react'
  import { useNavigate } from 'react-router-dom'
  import { useTheme } from '@/lib/theme-context'
  import { RESULT_COLOUR, CHART_THEME } from '@/lib/theme'
  import { fmtSlot, fmtDateTime } from '@/lib/format'
  import { buildGroupHeatmapData } from '../utils'
  import type { EvaluationSummary } from '@/features/evaluations/types'
  import type { HeatmapCell } from '../types'

  interface Props {
    evaluations: EvaluationSummary[]
    groupName: string
  }

  const PAD = 2

  export function GroupHeatmap({ evaluations, groupName }: Props) {
    const navigate = useNavigate()
    const { theme } = useTheme()
    const colours = RESULT_COLOUR[theme]
    const ct = CHART_THEME[theme]

    const { slots, rows, cells } = useMemo(
      () => buildGroupHeatmapData(evaluations),
      [evaluations],
    )

    const chartCells = cells.map(cell => ({
      ...cell,
      itemStyle: {
        color: cell.result === 'none'
          ? ct.bg
          : colours[cell.result as keyof typeof colours] ?? ct.bg,
        borderColor: 'transparent',
        borderWidth: 0,
      },
    }))

    const option = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item' as const,
        backgroundColor: ct.bg,
        borderColor: ct.border,
        textStyle: { color: ct.axisLabel },
        formatter: (p: { data: HeatmapCell }) => {
          const d = p.data
          if (d.result === 'none') return `${d.rowLabel}<br/>${fmtDateTime(d.slot)}<br/><em>no data</em>`
          const rc = colours[d.result as keyof typeof colours] ?? '#ccc'
          return [
            `<b>${d.rowLabel}</b>`,
            fmtDateTime(d.slot),
            `Score: <b style="color:${rc}">${d.score}%</b> · <b style="color:${rc}">${d.result.toUpperCase()}</b>`,
            `<span style="color:#888;font-size:10px">Click to open evaluations</span>`,
          ].join('<br/>')
        },
      },
      xAxis: {
        type: 'category' as const,
        data: slots.map(fmtSlot),
        axisLabel: { rotate: 45, fontSize: 11, color: ct.axisLabel },
        axisLine: { lineStyle: { color: ct.grid } },
        splitLine: { show: false },
      },
      yAxis: {
        type: 'category' as const,
        data: rows,
        axisLabel: { fontSize: 11, color: ct.axisLabel, width: 180, overflow: 'truncate' as const },
        axisLine: { lineStyle: { color: ct.grid } },
        splitLine: { lineStyle: { color: ct.bg } },
      },
      series: [{
        type: 'custom',
        renderItem: (
          _p: unknown,
          api: {
            value: (d: number) => number
            coord: (pos: [number, number]) => [number, number]
            size: (sz: [number, number]) => [number, number]
            style: (extra?: object) => object
          },
        ) => {
          const xi = api.value(0)
          const yi = api.value(1)
          const [cx, cy] = api.coord([xi, yi])
          const [w, h] = api.size([1, 1])
          return {
            type: 'rect',
            shape: { x: cx - w / 2 + PAD, y: cy - h / 2 + PAD, width: w - PAD * 2, height: h - PAD * 2, r: 3 },
            style: api.style(),
          }
        },
        data: chartCells,
        encode: { x: 0, y: 1 },
      }],
      grid: { top: 10, bottom: 80, left: 190, right: 20 },
    }

    return (
      <ReactECharts
        option={option}
        style={{ height: Math.max(200, rows.length * 28 + 100) }}
        opts={{ renderer: 'svg' }}
        onEvents={{
          click: (p: { data: HeatmapCell }) => {
            if (!p?.data?.slot) return
            const slotEnd = new Date(new Date(p.data.slot).getTime() + 1000).toISOString().slice(0, 19) + 'Z'
            navigate(`/evaluations?group_name=${encodeURIComponent(groupName)}&from=${p.data.slot}&to=${slotEnd}`)
          },
        }}
      />
    )
  }
  ```

- [ ] **Step 5.2: Implement `GroupScoreChart`**

  Stacked bar chart. Each bar = one time slot. Segments = per-asset score (0–100). Colors by result. Toggle switch: absolute (y-axis = n_assets × 100) vs normalized (y-axis = 0–100%).

  ```tsx
  // ui/src/features/navigator/components/GroupScoreChart.tsx
  import ReactECharts from 'echarts-for-react'
  import { useMemo, useState } from 'react'
  import { useTheme } from '@/lib/theme-context'
  import { RESULT_COLOUR, CHART_THEME } from '@/lib/theme'
  import { fmtSlot } from '@/lib/format'
  import { buildGroupScoreData } from '../utils'
  import type { EvaluationSummary } from '@/features/evaluations/types'

  interface Props {
    evaluations: EvaluationSummary[]
  }

  export function GroupScoreChart({ evaluations }: Props) {
    const { theme } = useTheme()
    const colours = RESULT_COLOUR[theme]
    const ct = CHART_THEME[theme]
    const [normalized, setNormalized] = useState(false)

    const slotData = useMemo(() => buildGroupScoreData(evaluations), [evaluations])
    const assetNames = Array.from(new Set(evaluations.map(e => e.asset_snapshot.name))).sort()
    const slots = slotData.map(d => d.slot)

    // One series per asset — stacked bars
    const series = assetNames.map(assetName => ({
      name: assetName,
      type: 'bar' as const,
      stack: 'score',
      data: slotData.map(slotRow => {
        const ap = slotRow.assets.find(a => a.assetName === assetName)
        if (!ap) return { value: 0, itemStyle: { color: ct.bg } }
        const value = normalized
          ? (ap.score / 100) * (100 / assetNames.length)
          : ap.score
        return {
          value: +value.toFixed(1),
          itemStyle: { color: colours[ap.result as keyof typeof colours] ?? ct.bg },
          // Store original data for tooltip
          assetName: ap.assetName,
          score: ap.score,
          result: ap.result,
        }
      }),
    }))

    const option = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis' as const,
        axisPointer: { type: 'shadow' as const },
        backgroundColor: ct.bg,
        borderColor: ct.border,
        textStyle: { color: ct.axisLabel },
        formatter: (params: Array<{ seriesName: string; data: { score?: number; result?: string; value: number } }>) => {
          const lines = params
            .filter(p => (p.data.score ?? p.data.value) > 0)
            .map(p => {
              const rc = colours[(p.data.result as keyof typeof colours) ?? 'pass'] ?? '#ccc'
              return `<span style="color:${rc}">● ${p.seriesName}: ${p.data.score ?? p.data.value}%</span>`
            })
          return lines.join('<br/>')
        },
      },
      xAxis: {
        type: 'category' as const,
        data: slots.map(fmtSlot),
        axisLabel: { rotate: 45, fontSize: 11, color: ct.axisLabel },
        axisLine: { lineStyle: { color: ct.grid } },
      },
      yAxis: {
        type: 'value' as const,
        max: normalized ? 100 : assetNames.length * 100,
        axisLabel: {
          color: ct.axisLabel,
          formatter: normalized ? (v: number) => `${v}%` : undefined,
        },
        splitLine: { lineStyle: { color: ct.grid } },
      },
      series,
      grid: { top: 20, bottom: 80, left: 50, right: 20 },
    }

    return (
      <div>
        <div className="flex items-center gap-2 mb-2 justify-end">
          <span className="text-xs text-muted-foreground">Scale:</span>
          <button
            onClick={() => setNormalized(false)}
            className={`px-2 py-0.5 text-xs rounded border transition-colors ${
              !normalized ? 'border-primary text-primary' : 'border-border text-muted-foreground'
            }`}
          >
            Absolute
          </button>
          <button
            onClick={() => setNormalized(true)}
            className={`px-2 py-0.5 text-xs rounded border transition-colors ${
              normalized ? 'border-primary text-primary' : 'border-border text-muted-foreground'
            }`}
          >
            0–100%
          </button>
        </div>
        <ReactECharts option={option} style={{ height: 320 }} opts={{ renderer: 'svg' }} notMerge />
      </div>
    )
  }
  ```

- [ ] **Step 5.3: Implement `GroupPanel`**

  Loads evaluations for the group, renders header with group name + score, toggle bar (Heatmap / Chart / Explorer icon button), and delegates to `GroupHeatmap` or `GroupScoreChart`.

  ```tsx
  // ui/src/features/navigator/components/GroupPanel.tsx
  import { useState } from 'react'
  import { useNavigate } from 'react-router-dom'
  import { useEvaluations } from '@/features/evaluations/hooks'
  import { GroupHeatmap } from './GroupHeatmap'
  import { GroupScoreChart } from './GroupScoreChart'

  type ViewMode = 'heatmap' | 'chart'

  interface Props {
    groupName: string
  }

  export function GroupPanel({ groupName }: Props) {
    const [mode, setMode] = useState<ViewMode>('heatmap')
    const navigate = useNavigate()
    const { data: evals = [], isLoading } = useEvaluations({ group_name: groupName })

    const latestScore = evals.length
      ? Math.round(evals.filter(e => !e.invalidated).slice(-1)[0]?.score ?? 0)
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
              {/* simple bar-chart icon using Unicode */}
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                <rect x="1" y="9" width="3" height="6" rx="0.5"/>
                <rect x="6" y="5" width="3" height="10" rx="0.5"/>
                <rect x="11" y="2" width="3" height="13" rx="0.5"/>
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="rounded-lg border border-border bg-card p-4">
          {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {!isLoading && evals.length === 0 && (
            <p className="text-sm text-muted-foreground">No evaluations found for this group.</p>
          )}
          {!isLoading && evals.length > 0 && mode === 'heatmap' && (
            <GroupHeatmap evaluations={evals} groupName={groupName} />
          )}
          {!isLoading && evals.length > 0 && mode === 'chart' && (
            <GroupScoreChart evaluations={evals} />
          )}
        </div>
      </div>
    )
  }
  ```

- [ ] **Step 5.4: Build and verify in browser**

  ```bash
  npm --prefix /mnt/d/DEV/keptn_rewrite/tropek/ui run build 2>&1 | tail -5
  ```

  Launch dev server and verify:
  - Clicking a group in the tree loads GroupPanel
  - Heatmap renders (rows=assets, cols=time slots)
  - Chart button shows stacked bars with absolute/normalized toggle
  - Graph icon navigates to `/explorer?group=X`
  - Clicking a heatmap cell navigates to `/evaluations?group_name=X&from=...`

- [ ] **Step 5.5: Commit**

  ```bash
  git -C /mnt/d/DEV/keptn_rewrite/tropek add ui/src/features/navigator/components/GroupHeatmap.tsx ui/src/features/navigator/components/GroupScoreChart.tsx ui/src/features/navigator/components/GroupPanel.tsx
  git -C /mnt/d/DEV/keptn_rewrite/tropek commit -m "feat(ui): add Group Panel with heatmap and stacked score chart"
  ```

---

## Chunk 6: Asset Panel

The asset panel shows a metric heatmap (rows=metrics, cols=evaluations), followed by per-metric trend charts reusing `MetricTrendBlock`, followed by the score table.

**Files:**
- Create: `ui/src/features/navigator/components/AssetHeatmap.tsx`
- Modify: `ui/src/features/navigator/components/AssetPanel.tsx` (replace stub)

- [ ] **Step 6.1: Implement `AssetHeatmap`**

  Similar shape to `GroupHeatmap` but uses `MetricHeatmapResponse` data (fetched via `useMetricHeatmap`). Click on a cell navigates to `EvaluationDetailPage`.

  ```tsx
  // ui/src/features/navigator/components/AssetHeatmap.tsx
  import ReactECharts from 'echarts-for-react'
  import { useMemo } from 'react'
  import { useNavigate } from 'react-router-dom'
  import { useTheme } from '@/lib/theme-context'
  import { RESULT_COLOUR, CHART_THEME } from '@/lib/theme'
  import { fmtSlot, fmtDateTime } from '@/lib/format'
  import { buildAssetHeatmapData } from '../utils'
  import type { MetricHeatmapResponse } from '../types'
  import type { HeatmapCell } from '../types'

  interface Props {
    data: MetricHeatmapResponse
  }

  const PAD = 2

  export function AssetHeatmap({ data }: Props) {
    const navigate = useNavigate()
    const { theme } = useTheme()
    const colours = RESULT_COLOUR[theme]
    const ct = CHART_THEME[theme]

    const { slots, rows, cells } = useMemo(() => buildAssetHeatmapData(data), [data])

    const chartCells = cells.map(cell => ({
      ...cell,
      itemStyle: {
        color: cell.result === 'none'
          ? ct.bg
          : colours[cell.result as keyof typeof colours] ?? ct.bg,
        borderColor: 'transparent',
        borderWidth: 0,
      },
    }))

    const option = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item' as const,
        backgroundColor: ct.bg,
        borderColor: ct.border,
        textStyle: { color: ct.axisLabel },
        formatter: (p: { data: HeatmapCell }) => {
          const d = p.data
          if (d.result === 'none') return `${d.rowLabel}<br/>${fmtDateTime(d.slot)}<br/><em>no data</em>`
          const rc = colours[d.result as keyof typeof colours] ?? '#ccc'
          return [
            `<b>${d.rowLabel}</b>`,
            fmtDateTime(d.slot),
            `Score: <b style="color:${rc}">${d.score}</b> · <b style="color:${rc}">${d.result.toUpperCase()}</b>`,
            d.evalId ? `<span style="color:#888;font-size:10px">Click to open evaluation detail</span>` : '',
          ].join('<br/>')
        },
      },
      xAxis: {
        type: 'category' as const,
        data: slots.map(fmtSlot),
        axisLabel: { rotate: 45, fontSize: 11, color: ct.axisLabel },
        axisLine: { lineStyle: { color: ct.grid } },
        splitLine: { show: false },
      },
      yAxis: {
        type: 'category' as const,
        data: rows,
        axisLabel: { fontSize: 10, color: ct.axisLabel, width: 180, overflow: 'truncate' as const },
        axisLine: { lineStyle: { color: ct.grid } },
        splitLine: { lineStyle: { color: ct.bg } },
      },
      series: [{
        type: 'custom',
        renderItem: (
          _p: unknown,
          api: {
            value: (d: number) => number
            coord: (pos: [number, number]) => [number, number]
            size: (sz: [number, number]) => [number, number]
            style: (extra?: object) => object
          },
        ) => {
          const xi = api.value(0)
          const yi = api.value(1)
          const [cx, cy] = api.coord([xi, yi])
          const [w, h] = api.size([1, 1])
          return {
            type: 'rect',
            shape: { x: cx - w / 2 + PAD, y: cy - h / 2 + PAD, width: w - PAD * 2, height: h - PAD * 2, r: 2 },
            style: api.style(),
          }
        },
        data: chartCells,
        encode: { x: 0, y: 1 },
      }],
      grid: { top: 10, bottom: 80, left: 190, right: 20 },
    }

    return (
      <ReactECharts
        option={option}
        style={{ height: Math.max(200, rows.length * 22 + 100) }}
        opts={{ renderer: 'svg' }}
        onEvents={{
          click: (p: { data: HeatmapCell }) => {
            if (p?.data?.evalId) {
              navigate(`/evaluations/${p.data.evalId}`)
            }
          },
        }}
      />
    )
  }
  ```

- [ ] **Step 6.2: Implement `AssetPanel`**

  Loads metric heatmap + evaluations for the asset. Renders: header + toggle + heatmap (or chart) + trend charts (only visible in heatmap mode, below heatmap) + score table.

  The trend charts reuse `MetricTrendBlock` from the existing `EvaluationDetailPage`. We need the latest `evalId` for the selected asset to feed into `MetricTrendBlock`. We get that from the evaluations query.

  **Toggle distinction:**
  - **Heatmap mode**: metric heatmap (overview grid) + first 8 trend charts below (all metric groups). Prioritises overview.
  - **Chart mode**: no heatmap. Shows trend charts only, with a metric-group filter row so users can narrow 30 metrics to a single group (e.g. "timing"). Prioritises deep-dive on specific metric families.

  ```tsx
  // ui/src/features/navigator/components/AssetPanel.tsx
  import { useState, useMemo } from 'react'
  import { useNavigate } from 'react-router-dom'
  import { useAssetEvaluations, useMetricHeatmap } from '../hooks'
  import { AssetHeatmap } from './AssetHeatmap'
  import { MetricTrendBlock } from '@/features/evaluations/components/MetricTrendBlock'
  import { EvaluationTable } from '@/features/evaluations/components/EvaluationTable'
  import { useColumnVisibility } from '@/features/evaluations/hooks'
  import type { IndicatorResult } from '@/features/evaluations/types'

  type ViewMode = 'heatmap' | 'chart'

  interface Props {
    assetName: string
  }

  export function AssetPanel({ assetName }: Props) {
    const [mode, setMode] = useState<ViewMode>('heatmap')
    const [metricGroupFilter, setMetricGroupFilter] = useState<string>('all')
    const navigate = useNavigate()

    const { data: evals = [], isLoading: evalsLoading } = useAssetEvaluations(assetName)
    const { data: heatmapData, isLoading: heatmapLoading } = useMetricHeatmap(assetName)

    // Latest non-invalidated evaluation for trend charts
    const latestEval = useMemo(() => {
      return [...evals]
        .filter(e => !e.invalidated)
        .sort((a, b) => b.period_start.localeCompare(a.period_start))[0]
    }, [evals])

    const latestScore = latestEval ? Math.round(latestEval.score) : null

    // Build indicator stubs for MetricTrendBlock from heatmap metric list.
    // heatmapData.metrics includes tab_group (set in generate.ts Step 4.6).
    // MetricTrendBlock only uses metric name, display_name, and evalId for trend data fetching.
    const allIndicators = useMemo((): IndicatorResult[] => {
      if (!heatmapData) return []
      return heatmapData.metrics.map(m => ({
        metric: m.name,
        display_name: m.display_name,
        tab_group: m.tab_group,   // MetricHeatmapResponse.metrics should include tab_group — see Step 4.6 note
        value: 0,
        compared_value: null,
        change_absolute: null,
        change_relative_pct: null,
        aggregation: 'avg',
        status: 'pass' as const,
        score: 0,
        weight: 1,
        key_sli: false,
        pass_targets: null,
        warning_targets: null,
      }))
    }, [heatmapData])

    // Unique tab_group values from the metric list
    const metricGroups = useMemo(
      () => Array.from(new Set(allIndicators.map(i => i.tab_group).filter(Boolean) as string[])),
      [allIndicators]
    )

    // Chart mode: filter by selected group; heatmap mode: show first 8 metrics
    const visibleIndicators = mode === 'chart'
      ? (metricGroupFilter === 'all' ? allIndicators : allIndicators.filter(i => i.tab_group === metricGroupFilter))
      : allIndicators.slice(0, 8)

    const colVis = useColumnVisibility([])
    const isLoading = evalsLoading || heatmapLoading

    return (
      <div className="p-6 space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold font-mono">{assetName}</h2>
            {evals.length > 0 && (
              <p className="text-xs text-muted-foreground mt-0.5">{evals.length} evaluations</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {latestScore != null && (
              <span className="text-2xl font-bold tabular-nums text-foreground">{latestScore}%</span>
            )}
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
            <button
              onClick={() => navigate(`/explorer?asset=${encodeURIComponent(assetName)}`)}
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

        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

        {/* Heatmap mode: overview grid + first 8 trend charts */}
        {!isLoading && heatmapData && mode === 'heatmap' && (
          <>
            <div className="rounded-lg border border-border bg-card p-4">
              <AssetHeatmap data={heatmapData} />
            </div>
            {latestEval && visibleIndicators.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  Metric Trends — {assetName} (first 8 metrics)
                </h3>
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                  {visibleIndicators.map(ind => (
                    <MetricTrendBlock key={ind.metric} evalId={latestEval.id} indicator={ind} />
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* Chart mode: metric group filter + all filtered trend charts, no heatmap */}
        {!isLoading && mode === 'chart' && latestEval && (
          <div className="space-y-4">
            {/* Metric group filter */}
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
              {visibleIndicators.map(ind => (
                <MetricTrendBlock key={ind.metric} evalId={latestEval.id} indicator={ind} />
              ))}
            </div>
          </div>
        )}

        {/* Score table — always shown at the bottom */}
        {!isLoading && evals.length > 0 && (
          <div className="rounded-lg border border-border bg-card p-4">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
              Evaluation History
            </h3>
            <EvaluationTable evaluations={evals} dynamicCols={[]} {...colVis} />
          </div>
        )}
      </div>
    )
  }
  ```

  `tab_group` is already included in `MetricHeatmapResponse.metrics` (Step 3.1 type definition) and populated via `ind.tab_group` from `generateEvaluationDetail` output (Step 4.6). No additional changes needed.

- [ ] **Step 6.3: Build and verify**

  ```bash
  npm --prefix /mnt/d/DEV/keptn_rewrite/tropek/ui run build 2>&1 | tail -5
  ```

  In browser with dev server, verify:
  - Clicking an asset in the tree loads AssetPanel
  - Metric heatmap renders (rows=30 metrics, cols=30 days)
  - Clicking a heatmap cell navigates to `/evaluations/{id}`
  - Trend charts load below the heatmap (in Heatmap mode)
  - Evaluation table shows at the bottom
  - Toggling to "Chart" shows trend charts fullscreen (no heatmap, metric group filter visible)
  - Selecting a metric group in Chart mode narrows the visible trend charts
  - Graph icon navigates to `/explorer?asset=X`

- [ ] **Step 6.4: Run all tests**

  ```bash
  npm --prefix /mnt/d/DEV/keptn_rewrite/tropek/ui test 2>&1 | tail -10
  ```
  Expected: all tests PASS.

- [ ] **Step 6.5: Commit**

  ```bash
  git -C /mnt/d/DEV/keptn_rewrite/tropek add ui/src/features/navigator/components/AssetHeatmap.tsx ui/src/features/navigator/components/AssetPanel.tsx
  git -C /mnt/d/DEV/keptn_rewrite/tropek commit -m "feat(ui): add Asset Panel with metric heatmap, trend charts, and score table"
  ```

---

## Chunk 7: Metric Explorer Page

Full-screen page showing all metrics for a group or asset as line/bar charts. Accessible via the graph icon in GroupPanel and AssetPanel.

**Files:**
- Modify: `ui/src/pages/MetricExplorerPage.tsx` (replace stub)

- [ ] **Step 7.1: Implement MetricExplorerPage**

  Reads `?group=` or `?asset=` from URL. Uses `useEvaluations` or `useAssetEvaluations` to get the latest eval ID. Groups metrics by `tab_group` (the same groups as the `EvaluationDetailPage` tabs). Each metric gets a `MetricTrendBlock`.

  ```tsx
  // ui/src/pages/MetricExplorerPage.tsx
  import { useState, useMemo } from 'react'
  import { useSearchParams, Link } from 'react-router-dom'
  import { useEvaluations } from '@/features/evaluations/hooks'
  import { useAssetEvaluations } from '@/features/navigator/hooks'
  import { MetricTrendBlock } from '@/features/evaluations/components/MetricTrendBlock'
  import { METRICS } from '@/mocks/generate'
  import type { IndicatorResult } from '@/features/evaluations/types'

  // Build minimal IndicatorResult stubs from METRICS catalogue (no actual values needed — MetricTrendBlock fetches its own trend data)
  function buildIndicatorStubs(): IndicatorResult[] {
    return METRICS.map(m => ({
      metric: m.name,
      display_name: m.display_name,
      tab_group: m.tab_group,
      value: 0,
      compared_value: null,
      change_absolute: null,
      change_relative_pct: null,
      aggregation: 'avg',
      status: 'pass' as const,
      score: 0,
      weight: m.weight,
      key_sli: m.key_sli,
      pass_targets: null,
      warning_targets: null,
    }))
  }

  export function MetricExplorerPage() {
    const [params] = useSearchParams()
    const groupName = params.get('group') ?? undefined
    const assetName = params.get('asset') ?? undefined
    const [metricGroupFilter, setMetricGroupFilter] = useState<string>('all')

    const { data: groupEvals = [] } = useEvaluations(
      groupName ? { group_name: groupName } : {},
    )
    const { data: assetEvals = [] } = useAssetEvaluations(assetName)

    // Pick the first asset's latest eval as the anchor for trend charts
    const evals = assetName ? assetEvals : groupEvals
    const latestEval = useMemo(() =>
      [...evals]
        .filter(e => !e.invalidated)
        .sort((a, b) => b.period_start.localeCompare(a.period_start))[0],
      [evals]
    )

    const allIndicators = useMemo(() => buildIndicatorStubs(), [])
    const metricGroups = Array.from(new Set(allIndicators.map(i => i.tab_group).filter(Boolean)))

    const visibleIndicators = metricGroupFilter === 'all'
      ? allIndicators
      : allIndicators.filter(i => i.tab_group === metricGroupFilter)

    const backHref = assetName
      ? `/navigator?asset=${encodeURIComponent(assetName)}`
      : groupName
      ? `/navigator?group=${encodeURIComponent(groupName)}`
      : '/navigator'

    return (
      <div className="p-6 space-y-4">
        <div className="flex items-center gap-3">
          <Link to={backHref} className="text-sm text-muted-foreground hover:text-foreground">
            ← Back
          </Link>
          <h1 className="text-xl font-semibold">Metric Explorer</h1>
          {(groupName || assetName) && (
            <span className="text-sm text-muted-foreground">
              — {assetName ?? groupName}
            </span>
          )}
        </div>

        {/* Metric group filter tabs */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setMetricGroupFilter('all')}
            className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
              metricGroupFilter === 'all' ? 'bg-muted text-foreground' : 'bg-background text-muted-foreground hover:text-foreground'
            }`}
          >
            All ({allIndicators.length})
          </button>
          {metricGroups.map(g => (
            <button
              key={g}
              onClick={() => setMetricGroupFilter(g!)}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                metricGroupFilter === g ? 'bg-muted text-foreground' : 'bg-background text-muted-foreground hover:text-foreground'
              }`}
            >
              {g} ({allIndicators.filter(i => i.tab_group === g).length})
            </button>
          ))}
        </div>

        {!latestEval && (
          <p className="text-sm text-muted-foreground">
            Select a group or asset from the Navigator to load metric trends.
          </p>
        )}

        {latestEval && (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {visibleIndicators.map(ind => (
              <MetricTrendBlock key={ind.metric} evalId={latestEval.id} indicator={ind} />
            ))}
          </div>
        )}
      </div>
    )
  }
  ```

- [ ] **Step 7.2: Build and verify**

  ```bash
  npm --prefix /mnt/d/DEV/keptn_rewrite/tropek/ui run build 2>&1 | tail -5
  ```

  In browser:
  - Click graph icon in GroupPanel → lands on `/explorer?group=X`, shows 30 metric charts
  - Click graph icon in AssetPanel → lands on `/explorer?asset=X`, shows metric charts for that asset
  - Metric group filter tabs narrow visible charts
  - "← Back" navigates back to correct Navigator selection

- [ ] **Step 7.3: Run all tests**

  ```bash
  npm --prefix /mnt/d/DEV/keptn_rewrite/tropek/ui test 2>&1 | tail -10
  ```
  Expected: all tests PASS.

- [ ] **Step 7.4: Commit**

  ```bash
  git -C /mnt/d/DEV/keptn_rewrite/tropek add ui/src/pages/MetricExplorerPage.tsx
  git -C /mnt/d/DEV/keptn_rewrite/tropek commit -m "feat(ui): add Metric Explorer full-screen page with metric group filter"
  ```

---

## Final Checklist

- [ ] "Navigator" appears as the first item in the top nav bar
- [ ] Navigator is the default landing page (`/` → `/navigator`)
- [ ] Tree shows groups → subgroups → assets; Performance Lab 1 has Linux/Windows subgroups
- [ ] Filter input narrows tree nodes
- [ ] Clicking group → group heatmap (rows=assets, cols=slots), click cell navigates to Evaluations
- [ ] Clicking group → chart mode shows stacked bar (absolute + normalized toggle)
- [ ] Clicking asset → metric heatmap (rows=metrics, cols=evaluations), click cell → EvaluationDetail
- [ ] Clicking asset → trend charts below heatmap; score table at bottom
- [ ] Graph icon in both panels → Metric Explorer with metric group filter tabs
- [ ] All existing tests pass: `npm test`
- [ ] Build succeeds: `npm run build`
