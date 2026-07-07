# Chart View Controls: Columns Toggle, Master Notes Switch, Hover-Note Tooltip

**Date:** 2026-07-02
**Status:** Design — pending review
**Area:** `ui/` — evaluation trend charts (`MetricTrendBlock` and its consumers)

## Problem

Trend charts render many note annotations (pills) above each plot. Two friction points:

1. **Too many pills, too little width.** With charts laid out two-per-row (`xl:grid-cols-2`),
  each chart is narrow, so the note-packing logic crams pills into up to three tight rows.
  Labels are clipped and overlap, making it impossible to tell which note belongs to which
  datapoint. Giving each chart a full row spreads the pills far more legibly.
2. **No efficient way to reveal a datapoint's note or bulk-toggle notes.** Hovering a datapoint
  does not show its note text, and notes can only be toggled one chart at a time — there is no
  single control to show/hide notes across every chart on screen.

## Goals

- A toggle to switch chart layout between **1 chart per row** and **2 charts per row**, shared
 across all views that render trend charts, and persisted across sessions.
- A **master notes switch** that shows/hides note pills across all charts at once, while
 preserving per-chart override.
- On **datapoint hover**, append that datapoint's notes to the bottom of the existing tooltip.
- A **chart-type toggle** (line ↔ bar) for the metric's own series, with the same master +
 per-chart-override behavior as the notes switch. Bars may read better at the larger
 one-per-row size.

## Non-goals

- No API/backend changes. All annotation data is already fetched and in scope on the client.
- No change to how notes are authored, categorized, or stored.
- No new note-packing algorithm — the existing `packRows` logic in `chartAnnotations.ts`
 already benefits automatically from wider charts.

## Current-state findings (code paths)

- **Charting:** ECharts 6 via `echarts-for-react`. Single chart component:
 `ui/src/features/evaluations/components/MetricTrendBlock.tsx`.
- **Chart option builder / tooltip:** `ui/src/features/evaluations/hooks/useMetricTrendState.ts`.
 The tooltip `formatter` (~line 472) already closes over `annotations: Map<evalId, Annotation[]>`
 and `categories: NoteCategory[]`.
- **Note pills:** built in `ui/src/lib/chartAnnotations.ts` (`buildNoteAnnotations`, `packRows`,
 `prepareLabels`). Pill visibility for a note depends on `annotation.category.showOnGraph`.
- **Notes visibility today:** owned by a per-chart `useState('notesVisible', true)` inside
 `useMetricTrendState` (line ~132), toggled by the `MessageSquareWarning` button in
 `MetricTrendBlock.tsx` (~line 207). There is no cross-chart control.
- **The 2-per-row grid appears in THREE places**, all with identical class
 `grid grid-cols-1 xl:grid-cols-2 gap-4`, all rendering `MetricTrendBlock`:
 - `ui/src/features/evaluations/components/EvaluationIndicatorSection.tsx:77`
 - `ui/src/features/navigator/components/AssetPanelChartView.tsx:200`
 - `ui/src/features/navigator/components/AssetPanelHeatmapView.tsx:316`
- **Toggle conventions to mirror:** `ui/src/components/charts/ViewToggle.tsx` (segmented button),
 the bordered icon-button in `MetricTrendBlock.tsx` `TargetDropdown`.
- **Persisted-context convention to mirror:** `ui/src/lib/theme-context.tsx` (Context + localStorage).

## Design

### 1. Shared preferences context

New `ui/src/lib/chart-preferences-context.tsx`, modeled on `theme-context.tsx`, provided at the
app root. It holds two independent preferences, both persisted to `localStorage`:

```
interface ChartPreferences {
 columns: 1 | 2
 setColumns: (n: 1 | 2) => void

 notesMaster: boolean            // global show/hide for note pills
 toggleNotesMaster: () => void
 notesGeneration: number         // bumped on each master flip; used to re-sync charts

 chartTypeMaster: 'line' | 'bar' // global series type for the metric's own series
 toggleChartType: () => void
 chartTypeGeneration: number     // bumped on each master flip; independent of notesGeneration
}
```

- `columns` defaults to `2` (preserves current behavior). Persisted key e.g. `tropek.chartColumns`.
 > **Superseded (2026-07-07 follow-up):** the shipped default is `1` (one chart per row). The
 > wider single-column layout directly serves the legibility problem in §Problem, so this was a
 > deliberate product decision. Trade-off: existing users see a one-up layout on first load until
 > they pick a layout (persisted thereafter) instead of the previous two-up default.
- `notesMaster` defaults to `true` (preserves current default-on behavior). Persisted key e.g.
 `tropek.notesMaster`. `notesGeneration` is in-memory only (not persisted) and increments
 whenever `toggleNotesMaster` runs.
- `chartTypeMaster` defaults to `'line'` (preserves current behavior). Persisted key e.g.
 `tropek.chartType`. `chartTypeGeneration` is in-memory only and increments on each
 `toggleChartType`. The two generation counters are independent so toggling chart type does not
 reset per-chart note overrides, and vice versa.

### 2. Columns toggle

- Add a small segmented control (reuse/extend the `ViewToggle` pattern) reading/writing
 `columns` from the context. Label options: "1 / row" and "2 / row" (or icons).
- In each of the three views, replace the hardcoded grid class with:
 `columns === 1 ? 'grid grid-cols-1 gap-4' : 'grid grid-cols-1 xl:grid-cols-2 gap-4'`.
- Place the control in each view's header row:
 - `EvaluationIndicatorSection`: in the "30-day trend for …" header area (near line 70-76).
 - `AssetPanelChartView`: alongside the existing `MetricGroupFilter` row.
 - `AssetPanelHeatmapView`: in the panel header, near the existing controls.
- No change needed to `chartAnnotations.ts`: pill packing already keys off measured chart width
 (via the `ResizeObserver` in `MetricTrendBlock`), so wider charts spread pills automatically.

### 3. Master notes switch + per-chart override

Move notes-visibility ownership **out of** `useMetricTrendState` and **into** `MetricTrendBlock`:

- `useMetricTrendState` stops owning `notesVisible`/`toggleNotes` state. Instead it accepts
 `notesVisible: boolean` as a parameter (it already forwards this value into `buildChartRender`).
 Its return type drops `notesVisible`/`toggleNotes`.
- `MetricTrendBlock`:
 - Reads `notesMaster` and `notesGeneration` from the context.
 - Holds `localOverride: boolean | null` via `useState` (null = "follow master").
 - Effective `notesVisible = localOverride ?? notesMaster`, passed into `useMetricTrendState`.
 - The per-chart `MessageSquareWarning` button sets `localOverride` to `!notesVisible`.
 - A `useEffect` keyed on `notesGeneration` resets `localOverride` back to `null`, so flipping the
   master re-syncs every chart to the master value.
 - Charts that mount later (tab/filter/group changes) start with `localOverride === null` and thus
   inherit the current persisted `notesMaster`.
- Add a master switch control (segmented or the same bordered icon-button style) bound to
 `notesMaster` / `toggleNotesMaster`, placed next to the columns toggle in each view header.

**Resulting behavior:**
- Master flip → all charts follow.
- Per-chart button → overrides just that chart until the next master flip.
- New charts inherit the persisted master.

### 4. Note in datapoint-hover tooltip

In `buildChartRender`'s existing `formatter` (`useMetricTrendState.ts` ~line 472), after the
current `lines` (evaluation name, timestamp, value, result, override, change-point), append:

- Look up `const pointNotes = annotations?.get(point.evalId) ?? []`.
- Filter to `note.category.showOnGraph === true`.
- If any remain, push a separator, then one line per note:
 `<div><b style="color:{fg}">{category.label}</b>: {escaped content}</div>`,
 where `fg` comes from `paletteOf(note.category.color)` (already imported from
 `@/features/note-categories` in `chartAnnotations.ts`; import into this module).
- HTML-escape note content (add a small local `escapeHtml`, or export the existing one from
 `chartAnnotations.ts`).
- This is **not** gated by the notes toggle — hover always reveals `showOnGraph` notes even when
 pills are hidden. (Consistent with the pills, which also only show `showOnGraph` categories.)

### 5. Chart-type toggle (line ↔ bar) + per-chart override

Mirrors the notes switch exactly, applied to the metric's own series type:

- **Context:** `chartTypeMaster` / `toggleChartType` / `chartTypeGeneration` (see section 1).
- **`useMetricTrendState` / `buildChartRender`:** add `chartType: 'line' | 'bar'` to
 `ChartOptionInput`, threaded from the hook parameter. The main metric series
 (`useMetricTrendState.ts` ~line 517) is built with `type: chartType`:
 - `line`: keep current `symbol: 'circle'`, dynamic `symbolSize`, `lineStyle`.
 - `bar`: drop the line-only props (`symbol`/`symbolSize`/`lineStyle`), optionally set a sane
   `barMaxWidth`. Per-datapoint `itemStyle` colors and selection borders already apply to bars.
 - `markLine` / `markPoint` (note pills) and the per-datapoint click handler attach to a bar
   series unchanged. Threshold series stay `line`; the change-point series stays `scatter`.
- **`MetricTrendBlock`:** holds `chartTypeOverride: 'line' | 'bar' | null` (null = follow master).
 Effective `chartType = chartTypeOverride ?? chartTypeMaster`, passed into the hook. A per-chart
 control sets the override; a `useEffect` keyed on `chartTypeGeneration` resets the override to
 `null` on a master flip. New charts inherit the persisted master.
- **Controls:** master chart-type toggle in each view header (next to columns + notes controls),
 plus a per-chart control in the `MetricTrendBlock` toolbar alongside the existing notes/target
 buttons, following the `ViewToggle` / bordered icon-button conventions.

## Testing

- **Unit (existing pattern):** `buildChartRender` / `buildChartOption` are pure and already tested.
 Add cases asserting the tooltip `formatter` output includes `showOnGraph` note content for a
 datapoint and excludes non-`showOnGraph` notes.
- **Context:** small test for `chart-preferences-context` persistence (read/write localStorage,
 `notesGeneration` increments on master toggle).
- **Component:** verify `MetricTrendBlock` effective visibility = `localOverride ?? notesMaster`
 and effective type = `chartTypeOverride ?? chartTypeMaster`; a `notesGeneration` bump clears the
 notes override and a `chartTypeGeneration` bump clears the chart-type override — independently.
- **Chart type:** unit-assert `buildChartRender` emits a `bar` main series when `chartType: 'bar'`
 (and `line` otherwise), with note pills / thresholds / change-points still present.
- **Manual:** toggle columns (1↔2) and confirm all three views + persistence across reload;
 master notes switch hides/shows across charts; master chart-type switch flips line↔bar across
 charts; each per-chart override survives until its own master flip; hover a datapoint with notes
 and confirm the tooltip shows them.

## Rollout / risk

- Pure UI change, additive. Notes-on and line-chart defaults preserve current behavior. (The
 columns default shipped as `1` rather than `2` — see the follow-up note in §1.)
- Main refactor risk is moving notes state out of `useMetricTrendState`; mitigated by the hook
 already threading `notesVisible` through to `buildChartRender`.

## Open questions

- None blocking. Control styling (segmented vs icon buttons) and exact header placement to be
 finalized during implementation, following existing `ViewToggle` / `TargetDropdown` conventions.
