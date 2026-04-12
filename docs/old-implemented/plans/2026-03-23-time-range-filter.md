# Time Range Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a global Grafana-style time range picker that filters evaluations by date presets (7d/14d/30d/60d/90d/6mo/1yr), shared across all panels via React context.

**Architecture:** A `TimeRangeProvider` context holds the selected preset and computes a `from` ISO date string (rounded to midnight). All evaluation-fetching hooks read from this context and include `from` in their API calls. The backend already supports `from`/`to` query parameters on `GET /evaluations` — no backend changes needed. The picker renders as a compact dropdown in the top-right of each panel's header area.

**Tech Stack:** React 19 context, existing shadcn Popover, existing `EvaluationFilters.from` field, Tailwind CSS.

---

## Clarifications

- **Date, not datetime.** The `from` value is always midnight (00:00:00) of the computed date. `to` is omitted (open-ended = now).
- **Global context (option B).** One time range shared across AllEvaluationsPanel, GroupPanel, AssetPanel, and MetricExplorerPage. Changing it in one panel changes it everywhere.
- **Presets only.** No custom date picker inputs. Just clickable preset buttons: Last 7 days, Last 14 days, Last 30 days, Last 60 days, Last 90 days, Last 6 months, Last 1 year.
- **Default: Last 30 days.** Reasonable default that shows enough history without overloading.
- **"N runs · M days" label stays.** It reflects what the server actually returned — still useful.
- **Persisted in localStorage.** So the user's preference survives page reloads.

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `ui/src/lib/time-range-context.tsx` | **Create** | `TimeRangeProvider`, `useTimeRange` hook, preset definitions, midnight rounding logic |
| `ui/src/lib/time-range-context.test.tsx` | **Create** | Unit tests for midnight rounding and preset computation |
| `ui/src/components/TimeRangePicker.tsx` | **Create** | Dropdown UI component using shadcn Popover, renders preset list |
| `ui/src/components/TimeRangePicker.test.tsx` | **Create** | Component render test — preset list renders, clicking updates context |
| `ui/src/App.tsx` | **Modify** | Wrap with `TimeRangeProvider` |
| `ui/src/features/evaluations/hooks.ts` | **Modify** | `useEvaluations` reads `from` from `useTimeRange()` and merges into filters |
| `ui/src/features/navigator/hooks.ts` | **Modify** | `useAssetEvaluations` reads `from` from `useTimeRange()` |
| `ui/src/features/navigator/components/AllEvaluationsPanel.tsx` | **Modify** | Add `<TimeRangePicker />` in header right side |
| `ui/src/features/navigator/components/GroupPanel.tsx` | **Modify** | Add `<TimeRangePicker />` in header right side |
| `ui/src/features/navigator/components/AssetPanel.tsx` | **Modify** | Add `<TimeRangePicker />` in header right side |
| `ui/src/pages/MetricExplorerPage.tsx` | **Modify** | Ensure it picks up filtered evals from context-aware hooks (may need picker placement too) |

## Constraints

- The API validates that `date` and `from`/`to` are mutually exclusive. Since we only use `from`, no conflict.
- The API's `limit` defaults to 50, max 200. For long ranges this may truncate results. That's a separate concern — the "N runs" label makes truncation visible. Out of scope for this plan.
- The heatmap endpoint (`/evaluations/metric-heatmap`) does NOT accept `from`/`to` today. The asset heatmap will continue showing all data. Out of scope.

---

### Task 1: Time Range Context — Pure Logic

**Files:**
- Create: `ui/src/lib/time-range-context.tsx`
- Create: `ui/src/lib/time-range-context.test.tsx`

- [ ] **Step 1: Write the test file for midnight rounding and preset computation**

```tsx
// ui/src/lib/time-range-context.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { computeFromDate, PRESETS } from './time-range-context'

describe('computeFromDate', () => {
  beforeEach(() => {
    // Fix "now" to 2026-03-23T14:30:00Z so tests are deterministic
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-03-23T14:30:00Z'))
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns midnight 7 days ago for 7-day preset', () => {
    const result = computeFromDate(7)
    // 2026-03-23 minus 7 days = 2026-03-16, midnight local
    const d = new Date(result)
    expect(d.getHours()).toBe(0)
    expect(d.getMinutes()).toBe(0)
    expect(d.getSeconds()).toBe(0)
    expect(d.getMilliseconds()).toBe(0)
  })

  it('returns midnight 30 days ago for 30-day preset', () => {
    const result = computeFromDate(30)
    const d = new Date(result)
    expect(d.getHours()).toBe(0)
    expect(d.getMinutes()).toBe(0)
    // 2026-03-23 minus 30 = 2026-02-21
    expect(d.getDate()).toBe(21)
    expect(d.getMonth()).toBe(1) // February = 1
  })

  it('returns midnight ~6 months ago for 180-day preset', () => {
    const result = computeFromDate(180)
    const d = new Date(result)
    expect(d.getHours()).toBe(0)
    // 2026-03-23 minus 180 days = 2025-09-25
    expect(d.getFullYear()).toBe(2025)
  })
})

describe('PRESETS', () => {
  it('contains expected preset options', () => {
    const labels = PRESETS.map(p => p.label)
    expect(labels).toEqual([
      'Last 7 days',
      'Last 14 days',
      'Last 30 days',
      'Last 60 days',
      'Last 90 days',
      'Last 6 months',
      'Last 1 year',
    ])
  })

  it('all presets have positive day values', () => {
    for (const p of PRESETS) {
      expect(p.days).toBeGreaterThan(0)
    }
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./scripts/ui-test.sh --tail 10 src/lib/time-range-context.test.tsx`
Expected: FAIL — module `./time-range-context` not found.

- [ ] **Step 3: Write the context module**

```tsx
// ui/src/lib/time-range-context.tsx
import { createContext, useContext, useState, useMemo, type ReactNode } from 'react'

export interface TimePreset {
  label: string
  days: number
}

export const PRESETS: TimePreset[] = [
  { label: 'Last 7 days', days: 7 },
  { label: 'Last 14 days', days: 14 },
  { label: 'Last 30 days', days: 30 },
  { label: 'Last 60 days', days: 60 },
  { label: 'Last 90 days', days: 90 },
  { label: 'Last 6 months', days: 180 },
  { label: 'Last 1 year', days: 365 },
]

const DEFAULT_DAYS = 30
const STORAGE_KEY = 'tropek-time-range-days'

/** Compute an ISO date string for midnight N days ago. */
export function computeFromDate(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  d.setHours(0, 0, 0, 0)
  return d.toISOString()
}

interface TimeRangeCtx {
  /** Currently selected preset */
  preset: TimePreset
  /** ISO string for the "from" date (midnight, N days ago) */
  from: string
  /** Update the selected preset by day count */
  setDays: (days: number) => void
}

const Ctx = createContext<TimeRangeCtx | null>(null)

function loadDays(): number {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (!stored) return DEFAULT_DAYS
  const n = Number(stored)
  return PRESETS.some(p => p.days === n) ? n : DEFAULT_DAYS
}

export function TimeRangeProvider({ children }: { children: ReactNode }) {
  const [days, _setDays] = useState(loadDays)

  function setDays(d: number) {
    _setDays(d)
    localStorage.setItem(STORAGE_KEY, String(d))
  }

  const preset = PRESETS.find(p => p.days === days) ?? PRESETS[2] // fallback: 30d
  const from = useMemo(() => computeFromDate(days), [days])

  return (
    <Ctx.Provider value={{ preset, from, setDays }}>
      {children}
    </Ctx.Provider>
  )
}

export function useTimeRange(): TimeRangeCtx {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useTimeRange must be used inside TimeRangeProvider')
  return ctx
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./scripts/ui-test.sh --tail 10 src/lib/time-range-context.test.tsx`
Expected: PASS — all 4 tests green.

- [ ] **Step 5: Commit**

```
feat(ui): add TimeRangeProvider context with date presets
```

---

### Task 2: TimeRangePicker Dropdown Component

**Files:**
- Create: `ui/src/components/TimeRangePicker.tsx`
- Create: `ui/src/components/TimeRangePicker.test.tsx`

- [ ] **Step 1: Write the component test**

```tsx
// ui/src/components/TimeRangePicker.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TimeRangePicker } from './TimeRangePicker'
import { TimeRangeProvider } from '@/lib/time-range-context'

function renderPicker() {
  return render(
    <TimeRangeProvider>
      <TimeRangePicker />
    </TimeRangeProvider>,
  )
}

describe('TimeRangePicker', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('renders the default preset label', () => {
    renderPicker()
    expect(screen.getByText('Last 30 days')).toBeInTheDocument()
  })

  it('opens dropdown and shows all presets on click', () => {
    renderPicker()
    fireEvent.click(screen.getByRole('button'))
    expect(screen.getByText('Last 7 days')).toBeInTheDocument()
    expect(screen.getByText('Last 14 days')).toBeInTheDocument()
    expect(screen.getByText('Last 90 days')).toBeInTheDocument()
    expect(screen.getByText('Last 6 months')).toBeInTheDocument()
    expect(screen.getByText('Last 1 year')).toBeInTheDocument()
  })

  it('selecting a preset updates the displayed label', () => {
    renderPicker()
    fireEvent.click(screen.getByRole('button'))
    fireEvent.click(screen.getByText('Last 7 days'))
    // After selection, the button should show the new label
    expect(screen.getByRole('button')).toHaveTextContent('Last 7 days')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./scripts/ui-test.sh --tail 10 src/components/TimeRangePicker.test.tsx`
Expected: FAIL — module `./TimeRangePicker` not found.

- [ ] **Step 3: Write the TimeRangePicker component**

Uses shadcn Popover. Compact button showing current preset label. Dropdown with clickable preset list. Uses `useTimeRange()` from context.

```tsx
// ui/src/components/TimeRangePicker.tsx
import { useState } from 'react'
import { Calendar, ChevronDown } from 'lucide-react'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover'
import { useTimeRange, PRESETS } from '@/lib/time-range-context'

export function TimeRangePicker() {
  const { preset, setDays } = useTimeRange()
  const [open, setOpen] = useState(false)

  return (
    <Popover open={open} onOpenChange={(nextOpen) => setOpen(nextOpen)}>
      <PopoverTrigger
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded border border-border bg-popover text-foreground hover:bg-muted transition-colors"
        style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}
      >
        <Calendar size={14} className="text-muted-foreground" />
        {preset.label}
        <ChevronDown size={12} className="text-muted-foreground" />
      </PopoverTrigger>
      <PopoverContent align="end" className="w-44 p-1">
        {PRESETS.map(p => (
          <button
            key={p.days}
            onClick={() => { setDays(p.days); setOpen(false) }}
            className={`w-full text-left px-3 py-1.5 text-xs rounded transition-colors ${
              p.days === preset.days
                ? 'bg-primary/15 text-primary'
                : 'text-foreground hover:bg-muted'
            }`}
            style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}
          >
            {p.label}
          </button>
        ))}
      </PopoverContent>
    </Popover>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./scripts/ui-test.sh --tail 10 src/components/TimeRangePicker.test.tsx`
Expected: PASS — all 3 tests green.

Note: if Popover portal rendering causes issues in happy-dom, the test may need adjustment (e.g. wrapping in a `<div id="root">` or checking the popover renders). Adapt as needed — the key assertion is that the button label updates.

- [ ] **Step 5: Commit**

```
feat(ui): add TimeRangePicker dropdown component
```

---

### Task 3: Wire Provider into App and Hooks

**Files:**
- Modify: `ui/src/App.tsx:65-101` — wrap with `TimeRangeProvider`
- Modify: `ui/src/features/evaluations/hooks.ts:22-29` — merge `from` into filters
- Modify: `ui/src/features/navigator/hooks.ts:5-11` — merge `from` into asset hook

- [ ] **Step 1: Add `TimeRangeProvider` to App.tsx**

In `ui/src/App.tsx`, wrap the app inside `TimeRangeProvider` — place it inside `ThemeProvider`, outside `QueryClientProvider` (both work, but context order doesn't matter here):

```tsx
// Add import at top:
import { TimeRangeProvider } from './lib/time-range-context'

// Wrap in the component tree — change:
//   <ThemeProvider>
//     <QueryClientProvider client={queryClient}>
// to:
//   <ThemeProvider>
//     <TimeRangeProvider>
//       <QueryClientProvider client={queryClient}>
// and add closing </TimeRangeProvider> before </ThemeProvider>
```

- [ ] **Step 2: Modify `useEvaluations` to include `from` from context**

In `ui/src/features/evaluations/hooks.ts`, change `useEvaluations`:

```tsx
// Before:
export function useEvaluations(filters: EvaluationFilters = {}) {
  return useQuery({
    queryKey: evaluationKeys.list(filters),
    queryFn: () => fetchEvaluations(filters),
    placeholderData: keepPreviousData,
  })
}

// After:
import { useTimeRange } from '@/lib/time-range-context'

export function useEvaluations(filters: EvaluationFilters = {}) {
  const { from } = useTimeRange()
  const merged = { ...filters, from }
  return useQuery({
    queryKey: evaluationKeys.list(merged),
    queryFn: () => fetchEvaluations(merged),
    placeholderData: keepPreviousData,
  })
}
```

This means every caller of `useEvaluations` automatically gets time filtering — no changes needed in individual panels for data fetching.

- [ ] **Step 3: Modify `useAssetEvaluations` to include `from` from context**

In `ui/src/features/navigator/hooks.ts`:

```tsx
// Before:
import { fetchEvaluations, fetchMetricHeatmap } from '@/features/evaluations/api'

export function useAssetEvaluations(assetName: string | undefined) {
  return useQuery({
    queryKey: evaluationKeys.list({ asset_name: assetName }),
    queryFn: () => fetchEvaluations({ asset_name: assetName }),
    enabled: !!assetName,
  })
}

// After:
import { fetchEvaluations, fetchMetricHeatmap } from '@/features/evaluations/api'
import { useTimeRange } from '@/lib/time-range-context'

export function useAssetEvaluations(assetName: string | undefined) {
  const { from } = useTimeRange()
  const filters = { asset_name: assetName, from }
  return useQuery({
    queryKey: evaluationKeys.list(filters),
    queryFn: () => fetchEvaluations(filters),
    enabled: !!assetName,
  })
}
```

- [ ] **Step 4: Run all UI tests to verify nothing breaks**

Run: `./scripts/ui-test.sh --tail 20`
Expected: All existing tests still pass. Some tests may fail if they render components that call `useTimeRange()` without a provider — if so, wrap those test renders in `<TimeRangeProvider>`. Check the error messages.

- [ ] **Step 5: Add `TimeRangeProvider` to TestWrapper and fix any broken tests**

First, add `TimeRangeProvider` to `ui/src/test-wrapper.tsx` (if it exists) so all future tests get the provider automatically. Then, if `AssetNavigatorPage.test.tsx` or other tests fail with "useTimeRange must be used inside TimeRangeProvider", add the provider wrapper to those test files. The pattern:

```tsx
import { TimeRangeProvider } from '@/lib/time-range-context'

// In render calls, wrap:
render(
  <TimeRangeProvider>
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ComponentUnderTest />
      </MemoryRouter>
    </QueryClientProvider>
  </TimeRangeProvider>
)
```

- [ ] **Step 6: Commit**

```
feat(ui): wire TimeRangeProvider into App and evaluation hooks
```

---

### Task 4: Place TimeRangePicker in Panel Headers

**Files:**
- Modify: `ui/src/features/evaluations/components/EvaluationHeader.tsx:11,24,77` — add `toolbar` slot
- Modify: `ui/src/features/navigator/components/AllEvaluationsPanel.tsx:34-38` — pass picker via toolbar
- Modify: `ui/src/features/navigator/components/GroupPanel.tsx:35-38` — pass picker via toolbar
- Modify: `ui/src/features/navigator/components/AssetPanel.tsx:102-137` — pass picker via toolbar

- [ ] **Step 1: Add `toolbar` prop to EvaluationHeader**

In `ui/src/features/evaluations/components/EvaluationHeader.tsx`, add a `toolbar` slot that renders between the note button and actions in the right column:

```tsx
// Add to Props interface:
  /** Toolbar rendered in right column, before noteButton/actions (e.g. time range picker) */
  toolbar?: ReactNode

// In the right column JSX (line 77), add toolbar before noteButton:
      <div className="flex items-center gap-2 justify-end">
        {toolbar}
        {noteButton}
        {actions}
      </div>
```

- [ ] **Step 2: Add TimeRangePicker to AllEvaluationsPanel**

In `ui/src/features/navigator/components/AllEvaluationsPanel.tsx`:

```tsx
// Add import:
import { TimeRangePicker } from '@/components/TimeRangePicker'

// Pass to EvaluationHeader:
      <EvaluationHeader
        title="All Evaluations"
        subtitle={evals.length > 0 && dateRange != null
          ? `${evals.length} runs · ${dateRange} days`
          : undefined}
        toolbar={<TimeRangePicker />}
      />
```

- [ ] **Step 3: Add TimeRangePicker to GroupPanel**

In `ui/src/features/navigator/components/GroupPanel.tsx`:

```tsx
// Add import:
import { TimeRangePicker } from '@/components/TimeRangePicker'

// Pass to EvaluationHeader:
      <EvaluationHeader
        title={prettyGroupName(groupName)}
        subtitle={evals.length > 0 ? `${evals.length} evaluations` : undefined}
        toolbar={<TimeRangePicker />}
      />
```

- [ ] **Step 4: Add TimeRangePicker to AssetPanel**

In `ui/src/features/navigator/components/AssetPanel.tsx`:

```tsx
// Add import:
import { TimeRangePicker } from '@/components/TimeRangePicker'

// In the EvaluationHeader at line 102, add toolbar prop alongside existing actions:
      <EvaluationHeader
        title={assetName}
        titleMono
        result={displayResult}
        score={score}
        metadata={...}  // keep existing
        toolbar={<TimeRangePicker />}
        noteButton={...}  // keep existing
        actions={...}  // keep existing
      />
```

- [ ] **Step 5: Run all UI tests**

Run: `./scripts/ui-test.sh --tail 20`
Expected: PASS — all tests green.

- [ ] **Step 6: Visually verify in dev server**

Run: `just dev` and navigate to `/navigator`. Verify:
1. Time range picker appears in top-right of header card on All Evaluations view
2. Clicking opens dropdown with 7 presets
3. Selecting "Last 7 days" re-fetches evaluations (check Network tab — `?from=...` param present)
4. Switch to a group → picker shows same selection
5. Switch to an asset → picker shows same selection
6. "N runs · M days" label updates to reflect the filtered data

- [ ] **Step 7: Commit**

```
feat(ui): place TimeRangePicker in all evaluation panel headers
```

---

### Task 5: MetricExplorerPage Integration

**Files:**
- Modify: `ui/src/pages/MetricExplorerPage.tsx:220-223` — no code change needed if hooks already use context

- [ ] **Step 1: Verify MetricExplorerPage works automatically**

Since `MetricExplorerPage` uses `useEvaluations()` (line 220) and `useAssetEvaluations()` (line 223), and both hooks now inject `from` from context, the explorer page already respects the time range. Verify:

Run: `just dev`, navigate to `/explorer?asset=some-asset`. Confirm evaluations are filtered.

- [ ] **Step 2: Add TimeRangePicker to MetricExplorerPage header (if it has one)**

Look at the page — if there's a header area, add the picker. If not, add a minimal toolbar row:

```tsx
// Add import:
import { TimeRangePicker } from '@/components/TimeRangePicker'

// Add near the top of the page content, before charts:
<div className="flex justify-end px-6 pt-4">
  <TimeRangePicker />
</div>
```

Exact placement depends on the page layout — read the full file and pick the right spot.

- [ ] **Step 3: Run all UI tests**

Run: `./scripts/ui-test.sh --tail 20`
Expected: PASS.

- [ ] **Step 4: Commit**

```
feat(ui): add time range picker to MetricExplorerPage
```

---

### Task 6: Final Review and Cleanup

- [ ] **Step 1: Run full test suite**

Run: `./scripts/ui-test.sh --tail 20`
Expected: All tests PASS.

- [ ] **Step 2: Run typecheck**

Run: `pnpm exec tsc --noEmit -p tsconfig.app.json` from `ui/` directory.
Expected: No errors.

- [ ] **Step 3: Verify `from` parameter in API calls**

Open browser dev tools, Network tab. Navigate to `/navigator`:
- `GET /api/evaluations?from=2026-02-21T00:00:00.000Z` (for 30-day default)
- Select "Last 7 days" → `GET /api/evaluations?from=2026-03-16T00:00:00.000Z`
- Click a group → `GET /api/evaluations?group_name=foo&from=2026-03-16T00:00:00.000Z`
- Click an asset → `GET /api/evaluations?asset_name=bar&from=2026-03-16T00:00:00.000Z`

- [ ] **Step 4: Verify localStorage persistence**

1. Select "Last 90 days"
2. Refresh page
3. Picker should still show "Last 90 days"

- [ ] **Step 5: Final commit if any cleanup was needed**

```
chore(ui): time range filter cleanup
```
