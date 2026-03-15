# tropek/ui Refactoring Design

**Date:** 2026-03-14
**Status:** Approved
**Scope:** Full rewrite of `tropek/ui/src/` — architecture, component structure, service layer, mock strategy

---

## Context

The `tropek/ui` codebase is a React 18 + TypeScript + Tailwind + ECharts + React Query dashboard (~1600 lines across 4 pages and 5 components). All data is currently served from mock generators. The code was written to satisfy UI requirements but does not meet coding standards: god components (391–420 lines each), DRY violations (colour palette duplicated in 6+ files, utility functions reimplemented in multiple places), no custom hooks, no atomic UI components, and mock logic tightly coupled to fetch functions.

---

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| External dependencies | Full modernisation — shadcn/ui + React Hook Form + MSW | Establishes a standard, recognisable stack; removes all ad-hoc patterns |
| Architecture | Feature-sliced design, single app | Right size for this project; microfrontend-style isolation without monorepo overhead |
| Service layer | Custom hooks (not repository classes) | Idiomatic React; same layering discipline as a Python service module without OOP ceremony |
| Mock strategy | MSW (Mock Service Worker) | Mocks intercept at network level; fetch functions become pure and mock-free |
| Migration | Full rewrite | At ~1600 lines, a clean slate costs less than threading new patterns through existing code |

---

## Folder Structure

```
src/
├── components/
│   └── ui/                          # shadcn/ui atomic components
│       ├── button.tsx
│       ├── badge.tsx
│       ├── input.tsx
│       ├── select.tsx
│       ├── dialog.tsx
│       ├── tabs.tsx
│       ├── combobox.tsx
│       └── collapsible.tsx
│
├── features/
│   ├── evaluations/
│   │   ├── api.ts                   # plain fetch functions, no mock logic
│   │   ├── hooks.ts                 # useEvaluations, useEvaluationDetail, useTrend, useColumnVisibility
│   │   ├── types.ts                 # EvaluationSummary, EvaluationDetail, IndicatorResult, etc.
│   │   ├── constants.ts             # RESULT_COLOUR (re-exported from lib/theme), FIXED_COLS, TAB_ORDER
│   │   └── components/
│   │       ├── EvaluationHeatmap.tsx
│   │       ├── EvaluationTable.tsx
│   │       ├── EvaluationTabs.tsx
│   │       ├── MetricTrendBlock.tsx
│   │       ├── SLIBreakdownTable.tsx
│   │       ├── AnnotationCell.tsx
│   │       ├── AnnotationForm.tsx
│   │       └── TriggerEvaluationModal.tsx
│   │
│   ├── assets/
│   │   ├── api.ts
│   │   ├── hooks.ts                 # useAssets, useAssetGroups
│   │   ├── types.ts                 # Asset, AssetGroup, AssetGroupTree
│   │   ├── utils.ts                 # collectGroupAssets() — single source of truth
│   │   └── components/
│   │       ├── AssetGroupCard.tsx
│   │       ├── ColourLegend.tsx
│   │       └── AssetFilter.tsx
│   │
│   └── slos/
│       ├── api.ts
│       ├── hooks.ts                 # useSlos, useSloDetail, useSloValidation
│       ├── types.ts                 # SloDefinition, SloObjective, SliQuery (indicator + query pair)
│       └── components/
│           ├── SloObjectiveTable.tsx
│           ├── SloYamlViewer.tsx
│           ├── SloObjectiveEditor.tsx   # row-edit mode
│           ├── SloYamlEditor.tsx        # raw YAML edit mode
│           └── SloYamlUpload.tsx        # file upload + validation
│
├── lib/
│   ├── theme.ts                     # RESULT_COLOUR, OS_COLOUR_MAP — single source of truth
│   ├── format.ts                    # fmt(), fmtPct(), fmtSlot(), fmtDate()
│   └── queryKeys.ts                 # typed React Query key factories per feature
│
├── mocks/
│   ├── browser.ts                   # MSW worker setup for development
│   ├── generate.ts                  # deterministic mock data generator (kept, cleaned up)
│   └── handlers/
│       ├── evaluations.ts           # GET /api/evaluations, GET /api/evaluations/:id,
│       │                            # GET /api/trend, POST /api/evaluations (trigger),
│       │                            # POST /api/evaluations/:id/annotations,
│       │                            # PATCH /api/evaluations/:id/invalidate
│       ├── assets.ts                # GET /api/assets, GET /api/asset-groups
│       └── slos.ts                  # GET /api/slos, GET /api/slos/:name, POST /api/slos/validate
│
├── pages/                           # thin shells — compose feature components, nothing more
│   ├── EvaluationsPage.tsx          # ~40 lines
│   ├── EvaluationDetailPage.tsx     # ~50 lines
│   ├── SloRegistryPage.tsx          # ~40 lines
│   └── AssetsPage.tsx               # ~40 lines
│
├── App.tsx                          # routing + QueryClientProvider + nav
└── main.tsx                         # React root; starts MSW worker in dev mode
```

---

## Data Flow

Four layers, each with one job. Nothing skips a layer.

```
Page (thin shell)
  └── calls useXxx() hook
        └── calls fetchXxx() api function
              └── fetch('/api/...') ← MSW intercepts in dev, real server in prod
```

**Python analogy:**
```
Flask route handler (thin shell)
  └── calls service.get_xxx()
        └── calls api_client.fetch_xxx()
              └── requests.get('/api/...') ← responses mock in test, real server in prod
```

### Layer responsibilities

| Layer | File | Job |
|---|---|---|
| MSW handler | `mocks/handlers/evaluations.ts` | Intercepts HTTP in dev; generates mock response; invisible in prod |
| API function | `features/evaluations/api.ts` | Pure async function — fetch + deserialise. No mock logic, ever. |
| Custom hook | `features/evaluations/hooks.ts` | Wraps React Query — owns queryKey, loading state, error state. The service layer. |
| Page component | `pages/EvaluationsPage.tsx` | Reads URL params, calls hook, composes feature components. No business logic. |

---

## Component Breakdown

### God components eliminated

**EvaluationListPage (391 lines) → 7 units**

| Unit | Responsibility |
|---|---|
| `pages/EvaluationsPage.tsx` | Thin shell; URL params; composes heatmap + table + trigger modal (~40 lines) |
| `features/evaluations/components/EvaluationHeatmap.tsx` | ECharts heatmap; receives data via props; no fetch |
| `features/evaluations/components/EvaluationTable.tsx` | Table with column picker; uses `useColumnVisibility` hook |
| `features/evaluations/components/AnnotationCell.tsx` | Annotation display in table cells |
| `features/evaluations/components/TriggerEvaluationModal.tsx` | Dialog form for triggering a new evaluation; calls `POST /api/evaluations`; uses `useAssetGroups()` and `useSlos()` to populate dropdowns; rendered by `EvaluationsPage` |
| `features/evaluations/hooks.ts → useEvaluations()` | Wraps two React Query calls (all evals + slot-filtered) |
| `features/evaluations/hooks.ts → useColumnVisibility()` | Column visibility state + outside-click; reusable |

**EvaluationDetailPage (420 lines) → 6 units**

| Unit | Responsibility |
|---|---|
| `pages/EvaluationDetailPage.tsx` | Thin shell; reads :id param; composes below (~50 lines) |
| `features/evaluations/components/SLIBreakdownTable.tsx` | Indicator table; uses `lib/format.ts`; no inline formatters |
| `features/evaluations/components/MetricTrendBlock.tsx` | Self-contained trend chart; fetches own data via `useTrend()` |
| `features/evaluations/components/AnnotationForm.tsx` | React Hook Form; replaces 10 useState calls; submits to `POST /api/evaluations/:id/annotations` |
| `features/evaluations/components/EvaluationTabs.tsx` | Tab bar driven by constants; no hardcoded `tabLabel()` |
| `features/evaluations/hooks.ts → useEvaluationDetail()` | Detail query + `useAddAnnotation()` mutation (POST) + `useInvalidate()` mutation (PATCH) |

**AssetRegistryPage (370 lines) → 5 units**

| Unit | Responsibility |
|---|---|
| `pages/AssetsPage.tsx` | Thin shell; composes card + legend (~40 lines) |
| `features/assets/components/AssetGroupCard.tsx` | Group card + subgroups + asset rows |
| `features/assets/components/ColourLegend.tsx` | OS colour picker; colour map from `lib/theme.ts` |
| `features/assets/components/AssetFilter.tsx` | Search + expand/collapse controls |
| `features/assets/hooks.ts → useAssets()` | Asset group query + filter logic |

---

## SLO Registry — Enhanced Design

The SLO Registry is redesigned beyond a simple cleanup. The new layout has three modes:

### Default view
- **Objectives table** at top: each row shows indicator name, SLI query (from the `indicators` block embedded in the SLO YAML), pass criteria, warning criteria, weight, key_sli flag side by side
- **Score thresholds** (pass/warn total score, comparison method) shown below table
- **Raw YAML** collapsed at bottom — expandable; editable as raw text for power users
- **"Test SLO" button** — render as a visually disabled button only; no handler, no hook, no file created for this feature in this phase

### Edit Rows mode (activated via "Edit Rows" button)
- Mode stored in local `useState` — no URL param, no browser back-button navigation (transient edit state)
- Replaces objectives table in place (no page navigation)
- Each objective row becomes editable inputs
- SLI indicator combobox populated from the current SLO's already-loaded `indicators` block (no extra API call); filtering is client-side string search over that list
- Pass/warn criteria validated client-side on change
- "Add Objective" row appended at bottom
- "Validate & Save" calls `POST /api/slos/validate` (backend validates full YAML structure and criteria); on success, saves and returns to default view

### Upload YAML mode (activated via "Upload YAML" button)
- Drag-and-drop or file picker for `.yaml` / `.yml` files
- File POSTed to `POST /api/slos/validate` — backend validates structure and criteria
- Validation errors displayed inline with field-level pointers
- On success, parsed objectives shown in preview before confirming save

### Component structure

| Component | Responsibility |
|---|---|
| `pages/SloRegistryPage.tsx` | Thin shell; `mode` local state (`'view' \| 'edit' \| 'upload'`); composes below (~50 lines) |
| `features/slos/hooks.ts → useSloDetail(name)` | Fetches single SLO from `GET /api/slos/:name`; called when a SLO row is expanded; provides `indicators` list to child components |
| `features/slos/components/SloObjectiveTable.tsx` | Read-only objectives table with SLI queries |
| `features/slos/components/SloYamlViewer.tsx` | Collapsible raw YAML display |
| `features/slos/components/SloObjectiveEditor.tsx` | Row edit mode with combobox + validation |
| `features/slos/components/SloYamlEditor.tsx` | Raw YAML text editor |
| `features/slos/components/SloYamlUpload.tsx` | File upload + backend validation + preview |
| `features/slos/hooks.ts → useSlos()` | SLO list query |
| `features/slos/hooks.ts → useSloValidation()` | Wraps POST /api/slos/validate mutation |

---

## Shared lib/ Layer

### lib/theme.ts
Single source of truth for all colour constants. Eliminates duplication across 6+ files.

```typescript
export const RESULT_COLOUR = {
  pass: '#7dc540',
  warning: '#e6be00',
  fail: '#dc172a',
  error: '#888888',
} as const

export const DEFAULT_OS_COLOUR_MAP: Record<string, string> = { ... }
```

### lib/format.ts
All number and date formatters extracted from inline component definitions.

```typescript
export const fmt = (v: number | null): string => ...
export const fmtPct = (v: number | null): string => ...
export const fmtSlot = (slot: string): string => ...
export const fmtDate = (iso: string): string => ...
```

### lib/queryKeys.ts
Typed key factory. Eliminates hardcoded query key strings across components.

```typescript
export const evaluationKeys = {
  all: ['evaluations'] as const,
  list: (filters: EvaluationFilters) => [...evaluationKeys.all, filters] as const,
  detail: (id: string) => [...evaluationKeys.all, id] as const,
  trend: (id: string, metric: string) => [...evaluationKeys.detail(id), metric] as const,
}
export const assetKeys = { ... }
export const sloKeys = { ... }
```

---

## MSW Mock Strategy

Mock logic is removed entirely from api functions. The `api/client.ts` god-file is deleted.

**Development:** `main.tsx` starts the MSW service worker before rendering. All fetch calls to `/api/*` are intercepted by handlers in `mocks/handlers/`. No environment variable toggle needed — MSW only runs when started.

**Production:** MSW is never imported or started. Fetch calls go to the real server.

**Handler structure:**
```typescript
// mocks/handlers/evaluations.ts
export const evaluationHandlers = [
  http.get('/api/evaluations', ({ request }) => {
    const filters = parseFilters(new URL(request.url).searchParams)
    return HttpResponse.json(generateEvaluations(filters))
  }),
  http.get('/api/evaluations/:id', ({ params }) => {
    return HttpResponse.json(generateEvaluationDetail(params.id))
  }),
  http.post('/api/evaluations', async ({ request }) => {
    const body = await request.json()
    return HttpResponse.json(generateTriggeredEvaluation(body), { status: 202 })
  }),
  http.post('/api/evaluations/:id/annotations', async ({ params, request }) => {
    const body = await request.json()
    return HttpResponse.json(generateAnnotation(params.id, body), { status: 201 })
  }),
  http.patch('/api/evaluations/:id/invalidate', async ({ params, request }) => {
    return HttpResponse.json({ id: params.id, invalidated: true })
  }),
]
```

---

## DRY Violations Fixed

| Violation | Fix |
|---|---|
| `RESULT_COLOUR` duplicated in 6 files | `lib/theme.ts` — single export |
| `computeRelativeThresholdSeries()` in both `utils/metrics.ts` and `MetricTrendChart.tsx` | Delete inline copy; import from `utils/metrics.ts` |
| `collectGroupAssets()` in both `api/client.ts` and `TriggerEvaluationModal.tsx` | Single implementation in `features/assets/utils.ts`; imported by both `useAssetGroups()` hook and `TriggerEvaluationModal` |
| `fmt()` / `fmtPct()` defined inline in 4+ components | `lib/format.ts` — single export |
| React Query keys as hardcoded strings | `lib/queryKeys.ts` factory |
| Button/input Tailwind classes repeated 20+ times | `components/ui/button.tsx`, `components/ui/input.tsx` |
| Collapse/expand triangle pattern in 4 places | `components/ui/collapsible.tsx` |

---

## Out of Scope

- **"Test SLO" feature** — render a visually disabled button only; do not create any file, hook, handler, or type for this feature
- **Real backend integration** — MSW stays; wiring to real API is a separate phase
- **Component tests / integration tests** — test infrastructure improvements deferred
- **Styled error UI** — on React Query `isError`, render a plain unstyled text fallback (`<p>Failed to load data.</p>`); no error boundary component, no retry logic, no toast notifications in this phase

---

## Constraints

- TypeScript throughout; beginner-friendly patterns (no classes, no DI containers)
- Each feature component must be understandable without reading its parent
- No component file should exceed ~150 lines; pages capped at ~50 lines
- Python-style thinking: hooks = service modules, api functions = client functions, pages = route handlers
