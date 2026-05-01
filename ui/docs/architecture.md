# UI Architecture

React 19 SPA built with Vite 8, TypeScript 5.9, Tailwind CSS 4, and shadcn/ui.

## Technology Stack

| Layer | Technology |
|---|---|
| Framework | React 19 |
| Language | TypeScript 5.9 (strict) |
| Build | Vite 8 |
| Styling | Tailwind CSS 4 + shadcn/ui (Base Nova) |
| Charts | Apache ECharts 6 (via echarts-for-react) |
| Timeline | vis-timeline (Gantt-style, used by meta-timeline) |
| Data fetching | TanStack React Query 5 |
| Routing | React Router 7 |
| Forms | React Hook Form + Zod 4 validation |
| Icons | Lucide React |
| API mocking | MSW 2 (Mock Service Worker) |
| Testing | Vitest + React Testing Library + happy-dom |
| Font | Geist Variable (body: monospace, UI chrome: system sans-serif) |
| Package manager | pnpm |

## Directory Structure

```
src/
├── App.tsx                      # Router, providers, navbar, theme controls
├── main.tsx                     # Entry point, MSW + config initialization
├── index.css                    # Tailwind base, theme CSS variables (626 lines)
├── features/                    # Domain modules (self-contained)
│   ├── evaluations/             # Evaluation list, detail, SLI breakdown, actions, trend
│   ├── navigator/               # Asset tree → group → asset drill-down navigation
│   ├── assets/                  # Asset CRUD, groups, tree selector
│   ├── registry/                # 3-mode SLO/SLI/datasource registry (tree + detail + forms)
│   ├── slos/                    # SLO CRUD, versioning, objectives editor
│   ├── slis/                    # SLI definition management
│   ├── slo-groups/              # SLO group hierarchy
│   ├── datasources/             # Datasource registry
│   ├── meta_timeline/           # Evaluation timeline (vis-timeline)
│   └── note-categories/         # Note category CRUD
├── pages/                       # Route-level page components
├── components/
│   ├── ui/                      # shadcn/ui primitives (15 components)
│   ├── charts/                  # ECharts wrappers (heatmap, multi-series, colours)
│   ├── AssetTree/               # Sidebar tree component (8 files)
│   ├── labels/                  # Label chip/editor components
│   ├── shared/                  # Shared UI primitives
│   └── tree/                    # Generic tree node/filter primitives
├── lib/                         # Shared utilities, contexts, constants
├── utils/                       # Pure helper functions
└── mocks/                       # MSW handlers + deterministic data generator
```

## Feature Module Pattern

Every feature follows a layered architecture with DTO/Domain/Mapper separation:

```
features/{domain}/
├── api.ts          # Fetch functions; invoke mapper before returning
├── domain.ts       # Hand-written domain types (camelCase, Date objects)
├── mappers.ts      # dtoToX() sync functions with exhaustiveness checks
├── hooks.ts        # React Query wrappers (useQuery/useMutation)
├── ui-types.ts     # UI-only types (optional)
├── index.ts        # Re-exports domain types + hooks (never mappers/DTOs)
└── components/     # Feature-specific React components
```

**Exception:** The registry feature has no API layer — it composes hooks from slos, slis, datasources, assets, and slo-groups.

**Navigator deviation:** Mappers run in component `useMemo` instead of `queryFn` because they depend on expand/collapse state.

→ Full details: [patterns.md](patterns.md)

## Routing

| Route | Page | URL State |
|---|---|---|
| `/` | redirect → `/navigator` | — |
| `/navigator` | `AssetNavigatorPage` | `?group=`, `?asset=`, `?eval=` |
| `/evaluations/:id` | `EvaluationDetailPage` | — |
| `/slos` | `SloRegistryPage` | `?mode=`, `?selected=`, `?type=`, `?group=` |
| `/assets` | `AssetsPage` | `?group=`, `?asset=` |
| `/explorer` | `MetricExplorerPage` | `?group=`, `?asset=` |
| `/settings/note-categories` | `CategoryManagementPage` | — |

## State Management

| Mechanism | Purpose | Persistence |
|---|---|---|
| React Query | Server state (evaluations, assets, SLOs, heatmaps) | In-memory cache (30s stale time) |
| React Context | Theme + font size (`ThemeProvider`) | localStorage |
| React Context | Time range (`TimeRangeProvider`) | localStorage |
| URL params | Navigation state (group/asset/eval selection) | URL |
| Component state | View mode, expand/collapse, action forms | Component lifecycle |

No Redux, Zustand, or Jotai.

→ Full details: [patterns.md](patterns.md)

## Feature Inventory

| Feature | Components | Layering | Notes |
|---|---|---|---|
| evaluations | 30+ | Full (with exhaustiveness) | Action forms, SLI tables, trend charts, annotations |
| navigator | 15 | Full (mapper exception) | Stacked mini-heatmaps, 3 panel types |
| assets | 10 | Full | CRUD dialogs, group hierarchy, tree selector |
| registry | 20+ | Orchestration only | 3-panel layout, 6 detail views, SLO wizard |
| slos | 7 | Full | Create form, objectives editor, version history |
| slis | — | Full | Consumed by registry |
| slo-groups | — | Full | Consumed by registry |
| datasources | — | Full | Consumed by registry |
| meta_timeline | 5 | Full | vis-timeline integration, DJB2 span colours |
| note-categories | 4 | Full | Category CRUD page |

→ Component catalogue: [components.md](components.md)

## Key Architectural Decisions

### Stacked Mini-Heatmaps

The Navigator's asset heatmap splits into independent per-SLO chart instances rather than one large ECharts heatmap. This enables per-SLO expand/collapse without re-rendering the entire grid. Off-screen segments use `useDeferredValue` for low-priority selection updates.

→ Full details: [charts.md](charts.md)

### Theme System

Three themes via `data-theme` attribute: `dark` (Radix scales), `current` (custom hex, "Alt" label), `light` (stub). ~100 functional CSS tokens in `index.css`. ECharts requires separate JS hex constants because it cannot resolve CSS variables.

→ Full details: [theming.md](theming.md)

### Form Patterns

Three patterns: inline action forms (evaluation popover), modal dialogs (entity CRUD), multi-step wizard (SLO creation). All use colour-identity via accent strips, not tinted backgrounds.

→ Full details: [forms.md](forms.md)

## Documentation Index

| Document | Scope |
|---|---|
| [patterns.md](patterns.md) | Data flow, state management, module structure, conventions |
| [components.md](components.md) | Component catalogue by feature area |
| [charts.md](charts.md) | HeatmapChart, mini-heatmaps, MultiSeriesChart, colour generation |
| [theming.md](theming.md) | Theme system, CSS tokens, colour scales |
| [forms.md](forms.md) | Action forms, SLO wizard, entity CRUD dialogs |
| [testing.md](testing.md) | Test stack, MSW setup, coverage gaps |
| [mocking.md](mocking.md) | MSW mock system and data generator |
| [known-issues.md](known-issues.md) | Technical debt, accessibility gaps, coverage gaps |

### User-Facing Module Docs (`docs/modules/`)

| Document | Feature |
|---|---|
| [navigator-ui.md](../../docs/modules/navigator-ui.md) | Navigator page and panels |
| [evaluations-ui.md](../../docs/modules/evaluations-ui.md) | Evaluation detail and actions |
| [registry-ui.md](../../docs/modules/registry-ui.md) | SLO/SLI/Datasource registry |
| [assets-ui.md](../../docs/modules/assets-ui.md) | Assets and datasources |
| [meta-timeline-ui.md](../../docs/modules/meta-timeline-ui.md) | Meta-timeline |
