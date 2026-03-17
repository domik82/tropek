# UI Architecture

React 19 SPA built with Vite 8, TypeScript 5.9, Tailwind CSS 4, and shadcn/ui.

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Framework | React 19 |
| Language | TypeScript 5.9 (strict) |
| Build | Vite 8 |
| Styling | Tailwind CSS 4 + shadcn/ui (Base Nova) |
| Charts | Apache ECharts 6 (via echarts-for-react) |
| Data fetching | TanStack React Query 5 |
| Routing | React Router 7 |
| Forms | React Hook Form + Zod validation |
| Icons | Lucide React |
| API mocking | MSW 2 (Mock Service Worker) |
| Testing | Vitest |
| Font | Geist Variable |

## Directory Structure

```
src/
  App.tsx                   -- Router, providers, navigation
  main.tsx                  -- Entry point, MSW initialization
  features/                 -- Domain modules (self-contained)
    evaluations/            -- Evaluation list, detail, annotations, trend
    assets/                 -- Asset inventory, groups, filtering
    navigator/              -- Drill-down navigation (tree -> group -> asset)
    slos/                   -- SLO registry, group management, SLO links
    slis/                   -- SLI definition management
  pages/                    -- Route-level page components
  components/
    ui/                     -- shadcn/ui primitives (button, dialog, tabs, etc.)
    charts/                 -- ECharts wrappers (heatmap, multi-series, view toggle)
    GroupTreeRenderer.tsx   -- Recursive asset group tree
  lib/                      -- Shared utilities
    theme-context.tsx       -- Dark/light theme provider (React Context)
    theme.ts                -- Color palettes per theme
    queryKeys.ts            -- React Query key factory
    format.ts               -- Number/date formatters
    utils.ts                -- cn() helper (clsx + tailwind-merge)
  mocks/                    -- MSW handlers + deterministic data generator
  utils/                    -- Pure helper functions (metrics calculations)
```

## Feature Module Pattern

Every feature follows a consistent structure:

```
features/{domain}/
  api.ts          -- Pure async fetch functions (no React/cache awareness)
  hooks.ts        -- React Query wrappers (useQuery/useMutation)
  types.ts        -- TypeScript interfaces
  components/     -- Feature-specific React components
  utils.ts        -- Pure helper functions (optional)
  constants.ts    -- Magic numbers, column definitions (optional)
```

### Data Flow

```
Components
    |
Custom Hooks (useQuery / useMutation)
    |
Pure fetch functions (features/*/api.ts)
    |
MSW Handlers (dev) / Real API (prod)
```

- **api.ts** functions are pure -- no state, no React Query knowledge
- **hooks.ts** wraps fetch with React Query (caching, stale time, invalidation)
- Mutations invalidate relevant query keys on success

## Routing

Defined in `App.tsx`:

| Route | Page | Purpose |
|-------|------|---------|
| `/` | redirect | -> `/navigator` |
| `/navigator` | `AssetNavigatorPage` | Drill-down: tree panel + group/asset detail |
| `/evaluations/:id` | `EvaluationDetailPage` | Single evaluation with SLI breakdown + trend |
| `/slos` | `SloRegistryPage` | SLO CRUD + group management sidebar |
| `/assets` | `AssetsPage` | Asset inventory with filtering |
| `/explorer` | `MetricExplorerPage` | Metric analysis dashboard |

URL state via `useSearchParams()`:
- Navigator: `?group=`, `?asset=`, `?eval=`
- SLO Registry: `?group=`

## State Management

| Mechanism | Purpose |
|-----------|---------|
| React Query | Server state (evaluations, assets, SLOs, SLIs, groups) |
| React Context | Theme + font size (persisted to localStorage) |
| URL params | Navigation state (group/asset/eval selection) |

No Redux, Zustand, or Jotai. React Query + Context is sufficient for the current scope.

## Query Key Factory

Structured keys prevent cache collisions:

```typescript
evaluationKeys.all            // ['evaluations']
evaluationKeys.list(filters)  // ['evaluations', {...filters}]
evaluationKeys.detail(id)     // ['evaluations', id]
evaluationKeys.trend(id, m)   // ['evaluations', id, metric]
```

## Theming

Three themes using OKLch color space with CSS custom properties:

| Theme | Style | Primary |
|-------|-------|---------|
| `forest` | Dark (default) | Teal/green |
| `current` | Dark | Neutral green |
| `corporate` | Light | Blue-green |

Status colors are theme-aware:
- Pass: green, Warning: amber, Fail: red, Error: gray, Invalidated: light gray

Theme and font size persist to `localStorage` (`tropek-theme`, `tropek-font-size`).

## API Integration

All fetch calls use the `/api` prefix. In development, Vite proxies to `:8080`.

Environment variables:
- `VITE_USE_MOCKS` -- Enable MSW (default: true in dev)
- `VITE_API_BASE` -- Backend URL override

Default `staleTime: 30_000` (30 seconds), overridable per hook.
