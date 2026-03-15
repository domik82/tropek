// src/lib/theme.ts
// Single source of truth for theme types, status colours, and ECharts chrome colours.

export type Theme = 'current' | 'forest' | 'corporate'

export interface ResultColours {
  pass:        string
  warning:     string
  fail:        string
  error:       string
  invalidated: string
}

export interface ChartTheme {
  bg:        string
  border:    string
  axisLabel: string
  grid:      string
}

// Status colours per theme — used in ECharts chart options (JS strings, not Tailwind).
// For Tailwind-class components, use CSS utilities text-pass / bg-pass / etc. instead.
export const RESULT_COLOUR: Record<Theme, ResultColours> = {
  current: {
    pass:        '#7dc540',
    warning:     '#e6be00',
    fail:        '#dc172a',
    error:       '#888888',
    invalidated: '#b0b0b0',
  },
  forest: {
    pass:        '#0a9f66',  // oklch(64.8% 0.15 160)
    warning:     '#ffb800',  // oklch(84.71% 0.199 83.87)
    fail:        '#ff4e57',  // oklch(71.76% 0.221 22.18)
    error:       '#595959',  // oklch(50% 0 0)
    invalidated: '#878787',  // oklch(65% 0 0)
  },
  corporate: {
    pass:        '#37a266',  // oklch(62% 0.194 149.214)
    warning:     '#d4b030',  // oklch(85% 0.199 91.936)
    fail:        '#e05050',  // oklch(70% 0.191 22.216)
    error:       '#595959',  // oklch(50% 0 0)
    invalidated: '#878787',  // oklch(65% 0 0)
  },
}

// ECharts chrome colours per theme — tooltip bg/border, axis label, grid line.
export const CHART_THEME: Record<Theme, ChartTheme> = {
  current:   {
    bg:        '#1a2030',
    border:    '#374151',
    axisLabel: '#c0c8d0',
    grid:      '#1a2030',
  },
  forest:    {
    bg:        '#1a1714',              // oklch(16.203% 0.007 17.911)
    border:    'rgba(28, 44, 36, 0.6)', // oklch(30% 0.039 171.364 / 60%)
    axisLabel: '#c0c0c0',
    grid:      '#14201a',              // oklch(18% 0.007 171.364)
  },
  corporate: {
    bg:        '#ededed',              // oklch(93% 0 0)
    border:    '#cccccc',              // oklch(80% 0 0)
    axisLabel: '#595959',              // oklch(50% 0 0)
    grid:      '#e0e0e0',              // oklch(88% 0 0)
  },
}

// Default OS → colour mapping for the asset registry colour legend.
export const DEFAULT_OS_COLOUR_MAP: Record<string, string> = {
  linux:   '#7dc540',
  windows: '#6495ed',
  macos:   '#e6be00',
  unknown: '#888888',
}
