# Chart View Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three cross-chart trend controls — a 1/2-columns layout toggle, a master notes show/hide switch, and a master line↔bar chart-type toggle (each with per-chart override) — plus a datapoint-hover note tooltip.

**Architecture:** A new app-root `ChartPreferencesProvider` (localStorage-backed, modeled on `time-range-context.tsx`) owns three preferences: `columns`, `notesMaster`, and `chartTypeMaster`, each with an in-memory "generation" counter for the two master/override toggles. `MetricTrendBlock` reads the master values via a small reusable `useMasterOverride` hook that resolves `override ?? master` and clears the override whenever its generation bumps. The pure chart builder (`buildChartRender`) gains a `chartType` mode and appends `showOnGraph` notes to the tooltip. A single `ChartViewControls` component renders all three master controls and is dropped into all three trend-grid views, which also swap their hardcoded grid class for a `columns`-driven one.

**Tech Stack:** React 18 + TypeScript (strict), Vite, ECharts 6 via `echarts-for-react`, lucide-react icons, Tailwind, vitest + `@testing-library/react` (happy-dom), pnpm.

## Global Constraints

- **UI layering:** never import `@/generated/api` outside `features/*/api.ts` / `features/*/mappers.ts`. This change touches none of those; it stays in `lib/`, `components/charts/`, and `features/*/components|hooks`.
- **No cryptic variable names.** Name variables for what they represent (`point` not `p`, `note` not `n`). Only `i`, `x`, `db`, `id` are acceptable short names. When rewriting an existing block, upgrade any single-letter names you touch.
- **Code style:** all imports at top of file (never inside functions/tests); single quotes; f-strings/template literals over concatenation; Pydantic-style parameter objects don't apply here (UI). Line length 120.
- **Never silence** lint/type/test failures (`// eslint-disable` only for the established `react-refresh/only-export-components` context pattern, exactly as `time-range-context.tsx` uses it). No `@ts-ignore`, no skipped tests.
- **Runtime config:** genuinely tunable values live in `ui/public/config.json` via `getConfig()`. The defaults here (columns=2, notes on, line) are behavior-preserving constants, persisted per-user in `localStorage`, not runtime config — keep them as module constants in the context file.
- **Test command (single file, from repo root):** `./scripts/ui-test.sh <path-relative-to-ui>` (auto-approved; add `--tail 30` to trim output). Full check: `just check`.
- **Persisted localStorage keys (exact):** `tropek.chartColumns`, `tropek.notesMaster`, `tropek.chartType`. Generation counters are in-memory only (never persisted).
- **Defaults (preserve current behavior):** `columns` → `2`, `notesMaster` → `true`, `chartTypeMaster` → `'line'`.
  > **Superseded (2026-07-07 follow-up):** the `columns` default was intentionally changed to `1`
  > (one chart per row) after implementation — the wider layout better serves the legibility goal.
  > `notesMaster`/`chartTypeMaster` defaults are unchanged.

---

## File Structure

**Create:**
- `ui/src/lib/chart-preferences-context.tsx` — the provider + `useChartPreferences` hook + persisted constants.
- `ui/src/lib/chart-preferences-context.test.ts` — persistence + generation-increment tests.
- `ui/src/features/evaluations/hooks/useMasterOverride.ts` — generic `override ?? master`, reset-on-generation hook.
- `ui/src/features/evaluations/hooks/useMasterOverride.test.ts` — hook behavior tests.
- `ui/src/components/charts/ChartViewControls.tsx` — the three master controls (columns / notes / chart-type).
- `ui/src/components/charts/ChartViewControls.test.tsx` — control interaction tests.

**Modify:**
- `ui/src/App.tsx` — mount `ChartPreferencesProvider`.
- `ui/src/lib/chartAnnotations.ts` — export the existing `escapeHtml` helper.
- `ui/src/features/evaluations/hooks/useMetricTrendState.ts` — tooltip notes, `chartType` in the builder, drop notes-state ownership, accept `notesVisible`/`chartType` params.
- `ui/src/features/evaluations/hooks/useMetricTrendState.test.ts` — new tooltip + bar-series test cases.
- `ui/src/features/evaluations/components/MetricTrendBlock.tsx` — read context, per-chart overrides, per-chart notes + chart-type buttons.
- `ui/src/features/evaluations/components/EvaluationIndicatorSection.tsx` — `ChartViewControls` in header + `columns`-driven grid.
- `ui/src/features/navigator/components/AssetPanelChartView.tsx` — same.
- `ui/src/features/navigator/components/AssetPanelHeatmapView.tsx` — same.

---

## Task 1: Chart preferences context + app-root wiring

**Files:**
- Create: `ui/src/lib/chart-preferences-context.tsx`
- Create: `ui/src/lib/chart-preferences-context.test.ts`
- Modify: `ui/src/App.tsx` (import at line 13 area; provider nesting at lines 80-119)

**Interfaces:**
- Produces: `ChartPreferencesProvider({ children })` component; `useChartPreferences(): ChartPreferencesCtx` hook. Exported types `ChartColumns = 1 | 2`, `ChartType = 'line' | 'bar'`. `ChartPreferencesCtx` fields: `columns: ChartColumns`, `setColumns: (n: ChartColumns) => void`, `notesMaster: boolean`, `toggleNotesMaster: () => void`, `notesGeneration: number`, `chartTypeMaster: ChartType`, `toggleChartType: () => void`, `chartTypeGeneration: number`.

- [ ] **Step 1: Write the failing context test**

Create `ui/src/lib/chart-preferences-context.test.ts`:

```ts
import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { ChartPreferencesProvider, useChartPreferences } from './chart-preferences-context'

function useCtx() {
  return useChartPreferences()
}

describe('chart-preferences-context', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('defaults to 2 columns, notes on, line charts', () => {
    const { result } = renderHook(useCtx, { wrapper: ChartPreferencesProvider })
    expect(result.current.columns).toBe(2)
    expect(result.current.notesMaster).toBe(true)
    expect(result.current.chartTypeMaster).toBe('line')
  })

  it('persists columns to localStorage', () => {
    const { result } = renderHook(useCtx, { wrapper: ChartPreferencesProvider })
    act(() => result.current.setColumns(1))
    expect(result.current.columns).toBe(1)
    expect(localStorage.getItem('tropek.chartColumns')).toBe('1')
  })

  it('reads persisted columns on mount', () => {
    localStorage.setItem('tropek.chartColumns', '1')
    const { result } = renderHook(useCtx, { wrapper: ChartPreferencesProvider })
    expect(result.current.columns).toBe(1)
  })

  it('toggles notesMaster, persists it, and bumps notesGeneration', () => {
    const { result } = renderHook(useCtx, { wrapper: ChartPreferencesProvider })
    const before = result.current.notesGeneration
    act(() => result.current.toggleNotesMaster())
    expect(result.current.notesMaster).toBe(false)
    expect(localStorage.getItem('tropek.notesMaster')).toBe('false')
    expect(result.current.notesGeneration).toBe(before + 1)
  })

  it('toggles chartTypeMaster, persists it, and bumps chartTypeGeneration independently', () => {
    const { result } = renderHook(useCtx, { wrapper: ChartPreferencesProvider })
    const notesGenBefore = result.current.notesGeneration
    act(() => result.current.toggleChartType())
    expect(result.current.chartTypeMaster).toBe('bar')
    expect(localStorage.getItem('tropek.chartType')).toBe('bar')
    expect(result.current.chartTypeGeneration).toBe(1)
    // toggling chart type must NOT bump the notes generation
    expect(result.current.notesGeneration).toBe(notesGenBefore)
  })

  it('throws when used outside the provider', () => {
    expect(() => renderHook(useCtx)).toThrow('useChartPreferences must be used inside ChartPreferencesProvider')
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./scripts/ui-test.sh src/lib/chart-preferences-context.test.ts --tail 30`
Expected: FAIL — cannot resolve `./chart-preferences-context` (module does not exist yet).

- [ ] **Step 3: Create the context**

Create `ui/src/lib/chart-preferences-context.tsx`:

```tsx
// src/lib/chart-preferences-context.tsx
import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

export type ChartColumns = 1 | 2
export type ChartType = 'line' | 'bar'

const COLUMNS_KEY = 'tropek.chartColumns'
const NOTES_KEY = 'tropek.notesMaster'
const CHART_TYPE_KEY = 'tropek.chartType'

interface ChartPreferencesCtx {
  columns: ChartColumns
  setColumns: (n: ChartColumns) => void
  notesMaster: boolean
  toggleNotesMaster: () => void
  /** Bumped on each master notes flip; used by charts to clear per-chart overrides. */
  notesGeneration: number
  chartTypeMaster: ChartType
  toggleChartType: () => void
  /** Bumped on each master chart-type flip; independent of notesGeneration. */
  chartTypeGeneration: number
}

const Ctx = createContext<ChartPreferencesCtx | null>(null)

function loadColumns(): ChartColumns {
  return localStorage.getItem(COLUMNS_KEY) === '1' ? 1 : 2
}

function loadNotesMaster(): boolean {
  // default ON: anything other than the explicit string 'false' is treated as true
  return localStorage.getItem(NOTES_KEY) !== 'false'
}

function loadChartType(): ChartType {
  return localStorage.getItem(CHART_TYPE_KEY) === 'bar' ? 'bar' : 'line'
}

export function ChartPreferencesProvider({ children }: { children: ReactNode }) {
  const [columns, setColumnsState] = useState<ChartColumns>(loadColumns)
  const [notesMaster, setNotesMaster] = useState<boolean>(loadNotesMaster)
  const [notesGeneration, setNotesGeneration] = useState(0)
  const [chartTypeMaster, setChartTypeMaster] = useState<ChartType>(loadChartType)
  const [chartTypeGeneration, setChartTypeGeneration] = useState(0)

  const setColumns = useCallback((n: ChartColumns) => {
    setColumnsState(n)
    localStorage.setItem(COLUMNS_KEY, String(n))
  }, [])

  const toggleNotesMaster = useCallback(() => {
    setNotesMaster(previous => {
      const next = !previous
      localStorage.setItem(NOTES_KEY, String(next))
      return next
    })
    setNotesGeneration(generation => generation + 1)
  }, [])

  const toggleChartType = useCallback(() => {
    setChartTypeMaster(previous => {
      const next = previous === 'line' ? 'bar' : 'line'
      localStorage.setItem(CHART_TYPE_KEY, next)
      return next
    })
    setChartTypeGeneration(generation => generation + 1)
  }, [])

  return (
    <Ctx.Provider
      value={{
        columns,
        setColumns,
        notesMaster,
        toggleNotesMaster,
        notesGeneration,
        chartTypeMaster,
        toggleChartType,
        chartTypeGeneration,
      }}
    >
      {children}
    </Ctx.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useChartPreferences(): ChartPreferencesCtx {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useChartPreferences must be used inside ChartPreferencesProvider')
  return ctx
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `./scripts/ui-test.sh src/lib/chart-preferences-context.test.ts --tail 30`
Expected: PASS — all 6 cases green.

- [ ] **Step 5: Mount the provider at the app root**

In `ui/src/App.tsx`, add the import next to the other context imports (after line 13, `import { TimeRangeProvider } from './lib/time-range-context'`):

```tsx
import { ChartPreferencesProvider } from './lib/chart-preferences-context'
```

Then wrap the tree. Change the opening providers (lines 80-83) from:

```tsx
    <ThemeProvider>
      <TimeRangeProvider>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
```

to:

```tsx
    <ThemeProvider>
      <TimeRangeProvider>
        <ChartPreferencesProvider>
          <QueryClientProvider client={queryClient}>
            <BrowserRouter>
```

And close it — change the closing providers (lines 116-119) from:

```tsx
        </BrowserRouter>
        </QueryClientProvider>
      </TimeRangeProvider>
    </ThemeProvider>
```

to:

```tsx
            </BrowserRouter>
          </QueryClientProvider>
        </ChartPreferencesProvider>
      </TimeRangeProvider>
    </ThemeProvider>
```

(Indentation is cosmetic — the required change is inserting `<ChartPreferencesProvider>` between `TimeRangeProvider` and `QueryClientProvider`, with a matching close. Run `just check` after to let the formatter settle indentation.)

- [ ] **Step 6: Typecheck + lint**

Run: `just check`
Expected: PASS (no type or lint errors introduced).

- [ ] **Step 7: Commit**

```bash
git add ui/src/lib/chart-preferences-context.tsx ui/src/lib/chart-preferences-context.test.ts ui/src/App.tsx
git commit -m "feat(ui): add chart preferences context (columns, notes master, chart type)"
```

---

## Task 2: Datapoint-hover note tooltip

**Files:**
- Modify: `ui/src/lib/chartAnnotations.ts:167` (export `escapeHtml`)
- Modify: `ui/src/features/evaluations/hooks/useMetricTrendState.ts` (imports at top; tooltip `formatter` ~lines 504-525)
- Test: `ui/src/features/evaluations/hooks/useMetricTrendState.test.ts` (add factories + cases)

**Interfaces:**
- Consumes: `escapeHtml(s: string): string` (newly exported from `chartAnnotations.ts`); `paletteOf(color): { bg: string; fg: string }` from `@/features/note-categories`; the `annotations?: Map<string, Annotation[]>` already present on `ChartOptionInput`.
- Produces: no signature change — the tooltip `formatter` now appends one `<div>` per `showOnGraph` note of the hovered point.

- [ ] **Step 1: Export `escapeHtml` from chartAnnotations.ts**

In `ui/src/lib/chartAnnotations.ts`, change line 167 from:

```ts
function escapeHtml(s: string): string {
```

to:

```ts
export function escapeHtml(s: string): string {
```

- [ ] **Step 2: Write the failing tooltip test**

In `ui/src/features/evaluations/hooks/useMetricTrendState.test.ts`, add these factory helpers just after `makeIndicator` (after line 62), so annotations can be built:

```ts
import type { Annotation } from '../domain'
import type { NoteCategory } from '@/features/note-categories'

function makeCategory(overrides: Partial<NoteCategory> = {}): NoteCategory {
  return {
    id: 'cat-1',
    name: 'deploy',
    label: 'Deploy',
    color: 'sky',
    showOnGraph: true,
    isSystem: false,
    createdAt: new Date('2026-01-01T00:00:00Z'),
    updatedAt: null,
    ...overrides,
  }
}

function makeAnnotation(overrides: Partial<Annotation> = {}): Annotation {
  return {
    id: 'note-1',
    sloEvaluationId: null,
    evaluationRunId: null,
    content: 'note content',
    author: null,
    categoryId: 'cat-1',
    category: makeCategory(),
    tags: {},
    noteGroupId: null,
    noteGroupName: null,
    hiddenAt: null,
    hiddenBy: null,
    hiddenReason: null,
    createdAt: new Date('2026-01-01T00:00:00Z'),
    updatedAt: null,
    ...overrides,
  }
}
```

(Move the two new `import type` lines to the top of the file alongside the existing imports — imports must be top-level. Add `Annotation` to the existing `../domain` import and add the `NoteCategory` import.)

Then add this test inside the `describe('buildChartOption', ...)` block (before its closing `})` at line 237):

```ts
  it('appends showOnGraph notes to the tooltip and escapes their content', () => {
    const shown = makeAnnotation({
      content: 'deploy <v2>',
      category: makeCategory({ label: 'Deploy', showOnGraph: true, color: 'sky' }),
    })
    const hidden = makeAnnotation({
      id: 'note-2',
      content: 'internal only',
      category: makeCategory({ id: 'cat-2', label: 'Internal', showOnGraph: false, color: 'gray' }),
    })
    const annotations = new Map<string, Annotation[]>([['eval-1', [shown, hidden]]])
    const trend = [makeTrendPoint({ evalId: 'eval-1' })]

    const option = buildChartOption(baseInput({ trend, annotations })) as Record<string, unknown>
    const tooltip = option.tooltip as { formatter: (params: unknown) => string }
    const html = tooltip.formatter([{ dataIndex: 0 }])

    expect(html).toContain('Deploy')
    expect(html).toContain('deploy &lt;v2&gt;') // HTML-escaped
    expect(html).not.toContain('internal only') // hidden category excluded
    expect(html).not.toContain('Internal')
  })
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `./scripts/ui-test.sh src/features/evaluations/hooks/useMetricTrendState.test.ts --tail 30`
Expected: FAIL — `html` does not contain `Deploy` (notes not yet rendered in the tooltip).

- [ ] **Step 4: Add note rendering to the tooltip formatter**

In `ui/src/features/evaluations/hooks/useMetricTrendState.ts`, extend the imports at the top. Change line 5 from:

```ts
import { buildNoteAnnotations, type MarkLineOption, type MarkPointOption } from '@/lib/chartAnnotations'
```

to:

```ts
import { buildNoteAnnotations, escapeHtml, type MarkLineOption, type MarkPointOption } from '@/lib/chartAnnotations'
import { paletteOf } from '@/features/note-categories'
```

Then replace `buildChartRender`'s entire tooltip `formatter` (currently lines 504-525). This both appends the note block and renames the single-letter local `p` → `point` throughout the block being touched (per the "no cryptic variable names" constraint — the formatter is the block we're editing). Change the formatter from:

```ts
      formatter: (params: unknown) => {
        const arr = Array.isArray(params) ? params : [params]
        const first = arr[0] as
          | { dataIndex?: number }
          | undefined
        const idx = first?.dataIndex
        const p = idx != null ? trend[idx] : undefined
        if (!p) return ''
        const lines = [
          `<b style="color:#58a6ff">${p.evaluationName ?? '(no evaluation_name)'}</b>`,
          `<b>${times[idx as number]}</b>`,
          `value: <b>${p.value}</b>`,
          `result: <b style="color:${colours[p.outcome as keyof typeof colours] ?? '#6b7280'}">${p.outcome.toUpperCase()}</b>`,
        ]
        if (p.overridden) lines.push(`<span style="color:${ct.axisLabel}">(override)</span>`)
        if (p.changePoint) {
          const cpColor = p.changePoint.direction === 'regression' ? 'var(--change-point-regression)' : 'var(--change-point-improvement)'
          const pctSign = p.changePoint.changeRelativePct > 0 ? '+' : ''
          lines.push(`<span style="color:${cpColor}">◆ ${p.changePoint.direction} (${pctSign}${p.changePoint.changeRelativePct.toFixed(1)}%)</span>`)
        }
        return lines.join('<br/>')
      },
```

to:

```ts
      formatter: (params: unknown) => {
        const arr = Array.isArray(params) ? params : [params]
        const first = arr[0] as
          | { dataIndex?: number }
          | undefined
        const idx = first?.dataIndex
        const point = idx != null ? trend[idx] : undefined
        if (!point) return ''
        const lines = [
          `<b style="color:#58a6ff">${point.evaluationName ?? '(no evaluation_name)'}</b>`,
          `<b>${times[idx as number]}</b>`,
          `value: <b>${point.value}</b>`,
          `result: <b style="color:${colours[point.outcome as keyof typeof colours] ?? '#6b7280'}">${point.outcome.toUpperCase()}</b>`,
        ]
        if (point.overridden) lines.push(`<span style="color:${ct.axisLabel}">(override)</span>`)
        if (point.changePoint) {
          const cpColor = point.changePoint.direction === 'regression' ? 'var(--change-point-regression)' : 'var(--change-point-improvement)'
          const pctSign = point.changePoint.changeRelativePct > 0 ? '+' : ''
          lines.push(`<span style="color:${cpColor}">◆ ${point.changePoint.direction} (${pctSign}${point.changePoint.changeRelativePct.toFixed(1)}%)</span>`)
        }
        // Always reveal showOnGraph notes on hover, even when pill display is toggled off —
        // matches the pill rule (only showOnGraph categories ever surface on the graph).
        const pointNotes = (annotations?.get(point.evalId) ?? []).filter(note => note.category.showOnGraph)
        if (pointNotes.length > 0) {
          lines.push(`<div style="margin-top:4px;border-top:1px solid ${ct.border}"></div>`)
          for (const note of pointNotes) {
            const noteColor = paletteOf(note.category.color).fg
            lines.push(
              `<div><b style="color:${noteColor}">${escapeHtml(note.category.label)}</b>: ${escapeHtml(note.content)}</div>`,
            )
          }
        }
        return lines.join('<br/>')
      },
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `./scripts/ui-test.sh src/features/evaluations/hooks/useMetricTrendState.test.ts --tail 30`
Expected: PASS — the new case and all existing cases green.

- [ ] **Step 6: Typecheck + lint**

Run: `just check`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add ui/src/lib/chartAnnotations.ts ui/src/features/evaluations/hooks/useMetricTrendState.ts ui/src/features/evaluations/hooks/useMetricTrendState.test.ts
git commit -m "feat(ui): show datapoint notes in trend chart hover tooltip"
```

---

## Task 3: Line ↔ bar chart-type in the pure builder

**Files:**
- Modify: `ui/src/features/evaluations/hooks/useMetricTrendState.ts` (`ChartOptionInput` ~line 277; `buildChartRender` destructure ~line 391; main series ~line 557)
- Test: `ui/src/features/evaluations/hooks/useMetricTrendState.test.ts`

**Interfaces:**
- Produces: `ChartOptionInput` gains `chartType?: 'line' | 'bar'` (defaults to `'line'` in `buildChartRender`). The main metric series is emitted with `type: chartType`; for `'bar'` the line-only props (`symbol`, `symbolSize`, `lineStyle`) are dropped and `barMaxWidth: 32` is set. `markLine`/`markPoint`, target series (`line`), and the change-point series (`scatter`) are unchanged.

- [ ] **Step 1: Write the failing bar-series tests**

In `ui/src/features/evaluations/hooks/useMetricTrendState.test.ts`, add inside the `describe('buildChartOption', ...)` block:

```ts
  it('emits a bar main series when chartType is bar (no line-only props)', () => {
    const trend = [makeTrendPoint({ value: 100 })]
    const option = buildChartOption(baseInput({ trend, chartType: 'bar' })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series[0].type).toBe('bar')
    expect(series[0].symbolSize).toBeUndefined()
    expect(series[0].lineStyle).toBeUndefined()
  })

  it('emits a line main series by default', () => {
    const option = buildChartOption(baseInput({ trend: [makeTrendPoint()] })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series[0].type).toBe('line')
  })

  it('keeps thresholds and change-points alongside a bar main series', () => {
    const trend = [
      makeTrendPoint({ value: 100, changePoint: { direction: 'regression', changeRelativePct: 12 } }),
    ]
    const option = buildChartOption(baseInput({
      trend,
      chartType: 'bar',
      targets: [{ key: 'pass:<=600', level: 'pass', criteria: '<=600', visible: true }],
    })) as Record<string, unknown>
    const series = option.series as Array<Record<string, unknown>>
    expect(series[0].type).toBe('bar')
    expect(series.some(s => s.type === 'scatter')).toBe(true) // change-point series
    expect(series.length).toBeGreaterThanOrEqual(3) // main + target + change-point
  })
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./scripts/ui-test.sh src/features/evaluations/hooks/useMetricTrendState.test.ts --tail 30`
Expected: FAIL — first case: `series[0].type` is `'line'`, not `'bar'` (chartType not yet honored).

- [ ] **Step 3: Add `chartType` to the input interface**

In `ui/src/features/evaluations/hooks/useMetricTrendState.ts`, in `interface ChartOptionInput` (ends ~line 306), add after `notesVisible?: boolean`:

```ts
  chartType?: 'line' | 'bar'
```

- [ ] **Step 4: Destructure `chartType` in buildChartRender**

In `buildChartRender`, in the destructure block (~lines 392-408), add `chartType = 'line',` alongside `notesVisible = true,`:

```ts
    chartWidth,
    notesVisible = true,
    chartType = 'line',
  } = input
```

- [ ] **Step 5: Build the main series with the chosen type**

Replace the main metric series object (currently lines 558-573, the first entry of the `series` array) from:

```ts
      {
        type: 'line',
        data: chartData,
        cursor: onEvalSelect ? 'pointer' : 'default',
        symbol: 'circle',
        symbolSize: (
          _val: unknown,
          params: { dataIndex: number },
        ) => {
          const p = trend[params.dataIndex]
          return p && isSelected(p) ? 10 : 6
        },
        lineStyle: { color: ct.line, width: 1.5 },
        ...(markLine ? { markLine } : {}),
        ...(markPoint ? { markPoint } : {}),
      },
```

to:

```ts
      {
        type: chartType,
        data: chartData,
        cursor: onEvalSelect ? 'pointer' : 'default',
        ...(chartType === 'line'
          ? {
              symbol: 'circle',
              symbolSize: (_val: unknown, params: { dataIndex: number }) => {
                const point = trend[params.dataIndex]
                return point && isSelected(point) ? 10 : 6
              },
              lineStyle: { color: ct.line, width: 1.5 },
            }
          : { barMaxWidth: 32 }),
        ...(markLine ? { markLine } : {}),
        ...(markPoint ? { markPoint } : {}),
      },
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `./scripts/ui-test.sh src/features/evaluations/hooks/useMetricTrendState.test.ts --tail 30`
Expected: PASS — new bar cases and all existing cases green.

- [ ] **Step 7: Typecheck + lint**

Run: `just check`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add ui/src/features/evaluations/hooks/useMetricTrendState.ts ui/src/features/evaluations/hooks/useMetricTrendState.test.ts
git commit -m "feat(ui): support bar chart type in trend chart builder"
```

---

## Task 4: `useMasterOverride` hook

**Files:**
- Create: `ui/src/features/evaluations/hooks/useMasterOverride.ts`
- Create: `ui/src/features/evaluations/hooks/useMasterOverride.test.ts`

**Interfaces:**
- Produces: `useMasterOverride<T>(master: T, generation: number): [T, (value: T) => void]`. Returns the effective value (`override ?? master`, where `override` is `null` until set) and a setter to apply a per-instance override. When `generation` changes, the override resets to `null` so the value re-follows `master`. This is the shared engine for both the notes switch and the chart-type toggle in `MetricTrendBlock`, and it is where the spec's "effective = override ?? master; a generation bump clears the override" behavior is unit-tested (extracted out of the component so it needs no ECharts/react-query mocking).

- [ ] **Step 1: Write the failing hook test**

Create `ui/src/features/evaluations/hooks/useMasterOverride.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useMasterOverride } from './useMasterOverride'

describe('useMasterOverride', () => {
  it('follows the master value until an override is set', () => {
    const { result } = renderHook(({ master, generation }) => useMasterOverride(master, generation), {
      initialProps: { master: true, generation: 0 },
    })
    expect(result.current[0]).toBe(true)
  })

  it('applies an override over the master value', () => {
    const { result } = renderHook(({ master, generation }) => useMasterOverride(master, generation), {
      initialProps: { master: true, generation: 0 },
    })
    act(() => result.current[1](false))
    expect(result.current[0]).toBe(false)
  })

  it('clears the override when the generation bumps (re-follows master)', () => {
    const { result, rerender } = renderHook(
      ({ master, generation }) => useMasterOverride(master, generation),
      { initialProps: { master: true, generation: 0 } },
    )
    act(() => result.current[1](false))
    expect(result.current[0]).toBe(false)
    rerender({ master: true, generation: 1 })
    expect(result.current[0]).toBe(true)
  })

  it('does not reset the override when master changes but generation does not', () => {
    const { result, rerender } = renderHook(
      ({ master, generation }) => useMasterOverride(master, generation),
      { initialProps: { master: true, generation: 0 } },
    )
    act(() => result.current[1](false))
    rerender({ master: false, generation: 0 })
    expect(result.current[0]).toBe(false) // still following the override
  })

  it('works with a string union (chart type)', () => {
    const { result } = renderHook(
      ({ master, generation }) => useMasterOverride<'line' | 'bar'>(master, generation),
      { initialProps: { master: 'line' as 'line' | 'bar', generation: 0 } },
    )
    act(() => result.current[1]('bar'))
    expect(result.current[0]).toBe('bar')
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./scripts/ui-test.sh src/features/evaluations/hooks/useMasterOverride.test.ts --tail 30`
Expected: FAIL — cannot resolve `./useMasterOverride`.

- [ ] **Step 3: Create the hook**

Create `ui/src/features/evaluations/hooks/useMasterOverride.ts`:

```ts
import { useState, useEffect } from 'react'

/**
 * Resolve a per-instance preference against a shared master value.
 *
 * Returns `[effective, setOverride]` where `effective = override ?? master`.
 * `override` starts as `null` ("follow master"). Calling `setOverride(value)`
 * pins this instance to `value`; when `generation` changes (i.e. the master was
 * toggled) the override resets to `null`, so every instance re-syncs to master.
 */
export function useMasterOverride<T>(master: T, generation: number): [T, (value: T) => void] {
  const [override, setOverride] = useState<T | null>(null)

  useEffect(() => {
    setOverride(null)
  }, [generation])

  const effective = override ?? master
  return [effective, setOverride as (value: T) => void]
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `./scripts/ui-test.sh src/features/evaluations/hooks/useMasterOverride.test.ts --tail 30`
Expected: PASS — all 5 cases green.

- [ ] **Step 5: Typecheck + lint**

Run: `just check`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ui/src/features/evaluations/hooks/useMasterOverride.ts ui/src/features/evaluations/hooks/useMasterOverride.test.ts
git commit -m "feat(ui): add useMasterOverride hook for master/per-chart preferences"
```

---

## Task 5: Move notes/chart-type ownership into MetricTrendBlock

**Files:**
- Modify: `ui/src/features/evaluations/hooks/useMetricTrendState.ts` (`MetricTrendState` interface ~lines 26-36; hook signature ~lines 150-160; state ~lines 161-165; builder input + deps ~lines 224-260; return ~lines 262-272)
- Modify: `ui/src/features/evaluations/components/MetricTrendBlock.tsx` (imports; hook destructure ~lines 137-154; notes button ~lines 207-218)
- Test: `ui/src/features/evaluations/hooks/useMetricTrendState.test.ts` (verify existing cases still pass — no new cases)

**Interfaces:**
- Consumes: `useChartPreferences()` (Task 1); `useMasterOverride` (Task 4); `chartType` support in the builder (Task 3).
- Produces: `useMetricTrendState(...)` gains two trailing params — `notesVisible: boolean = true` and `chartType: 'line' | 'bar' = 'line'` — after `chartWidth`. It **no longer owns** notes state: `MetricTrendState` drops `notesVisible` and `toggleNotes`. `MetricTrendBlock` now derives both effective values from context via `useMasterOverride` and renders a per-chart notes button and a per-chart chart-type button.

- [ ] **Step 1: Drop notes fields from the hook's return type**

In `ui/src/features/evaluations/hooks/useMetricTrendState.ts`, edit `interface MetricTrendState` (lines 26-36). Remove the last two fields so it becomes:

```ts
export interface MetricTrendState {
  yMin: string
  yMax: string
  setYMin: (v: string) => void
  setYMax: (v: string) => void
  targets: TargetToggle[]
  chartOption: object
  labelBandPx: number
}
```

- [ ] **Step 2: Add the two params to the hook signature; remove notes state**

Change the hook signature (lines 150-160) to append `notesVisible` and `chartType`:

```ts
export function useMetricTrendState(
  trend: TrendPoint[] | undefined,
  evalId: string,
  _indicator: Indicator,
  onEvalSelect?: (evalId: string) => void,
  selectedEvalIds?: ReadonlySet<string>,
  selectedPeriodStart?: string,
  annotations?: Map<string, Annotation[]>,
  categories?: NoteCategory[],
  chartWidth?: number,
  notesVisible = true,
  chartType: 'line' | 'bar' = 'line',
): MetricTrendState {
```

Remove the notes state (lines 164-165):

```ts
  const [notesVisible, setNotesVisible] = useState(true)
  const toggleNotes = useCallback(() => setNotesVisible(v => !v), [])
```

Delete both lines. (`useState` is still used for `yMin`/`yMax`/`visibility`; if `useCallback` becomes unused after this, remove it from the `react` import on line 2 — `just check` will flag it.)

- [ ] **Step 3: Thread `chartType` into the builder call**

In the `buildChartRender({...})` input object (lines 226-242), add `chartType,` next to `notesVisible,`:

```ts
        chartWidth,
        notesVisible,
        chartType,
      }),
```

Add `chartType` to that `useMemo`'s dependency array (after `notesVisible,` at line 258):

```ts
      notesVisible,
      chartType,
    ],
  )
```

- [ ] **Step 4: Remove notes fields from the hook return**

Change the return (lines 262-272) to:

```ts
  return {
    yMin,
    yMax,
    setYMin,
    setYMax,
    targets,
    chartOption: chartResult.option,
    labelBandPx: chartResult.labelBandPx,
  }
}
```

- [ ] **Step 5: Run the existing hook tests to verify they still pass**

Run: `./scripts/ui-test.sh src/features/evaluations/hooks/useMetricTrendState.test.ts --tail 30`
Expected: PASS — existing `useMetricTrendState` cases call the hook with ≤3 args, so the new params take their defaults; nothing references the removed `notesVisible`/`toggleNotes`.

- [ ] **Step 6: Wire MetricTrendBlock to context + overrides**

In `ui/src/features/evaluations/components/MetricTrendBlock.tsx`:

Update the lucide import (line 4) to add the chart-type icons:

```tsx
import { MessageSquareWarning, Sheet, Tags, LineChart, BarChart3 } from 'lucide-react'
```

Add two imports after the existing `useMetricTrendState` import (after line 9):

```tsx
import { useChartPreferences } from '@/lib/chart-preferences-context'
import { useMasterOverride } from '../hooks/useMasterOverride'
```

Inside the `MetricTrendBlock` component, right after the `useNoteCategories()` line (line 104), read the context and derive effective values:

```tsx
  const { notesMaster, notesGeneration, chartTypeMaster, chartTypeGeneration } = useChartPreferences()
  const [notesVisible, setNotesOverride] = useMasterOverride(notesMaster, notesGeneration)
  const [chartType, setChartTypeOverride] = useMasterOverride(chartTypeMaster, chartTypeGeneration)
```

Change the hook destructure + call (lines 137-154). Remove `notesVisible, toggleNotes,` from the destructured object and pass the two new args at the end of the call:

```tsx
  const {
    yMin, yMax, setYMin, setYMax,
    targets,
    chartOption,
    labelBandPx,
  } = useMetricTrendState(
    trend,
    selectedEvalId ?? '',
    indicator,
    onEvalSelect,
    selectedEvalIds,
    selectedPeriodStart,
    annotations,
    categories,
    containerWidth,
    notesVisible,
    chartType,
  )
```

- [ ] **Step 7: Repoint the notes button and add the chart-type button**

Replace the toolbar button group (lines 206-220, the `<div className="flex items-center gap-1 ml-auto text-xs">` block) with:

```tsx
            <div className="flex items-center gap-1 ml-auto text-xs">
              <button
                onClick={() => setNotesOverride(!notesVisible)}
                className={`p-1 rounded border transition-colors ${
                  notesVisible
                    ? 'border-primary/40 text-primary'
                    : 'border-border text-muted-foreground/60'
                }`}
                title="Toggle notes on chart"
                aria-label="Toggle notes on chart"
              >
                <MessageSquareWarning className="size-3.5" />
              </button>
              <button
                onClick={() => setChartTypeOverride(chartType === 'line' ? 'bar' : 'line')}
                className="p-1 rounded border border-border text-muted-foreground/60 transition-colors"
                title={chartType === 'line' ? 'Show as bars' : 'Show as line'}
                aria-label="Toggle chart type"
              >
                {chartType === 'line' ? <BarChart3 className="size-3.5" /> : <LineChart className="size-3.5" />}
              </button>
              <TargetDropdown targets={targets} />
            </div>
```

- [ ] **Step 8: Typecheck + lint + full UI test run**

Run: `just check`
Expected: PASS — confirms `MetricTrendBlock` compiles against the new hook shape and no unused imports remain.

Run: `./scripts/ui-test.sh --tail 40`
Expected: PASS — the whole UI suite is green. (The tests that render the section/panel/page mock `MetricTrendBlock` and the two view components, so the new `useChartPreferences()` call is never exercised without a provider there.)

- [ ] **Step 9: Commit**

```bash
git add ui/src/features/evaluations/hooks/useMetricTrendState.ts ui/src/features/evaluations/components/MetricTrendBlock.tsx
git commit -m "feat(ui): drive trend chart notes and type from shared master with per-chart override"
```

---

## Task 6: ChartViewControls + columns layout across the three views

**Files:**
- Create: `ui/src/components/charts/ChartViewControls.tsx`
- Create: `ui/src/components/charts/ChartViewControls.test.tsx`
- Modify: `ui/src/features/evaluations/components/EvaluationIndicatorSection.tsx` (lines 70-89)
- Modify: `ui/src/features/navigator/components/AssetPanelChartView.tsx` (lines 191-206)
- Modify: `ui/src/features/navigator/components/AssetPanelHeatmapView.tsx` (heatmap header lines 223-229; trend grid line 316)

**Interfaces:**
- Consumes: `useChartPreferences()` (Task 1).
- Produces: `<ChartViewControls />` — a self-contained header control cluster with a columns segmented toggle (1/row, 2/row), a master notes icon toggle, and a master chart-type segmented toggle (line/bar). Each of the three trend-grid views renders it in its header and computes its grid class from `columns`.

- [ ] **Step 1: Write the failing control test**

Create `ui/src/components/charts/ChartViewControls.test.tsx`:

```tsx
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ChartViewControls } from './ChartViewControls'
import { ChartPreferencesProvider } from '@/lib/chart-preferences-context'

function renderControls() {
  return render(
    <ChartPreferencesProvider>
      <ChartViewControls />
    </ChartPreferencesProvider>,
  )
}

describe('ChartViewControls', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('sets columns to 1 when the "1 / row" option is clicked', () => {
    renderControls()
    fireEvent.click(screen.getByRole('button', { name: '1 / row' }))
    expect(localStorage.getItem('tropek.chartColumns')).toBe('1')
  })

  it('toggles the master notes switch', () => {
    renderControls()
    fireEvent.click(screen.getByRole('button', { name: 'Toggle notes on all charts' }))
    expect(localStorage.getItem('tropek.notesMaster')).toBe('false')
  })

  it('switches the master chart type to bar', () => {
    renderControls()
    fireEvent.click(screen.getByRole('button', { name: 'Show all charts as bars' }))
    expect(localStorage.getItem('tropek.chartType')).toBe('bar')
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./scripts/ui-test.sh src/components/charts/ChartViewControls.test.tsx --tail 30`
Expected: FAIL — cannot resolve `./ChartViewControls`.

- [ ] **Step 3: Create the ChartViewControls component**

Create `ui/src/components/charts/ChartViewControls.tsx`:

```tsx
import { MessageSquareWarning, LineChart, BarChart3 } from 'lucide-react'
import { useChartPreferences } from '@/lib/chart-preferences-context'

/** Cross-chart controls: columns layout, master notes switch, master chart type.
 * Reads the shared ChartPreferences context; drop it into any trend-grid header. */
export function ChartViewControls() {
  const {
    columns,
    setColumns,
    notesMaster,
    toggleNotesMaster,
    chartTypeMaster,
    toggleChartType,
  } = useChartPreferences()

  return (
    <div className="flex items-center gap-2 text-xs">
      {/* Columns: 1 / row vs 2 / row */}
      <div className="flex border border-border rounded overflow-hidden">
        <button
          type="button"
          onClick={() => setColumns(1)}
          className={`px-2 py-1 transition-colors ${columns === 1 ? 'bg-state-selected-bg text-foreground' : 'text-muted-foreground'}`}
        >
          1 / row
        </button>
        <button
          type="button"
          onClick={() => setColumns(2)}
          className={`px-2 py-1 transition-colors ${columns === 2 ? 'bg-state-selected-bg text-foreground' : 'text-muted-foreground'}`}
        >
          2 / row
        </button>
      </div>

      {/* Master notes switch */}
      <button
        type="button"
        onClick={toggleNotesMaster}
        className={`p-1 rounded border transition-colors ${
          notesMaster ? 'border-primary/40 text-primary' : 'border-border text-muted-foreground/60'
        }`}
        title="Show or hide notes on all charts"
        aria-label="Toggle notes on all charts"
      >
        <MessageSquareWarning className="size-3.5" />
      </button>

      {/* Master chart type: line vs bar */}
      <div className="flex border border-border rounded overflow-hidden">
        <button
          type="button"
          onClick={() => { if (chartTypeMaster !== 'line') toggleChartType() }}
          className={`px-2 py-1 transition-colors ${chartTypeMaster === 'line' ? 'bg-state-selected-bg text-foreground' : 'text-muted-foreground'}`}
          title="Show all charts as lines"
          aria-label="Show all charts as lines"
        >
          <LineChart className="size-3.5" />
        </button>
        <button
          type="button"
          onClick={() => { if (chartTypeMaster !== 'bar') toggleChartType() }}
          className={`px-2 py-1 transition-colors ${chartTypeMaster === 'bar' ? 'bg-state-selected-bg text-foreground' : 'text-muted-foreground'}`}
          title="Show all charts as bars"
          aria-label="Show all charts as bars"
        >
          <BarChart3 className="size-3.5" />
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `./scripts/ui-test.sh src/components/charts/ChartViewControls.test.tsx --tail 30`
Expected: PASS — all 3 cases green.

- [ ] **Step 5: Wire into EvaluationIndicatorSection**

In `ui/src/features/evaluations/components/EvaluationIndicatorSection.tsx`, add the imports at the top (after line 6):

```tsx
import { ChartViewControls } from '@/components/charts/ChartViewControls'
import { useChartPreferences } from '@/lib/chart-preferences-context'
```

Inside the component, after the `useTabState` destructure (line 20), read columns:

```tsx
  const { columns } = useChartPreferences()
```

Replace the trend header + grid (lines 70-89) so the controls sit in a header row and the grid class follows `columns`:

```tsx
      {/* Trend charts */}
      <div className="space-y-4">
        <div className="flex items-start justify-between gap-3">
          <p className="text-xs text-muted-foreground">
            30-day trend for{' '}
            <strong className="text-foreground">{activeTab === 'all' ? 'All' : tabLabel(activeTab)}</strong>{' '}
            metrics on <strong className="text-foreground">{ev.assetSnapshot.displayName ?? assetDisplayName ?? ev.assetSnapshot.name}</strong>.
            Dot colour reflects each metric's own pass/warn/fail result.
          </p>
          <ChartViewControls />
        </div>
        <div className={columns === 1 ? 'grid grid-cols-1 gap-4' : 'grid grid-cols-1 xl:grid-cols-2 gap-4'}>
          {tabIndicators.map(ind => (
            <MetricTrendBlock
              key={ind.metric}
              assetName={ev.assetSnapshot.name}
              sloName={ev.sloName ?? ''}
              sloDisplayName={sloDisplayName}
              selectedEvalId={ev.id}
              indicator={ind}
              onScrollToTable={handleScrollToTable}
            />
          ))}
        </div>
      </div>
```

- [ ] **Step 6: Wire into AssetPanelChartView**

In `ui/src/features/navigator/components/AssetPanelChartView.tsx`, add imports at the top (after line 6):

```tsx
import { ChartViewControls } from '@/components/charts/ChartViewControls'
import { useChartPreferences } from '@/lib/chart-preferences-context'
```

Inside the component, after the `metricGroupFilter` state (line 38):

```tsx
  const { columns } = useChartPreferences()
```

Replace the filter row + grid (lines 191-206) with a filter row that also carries the controls, and a `columns`-driven grid:

```tsx
      {effectiveEvalId && (
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-3">
            <MetricGroupFilter
              allIndicators={allIndicators}
              metricGroups={metricGroups}
              activeFilter={metricGroupFilter}
              onFilterChange={setMetricGroupFilter}
            />
            <ChartViewControls />
          </div>

          <div className={columns === 1 ? 'grid grid-cols-1 gap-4' : 'grid grid-cols-1 xl:grid-cols-2 gap-4'}>
            {chartIndicators.map(ind => (
              <MetricTrendBlock key={ind.metric} assetName={assetName} sloName={metricSloMap.get(ind.metric) ?? ''} sloDisplayName={metricSloDisplayMap.get(ind.metric)} selectedEvalId={effectiveEvalId} selectedEvalIds={selectedColumnSloEvalIds} selectedPeriodStart={selectedPeriodStart} indicator={ind} onEvalSelect={handleTrendClick} />
            ))}
          </div>
        </div>
      )}
```

- [ ] **Step 7: Wire into AssetPanelHeatmapView**

In `ui/src/features/navigator/components/AssetPanelHeatmapView.tsx`, add imports at the top (after line 13):

```tsx
import { ChartViewControls } from '@/components/charts/ChartViewControls'
import { useChartPreferences } from '@/lib/chart-preferences-context'
```

Inside the component, after the `heatmapRef` declaration (line 51):

```tsx
  const { columns } = useChartPreferences()
```

Add the controls to the Metric Heatmap header. Change lines 224-229 from:

```tsx
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Metric Heatmap</h2>
            <div className="flex items-center gap-3">
              <ViewToggle mode={mode} setMode={setMode} />
              {explorerButton}
            </div>
          </div>
```

to:

```tsx
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Metric Heatmap</h2>
            <div className="flex items-center gap-3">
              <ChartViewControls />
              <ViewToggle mode={mode} setMode={setMode} />
              {explorerButton}
            </div>
          </div>
```

Then make each SLO group's trend grid follow `columns`. Change line 316 from:

```tsx
                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
```

to:

```tsx
                    <div className={columns === 1 ? 'grid grid-cols-1 gap-4' : 'grid grid-cols-1 xl:grid-cols-2 gap-4'}>
```

- [ ] **Step 8: Typecheck + lint + full UI test run**

Run: `just check`
Expected: PASS.

Run: `./scripts/ui-test.sh --tail 40`
Expected: PASS — full UI suite green (`AssetPanel.test.tsx` mocks both view components, so their new `useChartPreferences()` calls aren't exercised there without a provider).

- [ ] **Step 9: Commit**

```bash
git add ui/src/components/charts/ChartViewControls.tsx ui/src/components/charts/ChartViewControls.test.tsx ui/src/features/evaluations/components/EvaluationIndicatorSection.tsx ui/src/features/navigator/components/AssetPanelChartView.tsx ui/src/features/navigator/components/AssetPanelHeatmapView.tsx
git commit -m "feat(ui): add columns/notes/chart-type controls to all trend-chart views"
```

---

## Task 7: Manual verification

**Files:** none (runtime verification against the running dev UI).

- [ ] **Step 1: Start the dev environment**

Run: `just dev`
Expected: UI reachable at http://localhost:3000.

- [ ] **Step 2: Columns toggle + persistence**

Open the Navigator, select an asset with trend charts. In each of the three views (Evaluation detail indicator section, Asset panel Chart view, Asset panel Heatmap view):
- Click "1 / row" → charts stack one-per-row and pills spread out legibly; click "2 / row" → back to two-up.
- Reload the page → the last columns choice persists (localStorage `tropek.chartColumns`).

- [ ] **Step 3: Master notes switch + per-chart override**

- Flip the master notes switch off → note pills disappear on every chart at once; on → they return.
- On a single chart, click its per-chart notes button to override (opposite of master) → only that chart changes.
- Flip the master again → every chart (including the overridden one) re-syncs to the master value.

- [ ] **Step 4: Master chart-type switch + per-chart override**

- Flip the master line↔bar toggle → all metric series switch between line and bar; thresholds stay lines, change-point diamonds and note pills remain.
- Override one chart's type via its per-chart button → only that chart changes; flipping the master re-syncs all charts (independently of the notes override — toggling type must not reset a notes override and vice versa).

- [ ] **Step 5: Hover-note tooltip**

- Hover a datapoint that has one or more `showOnGraph` notes → the existing tooltip (eval name, time, value, result, change-point) now shows a divider and one line per note (`<category label>: <content>`), colored by category.
- Confirm hover still reveals notes even when the master notes switch is OFF.

- [ ] **Step 6: Final full check**

Run: `just check`
Expected: PASS.

Run: `./scripts/ui-test.sh --tail 40`
Expected: PASS — entire UI suite green.

---

## Self-Review notes (author checklist — already applied)

- **Spec §1 shared preferences context** → Task 1 (`chart-preferences-context.tsx`, all three prefs + two generations, persisted keys, defaults).
- **Spec §2 columns toggle** → Task 6 (control + `columns`-driven grid class in all three views).
- **Spec §3 master notes + per-chart override** → Tasks 4 (`useMasterOverride`) + 5 (hook loses notes ownership; `MetricTrendBlock` derives effective visibility, generation resets override) + 6 (master control).
- **Spec §4 hover-note tooltip** → Task 2 (`showOnGraph`-filtered, escaped, colored via `paletteOf`, not gated by the notes toggle).
- **Spec §5 chart-type toggle + per-chart override** → Tasks 3 (`chartType` in builder) + 5 (`MetricTrendBlock` override + button) + 6 (master control). Independent generation counters ensure the two overrides don't reset each other.
- **Spec Testing** → context persistence/generation (Task 1), tooltip content include/exclude (Task 2), bar-series emission with pills/thresholds/change-points intact (Task 3), effective = override ?? master + generation-clears-override (Task 4, the extracted engine used by both toggles), control interactions (Task 6), manual matrix (Task 7).
- **Type consistency:** `ChartColumns`/`ChartType` names, `useMasterOverride<T>` tuple `[T, (value: T) => void]`, and the two trailing hook params (`notesVisible`, `chartType`) are used identically wherever referenced.
- **Non-goals honored:** no API/backend changes; `chartAnnotations.ts` packing untouched (only `escapeHtml` exported); no new note-packing algorithm.
