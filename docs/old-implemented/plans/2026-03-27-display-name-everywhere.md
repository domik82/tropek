# Display Name Everywhere Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show user-friendly `display_name` instead of raw `name` across all UI surfaces — backed by adding `display_name` to `asset_snapshot` in evaluations.

**Architecture:** Two-layer fix: (1) backend adds `display_name` to `TriggerContext` and `asset_snapshot` JSONB, (2) UI reads `display_name` from snapshot/API data everywhere names are shown. The `display_name ?? name` fallback pattern is already established in some places — we extend it everywhere.

**Tech Stack:** Python/FastAPI (backend), React/TypeScript (UI)

---

## File Map

### Backend changes
| Action | File | Purpose |
|--------|------|---------|
| Modify | `api/app/modules/quality_gate/trigger.py:25-39` | Add `asset_display_name` to `TriggerContext` |
| Modify | `api/app/modules/quality_gate/trigger.py:111-115` | Populate `asset_display_name` from DB |
| Modify | `api/app/modules/quality_gate/trigger_service.py:70-74` | Include `display_name` in snapshot dict |
| Modify | `api/app/modules/quality_gate/trigger_service.py:117-121` | Same for batch path |
| Modify | `api/app/modules/assets/schemas.py:125-130` | Add `asset_display_name` to `AssetGroupMemberRead` |
| Modify | `api/app/modules/assets/repository.py:269-282` | Join `Asset.display_name` in member query |
| Modify | `api/tests/engine/test_trigger.py` | Update mock Asset to include `display_name` |

### UI changes
| Action | File | Purpose |
|--------|------|---------|
| Modify | `ui/src/features/evaluations/types.ts:46-51` | Add `display_name` to `asset_snapshot` type |
| Modify | `ui/src/features/evaluations/components/EvaluationTable.tsx:55-68` | Show display_name in asset column |
| Modify | `ui/src/features/evaluations/components/EvaluationHeatmap.tsx:29-81` | Use display_name for heatmap row labels |
| Modify | `ui/src/features/evaluations/components/EvaluationSummaryCard.tsx:28` | Show display_name in Asset: label |
| Modify | `ui/src/features/navigator/components/AssetPanel.tsx:103,110` | Show display_name in header |
| Modify | `ui/src/features/navigator/components/GroupPanel.tsx:16-18,36` | Use group display_name from API instead of prettyGroupName |
| Modify | `ui/src/features/navigator/components/GroupScoreChart.tsx:21,25-26` | Use display_name in chart legend |
| Modify | `ui/src/features/navigator/components/AllEvaluationsPanel.tsx:64` | Use display_name for eval click |
| Modify | `ui/src/features/registry/details/DatasourceDetailView.tsx:139` | Show SLI display_name in "Used by" list |
| Modify | `ui/src/features/assets/types.ts:21-25` | Add `asset_display_name` to `AssetGroupMember` |
| Modify | `ui/src/components/AssetTree/AssetTreeNode.tsx:261-262` | Show asset display_name in tree leaves |
| Modify | `ui/src/features/evaluations/components/EvaluationIndicatorSection.tsx:67` | Show display_name in trend description |
| Modify | `ui/src/features/navigator/utils.ts:7-44` | Use display_name for group heatmap row labels |

---

### Task 1: Add `display_name` to TriggerContext and asset_snapshot (backend)

**Files:**
- Modify: `api/app/modules/quality_gate/trigger.py:25-39,111-124`
- Modify: `api/app/modules/quality_gate/trigger_service.py:70-74,117-121`
- Test: `api/tests/engine/test_trigger.py`

- [ ] **Step 1: Update test mock to include `display_name`**

In `api/tests/engine/test_trigger.py`, update the mock Asset fixture (line ~21-29) to include `display_name`:

```python
asset_repo.get_by_name.return_value = type(
    "Asset",
    (),
    {
        "id": uuid.uuid4(),
        "name": "vm-01",
        "display_name": "Production VM 01",
        "tags": {"os": "linux"},
    },
)()
```

Add a new test at the end of the file:

```python
async def test_trigger_context_includes_display_name(mock_repos):
    ctx = await resolve_single_trigger(
        asset_name="vm-01",
        slo_name="perf-slo",
        **mock_repos,
    )
    assert ctx.asset_display_name == "Production VM 01"
```

- [ ] **Step 2: Run tests to verify the new test fails**

Run: `./scripts/api-test.sh --tail 10 tests/engine/test_trigger.py -v`
Expected: FAIL — `TriggerContext` has no `asset_display_name`

- [ ] **Step 3: Add `asset_display_name` to TriggerContext**

In `api/app/modules/quality_gate/trigger.py`, add to the `TriggerContext` dataclass after `asset_name`:

```python
asset_display_name: str | None
```

And in `resolve_single_trigger` return (line ~111-124), add:

```python
asset_display_name=getattr(asset, "display_name", None),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/api-test.sh --tail 10 tests/engine/test_trigger.py -v`
Expected: PASS

- [ ] **Step 5: Add `display_name` to snapshot dict in trigger_service.py**

In `api/app/modules/quality_gate/trigger_service.py`, update both `asset_snapshot` dicts.

Single trigger (line ~70):
```python
asset_snapshot={
    "name": ctx.asset_name,
    "display_name": ctx.asset_display_name,
    "tags": ctx.asset_tags,
    "variables": ctx.asset_variables,
},
```

Batch trigger (line ~117) — same change:
```python
asset_snapshot={
    "name": ctx.asset_name,
    "display_name": ctx.asset_display_name,
    "tags": ctx.asset_tags,
    "variables": ctx.asset_variables,
},
```

- [ ] **Step 6: Run full unit test suite**

Run: `./scripts/api-test.sh --tail 10`
Expected: All PASS

- [ ] **Step 7: Commit**

```
feat(api): include display_name in asset_snapshot for evaluations

TriggerContext now carries asset_display_name, written into the
evaluation's asset_snapshot JSONB so the UI can show user-friendly
names for historical evaluations.
```

---

### Task 2: Add `asset_display_name` to AssetGroupMemberRead (backend)

**Files:**
- Modify: `api/app/modules/assets/schemas.py:125-130`
- Modify: `api/app/modules/assets/repository.py:269-282`

- [ ] **Step 1: Add field to schema**

In `api/app/modules/assets/schemas.py`, update `AssetGroupMemberRead`:

```python
class AssetGroupMemberRead(BaseModel):
    """Read schema for a group member entry."""

    asset_id: uuid.UUID
    asset_name: str
    asset_display_name: str | None = None
    weight: float
```

- [ ] **Step 2: Update repository query to join display_name**

In `api/app/modules/assets/repository.py`, update `_build_read` (line ~269-282):

```python
# Members: join with assets to get asset_name + display_name
member_rows = await self._session.execute(
    select(
        AssetGroupMember,
        Asset.name.label("asset_name"),
        Asset.display_name.label("asset_display_name"),
    )
    .join(Asset, AssetGroupMember.asset_id == Asset.id)
    .where(AssetGroupMember.group_id == group.id)
)
members = [
    AssetGroupMemberRead(
        asset_id=row.AssetGroupMember.asset_id,
        asset_name=row.asset_name,
        asset_display_name=row.asset_display_name,
        weight=row.AssetGroupMember.weight,
    )
    for row in member_rows
]
```

- [ ] **Step 3: Run tests**

Run: `./scripts/api-test.sh --tail 10`
Expected: All PASS

- [ ] **Step 4: Commit**

```
feat(api): expose asset display_name in group member read schema
```

---

### Task 3: Update UI evaluation types

**Files:**
- Modify: `ui/src/features/evaluations/types.ts:46-51`
- Modify: `ui/src/features/assets/types.ts:21-25`

- [ ] **Step 1: Add `display_name` to asset_snapshot in EvaluationSummary**

In `ui/src/features/evaluations/types.ts`, update the `asset_snapshot` type (line ~46-51):

```typescript
asset_snapshot: {
  name: string
  display_name?: string | null
  tags: Record<string, string>
  primary_version?: string
  build_ref?: string
}
```

- [ ] **Step 2: Add `asset_display_name` to AssetGroupMember**

In `ui/src/features/assets/types.ts`, update `AssetGroupMember` (line ~21-25):

```typescript
export interface AssetGroupMember {
  asset_id: string
  asset_name: string
  asset_display_name?: string | null
  weight: number
}
```

- [ ] **Step 3: Run type check**

Run: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json`
Expected: No errors (new fields are optional)

- [ ] **Step 4: Commit**

```
feat(ui): add display_name to evaluation and member type definitions
```

---

### Task 4: Fix EvaluationTable asset column

**Files:**
- Modify: `ui/src/features/evaluations/components/EvaluationTable.tsx:55-68`

- [ ] **Step 1: Update the `cell` function's `'asset'` case**

In `EvaluationTable.tsx`, replace the `case 'asset'` block (line ~55-68):

```typescript
case 'asset': {
  const assetLabel = ev.asset_snapshot.display_name ?? ev.asset_snapshot.name
  return (
    <td key="asset" className="px-4 py-3 text-sm">
      {onAssetSelect ? (
        <button
          onClick={() => onAssetSelect(ev.asset_snapshot.name)}
          className="text-slate-200 hover:text-indigo-300 hover:underline decoration-dotted underline-offset-2 cursor-pointer transition-colors"
        >
          {assetLabel}
        </button>
      ) : (
        <span className="text-slate-200">{assetLabel}</span>
      )}
      {ev.asset_snapshot.display_name && (
        <span className="block text-xs text-muted-foreground font-mono">{ev.asset_snapshot.name}</span>
      )}
    </td>
  )
}
```

Note: `onAssetSelect` still passes `ev.asset_snapshot.name` (the identifier), not display_name.

- [ ] **Step 2: Commit**

```
feat(ui): show asset display_name in evaluation table
```

---

### Task 5: Fix EvaluationHeatmap row labels

**Files:**
- Modify: `ui/src/features/evaluations/components/EvaluationHeatmap.tsx:29-81`

- [ ] **Step 1: Update `buildData` to use display names for row labels**

In `EvaluationHeatmap.tsx`, the key insight: `cellMap` and `evalNameMap` are keyed by raw `asset_snapshot.name`.
The `rows` array (shown as Y-axis labels) should use display names, but internal lookups must still use raw names.
We keep a parallel `assetNames` array for internal keying.

Update `buildData`:

After line ~30 (`function buildData`), replace lines 31-33:
```typescript
const slots = Array.from(new Set(evals.map(e => e.period_start))).sort()
// Internal keys: raw asset names. Display: display_name ?? name.
const displayNameMap = new Map<string, string>()
for (const e of evals) {
  if (e.asset_snapshot.display_name && !displayNameMap.has(e.asset_snapshot.name)) {
    displayNameMap.set(e.asset_snapshot.name, e.asset_snapshot.display_name)
  }
}
const assetNames = Array.from(new Set(evals.map(e => e.asset_snapshot.name))).sort()
const rows = assetNames.map(n => displayNameMap.get(n) ?? n)
```

Keep the cellMap construction (lines ~35-58) unchanged — it still keys by `${e.asset_snapshot.name}::${e.period_start}`.

Replace the cell building loop (lines ~63-78) to use `assetNames[yi]` for cellMap/evalNameMap lookup but `rows[yi]` for display:
```typescript
const cells: HeatmapCell[] = []
const evalNameMap = new Map<string, string>()
for (let xi = 0; xi < slots.length; xi++) {
  for (let yi = 0; yi < assetNames.length; yi++) {
    const key = `${assetNames[yi]}::${slots[xi]}`
    const cell = cellMap.get(key)
    if (cell) evalNameMap.set(`${rows[yi]}::${slots[xi]}`, cell.evalName)
    cells.push({
      value: [xi, yi],
      result: cell?.result ?? 'none',
      score: cell ? Math.round(cell.score) : 0,
      slot: slots[xi],
      rowLabel: rows[yi],
      hasNote: cell?.hasNote ?? false,
      noteContent: cell?.noteContent ?? '',
    })
  }
}
```

Note: `evalNameMap` keys now use `rows[yi]` (display names) so tooltip lookups via `${cell.rowLabel}::${cell.slot}` work correctly.

Return `assetNames` alongside existing return values:
```typescript
return { slots, rows, cells, evalNameMap, assetNames }
```

In the component (line ~87):
```typescript
const { slots, rows, cells, evalNameMap, assetNames } = useMemo(() => buildData(evaluations), [evaluations])
```

Update `onCellClick` (line ~113-121) to resolve display label back to raw asset name:
```typescript
function onCellClick(cell: HeatmapCell) {
  if (cell.slot !== selectedDate) {
    onDateSelect(cell.slot)
  } else if (onAssetSelect) {
    const rowIdx = rows.indexOf(cell.rowLabel)
    const assetName = rowIdx >= 0 ? assetNames[rowIdx] : cell.rowLabel
    if (assetName.trim()) onAssetSelect(assetName)
  } else {
    onDateSelect(null)
  }
}
```

- [ ] **Step 2: Commit**

```
feat(ui): show asset display_name in evaluation heatmap rows
```

---

### Task 6: Fix EvaluationSummaryCard and AssetPanel metadata

**Files:**
- Modify: `ui/src/features/evaluations/components/EvaluationSummaryCard.tsx:28`
- Modify: `ui/src/features/navigator/components/AssetPanel.tsx:110`

- [ ] **Step 1: Update EvaluationSummaryCard**

In `EvaluationSummaryCard.tsx` line 28, change:
```typescript
<span>Asset: <span className="text-slate-200">{ev.asset_snapshot.display_name ?? ev.asset_snapshot.name}</span></span>
```

- [ ] **Step 2: Update AssetPanel**

In `AssetPanel.tsx` line 110, change:
```typescript
<span>Asset: <span className="text-slate-200">{ev.asset_snapshot.display_name ?? ev.asset_snapshot.name}</span></span>
```

- [ ] **Step 3: Commit**

```
feat(ui): show asset display_name in summary card and asset panel
```

---

### Task 7: Fix GroupPanel header — use group display_name

**Files:**
- Modify: `ui/src/features/navigator/components/GroupPanel.tsx:12-20,36`

- [ ] **Step 1: Replace prettyGroupName with real display_name lookup**

In `GroupPanel.tsx`, import `useAssetGroups` and resolve the display name from group data:

```typescript
import { useAssetGroups } from '@/features/assets/hooks'
```

Update the component:
```typescript
export function GroupPanel({ groupName, onSelectAsset }: Props) {
  const [mode, setMode] = useState<ViewMode>('heatmap')
  const [selectedDate, setSelectedDate] = useState<string | null>(null)

  const { data: tree } = useAssetGroups()
  const group = tree?.all_groups.find(g => g.name === groupName)
  const groupLabel = group?.display_name ?? prettyGroupName(groupName)

  const { data: evals = [], isLoading } = useEvaluations({ group_name: groupName })
```

Then update line 36:
```typescript
<EvaluationHeader
  title={groupLabel}
  subtitle={evals.length > 0 ? `${evals.length} evaluations` : undefined}
/>
```

Keep `prettyGroupName` as the fallback when group data hasn't loaded yet.

- [ ] **Step 2: Commit**

```
feat(ui): show group display_name in navigator GroupPanel header
```

---

### Task 8: Fix GroupScoreChart legend

**Files:**
- Modify: `ui/src/features/navigator/components/GroupScoreChart.tsx:21,25-26,59`

- [ ] **Step 1: Build display name map and use it in series names**

In `GroupScoreChart.tsx`, build a lookup:

```typescript
// Build display name lookup from evaluations
const displayNameMap = useMemo(() => {
  const map = new Map<string, string>()
  for (const e of evaluations) {
    if (e.asset_snapshot.display_name && !map.has(e.asset_snapshot.name)) {
      map.set(e.asset_snapshot.name, e.asset_snapshot.display_name)
    }
  }
  return map
}, [evaluations])
```

Update line 21:
```typescript
const assetNames = Array.from(new Set(evaluations.map(e => e.asset_snapshot.name))).sort()
```
(keep this — internal keys stay as `name`)

Update the series map (line 25-26):
```typescript
const series = assetNames.map(assetName => ({
  name: displayNameMap.get(assetName) ?? assetName,
```

And the tooltip data match (line 30):
```typescript
const ap = slotRow.assets.find(a => a.assetName === assetName)
```
(keep as-is — `slotRow.assets` uses internal name)

- [ ] **Step 2: Commit**

```
feat(ui): show asset display_name in group score chart legend
```

---

### Task 9: Fix DatasourceDetailView SLI list

**Files:**
- Modify: `ui/src/features/registry/details/DatasourceDetailView.tsx:139`

- [ ] **Step 1: Show display_name in SLI list items**

In `DatasourceDetailView.tsx` line 139, change:
```typescript
{sli.display_name ?? sli.name}
```

- [ ] **Step 2: Commit**

```
feat(ui): show SLI display_name in datasource detail view
```

---

### Task 10: Fix AssetTree leaf nodes

**Files:**
- Modify: `ui/src/components/AssetTree/AssetTreeNode.tsx:261-262`

- [ ] **Step 1: Show display_name for asset leaves in tree**

In `AssetTreeNode.tsx`, update the asset leaf rendering (line ~261-262):

```typescript
<span className="font-mono text-[13px] text-muted-foreground truncate py-1 flex-1">
  {m.asset_display_name ?? m.asset_name}
</span>
```

Also update the aria-label (line ~266):
```typescript
aria-label={`Actions for ${m.asset_display_name ?? m.asset_name}`}
```

And the filter matching (line ~35):
```typescript
if (group.members.some(m =>
  m.asset_name.toLowerCase().includes(q) ||
  (m.asset_display_name?.toLowerCase().includes(q) ?? false)
)) return true
```

Also update the secondary member filter (line ~64) to also match display names:
```typescript
const filteredMembers = (mode === 'navigator' || mode === 'assets')
  ? (filter
      ? group.members.filter(m =>
          m.asset_name.toLowerCase().includes(filter.toLowerCase()) ||
          (m.asset_display_name?.toLowerCase().includes(filter.toLowerCase()) ?? false)
        )
      : group.members)
  : []
```

- [ ] **Step 2: Commit**

```
feat(ui): show asset display_name in sidebar tree leaves
```

---

### Task 11: Fix EvaluationIndicatorSection trend description

**Files:**
- Modify: `ui/src/features/evaluations/components/EvaluationIndicatorSection.tsx:67`

- [ ] **Step 1: Use display_name in trend description text**

In `EvaluationIndicatorSection.tsx` line 67, change:
```typescript
metrics on <strong className="text-slate-300">{ev.asset_snapshot.display_name ?? ev.asset_snapshot.name}</strong>.
```

- [ ] **Step 2: Commit**

```
feat(ui): show asset display_name in indicator trend description
```

---

### Task 12: Fix navigator/utils.ts shared heatmap builder

**Files:**
- Modify: `ui/src/features/navigator/utils.ts:7-44`

- [ ] **Step 1: Update `buildGroupHeatmapData` to use display names for rows**

In `utils.ts`, update the function to build display-name-aware row labels while keeping internal keying by raw name:

```typescript
export function buildGroupHeatmapData(evals: EvaluationSummary[]): GroupHeatmapData {
  const slots = Array.from(new Set(evals.map(e => e.period_start))).sort()
  const assetNames = Array.from(new Set(evals.map(e => e.asset_snapshot.name))).sort()

  // Build display name lookup
  const displayNameMap = new Map<string, string>()
  for (const e of evals) {
    if (e.asset_snapshot.display_name && !displayNameMap.has(e.asset_snapshot.name)) {
      displayNameMap.set(e.asset_snapshot.name, e.asset_snapshot.display_name)
    }
  }
  const rows = assetNames.map(n => displayNameMap.get(n) ?? n)

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
    for (let yi = 0; yi < assetNames.length; yi++) {
      const key = `${assetNames[yi]}::${slots[xi]}`
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
```

- [ ] **Step 2: Run UI tests to verify utils.test.ts still passes**

Run: `./scripts/ui-test.sh --tail 10 src/features/navigator/utils.test.ts`
Expected: PASS (existing tests use raw names which have no display_name, so `rows` will equal `assetNames`)

- [ ] **Step 3: Commit**

```
feat(ui): show asset display_name in group heatmap row labels
```

---

### Task 13: Run full test suites and verify

- [ ] **Step 1: Run API tests**

Run: `./scripts/api-test.sh --tail 10`
Expected: All PASS

- [ ] **Step 2: Run UI type check**

Run: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json`
Expected: No errors

- [ ] **Step 3: Run UI tests**

Run: `./scripts/ui-test.sh --tail 15`
Expected: All PASS

- [ ] **Step 4: Run lint**

Run: `./scripts/api-test.sh --tail 5` (ruff) and `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json`

- [ ] **Step 5: Final commit (if any fixes needed)**

```
fix: address test/type/lint issues from display_name rollout
```
