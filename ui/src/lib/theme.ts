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

// ECharts chrome colours per theme — tooltip bg/border, axis label, grid line.
export const CHART_THEME: Record<Theme, ChartTheme> = {
  current:   {
    bg:        '#1a2030',
    border:    '#374151',
    axisLabel: '#6b7280',
    grid:      '#1a2030',
  },
  forest:    {
    bg:        'oklch(16.203% 0.007 17.911)',
    border:    'oklch(30% 0.039 171.364 / 60%)',
    axisLabel: 'oklch(55% 0.001 17.911)',
    grid:      'oklch(18% 0.007 171.364)',
  },
  corporate: {
    bg:        'oklch(93% 0 0)',
    border:    'oklch(80% 0 0)',
    axisLabel: 'oklch(50% 0 0)',
    grid:      'oklch(88% 0 0)',
  },
}

// Default OS → colour mapping for the asset registry colour legend.
export const DEFAULT_OS_COLOUR_MAP: Record<string, string> = {
  linux:   '#7dc540',
  windows: '#6495ed',
  macos:   '#e6be00',
  unknown: '#888888',
}
