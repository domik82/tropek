# Per-SLO Action Scoping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scope every column-level action (Override, Invalidate, Restore, Baseline Pin, Re-run) to a user-picked subset of SLO rows instead of silently targeting the "first SLO" in a multi-SLO column.

**Architecture:** New `SloScopePicker` component trio (`useSloScope` hook + `SloScopeField` + `SloScopeModal`) lifted into an anchored popover (`ActionPopover`) that replaces the current inline action form. Each of the five action forms gains a scope field at the top and fans out per-row backend calls via `Promise.allSettled`. One additive backend field (`slo_names` on `ReEvaluateRequest`) lets re-run scope a single async job.

**Design spec:** `docs/superpowers/specs/2026-04-14-per-slo-action-scoping-design.md` — read this first.

**Tech Stack:** Python 3.13 / FastAPI / Pydantic (backend); React 19 / TypeScript 5.9 / Vitest / React Testing Library / Tanstack Query / floating-ui (UI).

---

## File Structure

### Backend (create/modify)

- **Modify** `api/tropek/modules/quality_gate/schemas/re_evaluation.py` — add `slo_names: list[str] | None`, extend mutual-exclusion validator.
- **Modify** `api/tropek/modules/quality_gate/workflows/re_evaluation/re_evaluation_service.py` — consume `slo_names` in SLO filtering logic.
- **Modify** `api/tests/quality_gate/db/test_re_evaluation.py` — new test cases for `slo_names` happy path + validation errors.

### UI — new files under `ui/src/features/evaluations/components/actions/slo-scope/`

- `types.ts` — `SloScopeOption`, `SloScopeResult`, `SloScopeFilter`, `SloScopeInitialMode`.
- `useSloScope.ts` — derives column rows, manages selection state, exposes `lookupEvalId`.
- `useSloScope.test.ts` — hook unit tests.
- `SloScopeField.tsx` — compact summary row + edit + reset buttons.
- `SloScopeField.test.tsx` — component tests.
- `SloScopeModal.tsx` — search + checklist modal.
- `SloScopeModal.test.tsx` — component tests.

### UI — new files under `ui/src/features/evaluations/components/`

- `ActionPopover.tsx` — anchored container, renders the active action form.
- `ActionPopover.test.tsx` — popover behavior tests.
- `actions/invalidate-column-queries.ts` — shared cache-invalidation helper.

### UI — modifications

- `ui/src/features/evaluations/components/EvaluationActions.tsx` — collapse override, menu availability rules, switch `EvaluationActionForm` → `ActionPopover`.
- `ui/src/features/evaluations/components/actions/OverrideForm.tsx` — radio target, scope + fan-out.
- `ui/src/features/evaluations/components/actions/InvalidateForm.tsx` — scope + fan-out, filter non-invalidated.
- `ui/src/features/evaluations/components/actions/RestoreForm.tsx` — scope + fan-out, filter invalidated.
- `ui/src/features/evaluations/components/actions/BaselineForm.tsx` — scope + fan-out + per-SLO pin-conflict result list.
- `ui/src/features/evaluations/components/actions/ReEvaluateForm.tsx` — sends `slo_names` list instead of `slo_name`.
- `ui/src/features/evaluations/domain.ts` + `mappers.ts` — add `slo_names` to `ReEvaluateInput`.
- `ui/src/features/navigator/components/AssetPanel.tsx` — expose `selectedSingleSloEvalId`, mount `ActionPopover` in place of inline form, pass both column + single-SLO ids.

---

## Task 1: Backend — Add `slo_names` list scoping to `ReEvaluateRequest`

**Why first:** Smallest, fully backend-isolated change. Gives the UI a real field to target when Task 11 refactors `ReEvaluateForm`. Self-contained TDD cycle.

**Files:**
- Modify: `api/tropek/modules/quality_gate/schemas/re_evaluation.py`
- Modify: `api/tropek/modules/quality_gate/workflows/re_evaluation/re_evaluation_service.py`
- Test: `api/tests/quality_gate/db/test_re_evaluation.py`

- [ ] **Step 1: Read the existing re-evaluation service to understand SLO resolution**

Run: `cat api/tropek/modules/quality_gate/workflows/re_evaluation/re_evaluation_service.py | head -120`

You're looking for the function that resolves which SLOs to re-evaluate from `request.slo_name` (likely `_resolve_slo_names` or inline in `re_evaluate`). Note the existing pattern so the `slo_names` case follows it.

- [ ] **Step 2: Write a failing test for schema validation — both fields set → 422**

Add this test to `api/tests/quality_gate/db/test_re_evaluation.py` (or the nearest existing validation test file):

```python
import pytest
from pydantic import ValidationError

from tropek.modules.quality_gate.schemas.re_evaluation import ReEvaluateRequest


def test_slo_name_and_slo_names_mutually_exclusive():
    with pytest.raises(ValidationError, match='mutually exclusive'):
        ReEvaluateRequest(
            asset_name='checkout-api',
            slo_name='latency-slo',
            slo_names=['latency-slo', 'avail-slo'],
            from_baseline=True,
        )


def test_empty_slo_names_rejected():
    with pytest.raises(ValidationError, match='slo_names must be non-empty'):
        ReEvaluateRequest(
            asset_name='checkout-api',
            slo_names=[],
            from_baseline=True,
        )


def test_slo_names_happy_path():
    request = ReEvaluateRequest(
        asset_name='checkout-api',
        slo_names=['latency-slo', 'avail-slo'],
        from_baseline=True,
    )
    assert request.slo_names == ['latency-slo', 'avail-slo']
    assert request.slo_name is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `./scripts/api-test.sh --tail 30 tests/quality_gate/db/test_re_evaluation.py -v -k slo_names`

Expected: FAIL — the `slo_names` field does not exist yet.

- [ ] **Step 4: Add `slo_names` field to the schema**

In `api/tropek/modules/quality_gate/schemas/re_evaluation.py`, update the `ReEvaluateRequest` class:

```python
class ReEvaluateRequest(StrictInput):
    """Request body for POST /evaluations/re-evaluate.

    When ``slo_name`` is omitted and ``slo_names`` is omitted, all SLOs
    assigned to the asset are re-evaluated. When ``slo_names`` is provided,
    scoring runs only for the listed SLOs.
    """

    asset_name: str
    slo_name: str | None = None
    slo_names: list[str] | None = None

    # Scope — exactly one required
    from_date: datetime | None = None
    from_baseline: bool = False
    from_evaluation_id: uuid.UUID | None = None

    # Optional
    slo_version: int | None = None
    dry_run: bool = False
    pin_strategy: Literal['skip_to_pin', 'ignore_pin'] | None = None

    @model_validator(mode='after')
    def exactly_one_scope(self) -> ReEvaluateRequest:
        """Ensure exactly one scope parameter is provided."""
        scopes = sum(
            [
                self.from_date is not None,
                self.from_baseline,
                self.from_evaluation_id is not None,
            ]
        )
        if scopes != 1:
            msg = 'exactly one of from_date, from_baseline, or from_evaluation_id is required'
            raise ValueError(msg)
        return self

    @model_validator(mode='after')
    def slo_name_and_names_mutually_exclusive(self) -> ReEvaluateRequest:
        """slo_name and slo_names cannot be supplied together."""
        if self.slo_name is not None and self.slo_names is not None:
            msg = 'slo_name and slo_names are mutually exclusive'
            raise ValueError(msg)
        if self.slo_names is not None and len(self.slo_names) == 0:
            msg = 'slo_names must be non-empty when provided'
            raise ValueError(msg)
        return self
```

- [ ] **Step 5: Run schema tests to verify they pass**

Run: `./scripts/api-test.sh --tail 30 tests/quality_gate/db/test_re_evaluation.py -v -k slo_names`

Expected: PASS on all three new tests. Existing tests still pass.

- [ ] **Step 6: Write a failing integration test — `slo_names` filters scoring**

Add to `api/tests/quality_gate/db/test_re_evaluation.py` — the integration-style test file. Follow the existing pattern used by other re-evaluation tests in the file (fixtures, async/await, asset+SLO seeding):

```python
@pytest.mark.integration
async def test_re_evaluate_filters_to_slo_names_subset(
    db_session,
    seeded_multi_slo_asset,  # reuse existing fixture if present; otherwise inline seeding
):
    """slo_names filters re-evaluation to only the listed SLOs."""
    asset_name, slo_a, slo_b, slo_c = seeded_multi_slo_asset

    request = ReEvaluateRequest(
        asset_name=asset_name,
        slo_names=[slo_a, slo_b],
        from_baseline=True,
    )
    response = await re_evaluate(request, repos=make_test_repos(db_session))

    touched_slo_names = {item.slo_name for item in response.results}
    assert touched_slo_names == {slo_a, slo_b}
    assert slo_c not in touched_slo_names
```

**If `seeded_multi_slo_asset` does not exist:** copy the existing asset-seeding pattern from the nearest test in the same file (look for `seeded_asset` or similar) and create three SLOs against the same asset.

- [ ] **Step 7: Run integration test to verify it fails**

Run: `just test-env && ./scripts/api-test.sh --tail 30 tests/quality_gate/db/test_re_evaluation.py -m integration -v -k slo_names_subset`

Expected: FAIL — service still ignores `slo_names`.

- [ ] **Step 8: Update the service to honor `slo_names`**

In `api/tropek/modules/quality_gate/workflows/re_evaluation/re_evaluation_service.py`, find the function that resolves which SLO names to process. It's likely a block like:

```python
if request.slo_name:
    slo_names_to_run = [request.slo_name]
else:
    slo_names_to_run = await asset_service.list_slos_for_asset(request.asset_name)
```

Change it to:

```python
if request.slo_names is not None:
    slo_names_to_run = request.slo_names
elif request.slo_name is not None:
    slo_names_to_run = [request.slo_name]
else:
    slo_names_to_run = await asset_service.list_slos_for_asset(request.asset_name)
```

(Keep the rest of the service unchanged — it already iterates over `slo_names_to_run`.)

- [ ] **Step 9: Run integration test to verify it passes**

Run: `./scripts/api-test.sh --tail 30 tests/quality_gate/db/test_re_evaluation.py -m integration -v -k slo_names_subset`

Expected: PASS.

- [ ] **Step 10: Run the full re-evaluation test suite to catch regressions**

Run: `./scripts/api-test.sh --tail 50 tests/quality_gate/db/test_re_evaluation.py -v`

Expected: All tests pass (new + existing).

- [ ] **Step 11: Run API unit tests for the broader quality_gate module**

Run: `./scripts/api-test.sh --tail 20`

Expected: PASS.

- [ ] **Step 12: Lint + typecheck**

Run: `just check`

Expected: PASS.

- [ ] **Step 13: Commit**

```bash
git add api/tropek/modules/quality_gate/schemas/re_evaluation.py \
        api/tropek/modules/quality_gate/workflows/re_evaluation/re_evaluation_service.py \
        api/tests/quality_gate/db/test_re_evaluation.py
git commit -m "feat(re-eval): add slo_names list scoping to ReEvaluateRequest"
```

---

## Task 2: UI — `slo-scope/types.ts` + `useSloScope` hook

**Why next:** Pure logic, zero visual concerns. Every downstream task consumes this hook, so locking it down first prevents interface churn.

**Files:**
- Create: `ui/src/features/evaluations/components/actions/slo-scope/types.ts`
- Create: `ui/src/features/evaluations/components/actions/slo-scope/useSloScope.ts`
- Create: `ui/src/features/evaluations/components/actions/slo-scope/useSloScope.test.ts`

- [ ] **Step 1: Confirm heatmap domain types available**

Run: `grep -n 'heatmapData\|heatmap_data\|MetricHeatmapResponse\|GroupedMetricHeatmapResponse' ui/src/features/navigator/domain.ts`

You need the types for `heatmapData.groups[].cells[]`. Expected: a type like `HeatmapGroup` with `cells: HeatmapCell[]` where each cell has `evaluation_id`, `slo_evaluation_id`, `period_start`, `result`, and `invalidated`. Note the exact field names from what's returned — you'll import them in `useSloScope.ts`.

- [ ] **Step 2: Create the types module**

Write `ui/src/features/evaluations/components/actions/slo-scope/types.ts`:

```ts
export type SloScopeOutcome = 'pass' | 'warning' | 'fail' | 'invalidated' | 'error'

export interface SloScopeOption {
  sloName: string
  displayName: string
  sloEvaluationId: string
  currentResult: SloScopeOutcome
}

export type SloScopeFilter = 'all' | 'invalidated-only' | 'not-invalidated'

export type SloScopeInitialMode = 'all' | { singleSlo: string }

export interface SloScopeResult {
  availableSlos: SloScopeOption[]
  selected: Set<string>
  setSelected: (next: Set<string>) => void
  reset: () => void
  lookupEvalId: (sloName: string) => string | undefined
}
```

- [ ] **Step 3: Write the failing hook tests**

Write `ui/src/features/evaluations/components/actions/slo-scope/useSloScope.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useSloScope } from './useSloScope'
import type { GroupedMetricHeatmapResponse } from '@/features/navigator/domain'

function makeHeatmap(): GroupedMetricHeatmapResponse {
  return {
    groups: [
      {
        slo_name: 'latency-slo',
        slo_display_name: 'Latency SLO',
        cells: [
          {
            evaluation_id: 'col-1',
            slo_evaluation_id: 'sloeval-latency',
            period_start: '2026-04-10T00:00:00Z',
            result: 'fail',
            invalidated: false,
          },
          {
            evaluation_id: 'col-2',
            slo_evaluation_id: 'sloeval-latency-2',
            period_start: '2026-04-11T00:00:00Z',
            result: 'pass',
            invalidated: false,
          },
        ],
        summary: [],
      },
      {
        slo_name: 'avail-slo',
        slo_display_name: 'Availability SLO',
        cells: [
          {
            evaluation_id: 'col-1',
            slo_evaluation_id: 'sloeval-avail',
            period_start: '2026-04-10T00:00:00Z',
            result: 'pass',
            invalidated: true,
          },
        ],
        summary: [],
      },
    ],
    composite: [],
    columns: [],
  } as unknown as GroupedMetricHeatmapResponse
}

describe('useSloScope', () => {
  it('derives SLO rows for the selected column only', () => {
    const { result } = renderHook(() =>
      useSloScope({ heatmapData: makeHeatmap(), columnEvalId: 'col-1', initialMode: 'all' }),
    )
    expect(result.current.availableSlos.map(s => s.sloName)).toEqual(['latency-slo', 'avail-slo'])
    expect(result.current.availableSlos[1].currentResult).toBe('invalidated')
  })

  it('defaults selection to ALL when initialMode is "all"', () => {
    const { result } = renderHook(() =>
      useSloScope({ heatmapData: makeHeatmap(), columnEvalId: 'col-1', initialMode: 'all' }),
    )
    expect(result.current.selected).toEqual(new Set(['latency-slo', 'avail-slo']))
  })

  it('defaults selection to a single SLO when initialMode is { singleSlo }', () => {
    const { result } = renderHook(() =>
      useSloScope({
        heatmapData: makeHeatmap(),
        columnEvalId: 'col-1',
        initialMode: { singleSlo: 'latency-slo' },
      }),
    )
    expect(result.current.selected).toEqual(new Set(['latency-slo']))
  })

  it('reset() widens to ALL regardless of initialMode', () => {
    const { result } = renderHook(() =>
      useSloScope({
        heatmapData: makeHeatmap(),
        columnEvalId: 'col-1',
        initialMode: { singleSlo: 'latency-slo' },
      }),
    )
    act(() => result.current.reset())
    expect(result.current.selected).toEqual(new Set(['latency-slo', 'avail-slo']))
  })

  it('lookupEvalId maps sloName to sloEvaluationId for the current column', () => {
    const { result } = renderHook(() =>
      useSloScope({ heatmapData: makeHeatmap(), columnEvalId: 'col-1', initialMode: 'all' }),
    )
    expect(result.current.lookupEvalId('latency-slo')).toBe('sloeval-latency')
    expect(result.current.lookupEvalId('nope')).toBeUndefined()
  })

  it('filter "invalidated-only" removes non-invalidated rows', () => {
    const { result } = renderHook(() =>
      useSloScope({
        heatmapData: makeHeatmap(),
        columnEvalId: 'col-1',
        initialMode: 'all',
        filter: 'invalidated-only',
      }),
    )
    expect(result.current.availableSlos.map(s => s.sloName)).toEqual(['avail-slo'])
    expect(result.current.selected).toEqual(new Set(['avail-slo']))
  })

  it('filter "not-invalidated" removes invalidated rows', () => {
    const { result } = renderHook(() =>
      useSloScope({
        heatmapData: makeHeatmap(),
        columnEvalId: 'col-1',
        initialMode: 'all',
        filter: 'not-invalidated',
      }),
    )
    expect(result.current.availableSlos.map(s => s.sloName)).toEqual(['latency-slo'])
  })

  it('singleSlo fallback to ALL when that SLO is filtered out', () => {
    // user clicked invalidated cell then picked an action that filters invalidated away
    const { result } = renderHook(() =>
      useSloScope({
        heatmapData: makeHeatmap(),
        columnEvalId: 'col-1',
        initialMode: { singleSlo: 'avail-slo' },
        filter: 'not-invalidated',
      }),
    )
    expect(result.current.availableSlos.map(s => s.sloName)).toEqual(['latency-slo'])
    expect(result.current.selected).toEqual(new Set(['latency-slo']))
  })
})
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `./scripts/ui-test.sh --tail 30 src/features/evaluations/components/actions/slo-scope/useSloScope.test.ts`

Expected: FAIL — hook does not exist.

- [ ] **Step 5: Implement the hook**

Write `ui/src/features/evaluations/components/actions/slo-scope/useSloScope.ts`:

```ts
import { useMemo, useState, useCallback } from 'react'
import type { GroupedMetricHeatmapResponse } from '@/features/navigator/domain'
import type {
  SloScopeFilter,
  SloScopeInitialMode,
  SloScopeOption,
  SloScopeResult,
} from './types'

interface UseSloScopeArgs {
  heatmapData: GroupedMetricHeatmapResponse | undefined
  columnEvalId: string | undefined
  initialMode: SloScopeInitialMode
  filter?: SloScopeFilter
}

export function useSloScope({
  heatmapData,
  columnEvalId,
  initialMode,
  filter = 'all',
}: UseSloScopeArgs): SloScopeResult {
  const availableSlos = useMemo<SloScopeOption[]>(() => {
    if (!heatmapData || !columnEvalId) return []
    const rows: SloScopeOption[] = []
    for (const group of heatmapData.groups) {
      const cell = group.cells.find(c => c.evaluation_id === columnEvalId)
      if (!cell) continue
      const currentResult = cell.invalidated ? 'invalidated' : (cell.result as SloScopeOption['currentResult'])
      if (filter === 'invalidated-only' && currentResult !== 'invalidated') continue
      if (filter === 'not-invalidated' && currentResult === 'invalidated') continue
      rows.push({
        sloName: group.slo_name,
        displayName: group.slo_display_name ?? group.slo_name,
        sloEvaluationId: cell.slo_evaluation_id,
        currentResult,
      })
    }
    return rows
  }, [heatmapData, columnEvalId, filter])

  const defaultSelection = useMemo<Set<string>>(() => {
    const allNames = new Set(availableSlos.map(r => r.sloName))
    if (initialMode === 'all') return allNames
    if (allNames.has(initialMode.singleSlo)) return new Set([initialMode.singleSlo])
    return allNames
  }, [availableSlos, initialMode])

  const [selected, setSelected] = useState<Set<string>>(defaultSelection)

  // Keep selection in sync if availableSlos changes (e.g., column switch)
  const [lastKey, setLastKey] = useState(`${columnEvalId}:${filter}`)
  const currentKey = `${columnEvalId}:${filter}`
  if (currentKey !== lastKey) {
    setLastKey(currentKey)
    setSelected(defaultSelection)
  }

  const reset = useCallback(() => {
    setSelected(new Set(availableSlos.map(r => r.sloName)))
  }, [availableSlos])

  const lookupEvalId = useCallback(
    (sloName: string) => availableSlos.find(r => r.sloName === sloName)?.sloEvaluationId,
    [availableSlos],
  )

  return { availableSlos, selected, setSelected, reset, lookupEvalId }
}
```

- [ ] **Step 6: Run hook tests to verify they pass**

Run: `./scripts/ui-test.sh --tail 30 src/features/evaluations/components/actions/slo-scope/useSloScope.test.ts`

Expected: PASS on all 8 tests.

- [ ] **Step 7: Run lint on the new files**

Run: `./scripts/ui-lint.sh --tail 10 src/features/evaluations/components/actions/slo-scope/useSloScope.ts src/features/evaluations/components/actions/slo-scope/useSloScope.test.ts src/features/evaluations/components/actions/slo-scope/types.ts`

Expected: No errors. If there are import-order or unused-import warnings, fix them inline and re-run.

- [ ] **Step 8: Commit**

```bash
git add ui/src/features/evaluations/components/actions/slo-scope/
git commit -m "feat(ui): useSloScope hook for multi-SLO column scoping"
```

---

## Task 3: UI — `SloScopeField` component

**Files:**
- Create: `ui/src/features/evaluations/components/actions/slo-scope/SloScopeField.tsx`
- Create: `ui/src/features/evaluations/components/actions/slo-scope/SloScopeField.test.tsx`

- [ ] **Step 1: Write the failing component test**

Write `ui/src/features/evaluations/components/actions/slo-scope/SloScopeField.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach } from 'vitest'
import { SloScopeField } from './SloScopeField'
import type { SloScopeResult } from './types'

afterEach(() => cleanup())

function makeScope(overrides: Partial<SloScopeResult> = {}): SloScopeResult {
  return {
    availableSlos: [
      { sloName: 'a', displayName: 'A', sloEvaluationId: 'eid-a', currentResult: 'pass' },
      { sloName: 'b', displayName: 'B', sloEvaluationId: 'eid-b', currentResult: 'fail' },
      { sloName: 'c', displayName: 'C', sloEvaluationId: 'eid-c', currentResult: 'warning' },
    ],
    selected: new Set(['a', 'b', 'c']),
    setSelected: vi.fn(),
    reset: vi.fn(),
    lookupEvalId: vi.fn(),
    ...overrides,
  }
}

describe('SloScopeField', () => {
  it('renders N of M SLOs summary', () => {
    render(<SloScopeField scope={makeScope()} onOpenPicker={vi.fn()} />)
    expect(screen.getByText(/3 of 3 SLOs/i)).toBeInTheDocument()
  })

  it('renders a partial count when some are deselected', () => {
    const scope = makeScope({ selected: new Set(['a']) })
    render(<SloScopeField scope={scope} onOpenPicker={vi.fn()} />)
    expect(screen.getByText(/1 of 3 SLOs/i)).toBeInTheDocument()
  })

  it('clicking the summary row invokes onOpenPicker', async () => {
    const onOpenPicker = vi.fn()
    render(<SloScopeField scope={makeScope()} onOpenPicker={onOpenPicker} />)
    await userEvent.click(screen.getByRole('button', { name: /change scope/i }))
    expect(onOpenPicker).toHaveBeenCalledOnce()
  })

  it('clicking reset invokes scope.reset and does not open the picker', async () => {
    const onOpenPicker = vi.fn()
    const scope = makeScope({ selected: new Set(['a']) })
    render(<SloScopeField scope={scope} onOpenPicker={onOpenPicker} />)
    await userEvent.click(screen.getByRole('button', { name: /reset to all/i }))
    expect(scope.reset).toHaveBeenCalledOnce()
    expect(onOpenPicker).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./scripts/ui-test.sh --tail 20 src/features/evaluations/components/actions/slo-scope/SloScopeField.test.tsx`

Expected: FAIL — component does not exist.

- [ ] **Step 3: Implement `SloScopeField`**

Write `ui/src/features/evaluations/components/actions/slo-scope/SloScopeField.tsx`:

```tsx
import type { SloScopeResult } from './types'

interface Props {
  scope: SloScopeResult
  onOpenPicker: () => void
}

export function SloScopeField({ scope, onOpenPicker }: Props) {
  const total = scope.availableSlos.length
  const selectedCount = scope.selected.size
  const isPartial = selectedCount !== total

  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-muted/30 border border-border text-xs">
      <span className="text-muted-foreground shrink-0">Applies to:</span>
      <button
        type="button"
        onClick={onOpenPicker}
        aria-label="Change scope"
        className={`flex-1 text-left font-medium ${
          isPartial ? 'text-primary' : 'text-foreground'
        } hover:underline`}
      >
        {selectedCount} of {total} SLO{total === 1 ? '' : 's'}
        {isPartial && <span className="ml-2 text-muted-foreground">(partial)</span>}
      </button>
      {isPartial && (
        <button
          type="button"
          onClick={scope.reset}
          aria-label="Reset to all SLOs"
          className="text-xs text-muted-foreground hover:text-foreground px-2 py-0.5 rounded border border-border"
        >
          Reset
        </button>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/ui-test.sh --tail 20 src/features/evaluations/components/actions/slo-scope/SloScopeField.test.tsx`

Expected: PASS on all 4 tests.

- [ ] **Step 5: Lint**

Run: `./scripts/ui-lint.sh --tail 10 src/features/evaluations/components/actions/slo-scope/SloScopeField.tsx src/features/evaluations/components/actions/slo-scope/SloScopeField.test.tsx`

Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add ui/src/features/evaluations/components/actions/slo-scope/SloScopeField.tsx \
        ui/src/features/evaluations/components/actions/slo-scope/SloScopeField.test.tsx
git commit -m "feat(ui): SloScopeField summary row component"
```

---

## Task 4: UI — `SloScopeModal` component

**Files:**
- Create: `ui/src/features/evaluations/components/actions/slo-scope/SloScopeModal.tsx`
- Create: `ui/src/features/evaluations/components/actions/slo-scope/SloScopeModal.test.tsx`

- [ ] **Step 1: Write the failing component tests**

Write `ui/src/features/evaluations/components/actions/slo-scope/SloScopeModal.test.tsx`:

```tsx
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SloScopeModal } from './SloScopeModal'
import type { SloScopeOption } from './types'

afterEach(() => cleanup())

const slos: SloScopeOption[] = [
  { sloName: 'latency-slo', displayName: 'Latency', sloEvaluationId: 'e1', currentResult: 'fail' },
  { sloName: 'avail-slo', displayName: 'Availability', sloEvaluationId: 'e2', currentResult: 'pass' },
  { sloName: 'err-slo', displayName: 'Error Rate', sloEvaluationId: 'e3', currentResult: 'warning' },
]

describe('SloScopeModal', () => {
  it('renders all SLOs with current result badges', () => {
    render(
      <SloScopeModal
        open
        availableSlos={slos}
        initialSelected={new Set(['latency-slo'])}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    expect(screen.getByText('Latency')).toBeInTheDocument()
    expect(screen.getByText('Availability')).toBeInTheDocument()
    expect(screen.getByText('Error Rate')).toBeInTheDocument()
    expect(screen.getAllByRole('checkbox')).toHaveLength(3)
  })

  it('search filters by display name', async () => {
    render(
      <SloScopeModal
        open
        availableSlos={slos}
        initialSelected={new Set()}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    await userEvent.type(screen.getByPlaceholderText(/search/i), 'latency')
    expect(screen.getByText('Latency')).toBeInTheDocument()
    expect(screen.queryByText('Availability')).not.toBeInTheDocument()
  })

  it('Select all checks every row', async () => {
    const onConfirm = vi.fn()
    render(
      <SloScopeModal
        open
        availableSlos={slos}
        initialSelected={new Set()}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: /select all/i }))
    await userEvent.click(screen.getByRole('button', { name: /confirm/i }))
    expect(onConfirm).toHaveBeenCalledWith(new Set(['latency-slo', 'avail-slo', 'err-slo']))
  })

  it('Clear unchecks every row', async () => {
    const onConfirm = vi.fn()
    render(
      <SloScopeModal
        open
        availableSlos={slos}
        initialSelected={new Set(['latency-slo', 'avail-slo'])}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: /clear/i }))
    await userEvent.click(screen.getByRole('button', { name: /confirm/i }))
    expect(onConfirm).toHaveBeenCalledWith(new Set())
  })

  it('cancel discards changes and invokes onCancel', async () => {
    const onCancel = vi.fn()
    const onConfirm = vi.fn()
    render(
      <SloScopeModal
        open
        availableSlos={slos}
        initialSelected={new Set()}
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: /select all/i }))
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(onCancel).toHaveBeenCalledOnce()
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('returns null when open=false', () => {
    const { container } = render(
      <SloScopeModal
        open={false}
        availableSlos={slos}
        initialSelected={new Set()}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    expect(container.firstChild).toBeNull()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./scripts/ui-test.sh --tail 20 src/features/evaluations/components/actions/slo-scope/SloScopeModal.test.tsx`

Expected: FAIL — component does not exist.

- [ ] **Step 3: Implement `SloScopeModal`**

Write `ui/src/features/evaluations/components/actions/slo-scope/SloScopeModal.tsx`:

```tsx
import { useState, useEffect, useMemo } from 'react'
import type { SloScopeOption, SloScopeOutcome } from './types'

interface Props {
  open: boolean
  availableSlos: SloScopeOption[]
  initialSelected: Set<string>
  onConfirm: (selected: Set<string>) => void
  onCancel: () => void
}

const RESULT_BADGE_CLASS: Record<SloScopeOutcome, string> = {
  pass: 'text-pass bg-pass/10 border-pass/30',
  warning: 'text-warning bg-warning/10 border-warning/30',
  fail: 'text-fail bg-fail/10 border-fail/30',
  invalidated: 'text-muted-foreground bg-muted/20 border-border',
  error: 'text-muted-foreground bg-muted/20 border-border',
}

export function SloScopeModal({ open, availableSlos, initialSelected, onConfirm, onCancel }: Props) {
  const [draft, setDraft] = useState<Set<string>>(new Set(initialSelected))
  const [query, setQuery] = useState('')

  /* eslint-disable react-hooks/set-state-in-effect -- reset on reopen */
  useEffect(() => {
    if (open) {
      setDraft(new Set(initialSelected))
      setQuery('')
    }
  }, [open, initialSelected])
  /* eslint-enable react-hooks/set-state-in-effect */

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return availableSlos
    return availableSlos.filter(
      s => s.displayName.toLowerCase().includes(q) || s.sloName.toLowerCase().includes(q),
    )
  }, [availableSlos, query])

  if (!open) return null

  function toggle(sloName: string) {
    setDraft(prev => {
      const next = new Set(prev)
      if (next.has(sloName)) next.delete(sloName)
      else next.add(sloName)
      return next
    })
  }

  function selectAll() {
    setDraft(new Set(availableSlos.map(s => s.sloName)))
  }

  function clearAll() {
    setDraft(new Set())
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="Select SLOs"
    >
      <div className="w-full max-w-md bg-popover border border-border rounded-xl shadow-2xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">Select SLOs</h2>
          <span className="text-xs text-muted-foreground">
            {draft.size} of {availableSlos.length} selected
          </span>
        </div>

        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search SLOs…"
          className="w-full px-2 py-1.5 text-sm bg-background border border-border rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
        />

        <div className="flex gap-2">
          <button
            type="button"
            onClick={selectAll}
            className="text-xs px-2 py-1 rounded border border-border text-muted-foreground hover:text-foreground"
          >
            Select all
          </button>
          <button
            type="button"
            onClick={clearAll}
            className="text-xs px-2 py-1 rounded border border-border text-muted-foreground hover:text-foreground"
          >
            Clear
          </button>
        </div>

        <ul className="max-h-[50vh] overflow-y-auto space-y-1">
          {filtered.length === 0 && (
            <li className="text-xs text-muted-foreground px-2 py-4 text-center">No matches.</li>
          )}
          {filtered.map(slo => {
            const checked = draft.has(slo.sloName)
            return (
              <li key={slo.sloName}>
                <label className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-muted/40 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggle(slo.sloName)}
                    className="rounded border-border accent-primary"
                  />
                  <span className="flex-1 text-sm text-foreground">{slo.displayName}</span>
                  <span
                    className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${
                      RESULT_BADGE_CLASS[slo.currentResult]
                    }`}
                  >
                    {slo.currentResult}
                  </span>
                </label>
              </li>
            )
          })}
        </ul>

        <div className="flex justify-end gap-2 pt-2 border-t border-border">
          <button
            type="button"
            onClick={onCancel}
            className="px-3 py-1.5 text-xs rounded border border-border text-muted-foreground hover:text-foreground"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm(draft)}
            className="px-3 py-1.5 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/80"
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/ui-test.sh --tail 20 src/features/evaluations/components/actions/slo-scope/SloScopeModal.test.tsx`

Expected: PASS on all 6 tests.

- [ ] **Step 5: Lint**

Run: `./scripts/ui-lint.sh --tail 10 src/features/evaluations/components/actions/slo-scope/SloScopeModal.tsx src/features/evaluations/components/actions/slo-scope/SloScopeModal.test.tsx`

Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add ui/src/features/evaluations/components/actions/slo-scope/SloScopeModal.tsx \
        ui/src/features/evaluations/components/actions/slo-scope/SloScopeModal.test.tsx
git commit -m "feat(ui): SloScopeModal search + checklist picker"
```

---

## Task 5: UI — `invalidate-column-queries` shared cache helper

**Why:** Every refactored action form needs to invalidate the same set of React Query keys after fan-out. Centralize it so they stay in sync.

**Files:**
- Create: `ui/src/features/evaluations/components/actions/invalidate-column-queries.ts`
- Create: `ui/src/features/evaluations/components/actions/invalidate-column-queries.test.ts`

- [ ] **Step 1: Write the failing test**

Write `ui/src/features/evaluations/components/actions/invalidate-column-queries.test.ts`:

```ts
import { describe, it, expect, vi } from 'vitest'
import type { QueryClient } from '@tanstack/react-query'
import { invalidateColumnQueries } from './invalidate-column-queries'
import { evaluationKeys } from '@/lib/queryKeys'

describe('invalidateColumnQueries', () => {
  it('invalidates detail, list, heatmap, and trend keys', () => {
    const invalidateQueries = vi.fn()
    const qc = { invalidateQueries } as unknown as QueryClient

    invalidateColumnQueries(qc, ['sloeval-a', 'sloeval-b'])

    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: evaluationKeys.detail('sloeval-a') })
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: evaluationKeys.detail('sloeval-b') })
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: evaluationKeys.all })
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: evaluationKeys.allHeatmaps })
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: evaluationKeys.allTrends })
  })

  it('handles empty id list by only invalidating list-level keys', () => {
    const invalidateQueries = vi.fn()
    const qc = { invalidateQueries } as unknown as QueryClient

    invalidateColumnQueries(qc, [])

    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: evaluationKeys.all })
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: evaluationKeys.allHeatmaps })
    expect(invalidateQueries).not.toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: evaluationKeys.detail(expect.any(String)) }),
    )
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./scripts/ui-test.sh --tail 20 src/features/evaluations/components/actions/invalidate-column-queries.test.ts`

Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the helper**

Write `ui/src/features/evaluations/components/actions/invalidate-column-queries.ts`:

```ts
import type { QueryClient } from '@tanstack/react-query'
import { evaluationKeys } from '@/lib/queryKeys'

export function invalidateColumnQueries(
  queryClient: QueryClient,
  affectedSloEvaluationIds: string[],
): void {
  for (const id of affectedSloEvaluationIds) {
    queryClient.invalidateQueries({ queryKey: evaluationKeys.detail(id) })
  }
  queryClient.invalidateQueries({ queryKey: evaluationKeys.all })
  queryClient.invalidateQueries({ queryKey: evaluationKeys.allNames })
  queryClient.invalidateQueries({ queryKey: evaluationKeys.allHeatmaps })
  queryClient.invalidateQueries({ queryKey: evaluationKeys.allTrends })
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./scripts/ui-test.sh --tail 20 src/features/evaluations/components/actions/invalidate-column-queries.test.ts`

Expected: PASS.

- [ ] **Step 5: Lint**

Run: `./scripts/ui-lint.sh --tail 10 src/features/evaluations/components/actions/invalidate-column-queries.ts`

Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add ui/src/features/evaluations/components/actions/invalidate-column-queries.ts \
        ui/src/features/evaluations/components/actions/invalidate-column-queries.test.ts
git commit -m "feat(ui): invalidateColumnQueries shared cache helper"
```

---

## Task 6: UI — `ActionPopover` container

**Files:**
- Create: `ui/src/features/evaluations/components/ActionPopover.tsx`
- Create: `ui/src/features/evaluations/components/ActionPopover.test.tsx`

- [ ] **Step 1: Check whether floating-ui is already in deps**

Run: `grep -n 'floating-ui' ui/package.json`

Expected: one or more entries like `"@floating-ui/react"` or `"@floating-ui/dom"`. If absent, add to `ui/package.json` dependencies via `cd ui && pnpm add @floating-ui/react` before Step 3. If the codebase uses a different positioning library (e.g. Radix Popover), use that instead — check `ui/src/components/ui/` for a `popover.tsx` primitive.

- [ ] **Step 2: Write the failing component test**

Write `ui/src/features/evaluations/components/ActionPopover.test.tsx`:

```tsx
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ActionPopover } from './ActionPopover'

afterEach(() => cleanup())

describe('ActionPopover', () => {
  it('renders nothing when open is false', () => {
    const { container } = render(
      <ActionPopover open={false} onClose={vi.fn()}>
        <div>form content</div>
      </ActionPopover>,
    )
    expect(container.textContent).toBe('')
  })

  it('renders children when open is true', () => {
    render(
      <ActionPopover open onClose={vi.fn()}>
        <div data-testid="form-slot">form content</div>
      </ActionPopover>,
    )
    expect(screen.getByTestId('form-slot')).toBeInTheDocument()
  })

  it('ESC closes the popover', async () => {
    const onClose = vi.fn()
    render(
      <ActionPopover open onClose={onClose}>
        <div>form content</div>
      </ActionPopover>,
    )
    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('ESC does nothing when closed', async () => {
    const onClose = vi.fn()
    render(
      <ActionPopover open={false} onClose={onClose}>
        <div>form content</div>
      </ActionPopover>,
    )
    await userEvent.keyboard('{Escape}')
    expect(onClose).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `./scripts/ui-test.sh --tail 20 src/features/evaluations/components/ActionPopover.test.tsx`

Expected: FAIL — component does not exist.

- [ ] **Step 4: Implement `ActionPopover`**

Write `ui/src/features/evaluations/components/ActionPopover.tsx` as a dumb container that wraps children. It knows nothing about forms — the parent (`AssetPanel`) constructs the form element and passes it in. This keeps ActionPopover decoupled from the form refactors in later tasks.

```tsx
import { useEffect, type ReactNode } from 'react'

interface Props {
  open: boolean
  onClose: () => void
  children: ReactNode
}

export function ActionPopover({ open, onClose, children }: Props) {
  useEffect(() => {
    if (!open) return
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="absolute right-0 top-full mt-2 z-30 w-[380px] bg-popover border border-border rounded-xl shadow-xl p-4"
      role="dialog"
      aria-modal="false"
    >
      {children}
    </div>
  )
}
```

Note: the parent (`AssetPanel`) wraps `EvaluationActionsButton` in a `relative` container so this `absolute` child positions correctly below-right of the button. Task 13 wires that up.

- [ ] **Step 5: Run tests to verify they pass**

Run: `./scripts/ui-test.sh --tail 20 src/features/evaluations/components/ActionPopover.test.tsx`

Expected: PASS on all 4 tests. No form imports, so no cross-file type churn.

- [ ] **Step 6: Lint**

Run: `./scripts/ui-lint.sh --tail 10 src/features/evaluations/components/ActionPopover.tsx src/features/evaluations/components/ActionPopover.test.tsx`

Expected: No errors.

- [ ] **Step 7: Commit**

```bash
git add ui/src/features/evaluations/components/ActionPopover.tsx \
        ui/src/features/evaluations/components/ActionPopover.test.tsx
git commit -m "feat(ui): ActionPopover container"
```

---

## Task 7: UI — Refactor `OverrideForm` to scope + radio + fan-out

**Why this form first:** It's the most complex change (radio replaces smart pass/fail branching + fan-out logic pattern). Once this is working, the other forms follow the same shape with minor variations.

**Files:**
- Modify: `ui/src/features/evaluations/components/actions/OverrideForm.tsx`
- Modify: `ui/src/features/evaluations/components/actions/OverrideForm.test.tsx`

- [ ] **Step 1: Read the current test file to understand existing coverage**

Run: `cat ui/src/features/evaluations/components/actions/OverrideForm.test.tsx`

Expected: you'll see mocks for `useOverrideStatus` and tests that cover the current pass↔fail branching.

- [ ] **Step 2: Write the failing tests for the new scope+radio behavior**

Replace the body of `ui/src/features/evaluations/components/actions/OverrideForm.test.tsx` with:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { OverrideForm } from './OverrideForm'
import type { SloScopeResult } from './slo-scope/types'

const overrideStatusSpy = vi.fn()

vi.mock('../../api', async () => {
  const actual = await vi.importActual<typeof import('../../api')>('../../api')
  return {
    ...actual,
    overrideStatus: (...args: unknown[]) => overrideStatusSpy(...args),
  }
})

function makeScope(overrides: Partial<SloScopeResult> = {}): SloScopeResult {
  return {
    availableSlos: [
      { sloName: 'a', displayName: 'A', sloEvaluationId: 'eid-a', currentResult: 'fail' },
      { sloName: 'b', displayName: 'B', sloEvaluationId: 'eid-b', currentResult: 'pass' },
      { sloName: 'c', displayName: 'C', sloEvaluationId: 'eid-c', currentResult: 'warning' },
    ],
    selected: new Set(['a', 'b', 'c']),
    setSelected: vi.fn(),
    reset: vi.fn(),
    lookupEvalId: (sloName: string) => ({ a: 'eid-a', b: 'eid-b', c: 'eid-c' })[sloName],
    ...overrides,
  }
}

let queryClient: QueryClient
beforeEach(() => {
  overrideStatusSpy.mockReset()
  overrideStatusSpy.mockResolvedValue({ ok: true })
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
})
afterEach(() => {
  queryClient.cancelQueries()
  queryClient.clear()
  cleanup()
})

function renderForm(scope: SloScopeResult, onComplete = vi.fn()) {
  return render(
    <QueryClientProvider client={queryClient}>
      <OverrideForm scope={scope} columnEvalId="col-1" onComplete={onComplete} />
    </QueryClientProvider>,
  )
}

describe('OverrideForm (multi-SLO)', () => {
  it('radio target fans out to all selected SLOs', async () => {
    const user = userEvent.setup()
    renderForm(makeScope())
    await user.click(screen.getByRole('radio', { name: /fail/i }))
    await user.type(screen.getByPlaceholderText(/reason/i), 'noise')
    await user.type(screen.getByPlaceholderText(/author/i), 'domik')
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(overrideStatusSpy).toHaveBeenCalledTimes(1))
    // All 3 selected SLOs with currentResult !== fail get a call: a is already fail (skip), b=pass → 1 call, c=warning → 1 call
    // After no-op filter, b and c call. Assert:
    await waitFor(() => expect(overrideStatusSpy).toHaveBeenCalledTimes(2))
    const calls = overrideStatusSpy.mock.calls.map(c => c[0])
    expect(calls).toEqual(expect.arrayContaining(['eid-b', 'eid-c']))
    expect(calls).not.toContain('eid-a')
  })

  it('skipped SLOs are reported in the result list', async () => {
    const user = userEvent.setup()
    renderForm(makeScope())
    await user.click(screen.getByRole('radio', { name: /pass/i }))
    await user.type(screen.getByPlaceholderText(/reason/i), 'manual')
    await user.type(screen.getByPlaceholderText(/author/i), 'domik')
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(screen.getByText(/1 skipped/i)).toBeInTheDocument())
  })

  it('partial failure surfaces the Retry failed button', async () => {
    overrideStatusSpy.mockImplementation(async (evalId: string) => {
      if (evalId === 'eid-b') throw new Error('conflict')
      return { ok: true }
    })
    const user = userEvent.setup()
    renderForm(makeScope())
    await user.click(screen.getByRole('radio', { name: /fail/i }))
    await user.type(screen.getByPlaceholderText(/reason/i), 'noise')
    await user.type(screen.getByPlaceholderText(/author/i), 'domik')
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /retry failed/i })).toBeInTheDocument())
    expect(screen.getByText(/1 failed/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `./scripts/ui-test.sh --tail 40 src/features/evaluations/components/actions/OverrideForm.test.tsx`

Expected: FAIL — `OverrideForm` still has the old `evaluationId` prop and single-row logic.

- [ ] **Step 4: Rewrite `OverrideForm`**

Replace `ui/src/features/evaluations/components/actions/OverrideForm.tsx` with:

```tsx
import { useState, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { overrideStatus } from '../../api'
import { ActionFormShell } from './ActionFormShell'
import { ReasonAuthorFields } from './ReasonAuthorFields'
import { useReasonAuthor } from './useReasonAuthor'
import { SloScopeField } from './slo-scope/SloScopeField'
import { SloScopeModal } from './slo-scope/SloScopeModal'
import { invalidateColumnQueries } from './invalidate-column-queries'
import type { SloScopeResult } from './slo-scope/types'

type Outcome = 'pass' | 'warning' | 'fail'

interface Props {
  scope: SloScopeResult
  columnEvalId: string
  onComplete: () => void
}

interface RowResult {
  sloName: string
  sloEvaluationId: string
  status: 'success' | 'skipped' | 'failed'
  error?: string
}

const ACTION_DEF = {
  label: 'Override result',
  description: 'Override the current result for selected SLOs.',
  accentColor: 'var(--action-primary)',
  accentBorder: 'border-action-primary-border/25',
  accentText: 'text-action-primary',
  confirmClasses: 'bg-action-primary-bg hover:bg-action-primary-bg/80',
}

export function OverrideForm({ scope, columnEvalId, onComplete }: Props) {
  const { reason, setReason, author, setAuthor, canConfirm: reasonAuthorValid } = useReasonAuthor()
  const [target, setTarget] = useState<Outcome>('pass')
  const [pickerOpen, setPickerOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [results, setResults] = useState<RowResult[] | null>(null)
  const queryClient = useQueryClient()

  const canConfirm = reasonAuthorValid && scope.selected.size > 0 && !submitting
  void columnEvalId // reserved for future cache-scoping logic

  const handleConfirm = useCallback(async () => {
    if (!canConfirm) return
    setSubmitting(true)

    const targets = [...scope.selected].map(sloName => {
      const option = scope.availableSlos.find(s => s.sloName === sloName)
      return {
        sloName,
        sloEvaluationId: option?.sloEvaluationId ?? '',
        currentResult: option?.currentResult,
      }
    })

    const rowResults: RowResult[] = []
    await Promise.all(
      targets.map(async t => {
        if (t.currentResult === target) {
          rowResults.push({ sloName: t.sloName, sloEvaluationId: t.sloEvaluationId, status: 'skipped' })
          return
        }
        try {
          await overrideStatus(t.sloEvaluationId, { outcome: target, reason, author })
          rowResults.push({ sloName: t.sloName, sloEvaluationId: t.sloEvaluationId, status: 'success' })
        } catch (err) {
          rowResults.push({
            sloName: t.sloName,
            sloEvaluationId: t.sloEvaluationId,
            status: 'failed',
            error: err instanceof Error ? err.message : 'unknown error',
          })
        }
      }),
    )

    invalidateColumnQueries(
      queryClient,
      rowResults.filter(r => r.status === 'success').map(r => r.sloEvaluationId),
    )
    setResults(rowResults)
    setSubmitting(false)
  }, [canConfirm, scope, target, reason, author, queryClient])

  if (results) {
    const successCount = results.filter(r => r.status === 'success').length
    const skippedCount = results.filter(r => r.status === 'skipped').length
    const failedCount = results.filter(r => r.status === 'failed').length
    const failedNames = results.filter(r => r.status === 'failed').map(r => r.sloName)

    return (
      <ActionFormShell
        actionDef={ACTION_DEF}
        onClose={onComplete}
        onConfirm={onComplete}
        canConfirm={false}
        isPending={false}
        hideButtons
      >
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            {successCount} succeeded · {failedCount} failed · {skippedCount} skipped
          </p>
          <ul className="max-h-48 overflow-y-auto space-y-1">
            {results.map(r => (
              <li
                key={r.sloEvaluationId}
                className={`flex justify-between text-xs px-2 py-1 rounded ${
                  r.status === 'success'
                    ? 'bg-pass/10 text-pass'
                    : r.status === 'skipped'
                      ? 'bg-muted/20 text-muted-foreground'
                      : 'bg-fail/10 text-fail'
                }`}
              >
                <span>{r.sloName}</span>
                <span>{r.status === 'failed' ? r.error : r.status}</span>
              </li>
            ))}
          </ul>
          <div className="flex justify-end gap-2 pt-2">
            {failedCount > 0 && (
              <button
                type="button"
                onClick={() => {
                  scope.setSelected(new Set(failedNames))
                  setResults(null)
                }}
                className="px-3 py-1.5 text-xs rounded border border-border text-muted-foreground hover:text-foreground"
              >
                Retry failed
              </button>
            )}
            <button
              type="button"
              onClick={onComplete}
              className="px-3 py-1.5 text-xs rounded bg-primary text-primary-foreground"
            >
              Close
            </button>
          </div>
        </div>
      </ActionFormShell>
    )
  }

  return (
    <ActionFormShell
      actionDef={ACTION_DEF}
      onClose={onComplete}
      onConfirm={handleConfirm}
      canConfirm={canConfirm}
      isPending={submitting}
    >
      <SloScopeField scope={scope} onOpenPicker={() => setPickerOpen(true)} />
      <SloScopeModal
        open={pickerOpen}
        availableSlos={scope.availableSlos}
        initialSelected={scope.selected}
        onConfirm={next => {
          scope.setSelected(next)
          setPickerOpen(false)
        }}
        onCancel={() => setPickerOpen(false)}
      />
      <fieldset className="space-y-1">
        <legend className="text-xs text-muted-foreground mb-1">Set result to</legend>
        <div className="flex gap-3">
          {(['pass', 'warning', 'fail'] as const).map(opt => (
            <label key={opt} className="flex items-center gap-1.5 text-xs text-foreground">
              <input
                type="radio"
                name="override-target"
                value={opt}
                checked={target === opt}
                onChange={() => setTarget(opt)}
                className="accent-primary"
              />
              {opt}
            </label>
          ))}
        </div>
      </fieldset>
      <ReasonAuthorFields
        reason={reason}
        onReasonChange={setReason}
        author={author}
        onAuthorChange={setAuthor}
      />
    </ActionFormShell>
  )
}
```

**Note on `overrideStatus` API signature:** if the existing `overrideStatus` function in `ui/src/features/evaluations/api.ts` expects a different shape (e.g. named params), adapt the call at the `await overrideStatus(...)` line. Run `grep -n 'export.*overrideStatus' ui/src/features/evaluations/api.ts` to confirm. The existing hook passes `(evalId, input)` per `hooks.ts:162-173`, so that shape is preserved.

- [ ] **Step 5: Run tests to verify they pass**

Run: `./scripts/ui-test.sh --tail 30 src/features/evaluations/components/actions/OverrideForm.test.tsx`

Expected: PASS on all 3 tests.

- [ ] **Step 6: Lint + typecheck**

Run: `./scripts/ui-lint.sh --tail 10 src/features/evaluations/components/actions/OverrideForm.tsx`

Run: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json`

Expected: No errors. Fix any cross-file type mismatches (`ActionPopover` props vs new `OverrideForm` props) before proceeding.

- [ ] **Step 7: Commit**

```bash
git add ui/src/features/evaluations/components/actions/OverrideForm.tsx \
        ui/src/features/evaluations/components/actions/OverrideForm.test.tsx
git commit -m "feat(ui): OverrideForm multi-SLO scope + radio target"
```

---

## Task 8: UI — Refactor `InvalidateForm`

**Pattern note:** Follows the same shape as `OverrideForm` but without a radio target. Scope filter is `'not-invalidated'`.

**Files:**
- Modify: `ui/src/features/evaluations/components/actions/InvalidateForm.tsx`
- Modify: `ui/src/features/evaluations/components/actions/InvalidateForm.test.tsx`

- [ ] **Step 1: Write failing scope+fan-out tests**

Replace the body of `ui/src/features/evaluations/components/actions/InvalidateForm.test.tsx` with tests mirroring `OverrideForm.test.tsx`, but invoke `invalidateEvaluation` instead of `overrideStatus` and omit the radio assertion:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { InvalidateForm } from './InvalidateForm'
import type { SloScopeResult } from './slo-scope/types'

const invalidateSpy = vi.fn()
vi.mock('../../api', async () => {
  const actual = await vi.importActual<typeof import('../../api')>('../../api')
  return {
    ...actual,
    invalidateEvaluation: (...args: unknown[]) => invalidateSpy(...args),
  }
})

function makeScope(): SloScopeResult {
  return {
    availableSlos: [
      { sloName: 'a', displayName: 'A', sloEvaluationId: 'eid-a', currentResult: 'pass' },
      { sloName: 'b', displayName: 'B', sloEvaluationId: 'eid-b', currentResult: 'fail' },
    ],
    selected: new Set(['a', 'b']),
    setSelected: vi.fn(),
    reset: vi.fn(),
    lookupEvalId: (sn: string) => ({ a: 'eid-a', b: 'eid-b' })[sn],
  }
}

let queryClient: QueryClient
beforeEach(() => {
  invalidateSpy.mockReset()
  invalidateSpy.mockResolvedValue({ ok: true })
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
})
afterEach(() => {
  queryClient.cancelQueries()
  queryClient.clear()
  cleanup()
})

describe('InvalidateForm (multi-SLO)', () => {
  it('fans out to all selected SLOs', async () => {
    const user = userEvent.setup()
    render(
      <QueryClientProvider client={queryClient}>
        <InvalidateForm scope={makeScope()} columnEvalId="col-1" onComplete={vi.fn()} />
      </QueryClientProvider>,
    )
    await user.type(screen.getByPlaceholderText(/note/i), 'bad data')
    await user.type(screen.getByPlaceholderText(/author/i), 'domik')
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(invalidateSpy).toHaveBeenCalledTimes(2))
    const calls = invalidateSpy.mock.calls.map(c => c[0])
    expect(calls).toEqual(expect.arrayContaining(['eid-a', 'eid-b']))
  })
})
```

- [ ] **Step 2: Run failing tests**

Run: `./scripts/ui-test.sh --tail 20 src/features/evaluations/components/actions/InvalidateForm.test.tsx`

Expected: FAIL — `InvalidateForm` still takes `evaluationId`.

- [ ] **Step 3: Rewrite `InvalidateForm`**

Replace `ui/src/features/evaluations/components/actions/InvalidateForm.tsx` with the same pattern as `OverrideForm` but without the radio fieldset and without the no-op skip filter. The mutation call becomes:

```tsx
await invalidateEvaluation(t.sloEvaluationId, note)
```

Copy the full `OverrideForm.tsx` body from Task 7, then:
- Remove the `target` state + radio fieldset.
- Replace `useReasonAuthor` with a simple `note` + `author` state pair (grep `ui/src/features/evaluations/components/actions/InvalidateForm.tsx` for the current field names if `note` is wrong).
- Replace `overrideStatus(...)` call with `invalidateEvaluation(t.sloEvaluationId, note)`.
- Replace `ACTION_DEF` with the current `INVALIDATE` definition from the old form.
- Remove the "skipped" path — invalidation doesn't have a no-op check.

- [ ] **Step 4: Run tests**

Run: `./scripts/ui-test.sh --tail 20 src/features/evaluations/components/actions/InvalidateForm.test.tsx`

Expected: PASS.

- [ ] **Step 5: Lint**

Run: `./scripts/ui-lint.sh --tail 10 src/features/evaluations/components/actions/InvalidateForm.tsx`

Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add ui/src/features/evaluations/components/actions/InvalidateForm.tsx \
        ui/src/features/evaluations/components/actions/InvalidateForm.test.tsx
git commit -m "feat(ui): InvalidateForm multi-SLO fan-out"
```

---

## Task 9: UI — Refactor `RestoreForm`

**Pattern note:** Same as `InvalidateForm` but scope filter is `'invalidated-only'` and the API call is `restoreEvaluation(sloEvaluationId)`. No form fields other than scope.

**Files:**
- Modify: `ui/src/features/evaluations/components/actions/RestoreForm.tsx`
- Modify: `ui/src/features/evaluations/components/actions/RestoreForm.test.tsx`

- [ ] **Step 1: Write failing scope+fan-out test**

Mirror the `InvalidateForm.test.tsx` above, with `restoreEvaluation` as the spied function, scope populated with `currentResult: 'invalidated'` rows, and no note/author input. Spy signature: `restoreEvaluation(sloEvaluationId: string)`.

- [ ] **Step 2: Run failing test**

Expected: FAIL.

- [ ] **Step 3: Rewrite `RestoreForm`**

Copy `InvalidateForm.tsx` shape, remove the note field, replace `invalidateEvaluation(sloEvaluationId, note)` with `restoreEvaluation(sloEvaluationId)`, and use the current `RESTORE` `ACTION_DEF`.

- [ ] **Step 4: Run tests**

Expected: PASS.

- [ ] **Step 5: Lint**

Run: `./scripts/ui-lint.sh --tail 10 src/features/evaluations/components/actions/RestoreForm.tsx`

- [ ] **Step 6: Commit**

```bash
git add ui/src/features/evaluations/components/actions/RestoreForm.tsx \
        ui/src/features/evaluations/components/actions/RestoreForm.test.tsx
git commit -m "feat(ui): RestoreForm multi-SLO fan-out"
```

---

## Task 10: UI — Refactor `BaselineForm` with per-SLO pin-conflict handling

**Pattern note:** Fan-out like `OverrideForm`, but pin conflicts are domain-specific. Confirm button shows an inline count warning when scope > 5.

**Files:**
- Modify: `ui/src/features/evaluations/components/actions/BaselineForm.tsx`
- Modify: `ui/src/features/evaluations/components/actions/BaselineForm.test.tsx`

- [ ] **Step 1: Write failing tests**

Write tests covering: (a) fan-out for N selected SLOs, (b) 409 pin-conflict response rendered in result list, (c) inline count warning for scope > 5.

```tsx
// ui/src/features/evaluations/components/actions/BaselineForm.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BaselineForm } from './BaselineForm'
import type { SloScopeResult } from './slo-scope/types'

const pinSpy = vi.fn()
vi.mock('../../api', async () => {
  const actual = await vi.importActual<typeof import('../../api')>('../../api')
  return {
    ...actual,
    pinBaseline: (...args: unknown[]) => pinSpy(...args),
  }
})

function makeScope(count: number): SloScopeResult {
  const slos = Array.from({ length: count }, (_, i) => ({
    sloName: `slo-${i}`,
    displayName: `SLO ${i}`,
    sloEvaluationId: `eid-${i}`,
    currentResult: 'pass' as const,
  }))
  return {
    availableSlos: slos,
    selected: new Set(slos.map(s => s.sloName)),
    setSelected: vi.fn(),
    reset: vi.fn(),
    lookupEvalId: (sn: string) => slos.find(s => s.sloName === sn)?.sloEvaluationId,
  }
}

let queryClient: QueryClient
beforeEach(() => {
  pinSpy.mockReset()
  pinSpy.mockResolvedValue({ ok: true })
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
})
afterEach(() => {
  queryClient.cancelQueries()
  queryClient.clear()
  cleanup()
})

function renderForm(scope: SloScopeResult) {
  return render(
    <QueryClientProvider client={queryClient}>
      <BaselineForm scope={scope} columnEvalId="col-1" onComplete={vi.fn()} />
    </QueryClientProvider>,
  )
}

describe('BaselineForm (multi-SLO)', () => {
  it('fans out to all selected SLOs', async () => {
    const user = userEvent.setup()
    renderForm(makeScope(3))
    await user.type(screen.getByPlaceholderText(/reason/i), 'release')
    await user.type(screen.getByPlaceholderText(/author/i), 'domik')
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(pinSpy).toHaveBeenCalledTimes(3))
  })

  it('shows the inline count warning when scope > 5', () => {
    renderForm(makeScope(10))
    expect(screen.getByText(/10 baseline pins/i)).toBeInTheDocument()
  })

  it('does not show the count warning when scope <= 5', () => {
    renderForm(makeScope(5))
    expect(screen.queryByText(/baseline pins/i)).not.toBeInTheDocument()
  })

  it('409 pin conflict shows up in the result list', async () => {
    pinSpy.mockImplementation(async (evalId: string) => {
      if (evalId === 'eid-1') {
        const err = new Error('conflict')
        ;(err as Error & { status?: number }).status = 409
        throw err
      }
      return { ok: true }
    })
    const user = userEvent.setup()
    renderForm(makeScope(3))
    await user.type(screen.getByPlaceholderText(/reason/i), 'release')
    await user.type(screen.getByPlaceholderText(/author/i), 'domik')
    await user.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(screen.getByText(/conflict/i)).toBeInTheDocument())
  })
})
```

- [ ] **Step 2: Run failing tests**

Run: `./scripts/ui-test.sh --tail 30 src/features/evaluations/components/actions/BaselineForm.test.tsx`

Expected: FAIL.

- [ ] **Step 3: Rewrite `BaselineForm`**

Use the same pattern as `OverrideForm`:
- `ACTION_DEF` = the existing BaselineForm `ACTION_DEF`.
- Form fields: `reason` + `author` via `useReasonAuthor`.
- Above the confirm button (still inside the form body, not the shell), add:

```tsx
{scope.selected.size > 5 && (
  <p className="text-xs text-warning">
    This will create {scope.selected.size} baseline pins.
  </p>
)}
```

- Fan-out mutation: `pinBaseline(t.sloEvaluationId, { reason, author })` per selected SLO.
- Error handling: the result list treats 409 conflicts as `status: 'failed'` with `error: 'conflict'` (or the raw message) so the test picks it up naturally.

- [ ] **Step 4: Run tests**

Expected: PASS.

- [ ] **Step 5: Lint**

Run: `./scripts/ui-lint.sh --tail 10 src/features/evaluations/components/actions/BaselineForm.tsx`

- [ ] **Step 6: Commit**

```bash
git add ui/src/features/evaluations/components/actions/BaselineForm.tsx \
        ui/src/features/evaluations/components/actions/BaselineForm.test.tsx
git commit -m "feat(ui): BaselineForm multi-SLO pins + conflict handling"
```

---

## Task 11: UI — Refactor `ReEvaluateForm` to use `slo_names` list

**Pattern note:** No fan-out — one HTTP call with `slo_names` populated from `scope.selected`. The domain input type + mapper also change.

**Files:**
- Modify: `ui/src/features/evaluations/domain.ts`
- Modify: `ui/src/features/evaluations/mappers.ts`
- Modify: `ui/src/features/evaluations/components/actions/ReEvaluateForm.tsx`
- Modify: `ui/src/features/evaluations/components/actions/ReEvaluateForm.test.tsx`

- [ ] **Step 1: Read the current `ReEvaluateInput` and its mapper**

Run: `grep -n 'ReEvaluateInput\|reEvaluateInputToDto\|slo_name\|sloName' ui/src/features/evaluations/domain.ts ui/src/features/evaluations/mappers.ts`

Note: the domain type currently has `sloName: string | null`. The mapper converts to DTO with `slo_name`. You'll add a `sloNames: string[] | null` field and `slo_names` in the DTO side.

- [ ] **Step 2: Update `ReEvaluateInput` in domain.ts**

Add `sloNames: string[] | null` to `ReEvaluateInput`:

```ts
export interface ReEvaluateInput {
  assetName: string
  sloName: string | null
  sloNames: string[] | null
  mode: ReEvaluateMode
  sloVersion: number | null
  dryRun: boolean
  pinStrategy: 'skip_to_pin' | 'ignore_pin' | null
}
```

- [ ] **Step 3: Update the mapper**

In `ui/src/features/evaluations/mappers.ts`, add `slo_names` to the DTO output:

```ts
export function reEvaluateInputToDto(input: ReEvaluateInput): ReEvaluateRequestDto {
  return {
    asset_name: input.assetName,
    slo_name: input.sloName,
    slo_names: input.sloNames,
    // ... rest unchanged
  }
}
```

If the DTO type (`ReEvaluateRequestDto`) is defined by generated OpenAPI bindings, check `ui/src/generated/api.ts` — you may need to re-run codegen or manually add `slo_names` temporarily. Run `grep -n 'ReEvaluateRequest' ui/src/generated/api.ts` to find it. If codegen is available: `just codegen`. If not, edit the generated file directly with a comment `// TODO: regen from OpenAPI`.

- [ ] **Step 4: Write failing test for `ReEvaluateForm` + scope**

Replace the body of `ui/src/features/evaluations/components/actions/ReEvaluateForm.test.tsx` with (or add alongside existing tests):

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReEvaluateForm } from './ReEvaluateForm'
import type { SloScopeResult } from './slo-scope/types'

const reEvalSpy = vi.fn()
vi.mock('../../api', async () => {
  const actual = await vi.importActual<typeof import('../../api')>('../../api')
  return {
    ...actual,
    reEvaluate: (...args: unknown[]) => reEvalSpy(...args),
  }
})

function makeScope(): SloScopeResult {
  return {
    availableSlos: [
      { sloName: 'latency-slo', displayName: 'Latency', sloEvaluationId: 'e1', currentResult: 'fail' },
      { sloName: 'avail-slo', displayName: 'Availability', sloEvaluationId: 'e2', currentResult: 'pass' },
    ],
    selected: new Set(['latency-slo']),
    setSelected: vi.fn(),
    reset: vi.fn(),
    lookupEvalId: (sn: string) => ({ 'latency-slo': 'e1', 'avail-slo': 'e2' })[sn],
  }
}

let queryClient: QueryClient
beforeEach(() => {
  reEvalSpy.mockReset()
  reEvalSpy.mockResolvedValue({ affectedEvaluations: 1, sloVersionUsed: 3, results: [] })
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
})
afterEach(() => {
  queryClient.cancelQueries()
  queryClient.clear()
  cleanup()
})

describe('ReEvaluateForm (scoped)', () => {
  it('sends slo_names list from selected scope', async () => {
    const user = userEvent.setup()
    render(
      <QueryClientProvider client={queryClient}>
        <ReEvaluateForm
          scope={makeScope()}
          columnEvalId="col-1"
          assetName="checkout-api"
          onComplete={vi.fn()}
        />
      </QueryClientProvider>,
    )
    await user.click(screen.getByLabelText(/run from last baseline/i))
    await user.click(screen.getByRole('button', { name: /run/i }))
    await waitFor(() => expect(reEvalSpy).toHaveBeenCalledOnce())
    const payload = reEvalSpy.mock.calls[0][0]
    expect(payload.sloNames).toEqual(['latency-slo'])
    expect(payload.sloName).toBeNull()
  })
})
```

- [ ] **Step 5: Run failing test**

Run: `./scripts/ui-test.sh --tail 30 src/features/evaluations/components/actions/ReEvaluateForm.test.tsx`

Expected: FAIL — form still takes `sloName`.

- [ ] **Step 6: Rewrite `ReEvaluateForm`**

Rewrite `ui/src/features/evaluations/components/actions/ReEvaluateForm.tsx`:

- Replace the `assetName` + `sloName` props with `scope: SloScopeResult` + `columnEvalId: string` + `assetName: string`.
- Add `<SloScopeField>` + `<SloScopeModal>` at the top, same pattern as `OverrideForm`.
- Build the mutation payload with `sloNames: [...scope.selected]` and `sloName: null`.
- Keep the existing from-date / from-baseline / pin-conflict affordances. They are unrelated to scope and shouldn't regress.

The full rewrite is structurally close to the current `ReEvaluateForm.tsx` — keep the result view and pin-conflict handling intact, swap the input construction:

```ts
const mode: ReEvaluateMode = fromBaseline
  ? { kind: 'baseline' }
  : { kind: 'date', fromDate: new Date(fromDate).toISOString() }
reEvaluate.mutate(
  {
    assetName,
    sloName: null,
    sloNames: [...scope.selected],
    mode,
    sloVersion: null,
    dryRun: false,
    pinStrategy: pinStrategy ?? null,
  },
  { ... },
)
```

- [ ] **Step 7: Run tests**

Expected: PASS.

- [ ] **Step 8: Lint + typecheck**

Run: `./scripts/ui-lint.sh --tail 10 src/features/evaluations/components/actions/ReEvaluateForm.tsx src/features/evaluations/domain.ts src/features/evaluations/mappers.ts`

Run: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json`

Expected: No errors.

- [ ] **Step 9: Commit**

```bash
git add ui/src/features/evaluations/components/actions/ReEvaluateForm.tsx \
        ui/src/features/evaluations/components/actions/ReEvaluateForm.test.tsx \
        ui/src/features/evaluations/domain.ts \
        ui/src/features/evaluations/mappers.ts \
        ui/src/generated/api.ts
git commit -m "feat(ui): ReEvaluateForm sends slo_names list from scope"
```

---

## Task 12: UI — Update `EvaluationActions` menu (collapse override + availability rules)

**Files:**
- Modify: `ui/src/features/evaluations/components/EvaluationActions.tsx`
- Modify: `ui/src/features/evaluations/components/EvaluationActions.test.tsx`

- [ ] **Step 1: Write failing tests for the collapsed override and disabled items**

Update `ui/src/features/evaluations/components/EvaluationActions.test.tsx`:

```tsx
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EvaluationActionsButton } from './EvaluationActions'

afterEach(() => cleanup())

describe('EvaluationActionsButton menu', () => {
  it('shows a single "Override result..." item instead of pass/fail branching', async () => {
    const user = userEvent.setup()
    render(
      <EvaluationActionsButton
        currentResult="pass"
        allRowsInvalidated={false}
        noRowsInvalidated={false}
        activeAction={null}
        onSelectAction={vi.fn()}
      />,
    )
    await user.click(screen.getByRole('button', { name: /actions/i }))
    expect(screen.getByRole('menuitem', { name: /override result/i })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /mark as successful/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /mark as failure/i })).not.toBeInTheDocument()
  })

  it('disables Invalidate when all rows are already invalidated', async () => {
    const user = userEvent.setup()
    render(
      <EvaluationActionsButton
        currentResult="pass"
        allRowsInvalidated
        noRowsInvalidated={false}
        activeAction={null}
        onSelectAction={vi.fn()}
      />,
    )
    await user.click(screen.getByRole('button', { name: /actions/i }))
    const invalidate = screen.getByRole('menuitem', { name: /invalidate/i })
    expect(invalidate).toHaveAttribute('aria-disabled', 'true')
  })

  it('disables Restore when no rows are invalidated', async () => {
    const user = userEvent.setup()
    render(
      <EvaluationActionsButton
        currentResult="pass"
        allRowsInvalidated={false}
        noRowsInvalidated
        activeAction={null}
        onSelectAction={vi.fn()}
      />,
    )
    await user.click(screen.getByRole('button', { name: /actions/i }))
    const restore = screen.queryByRole('menuitem', { name: /restore/i })
    // When no rows are invalidated, Restore may be absent or disabled — accept either
    if (restore) {
      expect(restore).toHaveAttribute('aria-disabled', 'true')
    }
  })
})
```

- [ ] **Step 2: Run failing tests**

Expected: FAIL — component still has old props + override branching.

- [ ] **Step 3: Update `EvaluationActions.tsx`**

Apply these changes to `ui/src/features/evaluations/components/EvaluationActions.tsx`:

1. Remove `OVERRIDE_TO_PASS` and `OVERRIDE_TO_FAIL`, replace with a single:

```tsx
const OVERRIDE: ActionDef = {
  kind: 'override',
  label: 'Override result',
  description: 'Change the result for selected SLOs (pass / warning / fail).',
  accentColor: 'var(--action-primary)',
  accentBorder: 'border-action-primary-border/25',
  accentText: 'text-action-primary',
  confirmClasses: 'bg-action-primary-bg hover:bg-action-primary-bg/80',
}
```

2. Change `getActions(currentResult)` to take the new availability flags and return with per-item disabled state:

```tsx
interface ActionAvailability {
  currentResult: string
  allRowsInvalidated: boolean
  noRowsInvalidated: boolean
}

function getActions({ allRowsInvalidated, noRowsInvalidated }: ActionAvailability): (ActionDef & { disabled?: boolean; disabledReason?: string })[] {
  return [
    {
      ...INVALIDATE,
      disabled: allRowsInvalidated,
      disabledReason: 'all SLOs in this column are already invalidated',
    },
    OVERRIDE,
    BASELINE,
    RE_EVALUATE,
    // Restore appears only when at least one row is invalidated
    ...(noRowsInvalidated ? [] : [RESTORE]),
  ]
}
```

3. Update the `EvaluationActionsButton` props:

```tsx
interface ButtonProps {
  currentResult: string
  allRowsInvalidated: boolean
  noRowsInvalidated: boolean
  activeAction: ActionKind | null
  onSelectAction: (kind: ActionKind) => void
  onAddNote?: () => void
}
```

4. When rendering menu items, add `aria-disabled` and prevent the click when `disabled`:

```tsx
<button
  key={action.kind}
  onClick={() => { if (!action.disabled) { onSelectAction(action.kind); setMenuOpen(false) } }}
  aria-disabled={action.disabled}
  className={`flex items-start gap-3 w-full text-left px-3 py-2.5 transition-colors ${
    action.disabled ? 'opacity-40 cursor-not-allowed' : 'hover:bg-accent'
  }`}
  role="menuitem"
  aria-label={action.disabledReason ?? action.description}
>
  ...
</button>
```

5. Remove `EvaluationActionForm` entirely — `AssetPanel` (Task 13) will use `ActionPopover` directly. Leave the button component + action definitions.

- [ ] **Step 4: Run tests**

Expected: PASS.

- [ ] **Step 5: Lint**

Run: `./scripts/ui-lint.sh --tail 10 src/features/evaluations/components/EvaluationActions.tsx src/features/evaluations/components/EvaluationActions.test.tsx`

Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add ui/src/features/evaluations/components/EvaluationActions.tsx \
        ui/src/features/evaluations/components/EvaluationActions.test.tsx
git commit -m "feat(ui): collapse Override menu item + add availability rules"
```

---

## Task 13: UI — Wire `AssetPanel` to popover + `useSloScope`

**Files:**
- Modify: `ui/src/features/navigator/components/AssetPanel.tsx`
- Modify: `ui/src/pages/EvaluationDetailPage.tsx` (if it also mounts `EvaluationActionForm`)
- Modify: `ui/src/features/navigator/components/AssetPanel.test.tsx`

- [ ] **Step 1: Add failing tests for single-SLO vs ALL default scope**

First, read the existing file to understand the mock pattern it uses for `useMetricHeatmap`, `useAssetEvaluations`, and any wrapping providers:

Run: `cat ui/src/features/navigator/components/AssetPanel.test.tsx`

Then add two new tests at the bottom of the existing `describe` block. Use `vi.mock` to stub each form with a component that records its `scope.selected` via a `vi.fn` so assertions are possible:

```tsx
// Top of file — alongside existing mocks
const overrideFormSpy = vi.fn()
vi.mock('@/features/evaluations/components/actions/OverrideForm', () => ({
  OverrideForm: (props: { scope: { selected: Set<string> } }) => {
    overrideFormSpy(props)
    return <div data-testid="override-form-stub">override-stub</div>
  },
}))
// Add identical stubs for the other four forms so ActionPopover can render them
vi.mock('@/features/evaluations/components/actions/InvalidateForm', () => ({
  InvalidateForm: () => <div>invalidate-stub</div>,
}))
vi.mock('@/features/evaluations/components/actions/RestoreForm', () => ({
  RestoreForm: () => <div>restore-stub</div>,
}))
vi.mock('@/features/evaluations/components/actions/BaselineForm', () => ({
  BaselineForm: () => <div>baseline-stub</div>,
}))
vi.mock('@/features/evaluations/components/actions/ReEvaluateForm', () => ({
  ReEvaluateForm: () => <div>reevaluate-stub</div>,
}))

beforeEach(() => overrideFormSpy.mockReset())

// Inside the existing describe block
it('clicking the column header then opening Override scopes to ALL SLOs', async () => {
  // Use existing setup to render AssetPanel with a multi-SLO heatmap mock.
  // Find the slot/column header (not a specific SLO cell), click it.
  // Then click the Actions button, then the Override menu item.
  // Assert the OverrideForm stub was called with scope containing all SLO names.
  const user = userEvent.setup()
  renderAssetPanelWithMultiSloHeatmap()  // reuse existing helper or inline the mock
  await user.click(screen.getByTestId('column-header-col-1'))  // or however existing tests trigger this
  await user.click(screen.getByRole('button', { name: /actions/i }))
  await user.click(screen.getByRole('menuitem', { name: /override/i }))
  const scopeArg = overrideFormSpy.mock.calls.at(-1)?.[0].scope
  expect(scopeArg.selected).toEqual(new Set(['latency-slo', 'avail-slo', 'err-slo']))
})

it('clicking a specific SLO cell then opening Override scopes to that SLO only', async () => {
  const user = userEvent.setup()
  renderAssetPanelWithMultiSloHeatmap()
  await user.click(screen.getByTestId('cell-latency-slo-col-1'))  // specific SLO-group cell
  await user.click(screen.getByRole('button', { name: /actions/i }))
  await user.click(screen.getByRole('menuitem', { name: /override/i }))
  const scopeArg = overrideFormSpy.mock.calls.at(-1)?.[0].scope
  expect(scopeArg.selected).toEqual(new Set(['latency-slo']))
})
```

**Adapting to the existing file:** The existing `AssetPanel.test.tsx` already has mocks for `useMetricHeatmap`, `useAssetEvaluations`, `useColumnAnnotations`, and `useAssets`. Reuse that setup by replicating the multi-SLO mock data — a `heatmapData.groups` list with three groups (`latency-slo`, `avail-slo`, `err-slo`), each containing a cell for `evaluation_id: 'col-1'`. If the existing tests hard-code `data-testid` values for cells, match them. If they don't, you will need to locate cells via their text content or add `data-testid` props to `AssetHeatmap` cell render as a tiny accompanying change.

- [ ] **Step 2: Expose `selectedSingleSloEvalId` in AssetPanel**

In `ui/src/features/navigator/components/AssetPanel.tsx`, add a new state + update the cell-click handler path:

```tsx
const [selectedSingleSloEvalId, setSelectedSingleSloEvalId] = useState<string | undefined>(undefined)
```

Add a reset alongside the existing `useEffect` that clears state on asset change (around line 36-42):

```tsx
setSelectedSingleSloEvalId(undefined)
```

Update `handleSlotSelect` (around line 244):

```tsx
function handleSlotSelect(slot: TimeSlotSelection) {
  setSelectedSlot(slot)
  if (slot.evalIds.length > 0) {
    setSelectedEvalId(slot.evalIds[0])
  }
  // Column-header / slot click does NOT set a single SLO — popover defaults to ALL
  setSelectedSingleSloEvalId(undefined)
}
```

If `AssetHeatmap` fires a different handler on specific-cell clicks, locate it (grep `onCellClick\|cellClick` in `features/navigator/components/AssetHeatmap*`) and add a new callback path that sets `selectedSingleSloEvalId` to the clicked cell's `slo_evaluation_id`. If a separate handler does not exist, add a prop `onSpecificCellClick` to `AssetHeatmap` and hook it up:

```tsx
// In AssetPanel
function handleSpecificCellClick(cell: HeatmapCell, isComposite: boolean) {
  // Composite "Overall Score" row has no SLO identity — fall back to ALL default.
  setSelectedSingleSloEvalId(isComposite ? undefined : cell.slo_evaluation_id)
}

// Pass to AssetHeatmap
<AssetHeatmap ... onSpecificCellClick={handleSpecificCellClick} />
```

**Important — composite row filtering:** `AssetHeatmap` currently renders an "Overall Score" row separate from the per-SLO rows. That row corresponds to the composite column result, not any single SLO. Verify (grep `composite` in `features/navigator/components/AssetHeatmap*`) how composite-row clicks propagate. If they currently use the same click handler as SLO cells, update the handler to pass `isComposite: true` so the fallback above kicks in. If composite rows are non-interactive today, no change needed — just confirm.

- [ ] **Step 3: Compute the initial scope mode**

Above the `return`, add:

```tsx
const scopeInitialMode = useMemo(() => {
  if (!selectedSingleSloEvalId || !heatmapData) return 'all' as const
  // Find SLO name for this specific cell
  for (const group of heatmapData.groups) {
    if (group.cells.some(c => c.slo_evaluation_id === selectedSingleSloEvalId)) {
      return { singleSlo: group.slo_name } as const
    }
  }
  return 'all' as const
}, [selectedSingleSloEvalId, heatmapData])

const scope = useSloScope({
  heatmapData,
  columnEvalId: selectedColumnEvalId,
  initialMode: scopeInitialMode,
})
```

Add the import:

```tsx
import { useSloScope } from '@/features/evaluations/components/actions/slo-scope/useSloScope'
```

- [ ] **Step 4: Compute availability flags for the menu**

```tsx
const menuAvailability = useMemo(() => {
  if (!heatmapData || !selectedColumnEvalId) {
    return { allRowsInvalidated: false, noRowsInvalidated: true }
  }
  const rowsInColumn = heatmapData.groups.flatMap(g => g.cells.filter(c => c.evaluation_id === selectedColumnEvalId))
  if (rowsInColumn.length === 0) return { allRowsInvalidated: false, noRowsInvalidated: true }
  return {
    allRowsInvalidated: rowsInColumn.every(r => r.invalidated),
    noRowsInvalidated: rowsInColumn.every(r => !r.invalidated),
  }
}, [heatmapData, selectedColumnEvalId])
```

- [ ] **Step 5: Replace the inline `EvaluationActionForm` with `ActionPopover` + inline form tree**

Remove the block around lines 335-346 (`<EvaluationActionForm ... />`) and replace the `actions={...}` block in `EvaluationHeader` so the popover is rendered next to the button. `ActionPopover` is a dumb container (from Task 6) — the parent constructs the form element tree based on `activeAction`:

```tsx
actions={hasColumn && effectiveEvalId && selectedColumnEvalId ? (
  <div className="relative">
    <EvaluationActionsButton
      currentResult={columnInfo.result === 'invalidated' ? (ev?.outcome ?? 'error') : columnInfo.result}
      allRowsInvalidated={menuAvailability.allRowsInvalidated}
      noRowsInvalidated={menuAvailability.noRowsInvalidated}
      activeAction={activeAction}
      onSelectAction={setActiveAction}
      onAddNote={handleAddNote}
    />
    <ActionPopover open={activeAction !== null} onClose={() => setActiveAction(null)}>
      {activeAction === 'override' && (
        <OverrideForm
          scope={scope}
          columnEvalId={selectedColumnEvalId}
          onComplete={() => setActiveAction(null)}
        />
      )}
      {activeAction === 'invalidate' && (
        <InvalidateForm
          scope={scope}
          columnEvalId={selectedColumnEvalId}
          onComplete={() => setActiveAction(null)}
        />
      )}
      {activeAction === 'restore' && (
        <RestoreForm
          scope={scope}
          columnEvalId={selectedColumnEvalId}
          onComplete={() => setActiveAction(null)}
        />
      )}
      {activeAction === 'baseline' && (
        <BaselineForm
          scope={scope}
          columnEvalId={selectedColumnEvalId}
          onComplete={() => setActiveAction(null)}
        />
      )}
      {activeAction === 're-evaluate' && (
        <ReEvaluateForm
          scope={scope}
          columnEvalId={selectedColumnEvalId}
          assetName={assetName}
          defaultFromDate={earliestPeriodStart?.slice(0, 16)}
          onComplete={() => setActiveAction(null)}
        />
      )}
    </ActionPopover>
  </div>
) : undefined}
```

Delete the old standalone action-form block below `EvaluationHeader`.

Add the imports:

```tsx
import { ActionPopover } from '@/features/evaluations/components/ActionPopover'
import { OverrideForm } from '@/features/evaluations/components/actions/OverrideForm'
import { InvalidateForm } from '@/features/evaluations/components/actions/InvalidateForm'
import { RestoreForm } from '@/features/evaluations/components/actions/RestoreForm'
import { BaselineForm } from '@/features/evaluations/components/actions/BaselineForm'
import { ReEvaluateForm } from '@/features/evaluations/components/actions/ReEvaluateForm'
```

- [ ] **Step 6: Check `EvaluationDetailPage.tsx` for the same pattern**

Run: `grep -n 'EvaluationActionForm\|EvaluationActionsButton' ui/src/pages/EvaluationDetailPage.tsx`

If `EvaluationDetailPage` also mounts `EvaluationActionForm`, apply an analogous refactor: construct a synthetic scope with `initialMode: { singleSlo: evalDetail.sloName }`, wrap the button + popover the same way. The detail page is inherently single-SLO-per-row since the URL carries a specific `eval_id`, but the new component signatures still require a `scope` and `columnEvalId`.

- [ ] **Step 7: Run the AssetPanel tests**

Run: `./scripts/ui-test.sh --tail 30 src/features/navigator/components/AssetPanel.test.tsx`

Expected: PASS on the new single-SLO and ALL scope tests.

- [ ] **Step 8: Run the full UI test suite + typecheck**

Run: `./scripts/ui-test.sh --tail 30`

Run: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json`

Expected: PASS. Fix any broken pre-existing tests that relied on `EvaluationActionForm` by migrating their imports/props to the new shape.

- [ ] **Step 9: Lint**

Run: `./scripts/ui-lint.sh --tail 10 src/features/navigator/components/AssetPanel.tsx src/pages/EvaluationDetailPage.tsx`

Expected: No errors.

- [ ] **Step 10: Smoke-test manually in the browser**

Run: `just dev` in one terminal, `just migrate` if the DB is fresh, then open `http://localhost:5173` and exercise the flow:

1. Navigate to a multi-SLO asset.
2. Click the Actions button — verify the popover opens next to the button and the heatmap does not shift down.
3. Pick Override result → radio to `fail` → Confirm. Watch heatmap cells flip.
4. Click a specific red SLO cell → Actions → Override. Verify the scope field shows "1 of N SLOs".
5. In the scope field, click the summary → modal opens, shows search + checklist. Pick a subset, Confirm. Scope field updates.
6. Run Re-run with a narrowed scope. Verify the network request body carries `slo_names: [...]`.
7. Try Baseline Pin with 6+ SLOs selected — verify the count warning appears.
8. Invalidate a couple of SLOs, then Restore — verify the Restore form shows only the invalidated rows.

Fix any visual glitches or regressions you spot.

- [ ] **Step 11: Commit**

```bash
git add ui/src/features/navigator/components/AssetPanel.tsx \
        ui/src/features/navigator/components/AssetPanel.test.tsx \
        ui/src/pages/EvaluationDetailPage.tsx
git commit -m "feat(ui): wire AssetPanel to ActionPopover with scoped SLO picker"
```

---

## Final sweep

- [ ] **Step 1: Run the full test suite one more time**

Run: `just test-all`

Expected: PASS.

- [ ] **Step 2: Run `just check`**

Run: `just check`

Expected: PASS (lint + format + typecheck).

- [ ] **Step 3: Sanity grep for surviving references to the old single-evalId action flow**

Run: `grep -rn 'evaluationId.*activeAction\|EvaluationActionForm' ui/src/`

Expected: zero results. If any remain, migrate them.

- [ ] **Step 4: Squash-verify the feature works end-to-end**

Re-run the manual smoke test from Task 13 Step 10 against the current branch.

- [ ] **Step 5: Final commit if anything changed**

If any follow-up fixups were made during the final sweep, commit them as a tidy commit:

```bash
git add -u
git commit -m "chore(ui): final sweep after per-SLO action scoping"
```

---

## Out of scope (per spec — tracked as future work)

- Bulk backend endpoints (`POST /evaluations/bulk/*`) if transactional semantics become necessary.
- Removing the deprecated `slo_name` field from `ReEvaluateRequest`.
- Cross-column multi-select.
- Smarter default scope for Baseline Pin (single instead of ALL).
- Audit of other `ev.id` consumers outside the action forms.
