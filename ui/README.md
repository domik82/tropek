# TROPEK UI

React SPA for the TROPEK quality gate platform — asset navigation, evaluation drill-down, SLO registry, and metric exploration.

## Stack

React 19, TypeScript 5.9, Vite 8, Tailwind CSS 4, shadcn/ui, ECharts 6, TanStack Query 5, React Router 7, React Hook Form + Zod 4, Lucide React, MSW 2, Vitest + happy-dom.

## Quick Start

```bash
cd ui
pnpm install
pnpm run dev           # starts on http://localhost:5173 with mock data
```

By default the dev server runs with **MSW mocks enabled** — no backend needed. The browser console will show `[MSW] Mocking enabled` on startup.

To run against the real API:

```bash
VITE_USE_MOCKS=false pnpm run dev
```

## Scripts

| Command | Purpose |
|---|---|
| `pnpm run dev` | Vite dev server with HMR + MSW mocks |
| `pnpm run build` | TypeScript check + production build |
| `pnpm run preview` | Serve production build locally |
| `pnpm run lint` | ESLint |
| `pnpm run test` | Vitest (component tests) |

Or from the repo root:

```bash
just test-ui                    # all UI tests
just test-ui src/features/...   # specific file
just lint-ui                    # ESLint
```

## Routes

| Path | Page | URL State |
|---|---|---|
| `/` | Redirects to `/navigator` | — |
| `/navigator` | Asset navigator (tree + panels) | `?group=&asset=&eval=` |
| `/evaluations/:id` | Evaluation detail | — |
| `/slos` | SLO registry (3-mode) | `?mode=&selected=&type=&group=` |
| `/assets` | Asset management | `?group=&asset=` |
| `/explorer` | Metric explorer | `?group=&asset=` |
| `/settings/note-categories` | Note category management | — |

## Themes

Three themes via `data-theme` attribute on `<html>`:

| Theme | Style | Toggle |
|---|---|---|
| `current` | Dark, teal/green accent | Navbar "Dark" button |
| `dark` | Dark, Radix UI colour scales | Navbar "Alt" button |
| `light` | Light | Stub — not yet exposed |

Theme and font size persist in localStorage.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `VITE_USE_MOCKS` | `true` (dev) | Enable MSW browser mocking |
| `VITE_API_BASE` | `http://localhost:8080` | Backend API base URL |

## Documentation

### Architecture & Contributor Guides (`ui/docs/`)

| Document | Scope |
|---|---|
| [architecture.md](docs/architecture.md) | Tech stack, directory structure, feature inventory, key decisions |
| [patterns.md](docs/patterns.md) | Data flow, state management, module structure, conventions |
| [components.md](docs/components.md) | Component catalogue by feature area |
| [charts.md](docs/charts.md) | HeatmapChart, stacked mini-heatmaps, MultiSeriesChart, colours |
| [theming.md](docs/theming.md) | Theme system, CSS tokens, colour scales |
| [forms.md](docs/forms.md) | Action forms, SLO wizard, entity CRUD dialogs |
| [testing.md](docs/testing.md) | Test stack, MSW setup, QueryClient cleanup, coverage gaps |
| [mocking.md](docs/mocking.md) | MSW mock system and deterministic data generator |
| [known-issues.md](docs/known-issues.md) | Technical debt, accessibility gaps, test coverage |

### User-Facing Feature Docs (`docs/modules/`)

| Document | Feature |
|---|---|
| [navigator-ui.md](../docs/modules/navigator-ui.md) | Navigator page (heatmaps, panels, drill-down) |
| [evaluations-ui.md](../docs/modules/evaluations-ui.md) | Evaluations (detail, actions, SLI breakdown) |
| [registry-ui.md](../docs/modules/registry-ui.md) | SLO/SLI/Datasource registry |
| [assets-ui.md](../docs/modules/assets-ui.md) | Assets, groups, datasources |
| [meta-timeline-ui.md](../docs/modules/meta-timeline-ui.md) | Meta-timeline |
