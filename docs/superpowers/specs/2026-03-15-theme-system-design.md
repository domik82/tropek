# Theme System Design

**Date:** 2026-03-15
**Status:** Draft

## Overview

Implement a live, switchable theme system for the TROPEK UI with two dark themes available immediately (for comparison/development) and the architecture ready to add a corporate light theme later. A `🌙 Dark / ☀️ Light` toggle lives in the navbar; a font-size `−/+` control sits alongside it.

## Goals

- Switch between Forest dark and Current (shadcn/ui neutral) dark themes instantly in the running app
- Persist the chosen theme and font size to `localStorage`
- Replace hardcoded colour values in UI chrome and chart components with CSS-variable-driven tokens
- Keep status colours (pass/warning/fail) as a theme-aware object so they complement each theme
- Lay the groundwork for a Corporate light theme (tokens defined, `ThemeProvider` already typed for it)
- Font size adjustable via `−/+` control, range 12–18px, scales all `rem`-based Tailwind utilities

## Non-Goals

- Implementing the Corporate light theme UI (deferred — tokens defined but not activated)
- Changing ECharts chart types or layout
- Migrating every hardcoded `#7dc540` usage in SLO forms to CSS variables (those are accent/brand usages, not status, and are deferred)

---

## Architecture

### Token Strategy — `data-theme` attribute

Theme is controlled by a `data-theme` attribute on `<html>`. Three CSS blocks in `index.css` map each theme's values to the existing shadcn/ui variable names. All components continue using `bg-primary`, `text-foreground`, `border-border`, etc. — most components need no changes.

```css
[data-theme="current"]   { --background: ...; --primary: ...; ... }
[data-theme="forest"]    { --background: ...; --primary: ...; ... }
[data-theme="corporate"] { ... }   /* stub — not yet activated in UI */
```

The `@theme inline` block in `index.css` that maps CSS vars to Tailwind utility classes is **unchanged**.

### `@custom-variant dark` — updated to match `data-theme`

`index.css` line 4 currently reads:
```css
@custom-variant dark (&:is(.dark *));
```

This must be updated so shadcn/ui `dark:` Tailwind variants fire on both dark themes:
```css
@custom-variant dark (&:is([data-theme="forest"] *), &:is([data-theme="current"] *));
```

When corporate (light) theme is active, `data-theme="corporate"` is set and neither selector matches — `dark:` variants correctly do not fire.

### Token Mapping — Current Dark (shadcn/ui neutral)

Values are identical to the existing `.dark {}` block — just moved to `[data-theme="current"]`.

### Token Mapping — Forest Dark → shadcn/ui names

| shadcn/ui variable | Forest value |
|---|---|
| `--background` | `oklch(20.84% 0.008 17.911)` |
| `--foreground` | `oklch(83.768% 0.001 17.911)` |
| `--card`, `--popover` | `oklch(18.522% 0.007 17.911)` |
| `--card-foreground`, `--popover-foreground` | `oklch(83.768% 0.001 17.911)` |
| `--primary` | `oklch(68.628% 0.185 148.958)` — green |
| `--primary-foreground` | `oklch(0% 0 0)` |
| `--secondary`, `--muted` | `oklch(30.698% 0.039 171.364)` — teal-neutral |
| `--secondary-foreground`, `--muted-foreground` | `oklch(86.139% 0.007 171.364)` |
| `--accent` | `oklch(30.698% 0.039 171.364)` |
| `--accent-foreground` | `oklch(86.139% 0.007 171.364)` |
| `--border`, `--input` | `oklch(30.698% 0.039 171.364 / 40%)` |
| `--ring` | `oklch(68.628% 0.185 148.958 / 50%)` |
| `--destructive` | `oklch(71.76% 0.221 22.18)` |
| `--destructive-foreground` | `oklch(0% 0 0)` |
| `--radius` | `0.5rem` (unchanged) |
| `--chart-1` through `--chart-5` | Forest accent palette (teal/green range, to be defined) |

### Token Mapping — Corporate Light → shadcn/ui names (partial stub)

The following tokens are defined; all omitted tokens fall back to `:root` defaults (which are the existing shadcn light values — acceptable for a stub).

| shadcn/ui variable | Corporate value |
|---|---|
| `--background` | `oklch(100% 0 0)` |
| `--foreground` | `oklch(22.389% 0.031 278.072)` |
| `--card`, `--popover` | `oklch(93% 0 0)` |
| `--card-foreground`, `--popover-foreground` | `oklch(22.389% 0.031 278.072)` |
| `--primary` | `oklch(58% 0.158 241.966)` — blue |
| `--primary-foreground` | `oklch(100% 0 0)` |
| `--secondary`, `--muted` | `oklch(86% 0 0)` |
| `--secondary-foreground`, `--muted-foreground` | `oklch(22.389% 0.031 278.072)` |
| `--accent` | `oklch(86% 0 0)` |
| `--accent-foreground` | `oklch(22.389% 0.031 278.072)` |
| `--border`, `--input` | `oklch(86% 0 0)` |
| `--ring` | `oklch(58% 0.158 241.966 / 50%)` |
| `--destructive` | `oklch(70% 0.191 22.216)` |
| `--destructive-foreground` | `oklch(100% 0 0)` |

### ThemeContext

New file `src/lib/theme-context.tsx` (~30 lines):

```ts
type Theme = 'current' | 'forest' | 'corporate'

// ThemeProvider:
//   - reads localStorage('tropek-theme') on mount, defaults to 'forest'
//   - sets document.documentElement.setAttribute('data-theme', theme)
//   - tracks fontSize: number (default 14, range 12–18)
//   - sets document.documentElement.style.fontSize = fontSize + 'px'
//   - persists fontSize to localStorage('tropek-font-size')
//   - exports: ThemeProvider, useTheme()

// useTheme() returns:
//   theme: Theme
//   setTheme: (t: Theme) => void
//   isDark: boolean        // theme !== 'corporate'
//   fontSize: number
//   setFontSize: (n: number) => void
```

`ThemeProvider` wraps the root `App` component. `useTheme()` is available anywhere in the tree.

### Status Colours — theme-aware

`lib/theme.ts` gains a theme-keyed `RESULT_COLOUR` and `CHART_THEME`. The existing flat `RESULT_COLOUR` export is replaced.

```ts
export type Theme = 'current' | 'forest' | 'corporate'

export interface ResultColours {
  pass: string; warning: string; fail: string; error: string; invalidated: string
}

export interface ChartTheme {
  bg: string; border: string; axisLabel: string; grid: string
}

// Used in heatmap cells, trend dots, ResultBadge, SLIBreakdownTable, threshold lines
export const RESULT_COLOUR: Record<Theme, ResultColours> = {
  current: {
    pass:        '#7dc540',
    warning:     '#e6be00',
    fail:        '#dc172a',
    error:       '#888888',
    invalidated: '#b0b0b0',
  },
  forest: {
    pass:        'oklch(64.8% 0.15 160)',
    warning:     'oklch(84.71% 0.199 83.87)',
    fail:        'oklch(71.76% 0.221 22.18)',
    error:       'oklch(50% 0 0)',
    invalidated: 'oklch(65% 0 0)',
  },
  corporate: {
    pass:        'oklch(62% 0.194 149.214)',
    warning:     'oklch(85% 0.199 91.936)',
    fail:        'oklch(70% 0.191 22.216)',
    error:       'oklch(50% 0 0)',
    invalidated: 'oklch(65% 0 0)',
  },
}

// Used for ECharts tooltip bg, border, axis labels, grid lines
export const CHART_THEME: Record<Theme, ChartTheme> = {
  current:   { bg: '#1a2030',                        border: '#374151',                           axisLabel: '#6b7280',                  grid: '#1a2030' },
  forest:    { bg: 'oklch(16.203% 0.007 17.911)',    border: 'oklch(30% 0.039 171.364 / 60%)',   axisLabel: 'oklch(55% 0.001 17.911)',  grid: 'oklch(18% 0.007 171.364)' },
  corporate: { bg: 'oklch(93% 0 0)',                 border: 'oklch(80% 0 0)',                    axisLabel: 'oklch(50% 0 0)',           grid: 'oklch(88% 0 0)' },
}
```

Note the corrected alpha syntax: `oklch(L C H / alpha%)` with spaces around the slash.

### How components access themed colours

Components call `useTheme()` to get the active `theme`, then index into `RESULT_COLOUR[theme]` and `CHART_THEME[theme]`.

`buildHeatmapData()` in `EvaluationHeatmap.tsx` is a pure function that currently reads the flat `RESULT_COLOUR` directly. After the change it receives `colours: ResultColours` as a parameter:

```ts
function buildHeatmapData(
  evals: EvaluationSummary[],
  selectedDate: string | null,
  colours: ResultColours,   // ← new parameter
) { ... }
```

The caller (`useMemo` inside `EvaluationHeatmap`) passes `RESULT_COLOUR[theme]`. The `theme` variable comes from `useTheme()` called at the top of the component.

### Font Size Control

- `ThemeContext` tracks `fontSize: number` (default 14, range 12–18)
- On change: `document.documentElement.style.fontSize = fontSize + 'px'`
- All Tailwind `text-*` utilities use `rem` and scale automatically
- ECharts label sizes are hardcoded integers (`fontSize: 9`, `10`, `11`, `12`) — these are multiplied by `fontSize / 14` to keep proportional scaling. The factor is computed once and passed into the chart `option` object where font sizes appear.

### Navbar controls

`App.tsx` navbar gains two controls at the trailing edge, extracted into a `<NavControls />` inline component:

```
[ − 14px + ]   [ 🌙 Dark  |  ☀️ Light ]
```

- **Font control:** `−` / `+` buttons; current size displayed between them; clamped to 12–18
- **Theme toggle:** two-segment pill. Dark = forest; Light = corporate (no-op until corporate is activated)
- `App.tsx` root `<div>` changes from `bg-gray-950 text-gray-100` to `bg-background text-foreground`
- TROPEK logo changes from `text-green-400` to `text-primary`

---

## Files Changed

### Group 1 — Theme infrastructure (always required)

| File | Type | Change |
|---|---|---|
| `src/index.css` | Modify | Update `@custom-variant dark`; replace `.dark {}` with `[data-theme="current"]`, `[data-theme="forest"]`, `[data-theme="corporate"]` blocks including `--accent`/`--accent-foreground` |
| `src/lib/theme-context.tsx` | **New** | `ThemeProvider` + `useTheme()` + font-size management + localStorage |
| `src/lib/theme.ts` | Modify | Replace flat `RESULT_COLOUR` with `Record<Theme, ResultColours>`; add `CHART_THEME`; export `Theme`, `ResultColours`, `ChartTheme` types |
| `src/App.tsx` | Modify | Wrap in `ThemeProvider`; fix hardcoded root colours; add `<NavControls />` |

### Group 2 — Status colour callsites (use `RESULT_COLOUR[theme]`)

These files call `RESULT_COLOUR[result]` today. After `RESULT_COLOUR` becomes theme-keyed, they break unless updated to `RESULT_COLOUR[theme][result]`. All call `useTheme()` to get `theme`.

| File | Change |
|---|---|
| `src/features/evaluations/components/EvaluationHeatmap.tsx` | `useTheme()`, pass `RESULT_COLOUR[theme]` + `CHART_THEME[theme]` into chart; add `colours` param to `buildHeatmapData` |
| `src/features/evaluations/components/MetricTrendBlock.tsx` | `useTheme()`, use `RESULT_COLOUR[theme]` for dots/thresholds/STATUS_TEXT; use `CHART_THEME[theme]` for chart chrome; scale ECharts font sizes |
| `src/features/evaluations/components/EvaluationTable.tsx` | `useTheme()`, change `RESULT_COLOUR[ev.result]` → `RESULT_COLOUR[theme][ev.result]` |
| `src/pages/EvaluationDetailPage.tsx` | `useTheme()`, change `RESULT_COLOUR[ev.result]` → `RESULT_COLOUR[theme][ev.result]` |

### Group 3 — Hardcoded hex in status-display components

These files have hardcoded `#7dc540` / `#e6be00` / `#dc172a` in Tailwind arbitrary-value classes (e.g., `text-[#7dc540]`) for status display. They are updated to use `RESULT_COLOUR[theme].pass` etc. via inline `style` or a helper that maps to CSS-variable-friendly strings.

| File | Change |
|---|---|
| `src/features/evaluations/components/ResultBadge.tsx` | Replace `BADGE_CLS` hex values with `RESULT_COLOUR[theme]` lookups via `useTheme()` |
| `src/features/evaluations/components/SLIBreakdownTable.tsx` | Replace `STATUS_TEXT` hex values with `RESULT_COLOUR[theme]` lookups |
| `src/features/evaluations/components/EvaluationTabs.tsx` | Replace hardcoded `#7dc540` with `RESULT_COLOUR[theme].pass` |
| `src/pages/SloRegistryPage.tsx` | Replace `#7dc540` "active" badge with CSS variable equivalent (`text-primary bg-primary/20 border-primary/30`) |
| `src/features/slos/components/SloHistoryPanel.tsx` | Same as SloRegistryPage — "active" badge |

### Group 4 — Deferred (SLO form accent colours)

These files use `#7dc540` as an accent/brand colour for SLI names and criteria display (not a pass/fail status indicator). They work fine in both dark themes because `--primary` maps to green in forest. They are **not** changed in this implementation — the hardcoded hex produces the same visual as `text-primary` in forest theme.

| File | Why deferred |
|---|---|
| `src/features/slos/components/SloCreateForm.tsx` | Accent only — SLI name input text |
| `src/features/slos/components/SloObjectiveEditor.tsx` | Accent only — metric name buttons |
| `src/features/slos/components/SloObjectiveTable.tsx` | Mixed — SLI names (accent) + pass/warn threshold display. Threshold column colours deferred. |
| `src/features/slos/components/SloYamlUpload.tsx` | Mixed — pass/warn criteria columns. Deferred. |

---

## Behaviour

| Action | Result |
|---|---|
| Click 🌙 Dark | Sets `data-theme="forest"` on `<html>`, saves to localStorage |
| Click ☀️ Light | No-op (shows no visual change until corporate is implemented) |
| Click `+` font | Increases `font-size` on `<html>` by 1px (max 18px), saves to localStorage |
| Click `−` font | Decreases by 1px (min 12px), saves to localStorage |
| Page reload | Restores last theme + font size from localStorage; defaults: `forest` / `14px` |
| Dev comparison | Set `data-theme="current"` via DevTools attribute editor to switch to shadcn neutral dark |

---

## Future: Adding Light Theme

1. Complete `[data-theme="corporate"]` token block in `index.css` with all remaining tokens
2. Make ☀️ Light button call `setTheme('corporate')` instead of no-op
3. No other changes needed — `ThemeProvider`, `RESULT_COLOUR`, `CHART_THEME` are already typed for it

---

## Open Questions

None — all decisions made during brainstorming session 2026-03-15.
