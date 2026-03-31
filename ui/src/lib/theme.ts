// src/lib/theme.ts
// Single source of truth for theme types and ECharts-specific colour lookups.
// ECharts needs JS hex strings — it can't resolve CSS vars. Everything else
// should use the functional CSS aliases from index.css directly.

export type Theme = 'current' | 'dark' | 'light'

export interface ResultColours {
  pass:        string
  warning:     string
  fail:        string
  error:       string
  invalidated: string
}

export interface ChartTheme {
  bg:           string
  border:       string
  line:         string
  axisLabel:    string
  grid:         string
  selectionRing: string
}

// Status colours per theme — ONLY for ECharts (JS hex strings).
// For CSS/Tailwind components, use text-pass / bg-pass / etc. instead.
export const RESULT_COLOUR: Record<Theme, ResultColours> = {
  current: {
    pass:        '#7dc540',
    warning:     '#e6be00',
    fail:        '#dc172a',
    error:       '#888888',
    invalidated: '#b0b0b0',
  },
  dark: {
    pass:        '#46a758',  // Radix grass-9
    warning:     '#ffe629',  // Radix yellow-9
    fail:        '#e5484d',  // Radix red-9
    error:       '#696e77',  // Radix slate-9
    invalidated: '#777b84',  // Radix slate-10
  },
  light: {
    pass:        '#46a758',  // TODO: Radix grass-9 light
    warning:     '#ffe629',
    fail:        '#e5484d',
    error:       '#696e77',
    invalidated: '#777b84',
  },
}

// ECharts chrome colours per theme — tooltip bg/border, axis label, grid line.
// ONLY for ECharts JS context. For CSS, use chart-bg / chart-border / etc.
export const CHART_THEME: Record<Theme, ChartTheme> = {
  current: {
    bg:           '#1a2030',
    border:       '#374151',
    line:         '#374151',
    axisLabel:    '#c0c8d0',
    grid:         '#2a3040',
    selectionRing: '#ffffff',
  },
  dark: {
    bg:           '#18191b',   // Radix slate-2
    border:       '#363a3f',   // Radix slate-6
    line:         '#363a3f',   // Radix slate-6
    axisLabel:    '#b0b4ba',   // Radix slate-11
    grid:         '#212225',   // Radix slate-3
    selectionRing: '#ffffff',
  },
  light: {
    bg:           '#ffffff',   // TODO: Radix light scales
    border:       '#e0e0e0',
    line:         '#e0e0e0',
    axisLabel:    '#595959',
    grid:         '#f5f5f5',
    selectionRing: '#ffffff',
  },
}

// Default OS -> colour mapping for the asset registry colour legend.
export const DEFAULT_OS_COLOUR_MAP: Record<string, string> = {
  linux:   '#7dc540',
  windows: '#6495ed',
  macos:   '#e6be00',
  unknown: '#888888',
}
