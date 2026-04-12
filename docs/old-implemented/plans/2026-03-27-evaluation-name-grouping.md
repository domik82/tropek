# Evaluation Name Grouping & Filtering — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix heatmap cell collisions caused by evaluation_name being ignored, add a multi-select evaluation name filter to all navigator panels, and make evaluation names visible in tooltips.

**Architecture:** Backend gets one new field on `HeatmapCell` schema + one new endpoint for distinct evaluation names. UI gets the `EvaluationNameFilter` component wired into all three navigator panels, with cell keying fixed in all three build functions. Seed script gets realistic evaluation names.

**Tech Stack:** Python/FastAPI (backend), React/TypeScript (UI), SQLAlchemy (queries), React Query (caching), Vitest (tests), pytest (backend tests)

**Spec:** `docs/superpowers/specs/2026-03-27-evaluation-name-grouping-design.md`

---

## File Map

### Backend (create/modify)

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `api/app/modules/quality_gate/schemas.py` | Add `evaluation_name` to `HeatmapCell` |
| Modify | `api/app/modules/quality_gate/router.py` | Populate new field + new `/evaluations/names` endpoint |
| Modify | `api/app/modules/quality_gate/repository.py` | New `list_evaluation_names()` method |
| Create | `api/tests/db/test_evaluation_names.py` | Integration tests for the new endpoint |

### UI — Types & API (modify)

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `ui/src/features/evaluations/types.ts` | Add `evaluation_name` to `EvaluationFilters` |
| Modify | `ui/src/features/navigator/types.ts` | Add `evaluation_name` to `MetricHeatmapCell`, `HeatmapCell` |
| Modify | `ui/src/lib/queryKeys.ts` | Add `evaluation_name` to `EvalFilters`, update `heatmap` key |
| Modify | `ui/src/features/evaluations/api.ts` | Wire `evaluation_name` through `toParams`, `fetchMetricHeatmap`, new `fetchEvaluationNames` |
| Modify | `ui/src/features/navigator/hooks.ts` | Accept `evaluationNames` in hooks, add `useEvaluationNames` |
| Modify | `ui/src/features/evaluations/hooks.ts` | Pass `evaluation_name` through `useEvaluations` |

### UI — Cell keying fix (modify)

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `ui/src/features/navigator/utils.ts` | Fix `buildAssetHeatmapData` + `buildGroupHeatmapData` cell keys |
| Modify | `ui/src/features/evaluations/components/EvaluationHeatmap.tsx` | Fix `buildData` cell keys |

### UI — Filter component (create/modify)

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `ui/src/features/navigator/components/EvaluationNameFilter.tsx` | Multi-select chip filter |
| Create | `ui/src/features/navigator/components/EvaluationNameFilter.test.tsx` | Component tests |
| Modify | `ui/src/features/navigator/components/AssetPanel.tsx` | Wire filter into asset panel |
| Modify | `ui/src/features/navigator/components/GroupPanel.tsx` | Wire filter into group panel |
| Modify | `ui/src/features/navigator/components/AllEvaluationsPanel.tsx` | Wire filter into all-evals panel |

### UI — Tooltip (modify)

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `ui/src/features/navigator/components/AssetHeatmap.tsx` | Show `evaluation_name` in tooltip |

### Bug fix — Table row click (modify)

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `ui/src/pages/AssetNavigatorPage.tsx` | Pass `evalId` through `onSelectAsset` to URL params |

### Seed data (modify)

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `scripts/seed_evaluations.py` | Replace `seed-N` with realistic recurring evaluation names |

---

## Task 1: Backend — Add `evaluation_name` to HeatmapCell schema

**Files:**
- Modify: `api/app/modules/quality_gate/schemas.py:171-179`
- Modify: `api/app/modules/quality_gate/router.py:152-165`

- [ ] **Step 1: Add `evaluation_name` field to `HeatmapCell` schema**

In `api/app/modules/quality_gate/schemas.py`, add the field to `HeatmapCell`:

```python
class HeatmapCell(BaseModel):
    """A single cell in the metric heatmap grid."""

    slot: datetime
    metric: str
    display_name: str
    result: str
    score: float
    eval_id: uuid.UUID
    evaluation_name: str
```

- [ ] **Step 2: Populate `evaluation_name` in the router**

In `api/app/modules/quality_gate/router.py`, in the `get_metric_heatmap` function's cell construction loop (~line 152), add the field:

```python
cells.append(
    HeatmapCell(
        slot=ev.period_start,
        metric=metric_name,
        display_name=display,
        result=(
            "invalidated"
            if ev.invalidated
            else (ev.result or row.status)
            if ev.original_result is not None
            else row.status
        ),
        score=row.score,
        eval_id=ev.id,
        evaluation_name=ev.evaluation_name,
    )
)
```

- [ ] **Step 3: Run existing tests to verify no breakage**

Run: `./scripts/api-test.sh --tail 5`
Expected: All existing tests pass.

- [ ] **Step 4: Commit**

```
feat(api): add evaluation_name to metric-heatmap cell response
```

---

## Task 2: Backend — New `/evaluations/names` endpoint

**Files:**
- Modify: `api/app/modules/quality_gate/repository.py`
- Modify: `api/app/modules/quality_gate/schemas.py`
- Modify: `api/app/modules/quality_gate/router.py`
- Create: `api/tests/db/test_evaluation_names.py`

- [ ] **Step 1: Write integration test for the new endpoint**

Create `api/tests/db/test_evaluation_names.py`:

```python
"""Integration tests for GET /evaluations/names endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture()
async def async_client():
    """HTTP client wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_evaluation_names_returns_distinct_names(
    async_client: AsyncClient,
) -> None:
    """Endpoint returns distinct names with count and last_run, sorted by last_run DESC."""
    resp = await async_client.get("/evaluations/names")
    assert resp.status_code == 200
    names = resp.json()
    assert isinstance(names, list)
    # May be empty if no seeded data — just check structure
    for entry in names:
        assert "name" in entry
        assert "count" in entry
        assert "last_run" in entry
        assert entry["count"] > 0
    # Sorted by last_run descending
    runs = [e["last_run"] for e in names]
    assert runs == sorted(runs, reverse=True)


async def test_evaluation_names_empty_when_no_evals(
    async_client: AsyncClient,
) -> None:
    """Returns empty list when no evaluations match."""
    resp = await async_client.get(
        "/evaluations/names", params={"asset_name": "nonexistent-asset"},
    )
    assert resp.status_code == 200
    assert resp.json() == []
```

Note: Follow the `async_client` fixture pattern from `api/tests/db/test_slo_repository.py`.
If tests need seeded evaluation data, create it inline using the API's trigger endpoint or
direct DB insertion in a fixture — there is no shared `seeded_evaluations` fixture.

- [ ] **Step 2: Run test to verify it fails**

Run: `./scripts/api-test.sh --tail 20 tests/db/test_evaluation_names.py -v`
Expected: FAIL — endpoint does not exist yet.

- [ ] **Step 3: Add schema for the response**

In `api/app/modules/quality_gate/schemas.py`, add after the `MetricHeatmapResponse` class:

```python
class EvaluationNameEntry(BaseModel):
    """A distinct evaluation name with usage stats."""

    name: str
    count: int
    last_run: datetime
```

- [ ] **Step 4: Add repository method**

In `api/app/modules/quality_gate/repository.py`, add to the `EvaluationRepository` class:

```python
async def list_evaluation_names(
    self,
    *,
    asset_id: uuid.UUID | None = None,
    asset_ids: list[uuid.UUID] | None = None,
) -> list[tuple[str, int, datetime]]:
    """Return distinct evaluation names with count and last run timestamp.

    Returns tuples of (name, count, last_run) sorted by last_run DESC.
    """
    stmt = (
        select(
            Evaluation.evaluation_name,
            func.count().label("cnt"),
            func.max(Evaluation.period_start).label("last_run"),
        )
        .where(Evaluation.status == EvaluationStatus.COMPLETED)
        .group_by(Evaluation.evaluation_name)
        .order_by(func.max(Evaluation.period_start).desc())
    )
    if asset_id is not None:
        stmt = stmt.where(Evaluation.asset_id == asset_id)
    if asset_ids is not None:
        stmt = stmt.where(Evaluation.asset_id.in_(asset_ids))
    rows = (await self._session.execute(stmt)).all()
    return [(r.evaluation_name, r.cnt, r.last_run) for r in rows]
```

`func` is already imported in this file — no import change needed.

- [ ] **Step 5: Add router endpoint**

In `api/app/modules/quality_gate/router.py`, add **before** the `GET /evaluations/{eval_id}` route (to avoid path parameter matching "names" as an eval ID):

```python
@router.get("/evaluations/names", response_model=list[EvaluationNameEntry])
async def list_evaluation_names(
    asset_name: str | None = None,
    group_name: str | None = None,
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> list[EvaluationNameEntry]:
    """Return distinct evaluation names with count and last-run date."""
    resolved_asset_id = None
    asset_ids = None
    if asset_name:
        asset = await repos.asset_repo.get_by_name(asset_name)
        if asset is None:
            return []
        resolved_asset_id = asset.id
    if group_name:
        group = await repos.asset_group_repo.get_by_name(group_name)
        if group:
            asset_ids = [m.asset_id for m in (group.members or [])]
        else:
            return []
    rows = await repos.eval_repo.list_evaluation_names(
        asset_id=resolved_asset_id, asset_ids=asset_ids,
    )
    return [
        EvaluationNameEntry(name=name, count=count, last_run=last_run)
        for name, count, last_run in rows
    ]
```

Add `EvaluationNameEntry` to the schema imports at the top of the router file.

- [ ] **Step 6: Run integration tests**

Run: `./scripts/api-test.sh --tail 20 tests/db/test_evaluation_names.py -v`
Expected: Tests pass. The `async_client` fixture follows the pattern from `test_slo_repository.py`.

- [ ] **Step 7: Run all API tests**

Run: `./scripts/api-test.sh --tail 5`
Expected: All tests pass.

- [ ] **Step 8: Commit**

```
feat(api): add GET /evaluations/names endpoint for distinct evaluation names
```

---

## Task 3: Bug fix — Table row click loses evalId

**Files:**
- Modify: `ui/src/pages/AssetNavigatorPage.tsx:34`
- Modify: `ui/src/features/navigator/components/GroupPanel.tsx:14`

The root cause: `AssetNavigatorPage.tsx` line 34 calls `onSelectAsset={(name: string) => handleSelectAsset(name)}` which **drops the `evalId`** parameter from `GroupPanel.onSelectAsset`. The `handleSelectAsset` function only receives the asset name.

Similarly, line 37 for `AllEvaluationsPanel` has the same issue.

- [ ] **Step 1: Fix `AssetNavigatorPage` to pass evalId through**

In `ui/src/pages/AssetNavigatorPage.tsx`, keep `handleSelectAsset` for the tree (which passes `groupName`), but use inline callbacks for the panels (which pass `evalId`). Replace lines 33-38:

```typescript
{!selectedAsset && selectedGroup && (
  <GroupPanel
    groupName={selectedGroup}
    onSelectAsset={(name: string, evalId?: string) => {
      const next: Record<string, string> = { asset: name }
      if (selectedGroup) next.group = selectedGroup
      if (evalId) next.eval = evalId
      setParams(next)
    }}
  />
)}
{!selectedAsset && !selectedGroup && (
  <AllEvaluationsPanel
    onSelectAsset={(name: string, evalId?: string) => {
      const next: Record<string, string> = { asset: name }
      if (evalId) next.eval = evalId
      setParams(next)
    }}
  />
)}
```

Keep the `handleSelectAsset` for the tree (which passes groupName), and use inline callbacks for the panels (which pass evalId).

- [ ] **Step 2: Update AllEvaluationsPanel to pass evalId**

In `ui/src/features/navigator/components/AllEvaluationsPanel.tsx`, update the `Props` interface to accept evalId:

```typescript
interface Props {
  onSelectAsset: (name: string, evalId?: string) => void
}
```

The `EvaluationTable` already passes `assetDisplayNames` and `sloDisplayNames` — only fix
the `onEvalClick` callback to forward `evalId`:

```typescript
onEvalClick={ev => onSelectAsset(ev.asset_snapshot.name, ev.id)}
```

This is already correct in the current code (line 83). No change needed to `EvaluationTable` props — the fix is entirely in `AssetNavigatorPage.tsx` (Step 1) and the `Props` interface (above).

- [ ] **Step 3: Run UI tests**

Run: `./scripts/ui-test.sh --tail 10`
Expected: All pass.

- [ ] **Step 4: Commit**

```
fix(ui): pass evalId through table row click to asset panel
```

---

## Task 4: UI types — Extend filters and cell types

**Files:**
- Modify: `ui/src/features/evaluations/types.ts:99-105`
- Modify: `ui/src/features/navigator/types.ts:4-13,40-47`
- Modify: `ui/src/lib/queryKeys.ts:9-15,22`

- [ ] **Step 1: Add `evaluation_name` to `EvaluationFilters`**

In `ui/src/features/evaluations/types.ts`, update `EvaluationFilters`:

```typescript
export interface EvaluationFilters {
  group_name?: string
  asset_name?: string
  evaluation_name?: string[]
  date?: string
  from?: string
  to?: string
}
```

- [ ] **Step 2: Add `evaluation_name` to heatmap cell types**

In `ui/src/features/navigator/types.ts`, add to `HeatmapCell`:

```typescript
export interface HeatmapCell {
  value: [number, number]
  result: string
  score: number
  slot: string
  rowLabel: string
  evalId?: string
  evaluation_name?: string    // <-- new
  hasNote?: boolean
  noteContent?: string
}
```

Add to `MetricHeatmapCell`:

```typescript
export interface MetricHeatmapCell {
  slot: string
  metric: string
  display_name: string
  result: string
  score: number
  eval_id: string
  evaluation_name: string     // <-- new
}
```

- [ ] **Step 3: Update query keys**

In `ui/src/lib/queryKeys.ts`, update `EvalFilters`:

```typescript
type EvalFilters = {
  group_name?: string
  asset_name?: string
  evaluation_name?: string[]
  date?: string
  from?: string
  to?: string
}
```

Update `evaluationKeys.heatmap` — the current signature is
`(assetName: string, filters?: Record<string, string | undefined>)` (added by time-range feature).
Extend it to also include `evalNames`:

```typescript
heatmap: (assetName: string, filters?: Record<string, string | undefined>, evalNames?: string[]) =>
  evalNames?.length
    ? ['metric-heatmap', assetName, filters, evalNames] as const
    : ['metric-heatmap', assetName, filters] as const,
```

Add `names` key:

```typescript
names: (scope: { asset_name?: string; group_name?: string }) =>
  ['evaluation-names', scope] as const,
```

- [ ] **Step 4: Commit**

```
feat(ui): add evaluation_name to filter types, cell types, and query keys
```

---

## Task 5: UI API layer — Wire `evaluation_name` through fetch functions

**Files:**
- Modify: `ui/src/features/evaluations/api.ts`

- [ ] **Step 1: Update `toParams` to handle `evaluation_name`**

In `ui/src/features/evaluations/api.ts`, update `toParams`:

```typescript
function toParams(filters: EvaluationFilters): string {
  const p = new URLSearchParams()
  if (filters.group_name) p.set('group_name', filters.group_name)
  if (filters.asset_name) p.set('asset_name', filters.asset_name)
  if (filters.evaluation_name?.length) {
    for (const n of filters.evaluation_name) p.append('evaluation_name', n)
  }
  if (filters.date) p.set('date', filters.date)
  if (filters.from) p.set('from', filters.from)
  if (filters.to) p.set('to', filters.to)
  return p.toString()
}
```

- [ ] **Step 2: Update `fetchMetricHeatmap` to accept evaluation names**

The current signature (from time-range feature) is:
`fetchMetricHeatmap(assetName: string, filters?: { from?: string; to?: string })`.
Extend the `filters` type to include `evaluation_name`:

```typescript
export async function fetchMetricHeatmap(
  assetName: string,
  filters?: { from?: string; to?: string; evaluation_name?: string[] },
): Promise<MetricHeatmapResponse> {
  const params = new URLSearchParams({ asset_name: assetName })
  if (filters?.from) params.set('from', filters.from)
  if (filters?.to) params.set('to', filters.to)
  if (filters?.evaluation_name?.length) {
    for (const n of filters.evaluation_name) params.append('evaluation_name', n)
  }
  const res = await fetch(`${BASE}/evaluations/metric-heatmap?${params}`)
  if (!res.ok) throw new Error(`fetchMetricHeatmap: ${res.status}`)
  return res.json()
}
```

- [ ] **Step 3: Add `fetchEvaluationNames` function**

```typescript
export interface EvaluationNameEntry {
  name: string
  count: number
  last_run: string
}

export async function fetchEvaluationNames(
  params: { asset_name?: string; group_name?: string },
): Promise<EvaluationNameEntry[]> {
  const p = new URLSearchParams()
  if (params.asset_name) p.set('asset_name', params.asset_name)
  if (params.group_name) p.set('group_name', params.group_name)
  const qs = p.toString()
  const res = await fetch(`${BASE}/evaluations/names${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error(`fetchEvaluationNames: ${res.status}`)
  return res.json()
}
```

- [ ] **Step 4: Commit**

```
feat(ui): wire evaluation_name through API fetch functions
```

---

## Task 6: UI hooks — Accept evaluation names, add useEvaluationNames

**Files:**
- Modify: `ui/src/features/navigator/hooks.ts`
- Modify: `ui/src/features/evaluations/hooks.ts`

- [ ] **Step 1: Update navigator hooks**

The current file uses `useTimeRange()` context (from time-range feature). Do NOT replace
the file — modify the existing hooks and add the new one.

In `ui/src/features/navigator/hooks.ts`:

1. Add `fetchEvaluationNames` to the import from `@/features/evaluations/api`.

2. Update `useAssetEvaluations` to accept `evaluationNames`:

```typescript
export function useAssetEvaluations(assetName: string | undefined, evaluationNames?: string[]) {
  const { from, to } = useTimeRange()
  const filters = {
    asset_name: assetName,
    evaluation_name: evaluationNames,
    from,
    ...(to ? { to } : {}),
  }
  return useQuery({
    queryKey: evaluationKeys.list(filters),
    queryFn: () => fetchEvaluations(filters),
    enabled: !!assetName,
  })
}
```

3. Update `useMetricHeatmap` to accept `evaluationNames`:

```typescript
export function useMetricHeatmap(assetName: string | undefined, evaluationNames?: string[]) {
  const { from, to } = useTimeRange()
  const timeFilters = { from, ...(to ? { to } : {}), evaluation_name: evaluationNames }
  return useQuery({
    queryKey: evaluationKeys.heatmap(assetName!, timeFilters, evaluationNames),
    queryFn: () => fetchMetricHeatmap(assetName!, timeFilters),
    enabled: !!assetName,
  })
}
```

4. Add the new hook at the end of the file:

```typescript
export function useEvaluationNames(assetName?: string, groupName?: string) {
  return useQuery({
    queryKey: evaluationKeys.names({ asset_name: assetName, group_name: groupName }),
    queryFn: () => fetchEvaluationNames({ asset_name: assetName, group_name: groupName }),
    enabled: !!(assetName || groupName),
  })
}
```

- [ ] **Step 2: Verify no breakage in existing hooks**

The `useEvaluations` hook in `ui/src/features/evaluations/hooks.ts` already passes `EvaluationFilters` to `fetchEvaluations`. Since we updated `EvaluationFilters` to include `evaluation_name` and `toParams` to serialize it, this hook automatically gains filtering support. No code change needed in this file.

- [ ] **Step 3: Run UI tests**

Run: `./scripts/ui-test.sh --tail 10`
Expected: All pass.

- [ ] **Step 4: Commit**

```
feat(ui): add useEvaluationNames hook, wire evaluation_name through existing hooks
```

---

## Task 7: Fix cell keying in all three build functions

**Files:**
- Modify: `ui/src/features/navigator/utils.ts:7-53,76-103`
- Modify: `ui/src/features/evaluations/components/EvaluationHeatmap.tsx:29-89`

- [ ] **Step 1: Write test for `buildAssetHeatmapData` collision fix**

Create `ui/src/features/navigator/utils.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { buildAssetHeatmapData, buildGroupHeatmapData } from './utils'
import type { MetricHeatmapResponse } from './types'
import type { EvaluationSummary } from '@/features/evaluations/types'

describe('buildAssetHeatmapData', () => {
  it('creates separate cells for same metric+slot with different evaluation_name', () => {
    const resp: MetricHeatmapResponse = {
      asset_name: 'test-asset',
      slots: ['2026-03-15T00:00:00Z', '2026-03-15T00:00:00Z'],
      metrics: [{ name: 'latency_p95', display_name: 'Latency P95' }],
      cells: [
        { slot: '2026-03-15T00:00:00Z', metric: 'latency_p95', display_name: 'Latency P95', result: 'pass', score: 90, eval_id: 'eval-1', evaluation_name: 'load-test' },
        { slot: '2026-03-15T00:00:00Z', metric: 'latency_p95', display_name: 'Latency P95', result: 'fail', score: 40, eval_id: 'eval-2', evaluation_name: 'ad-hoc-run' },
      ],
    }
    const data = buildAssetHeatmapData(resp)
    // Both cells should exist — no overwrite
    const latencyCells = data.cells.filter(c => c.rowLabel === 'Latency P95' && c.result !== 'none')
    expect(latencyCells).toHaveLength(2)
    expect(latencyCells.map(c => c.evalId).sort()).toEqual(['eval-1', 'eval-2'])
  })

  it('stores evaluation_name on each cell', () => {
    const resp: MetricHeatmapResponse = {
      asset_name: 'test-asset',
      slots: ['2026-03-15T00:00:00Z'],
      metrics: [{ name: 'latency_p95', display_name: 'Latency P95' }],
      cells: [
        { slot: '2026-03-15T00:00:00Z', metric: 'latency_p95', display_name: 'Latency P95', result: 'pass', score: 90, eval_id: 'eval-1', evaluation_name: 'load-test' },
      ],
    }
    const data = buildAssetHeatmapData(resp)
    const cell = data.cells.find(c => c.result !== 'none')!
    expect(cell.evaluation_name).toBe('load-test')
  })
})

describe('buildGroupHeatmapData', () => {
  it('creates separate cells for same asset+slot with different evaluation_name', () => {
    const evals: EvaluationSummary[] = [
      makeSummary({ name: 'checkout-api', period_start: '2026-03-15T00:00:00Z', evaluation_name: 'load-test', result: 'pass', score: 90 }),
      makeSummary({ name: 'checkout-api', period_start: '2026-03-15T00:00:00Z', evaluation_name: 'ad-hoc-run', result: 'fail', score: 40 }),
    ]
    const data = buildGroupHeatmapData(evals)
    const checkoutCells = data.cells.filter(c => c.rowLabel === 'checkout-api' && c.result !== 'none')
    expect(checkoutCells).toHaveLength(2)
  })
})

function makeSummary(overrides: {
  name: string
  period_start: string
  evaluation_name: string
  result: string
  score: number
}): EvaluationSummary {
  return {
    id: `eval-${Math.random()}`,
    evaluation_name: overrides.evaluation_name,
    status: 'completed',
    result: overrides.result as 'pass' | 'warning' | 'fail' | 'error',
    score: overrides.score,
    period_start: overrides.period_start,
    period_end: '2026-03-15T00:30:00Z',
    slo_name: 'test-slo',
    slo_version: 1,
    sli_name: null,
    sli_version: null,
    data_source_name: null,
    ingestion_mode: 'adapter',
    adapter_used: 'mock',
    invalidated: false,
    original_result: null,
    original_score: null,
    override_reason: null,
    override_author: null,
    asset_snapshot: { name: overrides.name, tags: {} },
    evaluation_metadata: {},
    created_at: '2026-03-15T00:00:00Z',
  }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/ui-test.sh --tail 20 src/features/navigator/utils.test.ts`
Expected: FAIL — cells overwrite each other.

- [ ] **Step 3: Fix `buildAssetHeatmapData` in utils.ts**

The key change: include `evaluation_name` in the cell map key, and use `\0` as separator (safe — never appears in names or timestamps). Expand the column axis to treat each `(slot, evalName)` pair as a unique column.

```typescript
export function buildAssetHeatmapData(resp: MetricHeatmapResponse): AssetHeatmapData {
  const { metrics, cells } = resp

  // Build ordered unique columns. Each column is a (slot, evaluationName) pair.
  // In the common case (one eval name), this equals resp.slots.
  const colEntries: Array<{ slot: string; evalName: string }> = []
  const colKeySet = new Set<string>()
  for (const c of cells) {
    const ck = `${c.slot}\0${c.evaluation_name}`
    if (!colKeySet.has(ck)) {
      colKeySet.add(ck)
      colEntries.push({ slot: c.slot, evalName: c.evaluation_name })
    }
  }
  // Fallback for empty cells
  if (colEntries.length === 0) {
    for (const s of resp.slots) colEntries.push({ slot: s, evalName: '' })
  }

  const slots = colEntries.map(e => e.slot)
  const rows = metrics.map(m => m.display_name)

  // Cell map keyed by metric + slot + evalName
  const cellMap = new Map<string, MetricHeatmapResponse['cells'][0]>()
  for (const c of cells) {
    cellMap.set(`${c.metric}\0${c.slot}\0${c.evaluation_name}`, c)
  }

  const gridCells: HeatmapCell[] = []
  for (let xi = 0; xi < colEntries.length; xi++) {
    const col = colEntries[xi]
    for (let yi = 0; yi < metrics.length; yi++) {
      const key = `${metrics[yi].name}\0${col.slot}\0${col.evalName}`
      const c = cellMap.get(key)
      gridCells.push({
        value: [xi, yi],
        result: c?.result ?? 'none',
        score: c ? Math.round(c.score) : 0,
        slot: col.slot,
        rowLabel: metrics[yi].display_name,
        evalId: c?.eval_id,
        evaluation_name: c?.evaluation_name,
      })
    }
  }

  return { slots, rows, cells: gridCells }
}
```

- [ ] **Step 4: Fix `buildGroupHeatmapData` in utils.ts**

Change cell key to include `evaluation_name`:

Note: the current function signature is `buildGroupHeatmapData(evals, fallbackNames?)` —
preserve the `fallbackNames` parameter (added by the display-name feature).

```typescript
export function buildGroupHeatmapData(evals: EvaluationSummary[], fallbackNames?: Map<string, string>): GroupHeatmapData {
  const slots = Array.from(new Set(evals.map(e => e.period_start))).sort()
  const assetNames = Array.from(new Set(evals.map(e => e.asset_snapshot.name))).sort()

  // Build display name lookup: snapshot display_name → fallback map → raw name
  const displayNameMap = new Map<string, string>()
  for (const e of evals) {
    if (!displayNameMap.has(e.asset_snapshot.name)) {
      const dn = e.asset_snapshot.display_name ?? fallbackNames?.get(e.asset_snapshot.name)
      if (dn) displayNameMap.set(e.asset_snapshot.name, dn)
    }
  }
  const rows = assetNames.map(n => displayNameMap.get(n) ?? n)

  // Key by asset+slot+evalName to prevent cross-name merging
  const cellMap = new Map<string, { result: string; score: number; count: number; evalName: string }>()
  for (const e of evals) {
    const key = `${e.asset_snapshot.name}\0${e.period_start}\0${e.evaluation_name}`
    const effectiveResult = e.invalidated ? 'invalidated' : e.result
    const existing = cellMap.get(key)
    if (!existing) {
      cellMap.set(key, { result: effectiveResult, score: e.score, count: 1, evalName: e.evaluation_name })
    } else {
      cellMap.set(key, {
        result: (RESULT_RANK[effectiveResult] ?? 0) > (RESULT_RANK[existing.result] ?? 0)
          ? effectiveResult : existing.result,
        score: (existing.score * existing.count + e.score) / (existing.count + 1),
        count: existing.count + 1,
        evalName: existing.evalName,
      })
    }
  }

  const cells: HeatmapCell[] = []
  for (let xi = 0; xi < slots.length; xi++) {
    for (let yi = 0; yi < assetNames.length; yi++) {
      // Try all eval names for this asset+slot
      const matchingKeys = [...cellMap.keys()].filter(k =>
        k.startsWith(`${assetNames[yi]}\0${slots[xi]}\0`)
      )
      if (matchingKeys.length === 0) {
        cells.push({
          value: [xi, yi],
          result: 'none',
          score: 0,
          slot: slots[xi],
          rowLabel: rows[yi],
        })
      } else {
        for (const mk of matchingKeys) {
          const cell = cellMap.get(mk)!
          cells.push({
            value: [xi, yi],
            result: cell.result,
            score: Math.round(cell.score),
            slot: slots[xi],
            rowLabel: rows[yi],
            evaluation_name: cell.evalName,
          })
        }
      }
    }
  }

  return { slots, rows, cells }
}
```

Note: In the common case (one eval name per asset+slot), this produces identical output to the old code. When there are collisions, it produces multiple cells at the same grid position — the filter UI (Task 9) ensures users almost always view one name at a time, making visual collisions a non-issue.

- [ ] **Step 5: Write test for `buildData` in EvaluationHeatmap**

The `buildData` function is not exported, so test it indirectly by extracting it or testing
through the component. The simplest approach: extract `buildData` to a named export and test it
directly. If refactoring is too invasive, test via the component's rendered output.

Create `ui/src/features/evaluations/components/EvaluationHeatmap.test.tsx` (or add to the
existing utils test file if `buildData` is extracted to a shared location):

```typescript
import { describe, it, expect } from 'vitest'
// If buildData is extracted and exported:
// import { buildData } from './EvaluationHeatmap'
// Otherwise, test through component rendering with @testing-library/react
```

The test should verify: given two `EvaluationSummary` items with the same asset+slot but
different `evaluation_name`, the result contains two distinct cells (not merged).

- [ ] **Step 6: Fix `buildData` in EvaluationHeatmap.tsx**

The current `buildData` function (not exported, inside `EvaluationHeatmap.tsx`) uses a
`CellAccum` type with `{ result, score, count, hasNote, noteContent, evalName }` and
returns `{ slots, rows, cells, evalNameMap, assetNames }`. The tooltip already reads
`evalNameMap` — so we only need to fix the cell key to include `evaluation_name`.

**Change 1:** Update the cell map key (line ~50) from:
```typescript
const key = `${rowKey}::${e.period_start}`
```
to:
```typescript
const key = `${rowKey}\0${e.period_start}\0${e.evaluation_name}`
```

**Change 2:** Update the grid loop (line ~76) to look up the cell key with evalName. The
current code iterates `slots × assetNames` and builds a key `${assetNames[yi]}::${slots[xi]}`.
This needs to find all matching evalNames for that cell, similar to `buildGroupHeatmapData`.
The simplest approach: iterate `cellMap` entries grouped by `(asset, slot)`:

```typescript
// Step 3: produce one HeatmapCell per grid position + build evalName lookup for tooltip
const cells: HeatmapCell[] = []
const evalNameMap = new Map<string, string>()
for (let xi = 0; xi < slots.length; xi++) {
  for (let yi = 0; yi < assetNames.length; yi++) {
    // Find all cells for this asset+slot (across eval names)
    const matchingKeys = [...cellMap.keys()].filter(k =>
      k.startsWith(`${assetNames[yi]}\0${slots[xi]}\0`)
    )
    if (matchingKeys.length === 0) {
      cells.push({
        value: [xi, yi],
        result: 'none',
        score: 0,
        slot: slots[xi],
        rowLabel: rows[yi],
        hasNote: false,
        noteContent: '',
      })
    } else {
      for (const mk of matchingKeys) {
        const cell = cellMap.get(mk)!
        evalNameMap.set(`${rows[yi]}::${slots[xi]}`, cell.evalName)
        cells.push({
          value: [xi, yi],
          result: cell.result,
          score: Math.round(cell.score),
          slot: slots[xi],
          rowLabel: rows[yi],
          hasNote: cell.hasNote,
          noteContent: cell.noteContent,
          evaluation_name: cell.evalName,
        })
      }
    }
  }
}
```

**Change 3:** The tooltip lookup (line ~108) uses `evalNameMap.get(...)` with `::` separator.
Keep it as-is (it's set above with `::`) — OR use the cell's own `evaluation_name` field
directly for cleaner code:

```typescript
const evalName = cell.evaluation_name ?? evalNameMap.get(`${cell.rowLabel}::${cell.slot}`)
```

- [ ] **Step 7: Run tests**

Run: `./scripts/ui-test.sh --tail 20 src/features/navigator/utils.test.ts`
Expected: All pass.

- [ ] **Step 8: Run all UI tests**

Run: `./scripts/ui-test.sh --tail 10`
Expected: All pass.

- [ ] **Step 9: Commit**

```
fix(ui): include evaluation_name in heatmap cell keys to prevent collisions
```

---

## Task 8: UI — AssetHeatmap tooltip enhancement

**Files:**
- Modify: `ui/src/features/navigator/components/AssetHeatmap.tsx`

- [ ] **Step 1: Add `evaluation_name` to the tooltip**

In `AssetHeatmap.tsx`, the current `formatTooltip` is a plain function (line 30-43) that
returns an array of HTML strings joined by `<br/>`. Add `evaluation_name` as a line:

```typescript
function formatTooltip(cell: HeatmapCell): string {
  if (cell.result === 'none') {
    return `${cell.rowLabel}<br/>${fmtDateTime(cell.slot)}<br/><em>no data</em>`
  }
  const rc = colours[cell.result as keyof typeof colours] ?? '#ccc'
  return [
    cell.evaluation_name ? `<span style="color:#94a3b8">${cell.evaluation_name}</span>` : '',
    `<b>${cell.rowLabel}</b>`,
    fmtDateTime(cell.slot),
    `Score: <b style="color:${rc}">${cell.score}</b> · <b style="color:${rc}">${cell.result.toUpperCase()}</b>`,
    cell.evalId
      ? `<span style="color:#888;font-size:10px">Click to select this evaluation</span>`
      : '',
  ].filter(Boolean).join('<br/>')
}
```

The `evaluation_name` field is now available on `HeatmapCell` from the `buildAssetHeatmapData` fix in Task 7.

- [ ] **Step 2: Commit**

```
feat(ui): show evaluation_name in asset heatmap tooltip
```

---

## Task 9: UI — EvaluationNameFilter component

**Files:**
- Create: `ui/src/features/navigator/components/EvaluationNameFilter.tsx`
- Create: `ui/src/features/navigator/components/EvaluationNameFilter.test.tsx`

- [ ] **Step 1: Write component test**

Create `ui/src/features/navigator/components/EvaluationNameFilter.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EvaluationNameFilter } from './EvaluationNameFilter'

const NAMES = [
  { name: 'load-test', count: 42, last_run: '2026-03-27T08:00:00Z' },
  { name: 'ad-hoc-run', count: 3, last_run: '2026-03-26T14:00:00Z' },
]

describe('EvaluationNameFilter', () => {
  it('renders chips for each name plus All', () => {
    render(
      <EvaluationNameFilter
        names={NAMES}
        selected={['load-test']}
        onChange={vi.fn()}
      />
    )
    expect(screen.getByText('All')).toBeInTheDocument()
    expect(screen.getByText(/load-test/)).toBeInTheDocument()
    expect(screen.getByText(/ad-hoc-run/)).toBeInTheDocument()
  })

  it('shows count on each chip', () => {
    render(
      <EvaluationNameFilter
        names={NAMES}
        selected={['load-test']}
        onChange={vi.fn()}
      />
    )
    expect(screen.getByText(/42/)).toBeInTheDocument()
    expect(screen.getByText(/3/)).toBeInTheDocument()
  })

  it('toggles a name when clicked', async () => {
    const onChange = vi.fn()
    render(
      <EvaluationNameFilter
        names={NAMES}
        selected={['load-test']}
        onChange={onChange}
      />
    )
    await userEvent.click(screen.getByText(/ad-hoc-run/))
    expect(onChange).toHaveBeenCalledWith(['load-test', 'ad-hoc-run'])
  })

  it('deselects a name when clicked again (if others remain)', async () => {
    const onChange = vi.fn()
    render(
      <EvaluationNameFilter
        names={NAMES}
        selected={['load-test', 'ad-hoc-run']}
        onChange={onChange}
      />
    )
    await userEvent.click(screen.getByText(/load-test/))
    expect(onChange).toHaveBeenCalledWith(['ad-hoc-run'])
  })

  it('does not deselect the last name', async () => {
    const onChange = vi.fn()
    render(
      <EvaluationNameFilter
        names={NAMES}
        selected={['load-test']}
        onChange={onChange}
      />
    )
    await userEvent.click(screen.getByText(/load-test/))
    expect(onChange).not.toHaveBeenCalled()
  })

  it('All selects undefined (no filter)', async () => {
    const onChange = vi.fn()
    render(
      <EvaluationNameFilter
        names={NAMES}
        selected={['load-test']}
        onChange={onChange}
      />
    )
    await userEvent.click(screen.getByText('All'))
    expect(onChange).toHaveBeenCalledWith(undefined)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/ui-test.sh --tail 20 src/features/navigator/components/EvaluationNameFilter.test.tsx`
Expected: FAIL — component doesn't exist.

- [ ] **Step 3: Implement the component**

Create `ui/src/features/navigator/components/EvaluationNameFilter.tsx`:

```typescript
import type { EvaluationNameEntry } from '@/features/evaluations/api'

interface Props {
  names: EvaluationNameEntry[]
  /** Selected names, or undefined = "All" (no filter). */
  selected: string[] | undefined
  onChange: (names: string[] | undefined) => void
}

export function EvaluationNameFilter({ names, selected, onChange }: Props) {
  if (names.length === 0) return null

  const isAll = selected === undefined

  function handleToggle(name: string) {
    if (isAll) {
      // Switch from All to just this name
      onChange([name])
      return
    }
    if (selected!.includes(name)) {
      // Deselect — but don't allow empty
      if (selected!.length <= 1) return
      onChange(selected!.filter(n => n !== name))
    } else {
      onChange([...selected!, name])
    }
  }

  function handleAll() {
    onChange(undefined)
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span
        className="text-xs uppercase tracking-wide text-slate-500 mr-1"
        style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}
      >
        Eval name
      </span>
      <button
        onClick={handleAll}
        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
          isAll
            ? 'bg-primary/20 text-primary border border-primary/40'
            : 'bg-gray-800 text-slate-400 border border-slate-700 hover:text-slate-200'
        }`}
      >
        All
      </button>
      {names.map(entry => {
        const active = !isAll && selected!.includes(entry.name)
        return (
          <button
            key={entry.name}
            onClick={() => handleToggle(entry.name)}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
              active
                ? 'bg-primary/20 text-primary border border-primary/40'
                : 'bg-gray-800 text-slate-400 border border-slate-700 hover:text-slate-200'
            }`}
          >
            {entry.name}
            <span className="text-[10px] opacity-60">{entry.count}</span>
          </button>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 4: Run tests**

Run: `./scripts/ui-test.sh --tail 20 src/features/navigator/components/EvaluationNameFilter.test.tsx`
Expected: All pass.

- [ ] **Step 5: Commit**

```
feat(ui): add EvaluationNameFilter multi-select chip component
```

---

## Task 10: Wire filter into AssetPanel

**Files:**
- Modify: `ui/src/features/navigator/components/AssetPanel.tsx`

- [ ] **Step 1: Add filter state and wire hooks**

`AssetPanel.tsx` already imports `useState, useMemo, useRef, useEffect` from `'react'`,
`useAssetEvaluations, useMetricHeatmap` from `'../hooks'`, `useAssets` from assets hooks,
`useSlos` from slos hooks, and `TimeRangePicker`.

Add `useEvaluationNames` to the `'../hooks'` import:

```typescript
import { useAssetEvaluations, useMetricHeatmap, useEvaluationNames } from '../hooks'
```

Add the filter component import:

```typescript
import { EvaluationNameFilter } from './EvaluationNameFilter'
```

Add state after the existing `useState` calls (after line 26):

```typescript
const [selectedNames, setSelectedNames] = useState<string[] | undefined>(undefined)
const [namesInitialized, setNamesInitialized] = useState(false)
```

Extend the existing reset `useEffect` on line 29 to also reset name state:

```typescript
useEffect(() => {
  setSelectedEvalId(undefined)
  setActiveAction(null)
  setSelectedNames(undefined)
  setNamesInitialized(false)
}, [assetName])
```

Add the names query (after the hook calls, ~line 57):

```typescript
const { data: evalNames = [] } = useEvaluationNames(assetName)
```

Auto-select the most recent name on first load:

```typescript
useEffect(() => {
  if (evalNames.length > 0 && !namesInitialized) {
    setSelectedNames([evalNames[0].name])
    setNamesInitialized(true)
  }
}, [evalNames, namesInitialized])
```

Update the existing hook calls on line 57-58 to pass `selectedNames`:

```typescript
const { data: evals = [], isLoading: evalsLoading } = useAssetEvaluations(assetName, selectedNames)
const { data: heatmapData, isLoading: heatmapLoading } = useMetricHeatmap(assetName, selectedNames)
```

- [ ] **Step 2: Render the filter between header and content**

Insert between the action form and the loading indicator (~line 151):

```typescript
{/* Evaluation name filter */}
{evalNames.length > 1 && (
  <EvaluationNameFilter
    names={evalNames}
    selected={selectedNames}
    onChange={setSelectedNames}
  />
)}
```

Only show when there are 2+ names (single-name assets don't need the filter).

- [ ] **Step 3: Run UI tests**

Run: `./scripts/ui-test.sh --tail 10`
Expected: All pass.

- [ ] **Step 4: Commit**

```
feat(ui): wire evaluation name filter into AssetPanel
```

---

## Task 11: Wire filter into GroupPanel and AllEvaluationsPanel

**Files:**
- Modify: `ui/src/features/navigator/components/GroupPanel.tsx`
- Modify: `ui/src/features/navigator/components/AllEvaluationsPanel.tsx`

- [ ] **Step 1: Wire into GroupPanel**

`GroupPanel.tsx` already imports `useState` from `'react'`, `useEvaluations` from evaluations hooks,
`useAssetGroups`/`useAssets` from assets hooks, `useSlos` from slos hooks, `TimeRangePicker`,
display name lookups (`assetDisplayNames`, `sloDisplayNames`), and `EvaluationHeatmap`/`EvaluationTable`.

Add these new imports only:

```typescript
import { useEffect } from 'react'  // add to existing 'react' import
import { useEvaluationNames } from '../hooks'
import { EvaluationNameFilter } from './EvaluationNameFilter'
```

Add state and query after existing `useState` calls (~line 25):

```typescript
const [selectedNames, setSelectedNames] = useState<string[] | undefined>(undefined)
const [namesInitialized, setNamesInitialized] = useState(false)
const { data: evalNames = [] } = useEvaluationNames(undefined, groupName)

useEffect(() => {
  if (evalNames.length > 0 && !namesInitialized) {
    setSelectedNames([evalNames[0].name])
    setNamesInitialized(true)
  }
}, [evalNames, namesInitialized])
```

Update the existing evaluations query to pass evaluation names:

```typescript
const { data: evals = [], isLoading } = useEvaluations({
  group_name: groupName,
  evaluation_name: selectedNames,
})
```

Add filter UI between the `<EvaluationHeader>` and the content section (~after line 60):

```typescript
{evalNames.length > 1 && (
  <EvaluationNameFilter
    names={evalNames}
    selected={selectedNames}
    onChange={setSelectedNames}
  />
)}
```

- [ ] **Step 2: Wire into AllEvaluationsPanel**

`AllEvaluationsPanel.tsx` already imports `useState`, `useMemo` from `'react'`, `useAssets`
from assets hooks, `useSlos` from slos hooks, `useEvaluations`/`useDynamicColumns`/
`useColumnVisibility` from evaluations hooks, `EvaluationHeatmap`, `EvaluationTable`,
`EvaluationHeader`, `TimeRangePicker`, and has display name lookups.

Add these new imports only:

```typescript
import { useEffect } from 'react'  // add to existing 'react' import
import { useEvaluationNames } from '../hooks'
import { EvaluationNameFilter } from './EvaluationNameFilter'
```

Add state and query after existing `useState` calls:

```typescript
const [selectedNames, setSelectedNames] = useState<string[] | undefined>(undefined)
const [namesInitialized, setNamesInitialized] = useState(false)
const { data: evalNames = [] } = useEvaluationNames()
```

Auto-init:

```typescript
useEffect(() => {
  if (evalNames.length > 0 && !namesInitialized) {
    setSelectedNames([evalNames[0].name])
    setNamesInitialized(true)
  }
}, [evalNames, namesInitialized])
```

**Important:** `useEvaluationNames()` with no arguments needs to work. Update the hook in
`ui/src/features/navigator/hooks.ts` — remove the `enabled` guard from Task 6:

```typescript
export function useEvaluationNames(
  assetName?: string,
  groupName?: string,
) {
  return useQuery({
    queryKey: evaluationKeys.names({ asset_name: assetName, group_name: groupName }),
    queryFn: () => fetchEvaluationNames({ asset_name: assetName, group_name: groupName }),
    // Always enabled: no scope = global (for AllEvaluationsPanel).
  })
}
```

Update `AllEvaluationsPanel` evaluations query to pass names:

```typescript
const { data: evals = [], isLoading } = useEvaluations({
  evaluation_name: selectedNames,
})
```

Add filter UI between `<EvaluationHeader>` and content (~after line 57):

```typescript
{evalNames.length > 1 && (
  <EvaluationNameFilter
    names={evalNames}
    selected={selectedNames}
    onChange={setSelectedNames}
  />
)}
```

- [ ] **Step 3: Run UI tests**

Run: `./scripts/ui-test.sh --tail 10`
Expected: All pass.

- [ ] **Step 4: Commit**

```
feat(ui): wire evaluation name filter into GroupPanel and AllEvaluationsPanel
```

---

## Task 12: Cache invalidation

**Files:**
- Modify: `ui/src/features/evaluations/hooks.ts`

- [ ] **Step 1: Invalidate names cache on mutations**

In the `useReEvaluate` hook's `onSuccess`, add invalidation for the names query. Find the existing query invalidation in mutation hooks and add:

```typescript
queryClient.invalidateQueries({ queryKey: ['evaluation-names'] })
```

Do the same in `useInvalidateEvaluation`, `useOverrideStatus`, and any other mutation that changes evaluation state.

Also check `useTriggerEvaluation` if it exists — new evaluations could introduce new names.

- [ ] **Step 2: Run UI tests**

Run: `./scripts/ui-test.sh --tail 10`
Expected: All pass.

- [ ] **Step 3: Commit**

```
fix(ui): invalidate evaluation-names cache on evaluation mutations
```

---

## Task 13: Seed script — Realistic evaluation names

**Files:**
- Modify: `scripts/seed_evaluations.py`

- [ ] **Step 1: Replace `seed-N` with realistic names**

Update `scripts/seed_evaluations.py`. Replace the trigger loop that uses `f"seed-{asset_idx}"` with realistic, recurring names.

Strategy:
- E-commerce assets get `load-test` (frequent, all windows) and `prod-validation` (every other window)
- VM assets get `user-experience` (all windows) and `optimization-testing` (windows 0, 3, 6, 9 only)
- Laptop assets get `load-test` (all windows)

```python
# Evaluation name assignments per asset category
def get_eval_runs(asset_name: str, slo_name: str) -> list[tuple[str, list[int]]]:
    """Return (evaluation_name, window_indices) pairs for this asset."""
    if "laptop" in asset_name:
        return [("load-test", list(range(10)))]
    if "vm-" in asset_name:
        return [
            ("user-experience", list(range(10))),
            ("optimization-testing", [0, 3, 6, 9]),
        ]
    # E-commerce
    return [
        ("load-test", list(range(10))),
        ("prod-validation", [0, 2, 4, 6, 8]),
    ]
```

Then the trigger loop becomes:

```python
eval_ids: list[str] = []
for asset_name, slo_name in ASSETS:
    runs = get_eval_runs(asset_name, slo_name)
    for eval_name, window_indices in runs:
        for wi in window_indices:
            start, end = WINDOWS[wi]
            result = client.evaluations.trigger(
                asset_name,
                eval_name,
                slo_name,
                start,
                end,
            )
            eval_ids.append(result["id"])
```

Update the total count print:

```python
total = sum(
    sum(len(indices) for _, indices in get_eval_runs(a, s))
    for a, s in ASSETS
)
```

- [ ] **Step 2: Verify script runs without syntax errors**

Run: `uv run python -c "import ast; ast.parse(open('scripts/seed_evaluations.py').read())"`
Expected: No output (clean parse).

- [ ] **Step 3: Commit**

```
feat(seed): use realistic recurring evaluation names instead of seed-N
```

---

## Task 14: Final integration verification

- [ ] **Step 1: Run all API tests**

Run: `./scripts/api-test.sh --tail 5`
Expected: All pass.

- [ ] **Step 2: Run all UI tests**

Run: `./scripts/ui-test.sh --tail 10`
Expected: All pass.

- [ ] **Step 3: Run linting and type checks**

Run: `just check`
Expected: Clean.

Run (from ui/): `pnpm exec tsc --noEmit -p tsconfig.app.json`
Expected: Clean.

- [ ] **Step 4: Manual smoke test**

Start the dev environment with `./scripts/dev-start.sh` and verify:
1. Navigator loads, group heatmap shows
2. Evaluation name filter chips appear when 2+ names exist
3. Clicking a chip filters the heatmap and table
4. "All" shows everything
5. Clicking a table row navigates to the correct evaluation in AssetPanel
6. Heatmap cell tooltips show evaluation name
7. No cell collision when multiple names share a timestamp

- [ ] **Step 5: Commit any final fixes**
