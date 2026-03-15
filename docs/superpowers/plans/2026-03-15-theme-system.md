# Theme System Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live `🌙 Dark / ☀️ Light` theme toggle and `−/+` font-size control to the TROPEK navbar, switching between a Forest dark theme and the current shadcn/ui neutral dark, with all status colours (pass/warning/fail) adapting per theme.

**Architecture:** A `data-theme` attribute on `<html>` selects between `[data-theme="current"]` and `[data-theme="forest"]` CSS blocks in `index.css`. A React `ThemeContext` manages the value and persists it to `localStorage`. Status colours are exposed two ways: as CSS custom properties (`--status-pass` etc.) for Tailwind-class-based components, and as a `RESULT_COLOUR[theme]` JS object for ECharts chart options.

**Tech Stack:** React 19, TypeScript, Tailwind CSS v4, Vite, ECharts 6, shadcn/ui (base-nova), vitest

**Spec:** `docs/superpowers/specs/2026-03-15-theme-system-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/lib/theme.ts` | Modify | `Theme` type, `RESULT_COLOUR[theme]`, `CHART_THEME[theme]`, exported types |
| `src/lib/theme-context.tsx` | **Create** | `ThemeProvider`, `useTheme()`, localStorage, font-size management |
| `src/index.css` | Modify | `@custom-variant dark`, `[data-theme]` blocks, `--status-*` CSS vars |
| `src/App.tsx` | Modify | Wrap in `ThemeProvider`, fix hardcoded colours, add `NavControls` |
| `src/features/evaluations/components/EvaluationHeatmap.tsx` | Modify | `useTheme()`, `CHART_THEME[theme]`, `RESULT_COLOUR[theme]` to `buildHeatmapData` |
| `src/features/evaluations/components/MetricTrendBlock.tsx` | Modify | `useTheme()`, `CHART_THEME[theme]`, `RESULT_COLOUR[theme]`, font scaling |
| `src/features/evaluations/components/EvaluationTable.tsx` | Modify | `RESULT_COLOUR[theme][ev.result]` |
| `src/pages/EvaluationDetailPage.tsx` | Modify | `RESULT_COLOUR[theme][ev.result]` |
| `src/features/evaluations/components/ResultBadge.tsx` | Modify | Replace hardcoded hex with `text-pass`, `bg-pass/20` Tailwind utilities |
| `src/features/evaluations/components/SLIBreakdownTable.tsx` | Modify | `STATUS_TEXT`: replace hex with `text-pass`, `text-warning`, `text-fail` |
| `src/features/evaluations/components/MetricTrendBlock.tsx` | Modify | `STATUS_TEXT`: same as above (same file as ECharts change above) |
| `src/features/evaluations/components/EvaluationTabs.tsx` | Modify | Replace `border-[#7dc540] text-[#7dc540]` with `border-pass text-pass` |
| `src/pages/SloRegistryPage.tsx` | Modify | Replace "active" hardcoded badge hex with `bg-pass/20 text-pass border-pass/30` |
| `src/features/slos/components/SloHistoryPanel.tsx` | Modify | Same as SloRegistryPage |

---

## Chunk 1: Foundation — theme types, context, CSS tokens

### Task 1: Update `src/lib/theme.ts`

**Files:**
- Modify: `src/lib/theme.ts`

- [ ] **Step 1: Replace file content**

```typescript
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
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /mnt/d/DEV/keptn_rewrite/tropek/ui && npx tsc --noEmit 2>&1 | head -30
```

Expected: errors only in files that import `RESULT_COLOUR` and still use the old flat indexing `RESULT_COLOUR[result]` — those are fixed in later tasks. Zero errors from `theme.ts` itself.

---

### Task 2: Create `src/lib/theme-utils.ts` and `src/lib/theme-context.tsx`

`clampFontSize` is extracted to a separate pure-function file so it can be unit-tested without React or DOM imports. Vitest has no jsdom configured — importing React context in a test file would crash with `ReferenceError: document is not defined`.

**Files:**
- Create: `src/lib/theme-utils.ts`
- Create: `src/lib/theme-utils.test.ts`
- Create: `src/lib/theme-context.tsx`

- [ ] **Step 1: Write failing test for clampFontSize**

Create `src/lib/theme-utils.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { clampFontSize } from './theme-utils'

describe('clampFontSize', () => {
  it('clamps below minimum to 12', () => {
    expect(clampFontSize(10)).toBe(12)
    expect(clampFontSize(0)).toBe(12)
  })
  it('clamps above maximum to 18', () => {
    expect(clampFontSize(20)).toBe(18)
    expect(clampFontSize(100)).toBe(18)
  })
  it('passes through values in range', () => {
    expect(clampFontSize(12)).toBe(12)
    expect(clampFontSize(14)).toBe(14)
    expect(clampFontSize(18)).toBe(18)
  })
})
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd /mnt/d/DEV/keptn_rewrite/tropek/ui && npx vitest run src/lib/theme-utils.test.ts 2>&1
```

Expected: FAIL — `clampFontSize` not found.

- [ ] **Step 3: Create `src/lib/theme-utils.ts`**

```typescript
// src/lib/theme-utils.ts
// Pure utility functions for the theme system — no React or DOM imports.

export const FONT_MIN = 12
export const FONT_MAX = 18

export function clampFontSize(n: number): number {
  return Math.max(FONT_MIN, Math.min(FONT_MAX, n))
}
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
cd /mnt/d/DEV/keptn_rewrite/tropek/ui && npx vitest run src/lib/theme-utils.test.ts 2>&1
```

Expected: PASS — 3 tests passing.

- [ ] **Step 5: Create `src/lib/theme-context.tsx`**

```tsx
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import type { Theme } from './theme'
import { clampFontSize } from './theme-utils'

const FONT_DEFAULT = 14
const THEME_DEFAULT: Theme = 'forest'

interface ThemeCtx {
  theme:       Theme
  setTheme:    (t: Theme) => void
  isDark:      boolean
  fontSize:    number
  setFontSize: (n: number) => void
}

const Ctx = createContext<ThemeCtx | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, _setTheme] = useState<Theme>(() =>
    (localStorage.getItem('tropek-theme') as Theme | null) ?? THEME_DEFAULT
  )
  const [fontSize, _setFontSize] = useState<number>(() =>
    clampFontSize(Number(localStorage.getItem('tropek-font-size')) || FONT_DEFAULT)
  )

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('tropek-theme', theme)
  }, [theme])

  useEffect(() => {
    document.documentElement.style.fontSize = `${fontSize}px`
    localStorage.setItem('tropek-font-size', String(fontSize))
  }, [fontSize])

  function setTheme(t: Theme) { _setTheme(t) }
  function setFontSize(n: number) { _setFontSize(clampFontSize(n)) }

  return (
    <Ctx.Provider value={{ theme, setTheme, isDark: theme !== 'corporate', fontSize, setFontSize }}>
      {children}
    </Ctx.Provider>
  )
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useTheme must be used inside ThemeProvider')
  return ctx
}
```

- [ ] **Step 6: Verify TypeScript**

```bash
cd /mnt/d/DEV/keptn_rewrite/tropek/ui && npx tsc --noEmit 2>&1 | grep -E "theme-context|theme-utils"
```

Expected: no errors.

---

### Task 3: Update `src/index.css`

**Files:**
- Modify: `src/index.css`

- [ ] **Step 1: Replace file content with themed version**

```css
@import "tailwindcss";
@import "tw-animate-css";

/* dark: variant fires when [data-theme="forest"] or [data-theme="current"] ancestor present.
   Replace the original .dark class-based variant. */
@custom-variant dark (&:is([data-theme="forest"] *), &:is([data-theme="current"] *));

/* ── Base (light/fallback) defaults ──────────────────────────── */
:root {
  --background:          oklch(1 0 0);
  --foreground:          oklch(0.145 0 0);
  --card:                oklch(1 0 0);
  --card-foreground:     oklch(0.145 0 0);
  --popover:             oklch(1 0 0);
  --popover-foreground:  oklch(0.145 0 0);
  --primary:             oklch(0.205 0 0);
  --primary-foreground:  oklch(0.985 0 0);
  --secondary:           oklch(0.97 0 0);
  --secondary-foreground:oklch(0.205 0 0);
  --muted:               oklch(0.97 0 0);
  --muted-foreground:    oklch(0.556 0 0);
  --accent:              oklch(0.97 0 0);
  --accent-foreground:   oklch(0.205 0 0);
  --destructive:         oklch(0.577 0.245 27.325);
  --destructive-foreground: oklch(0.985 0 0);
  --border:              oklch(0.922 0 0);
  --input:               oklch(0.922 0 0);
  --ring:                oklch(0.708 0 0);
  --radius:              0.5rem;
  --chart-1:             oklch(0.646 0.222 41.116);
  --chart-2:             oklch(0.6 0.118 184.704);
  --chart-3:             oklch(0.398 0.07 227.392);
  --chart-4:             oklch(0.828 0.189 84.429);
  --chart-5:             oklch(0.769 0.188 70.08);
  /* Status colour defaults (corporate/light values) */
  --status-pass:         oklch(62% 0.194 149.214);
  --status-warning:      oklch(85% 0.199 91.936);
  --status-fail:         oklch(70% 0.191 22.216);
  --status-error:        oklch(50% 0 0);
  --status-invalidated:  oklch(65% 0 0);
}

/* ── Current dark theme (shadcn/ui neutral) ───────────────────── */
[data-theme="current"] {
  --background:          oklch(0.145 0 0);
  --foreground:          oklch(0.985 0 0);
  --card:                oklch(0.205 0 0);
  --card-foreground:     oklch(0.985 0 0);
  --popover:             oklch(0.205 0 0);
  --popover-foreground:  oklch(0.985 0 0);
  --primary:             oklch(0.985 0 0);
  --primary-foreground:  oklch(0.205 0 0);
  --secondary:           oklch(0.269 0 0);
  --secondary-foreground:oklch(0.985 0 0);
  --muted:               oklch(0.269 0 0);
  --muted-foreground:    oklch(0.708 0 0);
  --accent:              oklch(0.269 0 0);
  --accent-foreground:   oklch(0.985 0 0);
  --destructive:         oklch(0.396 0.141 25.723);
  --destructive-foreground: oklch(0.985 0 0);
  --border:              oklch(1 0 0 / 10%);
  --input:               oklch(1 0 0 / 15%);
  --ring:                oklch(0.556 0 0);
  --chart-1:             oklch(0.488 0.243 264.376);
  --chart-2:             oklch(0.696 0.17 162.48);
  --chart-3:             oklch(0.769 0.188 70.08);
  --chart-4:             oklch(0.627 0.265 303.9);
  --chart-5:             oklch(0.645 0.246 16.439);
  --status-pass:         #7dc540;
  --status-warning:      #e6be00;
  --status-fail:         #dc172a;
  --status-error:        #888888;
  --status-invalidated:  #b0b0b0;
}

/* ── Forest dark theme ────────────────────────────────────────── */
[data-theme="forest"] {
  --background:          oklch(20.84% 0.008 17.911);
  --foreground:          oklch(83.768% 0.001 17.911);
  --card:                oklch(18.522% 0.007 17.911);
  --card-foreground:     oklch(83.768% 0.001 17.911);
  --popover:             oklch(18.522% 0.007 17.911);
  --popover-foreground:  oklch(83.768% 0.001 17.911);
  --primary:             oklch(68.628% 0.185 148.958);
  --primary-foreground:  oklch(0% 0 0);
  --secondary:           oklch(30.698% 0.039 171.364);
  --secondary-foreground:oklch(86.139% 0.007 171.364);
  --muted:               oklch(30.698% 0.039 171.364);
  --muted-foreground:    oklch(86.139% 0.007 171.364);
  --accent:              oklch(30.698% 0.039 171.364);
  --accent-foreground:   oklch(86.139% 0.007 171.364);
  --destructive:         oklch(71.76% 0.221 22.18);
  --destructive-foreground: oklch(0% 0 0);
  --border:              oklch(30.698% 0.039 171.364 / 40%);
  --input:               oklch(30.698% 0.039 171.364 / 40%);
  --ring:                oklch(68.628% 0.185 148.958 / 50%);
  --chart-1:             oklch(68.628% 0.185 148.958);
  --chart-2:             oklch(69.776% 0.135 168.327);
  --chart-3:             oklch(70.628% 0.119 185.713);
  --chart-4:             oklch(84.71% 0.199 83.87);
  --chart-5:             oklch(72.06% 0.191 231.6);
  --status-pass:         oklch(64.8% 0.15 160);
  --status-warning:      oklch(84.71% 0.199 83.87);
  --status-fail:         oklch(71.76% 0.221 22.18);
  --status-error:        oklch(50% 0 0);
  --status-invalidated:  oklch(65% 0 0);
}

/* ── Corporate light theme (stub — not yet activated in navbar) ── */
[data-theme="corporate"] {
  --background:          oklch(100% 0 0);
  --foreground:          oklch(22.389% 0.031 278.072);
  --card:                oklch(93% 0 0);
  --card-foreground:     oklch(22.389% 0.031 278.072);
  --popover:             oklch(93% 0 0);
  --popover-foreground:  oklch(22.389% 0.031 278.072);
  --primary:             oklch(58% 0.158 241.966);
  --primary-foreground:  oklch(100% 0 0);
  --secondary:           oklch(86% 0 0);
  --secondary-foreground:oklch(22.389% 0.031 278.072);
  --muted:               oklch(86% 0 0);
  --muted-foreground:    oklch(22.389% 0.031 278.072);
  --accent:              oklch(86% 0 0);
  --accent-foreground:   oklch(22.389% 0.031 278.072);
  --destructive:         oklch(70% 0.191 22.216);
  --destructive-foreground: oklch(100% 0 0);
  --border:              oklch(86% 0 0);
  --input:               oklch(86% 0 0);
  --ring:                oklch(58% 0.158 241.966 / 50%);
  --status-pass:         oklch(62% 0.194 149.214);
  --status-warning:      oklch(85% 0.199 91.936);
  --status-fail:         oklch(70% 0.191 22.216);
  --status-error:        oklch(50% 0 0);
  --status-invalidated:  oklch(65% 0 0);
}

/* ── Tailwind token registration ─────────────────────────────── */
@theme inline {
  --color-background:          var(--background);
  --color-foreground:          var(--foreground);
  --color-card:                var(--card);
  --color-card-foreground:     var(--card-foreground);
  --color-popover:             var(--popover);
  --color-popover-foreground:  var(--popover-foreground);
  --color-primary:             var(--primary);
  --color-primary-foreground:  var(--primary-foreground);
  --color-secondary:           var(--secondary);
  --color-secondary-foreground:var(--secondary-foreground);
  --color-muted:               var(--muted);
  --color-muted-foreground:    var(--muted-foreground);
  --color-accent:              var(--accent);
  --color-accent-foreground:   var(--accent-foreground);
  --color-destructive:         var(--destructive);
  --color-destructive-foreground: var(--destructive-foreground);
  --color-border:              var(--border);
  --color-input:               var(--input);
  --color-ring:                var(--ring);
  --color-chart-1:             var(--chart-1);
  --color-chart-2:             var(--chart-2);
  --color-chart-3:             var(--chart-3);
  --color-chart-4:             var(--chart-4);
  --color-chart-5:             var(--chart-5);
  --radius-sm:                 calc(var(--radius) - 4px);
  --radius-md:                 calc(var(--radius) - 2px);
  --radius-lg:                 var(--radius);
  --radius-xl:                 calc(var(--radius) + 4px);
  /* Status colour utilities: text-pass, bg-pass, bg-pass/20, border-pass, etc.
     Values are CSS vars so they auto-update when data-theme changes. */
  --color-pass:                var(--status-pass);
  --color-warning:             var(--status-warning);
  --color-fail:                var(--status-fail);
  --color-status-error:        var(--status-error);
  --color-invalidated:         var(--status-invalidated);
  /* info colour — static, not status-specific */
  --color-info:                oklch(0.556 0 0);
}

body {
  background: var(--background);
  color: var(--foreground);
  font-family: system-ui, 'Segoe UI', sans-serif;
}
```

- [ ] **Step 2: Start dev server and verify visual baseline**

```bash
cd /mnt/d/DEV/keptn_rewrite/tropek/ui && npm run dev 2>&1 &
```

Open http://localhost:5173 (or whichever port Vite uses). The app should still render. Background will be the `:root` light colour because no `data-theme` is set on `<html>` yet — that's expected.

- [ ] **Step 3: Manual smoke-test: set data-theme in DevTools**

In browser DevTools console:
```js
document.documentElement.setAttribute('data-theme', 'forest')
```

Expected: background turns dark brown-black, primary buttons turn green.

```js
document.documentElement.setAttribute('data-theme', 'current')
```

Expected: the old shadcn neutral dark look.

- [ ] **Step 4: Commit Chunk 1**

```bash
cd /mnt/d/DEV/keptn_rewrite/tropek && git add ui/src/lib/theme.ts ui/src/lib/theme-utils.ts ui/src/lib/theme-utils.test.ts ui/src/lib/theme-context.tsx ui/src/index.css && git commit -m "feat(ui): add Theme type, RESULT_COLOUR/CHART_THEME per theme, ThemeContext, data-theme CSS blocks"
```

---

## Chunk 2: Wire up ThemeProvider and navbar controls

### Task 4: Update `src/App.tsx`

**Files:**
- Modify: `src/App.tsx`

- [ ] **Step 1: Replace App.tsx content**

```tsx
// src/App.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import { EvaluationsPage } from './pages/EvaluationsPage'
import { EvaluationDetailPage } from './pages/EvaluationDetailPage'
import { SloRegistryPage } from './pages/SloRegistryPage'
import { AssetsPage } from './pages/AssetsPage'
import { ThemeProvider, useTheme } from './lib/theme-context'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000 } },
})

const NAV_ITEMS = [
  { to: '/evaluations', label: 'Evaluations' },
  { to: '/slos', label: 'SLOs' },
  { to: '/assets', label: 'Assets' },
]

function NavControls() {
  const { theme, setTheme, fontSize, setFontSize } = useTheme()
  const isDark = theme !== 'corporate'

  return (
    <div className="flex items-center gap-2 ml-auto">
      {/* Font size control */}
      <div className="flex items-center border border-border rounded overflow-hidden text-xs">
        <button
          onClick={() => setFontSize(fontSize - 1)}
          className="px-2 py-1 hover:bg-muted transition-colors text-muted-foreground"
          aria-label="Decrease font size"
        >
          −
        </button>
        <span className="px-2 py-1 text-muted-foreground tabular-nums">{fontSize}px</span>
        <button
          onClick={() => setFontSize(fontSize + 1)}
          className="px-2 py-1 hover:bg-muted transition-colors text-muted-foreground"
          aria-label="Increase font size"
        >
          +
        </button>
      </div>

      {/* Theme toggle */}
      <div className="flex border border-border rounded overflow-hidden text-xs">
        <button
          onClick={() => setTheme('forest')}
          className={`px-3 py-1 transition-colors ${isDark ? 'bg-muted text-foreground font-semibold' : 'text-muted-foreground hover:bg-muted/50'}`}
        >
          🌙 Dark
        </button>
        <button
          onClick={() => setTheme('corporate')}
          className={`px-3 py-1 transition-colors ${!isDark ? 'bg-muted text-foreground font-semibold' : 'text-muted-foreground hover:bg-muted/50'}`}
          title="Light theme coming soon"
        >
          ☀️ Light
        </button>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <div className="min-h-screen bg-background text-foreground">
            <nav className="border-b border-border px-6 py-3 flex items-center gap-6">
              <span className="font-bold text-sm tracking-widest text-primary">TROPEK</span>
              {NAV_ITEMS.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `text-sm transition-colors ${isActive ? 'text-foreground' : 'text-muted-foreground hover:text-foreground'}`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
              <NavControls />
            </nav>
            <main>
              <Routes>
                <Route path="/" element={<Navigate to="/evaluations" replace />} />
                <Route path="/evaluations" element={<EvaluationsPage />} />
                <Route path="/evaluations/:id" element={<EvaluationDetailPage />} />
                <Route path="/slos" element={<SloRegistryPage />} />
                <Route path="/assets" element={<AssetsPage />} />
              </Routes>
            </main>
          </div>
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  )
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd /mnt/d/DEV/keptn_rewrite/tropek/ui && npx tsc --noEmit 2>&1 | grep "App.tsx"
```

Expected: no errors from App.tsx.

- [ ] **Step 3: Visual check in browser**

Open http://localhost:5173. The navbar should show `🌙 Dark` / `☀️ Light` toggle and `−/+` font size. Clicking `🌙 Dark` keeps forest theme (default), clicking `☀️ Light` switches to corporate (light background). Font `−/+` should resize all text.

- [ ] **Step 4: Verify dark: variants still work**

In browser, ensure the app is on Forest dark. Open DevTools → Elements, check that `<html>` has `data-theme="forest"`. Inspect a destructive button — it should have dark-mode styling applied (darker red background from `dark:bg-destructive/20`).

- [ ] **Step 5: Commit**

```bash
cd /mnt/d/DEV/keptn_rewrite/tropek && git add ui/src/App.tsx && git commit -m "feat(ui): wire ThemeProvider, replace hardcoded nav colours, add NavControls"
```

---

## Chunk 3: ECharts components

### Task 5: Update `EvaluationHeatmap.tsx`

**Files:**
- Modify: `src/features/evaluations/components/EvaluationHeatmap.tsx`

The heatmap has three colour concerns:
1. **Cell fill** — `RESULT_COLOUR[result]` for coloured cells, `EMPTY_COLOUR` for empty
2. **Tooltip chrome** — bg, border, text colour
3. **Axis chrome** — label colour, line/split-line colour

`buildHeatmapData` is a pure function. It currently reads `RESULT_COLOUR` at module scope. After this task it receives `colours: ResultColours` + `emptyColour: string` as parameters. The spec defines only `colours` as a new parameter, but adding `emptyColour` is an intentional improvement — it keeps the function fully pure without depending on `CHART_THEME` at call time, and makes it unit-testable in isolation.

- [ ] **Step 1: Update the file**

Apply the following changes to `EvaluationHeatmap.tsx`:

**a) Add imports at top:**
```tsx
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR, CHART_THEME } from '@/lib/theme'
import type { ResultColours } from '@/lib/theme'
```
Remove `import { RESULT_COLOUR } from '../constants'`

**b) Remove `EMPTY_COLOUR` module-level constant:**
```tsx
// DELETE this line only:
const EMPTY_COLOUR = '#1e2433'
// KEEP: const SELECTED_BORDER = '#ffffff' — still used for cell selection highlight
```

**c) Update `buildHeatmapData` signature** — add two parameters:
```tsx
function buildHeatmapData(
  evals: EvaluationSummary[],
  selectedDate: string | null,
  colours: ResultColours,
  emptyColour: string,
) {
```

**d) Inside `buildHeatmapData`, replace the result colour lookup expression and the standalone fallback.** There are 2 occurrences total:

- The whole expression `(RESULT_COLOUR as Record<string, string>)[cell.result] ?? EMPTY_COLOUR` → replace with:
  ```tsx
  colours[cell.result as keyof ResultColours] ?? emptyColour
  ```
- The standalone fallback `: EMPTY_COLOUR` (the ternary else branch) → replace with `: emptyColour`.

**e) Update `EvaluationHeatmap` component** — call `useTheme()` and pass values through:

```tsx
export function EvaluationHeatmap({ evaluations, selectedDate, onDateSelect }: Props) {
  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]
  const ct = CHART_THEME[theme]
  const emptyColour = ct.bg

  const { slots, rows, data, pad } = useMemo(
    () => buildHeatmapData(evaluations, selectedDate, colours, emptyColour),
    [evaluations, selectedDate, colours, emptyColour],
  )
```

**f) Update chart `option` object** — replace all hardcoded hex strings with `ct.*`:

```tsx
const option = {
  backgroundColor: 'transparent',
  tooltip: {
    trigger: 'item' as const,
    backgroundColor: ct.bg,
    borderColor: ct.border,
    textStyle: { color: ct.axisLabel },   // was '#e2e8f0'
    formatter: (p: { data: CellData }) => {
      const d = p.data
      if (d.result === 'none') return `${d.row}<br/>${fmtDateTime(d.slot)}<br/><em>no data</em>`
      const rc = colours[d.result as keyof ResultColours] ?? '#ccc'
      return [
        `<b>${d.row}</b>`,
        fmtDateTime(d.slot),
        `Score: <b style="color:${rc}">${d.score}%</b> · <b style="color:${rc}">${d.result.toUpperCase()}</b>`,
      ].join('<br/>')
    },
  },
  xAxis: {
    type: 'category' as const,
    data: slots.map(fmtSlot),
    axisLabel: { rotate: 45, fontSize: 11, color: ct.axisLabel },
    axisLine: { lineStyle: { color: ct.grid } },
    splitLine: { show: false },
  },
  yAxis: {
    type: 'category' as const,
    data: rows,
    axisLabel: { fontSize: 11, color: ct.axisLabel, width: 210, overflow: 'truncate' as const },
    axisLine: { lineStyle: { color: ct.grid } },
    splitLine: { lineStyle: { color: ct.bg } },
  },
  // ... rest of series unchanged ...
}
```

**g) Update the colour legend** at the bottom of the JSX — replace `RESULT_COLOUR[r]` with `colours[r]`:
```tsx
style={{ backgroundColor: colours[r] }}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd /mnt/d/DEV/keptn_rewrite/tropek/ui && npx tsc --noEmit 2>&1 | grep "EvaluationHeatmap"
```

Expected: no errors.

- [ ] **Step 3: Visual check — switch themes and verify heatmap**

Navigate to `/evaluations`. Toggle between Dark and Light. The heatmap cells, tooltip, and axis chrome should change. Pass cells should be lime green on `current` and muted forest green on `forest`.

---

### Task 6: Update `MetricTrendBlock.tsx`

**Files:**
- Modify: `src/features/evaluations/components/MetricTrendBlock.tsx`

This file has both `STATUS_TEXT` (Tailwind classes — migrated to `text-pass` etc.) and `RESULT_COLOUR` usage (ECharts — migrated to `RESULT_COLOUR[theme]`).

- [ ] **Step 1: Update the file**

**a) Add imports, remove old RESULT_COLOUR import:**
```tsx
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR, CHART_THEME } from '@/lib/theme'
// Remove: import { RESULT_COLOUR } from '../constants'
```

**b) Replace `STATUS_TEXT` constant** with CSS utility classes:
```tsx
// Before:
const STATUS_TEXT: Record<string, string> = {
  pass:    'text-[#7dc540]',
  warning: 'text-[#e6be00]',
  fail:    'text-[#dc172a]',
}

// After:
const STATUS_TEXT: Record<string, string> = {
  pass:    'text-pass',
  warning: 'text-warning',
  fail:    'text-fail',
}
```

**c) At the top of the `MetricTrendBlock` component function, add:**
```tsx
const { theme, fontSize } = useTheme()
const colours = RESULT_COLOUR[theme]
const ct = CHART_THEME[theme]
const fontScale = fontSize / 14   // scale ECharts labels with the global font size
```

**d) Replace all `RESULT_COLOUR` usages** in the function body with `colours` (7 occurrences total):
- Line 45: `RESULT_COLOUR[p.result]` → `colours[p.result as keyof typeof colours]`
- Line 62: `RESULT_COLOUR.pass` (markLine lineStyle) → `colours.pass`
- Line 63: `RESULT_COLOUR.pass` (markLine label color) → `colours.pass`
- Line 68: `RESULT_COLOUR.warning` (markLine lineStyle) → `colours.warning`
- Line 69: `RESULT_COLOUR.warning` (markLine label color) → `colours.warning`
- Line 117: `RESULT_COLOUR.pass` (passRel series lineStyle) → `colours.pass`
- Line 122: `RESULT_COLOUR.warning` (warnRel series lineStyle) → `colours.warning`

**e) Update `option` object** — replace hardcoded hex strings with `ct.*` and apply font scaling:
```tsx
tooltip: {
  trigger: 'axis',
  backgroundColor: ct.bg,
  borderColor: ct.border,
  textStyle: { color: ct.axisLabel, fontSize: Math.round(12 * fontScale) },
},
xAxis: {
  // ...
  axisLabel: { color: ct.axisLabel, fontSize: Math.round(9 * fontScale), rotate: 35 },
  axisLine: { lineStyle: { color: ct.grid } },
},
yAxis: {
  // ...
  axisLabel: { color: ct.axisLabel, fontSize: Math.round(10 * fontScale) },
  splitLine: { lineStyle: { color: ct.bg } },
},
series: [
  {
    // ...
    lineStyle: { color: ct.border, width: 1.5 },   // was '#374151' (= current theme border)
    // ...
  },
  // ...
]
```

Also update the `label` inside `markLines`:
```tsx
label: { formatter: `...`, color: colours.pass, fontSize: Math.round(10 * fontScale) },
```
and same for warning.

**f) Replace hardcoded hex in the threshold toggle buttons** (JSX lines ~158-178). The pass button:
```tsx
// Before:
? 'border-[#7dc540]/50 text-[#7dc540] bg-[#7dc540]/10'
// After:
? 'border-pass/50 text-pass bg-pass/10'
```
The warn button:
```tsx
// Before:
? 'border-[#e6be00]/50 text-[#e6be00] bg-[#e6be00]/10'
// After:
? 'border-warning/50 text-warning bg-warning/10'
```

**g) Add `theme` and `fontSize` to the `option` useMemo deps** if the option is wrapped in `useMemo` (it isn't currently — the option is computed inline, so no change needed).

- [ ] **Step 2: Verify TypeScript**

```bash
cd /mnt/d/DEV/keptn_rewrite/tropek/ui && npx tsc --noEmit 2>&1 | grep "MetricTrendBlock"
```

Expected: no errors.

- [ ] **Step 3: Visual check**

Navigate to an evaluation detail page with metric trends. Toggle theme — chart chrome (tooltip background, axis labels) should shift between blue-gray and warm teal. Adjust font size — chart axis labels should scale proportionally.

- [ ] **Step 4: Commit Chunk 3**

```bash
cd /mnt/d/DEV/keptn_rewrite/tropek && git add ui/src/features/evaluations/components/EvaluationHeatmap.tsx ui/src/features/evaluations/components/MetricTrendBlock.tsx && git commit -m "feat(ui): make ECharts chart chrome and status colours theme-aware"
```

---

## Chunk 4: Remaining colour callsites

### Task 7: `EvaluationTable.tsx` and `EvaluationDetailPage.tsx`

Both files import `RESULT_COLOUR` and index it with a result string. After Task 1, `RESULT_COLOUR` is `Record<Theme, ResultColours>` — both break unless updated.

**Files:**
- Modify: `src/features/evaluations/components/EvaluationTable.tsx`
- Modify: `src/pages/EvaluationDetailPage.tsx`

- [ ] **Step 1: Update `EvaluationTable.tsx`**

Add to imports:
```tsx
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR } from '@/lib/theme'
import type { ResultColours } from '@/lib/theme'
// Remove: import { RESULT_COLOUR } from '../constants'
```

**Important:** `cell()` is a module-level function (not a component), so it cannot call hooks. Instead, add `colours` as a third parameter to `cell()`:

```tsx
// Change signature (line 27):
function cell(ev: EvaluationSummary, key: string, colours: ResultColours) {
```

Change the Badge style inside `cell()` (case 'result', line ~56):
```tsx
// Before:
<Badge style={{ backgroundColor: RESULT_COLOUR[ev.result] ?? '#888', color: '#fff' }}>

// After:
<Badge style={{ backgroundColor: colours[ev.result as keyof ResultColours] ?? colours.error, color: '#fff' }}>
```

In the `EvaluationTable` component function, add at the top:
```tsx
const { theme } = useTheme()
const colours = RESULT_COLOUR[theme]
```

Update the `cell()` call site in the JSX (line ~121 — there is exactly one):
```tsx
// Before:
? cell(ev, col.key)
// After:
? cell(ev, col.key, colours)
```

- [ ] **Step 2: Update `EvaluationDetailPage.tsx`**

Add to imports:
```tsx
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR } from '@/lib/theme'
// Remove: import { RESULT_COLOUR } from '@/features/evaluations/constants'
```

In the component function, add near top (after `useState` calls):
```tsx
const { theme } = useTheme()
const colours = RESULT_COLOUR[theme]
```

Change score display (line ~100):
```tsx
// Before:
style={{ color: RESULT_COLOUR[ev.result] ?? '#ccc' }}

// After:
style={{ color: colours[ev.result as keyof typeof colours] ?? colours.error }}
```

- [ ] **Step 3: Verify TypeScript**

```bash
cd /mnt/d/DEV/keptn_rewrite/tropek/ui && npx tsc --noEmit 2>&1 | grep -E "EvaluationTable|EvaluationDetailPage"
```

Expected: no errors.

---

### Task 8: Tailwind-class status components

These files use hardcoded hex in Tailwind arbitrary values. The `--status-*` CSS vars registered via `@theme inline` in Task 3 mean `text-pass`, `bg-pass/20`, `border-pass/40` etc. are valid Tailwind utilities that respond to the active theme automatically. No `useTheme()` needed in these components — this is an intentional improvement over the spec's `RESULT_COLOUR[theme]` approach for components that only need CSS class styling (not JS colour strings). The CSS variable path is simpler and avoids React overhead.

**Files:**
- Modify: `src/features/evaluations/components/ResultBadge.tsx`
- Modify: `src/features/evaluations/components/SLIBreakdownTable.tsx`
- Modify: `src/features/evaluations/components/EvaluationTabs.tsx`
- Modify: `src/pages/SloRegistryPage.tsx`
- Modify: `src/features/slos/components/SloHistoryPanel.tsx`

- [ ] **Step 1: Update `ResultBadge.tsx`**

```tsx
const BADGE_CLS: Record<string, string> = {
  pass:        'bg-pass/20 text-pass border border-pass/40',
  warning:     'bg-warning/20 text-warning border border-warning/40',
  fail:        'bg-fail/20 text-fail border border-fail/40',
  invalidated: 'bg-slate-700/40 text-slate-400 border border-slate-600/40',
}
```

No other changes to this file.

- [ ] **Step 2: Update `SLIBreakdownTable.tsx`**

```tsx
const STATUS_TEXT: Record<string, string> = {
  pass:    'text-pass',
  warning: 'text-warning',
  fail:    'text-fail',
}
```

No other changes to this file.

- [ ] **Step 3: Update `EvaluationTabs.tsx`**

Find the line (line 26):
```tsx
? 'border-[#7dc540] text-[#7dc540]'
```
Replace with:
```tsx
? 'border-pass text-pass'
```

- [ ] **Step 4: Update `SloRegistryPage.tsx`**

Find the "active" badge span (line ~174):
```tsx
<span className="text-xs bg-[#7dc540]/20 text-[#7dc540] border border-[#7dc540]/30 px-1.5 py-0.5 rounded-full shrink-0">active</span>
```
Replace with:
```tsx
<span className="text-xs bg-pass/20 text-pass border border-pass/30 px-1.5 py-0.5 rounded-full shrink-0">active</span>
```

- [ ] **Step 5: Update `SloHistoryPanel.tsx`**

Find the "active" badge span (line ~24):
```tsx
<span className="text-xs bg-[#7dc540]/20 text-[#7dc540] border border-[#7dc540]/30 px-1.5 py-0.5 rounded-full">active</span>
```
Replace with:
```tsx
<span className="text-xs bg-pass/20 text-pass border border-pass/30 px-1.5 py-0.5 rounded-full">active</span>
```

- [ ] **Step 6: Verify TypeScript**

```bash
cd /mnt/d/DEV/keptn_rewrite/tropek/ui && npx tsc --noEmit 2>&1
```

Expected: zero errors.

- [ ] **Step 7: Visual check**

Toggle between Forest and Current themes. Verify:
- Pass/warning/fail badges in evaluations list change colour
- SLI breakdown table status text changes colour
- Active SLO badge changes colour
- Evaluation tabs active indicator changes colour

- [ ] **Step 8: Commit Chunk 4**

```bash
cd /mnt/d/DEV/keptn_rewrite/tropek && git add \
  ui/src/features/evaluations/components/EvaluationTable.tsx \
  ui/src/pages/EvaluationDetailPage.tsx \
  ui/src/features/evaluations/components/ResultBadge.tsx \
  ui/src/features/evaluations/components/SLIBreakdownTable.tsx \
  ui/src/features/evaluations/components/EvaluationTabs.tsx \
  ui/src/pages/SloRegistryPage.tsx \
  ui/src/features/slos/components/SloHistoryPanel.tsx \
  && git commit -m "feat(ui): migrate all status colour callsites to theme-aware tokens"
```

---

## Verification checklist (run after all chunks complete)

- [ ] `npx tsc --noEmit` — zero type errors across the entire `ui/src/` tree
- [ ] `npx vitest run` — all tests pass
- [ ] Dev server: toggle 🌙 Dark → entire app shifts from neutral dark to forest green-tinted dark
- [ ] Dev server: toggle ☀️ Light → app shifts to white/blue corporate palette
- [ ] Dev server: `−/+` buttons change font size and persist across page reload
- [ ] Dev server: theme choice persists across page reload (localStorage)
- [ ] Dev server: evaluate detail page — heatmap cells, trend chart dots all change colour with theme
- [ ] Dev server: `dark:` variants (destructive buttons, outline buttons) still display correctly on both dark themes
- [ ] DevTools: `<html data-theme="current">` switches to neutral dark correctly

---

## Notes for implementer

- **`constants.ts` re-export is unchanged** — it still re-exports `RESULT_COLOUR` from `lib/theme`. Files migrated in Tasks 5–7 should import directly from `@/lib/theme` instead of from `../constants`. The `constants.ts` re-export can stay as-is or be cleaned up as a follow-up.

- **Deferred files** — `SloCreateForm.tsx`, `SloObjectiveEditor.tsx`, `SloObjectiveTable.tsx`, `SloYamlUpload.tsx` use `#7dc540` as accent/brand colour only. In forest theme, `--primary` maps to the same hue, so these look correct without changes.

- **Corporate light activation** — when ready, update `NavControls` in `App.tsx`: change `setTheme('corporate')` (already wired) and optionally add a `dev-only` internal toggle to switch between the two dark themes via DevTools instead.
