# Theme System Design

**Date:** 2026-03-15
**Status:** Draft

## Overview

Implement a live, switchable theme system for the TROPEK UI with two dark themes available immediately (for comparison/development) and the architecture ready to add a corporate light theme later. A `🌙 Dark / ☀️ Light` toggle lives in the navbar; a font-size `−/+` control sits alongside it.

## Goals

- Switch between Forest dark and Current (shadcn/ui neutral) dark themes instantly in the running app
- Persist the chosen theme and font size to `localStorage`
- Replace all hardcoded colour values in the UI chrome with CSS-variable-driven tokens
- Keep status colours (pass/warning/fail) as a theme-aware object so they complement each theme
- Lay the groundwork for a Corporate light theme (tokens defined, `ThemeProvider` already typed for it)
- Font size adjustable via `−/+` control, range 12–18px, scales all `rem`-based Tailwind utilities

## Non-Goals

- Implementing the Corporate light theme UI (deferred — tokens are defined but not activated)
- Changing the ECharts chart type or layout
- Modifying any existing component logic outside the five files listed below

---

## Architecture

### Token Strategy — `data-theme` attribute

Theme is controlled by a `data-theme` attribute on `<html>`. Two CSS blocks in `index.css` map each theme's values to the existing shadcn/ui variable names. All components continue using `bg-primary`, `text-foreground`, `border-border`, etc. — no component changes needed.

```
[data-theme="current"] { --background: ...; --primary: ...; ... }
[data-theme="forest"]  { --background: ...; --primary: ...; ... }
[data-theme="corporate"] { ... }   /* stub only — not yet activated */
```

The `@theme inline` block in `index.css` that maps CSS vars to Tailwind utility classes is unchanged.

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
| `--border`, `--input` | `oklch(30.698% 0.039 171.364 / 40%)` |
| `--ring` | `oklch(68.628% 0.185 148.958 / 50%)` |
| `--destructive` | `oklch(71.76% 0.221 22.18)` |
| `--destructive-foreground` | `oklch(0% 0 0)` |
| `--radius` | `0.5rem` (unchanged) |

Status chart colours remain as theme-specific values (see `CHART_THEME` and `RESULT_COLOUR` below).

### Token Mapping — Corporate Light → shadcn/ui names (stub)

| shadcn/ui variable | Corporate value |
|---|---|
| `--background` | `oklch(100% 0 0)` |
| `--foreground` | `oklch(22.389% 0.031 278.072)` |
| `--card`, `--popover` | `oklch(93% 0 0)` |
| `--primary` | `oklch(58% 0.158 241.966)` — blue |
| `--primary-foreground` | `oklch(100% 0 0)` |
| `--secondary`, `--muted` | `oklch(86% 0 0)` |
| `--border`, `--input` | `oklch(86% 0 0)` |
| `--destructive` | `oklch(70% 0.191 22.216)` |

### ThemeContext

New file `src/lib/theme-context.tsx` (~25 lines):

```ts
type Theme = 'current' | 'forest' | 'corporate'

// ThemeProvider:
//   - reads localStorage('tropek-theme') on mount, defaults to 'forest'
//   - sets document.documentElement.setAttribute('data-theme', theme)
//   - exports: ThemeProvider, useTheme()

// useTheme() returns:
//   theme: Theme
//   setTheme: (t: Theme) => void
//   isDark: boolean   // theme !== 'corporate'
```

`ThemeProvider` wraps the root `App` component. `useTheme()` is available anywhere in the tree.

### Status Colours — theme-aware

`lib/theme.ts` gains a `RESULT_COLOUR` object keyed by theme, and a `CHART_THEME` object for ECharts chrome colours. Both are indexed by `Theme`.

```ts
// RESULT_COLOUR[theme] — used in heatmap cells, trend dots, ResultBadge, threshold lines
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

// CHART_THEME[theme] — used for ECharts tooltip bg, border, axis labels, grid lines
export const CHART_THEME: Record<Theme, ChartTheme> = {
  current:   { bg: '#1a2030', border: '#374151', axisLabel: '#6b7280', grid: '#1a2030' },
  forest:    { bg: 'oklch(16.203% 0.007 17.911)', border: 'oklch(30% 0.039 171/60%)', axisLabel: 'oklch(55% 0.001 17.911)', grid: 'oklch(18% 0.007 171)' },
  corporate: { bg: 'oklch(93% 0 0)', border: 'oklch(80% 0 0)', axisLabel: 'oklch(50% 0 0)', grid: 'oklch(88% 0 0)' },
}
```

Existing `RESULT_COLOUR` flat object in `constants.ts` (used by both chart files today) is replaced by `RESULT_COLOUR[theme]` calls. Components that use status colours receive `theme` via `useTheme()`.

### Font Size Control

- `ThemeContext` also tracks `fontSize: number` (default 14, range 12–18)
- On change: `document.documentElement.style.fontSize = fontSize + 'px'`
- Persisted to `localStorage('tropek-font-size')`
- `CHART_THEME` entries gain an optional `axisFontScale` multiplier: `axisFontSize = baseFontSize * scale` passed to ECharts options so chart labels scale proportionally
- `EvaluationHeatmap` and `MetricTrendBlock` both accept no extra props — they call `useTheme()` internally

### Navbar toggle

`App.tsx` navbar gains two controls at the trailing edge:

```
[ − 14px + ]   [ 🌙 Dark  |  ☀️ Light ]
```

- **Font control:** `−` / `+` buttons, current size displayed between them
- **Theme toggle:** two-segment pill. Currently: Dark = forest, Light = corporate (stub — clicking Light is a no-op until corporate theme is implemented, or shows a toast "coming soon")
- Both controls are extracted into a `<NavControls />` component inside `App.tsx` (not a separate file — too small)

### Hardcoded colour cleanup in App.tsx

`App.tsx` currently has `bg-gray-950` on the root `<div>` and `text-green-400` on the TROPEK logo. These are replaced with `bg-background` and `text-primary` respectively.

---

## Files Changed

| File | Type | Change |
|---|---|---|
| `src/index.css` | Modify | Replace `.dark {}` with `[data-theme="current"] {}`, `[data-theme="forest"] {}`, `[data-theme="corporate"] {}` blocks |
| `src/lib/theme-context.tsx` | New | `ThemeProvider` + `useTheme()` hook, localStorage persistence, font-size management |
| `src/lib/theme.ts` | Modify | Replace flat `RESULT_COLOUR` with theme-keyed object; add `CHART_THEME`; add `ChartTheme` type |
| `src/App.tsx` | Modify | Wrap in `ThemeProvider`; fix `bg-gray-950`/`text-green-400`; add `<NavControls />` with toggle + font size |
| `src/features/evaluations/components/EvaluationHeatmap.tsx` | Modify | Call `useTheme()`, use `CHART_THEME[theme]` for chrome, `RESULT_COLOUR[theme]` for cell colours |
| `src/features/evaluations/components/MetricTrendBlock.tsx` | Modify | Call `useTheme()`, use `CHART_THEME[theme]` for chart chrome, `RESULT_COLOUR[theme]` for dots/thresholds |

No other files change. All shadcn/ui primitives (`button.tsx`, `badge.tsx`, `input.tsx`, etc.) work as-is.

---

## Behaviour

| Action | Result |
|---|---|
| Click 🌙 Dark | Sets `data-theme="forest"` on `<html>`, saves to localStorage |
| Click ☀️ Light | No-op for now (corporate theme stub not yet activated) |
| Click `+` font | Increases `font-size` on `<html>` by 1px (max 18px), saves |
| Click `−` font | Decreases by 1px (min 12px), saves |
| Page reload | Restores last theme + font size from localStorage; defaults: forest / 14px |
| Dev comparison | To temporarily compare both dark themes, developer sets `data-theme="current"` in DevTools |

## Future: Adding Light Theme

1. Uncomment / complete `[data-theme="corporate"]` token block in `index.css`
2. Make ☀️ Light button call `setTheme('corporate')` instead of no-op
3. No other changes needed — `ThemeProvider`, `RESULT_COLOUR`, `CHART_THEME` are already typed for it

---

## Open Questions

None — all decisions made during brainstorming session 2026-03-15.
