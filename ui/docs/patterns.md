# Patterns

Data flow patterns, state management, and architectural conventions in the TROPEK UI.

## Data Fetching: React Query

All server state is managed via [TanStack Query](https://tanstack.com/query) (React Query). No Redux, Zustand, or other state management libraries.

### Query Key Factory

**File:** `src/lib/queryKeys.ts`

All query keys are centralized in factory objects with methods returning tuple keys:

| Factory | Keys |
|---|---|
| `evaluationKeys` | `all`, `list(filters)`, `detail(id)`, `allTrends`, `trend(asset, slo, metric, dateRange?)`, `allHeatmaps`, `heatmap(...)`, `allNames`, `names(scope)`, `columnAnnotations(evalId)` |
| `assetKeys` | `all`, `groups()` |
| `sloKeys` | `all`, `detail(name)`, `tagKeys()`, `tagValues(key)` |
| `sliKeys` | `all`, `detail(name)`, `versions(name)`, `tagKeys()`, `tagValues(key)` |
| `groupKeys` | `all`, `tree()`, `detail(name)`, `links(name)`, `assignments(name)` |
| `assignmentKeys` | `all`, `asset(assetName)`, `group(groupName)` |
| `datasourceKeys` | `all`, `detail(name)`, `tagKeys()`, `tagValues(key)` |
| `sloGroupKeys` | `all`, `detail(name)` |

Keys use hierarchical spread composition: `detail(id) => [...all, id]`. This enables broad invalidation (`evaluationKeys.all` invalidates everything) and targeted invalidation (`evaluationKeys.detail(id)` targets one).

### QueryClient Configuration

Created in `App.tsx` with `defaultOptions.queries.staleTime = 30_000` (30 seconds).

### Fetch Functions

Each feature has an `api.ts` with fetch functions that:
1. Call the API endpoint
2. Check `res.ok`, throw on failure
3. Map the DTO to domain type via mapper
4. Return domain type

React Query cache stores **domain types**, not DTOs.

## DTO → Domain Mapping (Anti-Corruption Layer)

Full design spec: `docs/superpowers/specs/2026-04-12-ui-layering-design.md`

### Two Type Universes

| Layer | Location | Naming | Dates | Used By |
|---|---|---|---|---|
| **DTOs** | `src/generated/api.ts` | snake_case | strings | `api.ts`, `mappers.ts` only |
| **Domain types** | `features/<x>/domain.ts` | camelCase | `Date` objects | Components, hooks |

### Mapping Point

Mappers live in `features/<x>/mappers.ts` and run inside fetch functions in `api.ts` — once per network call, before the result enters the React Query cache. Components never see DTOs.

### Exhaustiveness Checks

Mapper files include compile-time type assertions that catch new DTO fields at compile time:

```ts
type MappedKeys = 'field_a' | 'field_b' | ...
type Coverage = Exclude<keyof SomeDto, MappedKeys | DroppedKeys>
const _exhaustive: Coverage extends never ? true : Coverage = true
```

If the backend adds a field, the mapper fails to compile. Implemented in evaluations, slos, slis, assets, datasources, slo-groups.

### Write Path

Write paths send backend-shaped bodies directly. Reverse mappers (`xInputToDto`) exist only when domain vocabulary diverges from request body shape. Input types are typically DTO aliases re-exported from `api.ts`.

### One Documented Deviation

The Navigator caches raw DTOs because its mappers (`overallScoreToMiniView`, `sloGroupToMiniView`) depend on `expandState`. Mappers run in component `useMemo` instead of `queryFn`. See [charts.md](charts.md) for details.

## Per-Feature Module Structure

```
features/<x>/
├── api.ts         # fetch fns — invoke mapper before returning
├── domain.ts      # domain types (UI vocabulary, camelCase)
├── mappers.ts     # dtoToX() + optional reverse mappers
├── hooks.ts       # thin React Query wrappers
├── ui-types.ts    # UI-only types (not domain, not DTO)
├── index.ts       # re-exports domain types + hooks ONLY
└── components/    # import domain types from '@/features/<x>'
```

### Barrel Rules

- `index.ts` re-exports domain types, hooks, and key components
- Never re-exports mappers or DTOs
- A small number of raw fetch functions may be exported for use in `queryFn` positions

### Feature Without API Layer

The registry feature has **no `api.ts`, `domain.ts`, or `mappers.ts`**. It is purely a UI orchestration layer that composes hooks from `slos`, `slis`, `datasources`, `assets`, and `slo-groups`.

## State Management

### Three State Categories

| Category | Mechanism | Examples |
|---|---|---|
| **Server state** | React Query | Evaluations, assets, SLOs, heatmap data |
| **URL state** | `useSearchParams` | Selected asset, group, mode, eval ID |
| **Local component state** | `useState` | Expand/collapse, action form visibility, filter selections |

### URL State

Both `AssetNavigatorPage` and `SloRegistryPage` persist selection state in URL search params:

**Navigator:** `?asset=X`, `?group=X`, `?eval=X`
**Registry:** `?mode=slo`, `?selected=X`, `?type=Y`, `?group=Z`

Navigations replace (not append) params to prevent stale values.

### Time Range Context

**File:** `src/lib/time-range-context.tsx`

Global provider for time range state. Two modes: `preset` (relative days) or `absolute` (ISO date range). Persisted in `localStorage`. Consumed by hooks like `useEvaluations` which merge caller filters with the time range.

## Mutation Patterns

### Single Mutations

Hooks like `useInvalidateEvaluation` wrap `useMutation`. On success, they invalidate relevant query keys.

### Batch Mutations

Action forms fire parallel API calls via `Promise.all`, collecting per-row results. `invalidateColumnQueries()` centralises cache invalidation after batch actions.

### Cross-Feature Invalidation

Some mutations affect multiple features:
- Deleting a group invalidates `groupKeys.all` + `assetKeys.groups()` + `sloKeys.all`
- SLO-group mutations invalidate both `sloGroupKeys.all` and `sloKeys.all`
- Creating an asset invalidates both `assetKeys.all` and `groupKeys.all`

## Lazy Loading

Conditional queries use the `enabled` flag:

```ts
useQuery({
  queryKey: sloKeys.detail(name),
  queryFn: () => fetchSloDetail(name),
  enabled: !!name,  // only fetch when name is set
})
```

The Navigator uses `IntersectionObserver`-based lazy mounting for expanded SLO heatmap segments.

## Error Handling

### Current State

Fetch functions consistently throw on non-OK responses: `if (!res.ok) throw new Error(...)`. Only `reEvaluate` in `evaluations/api.ts` parses the error body for a better message; other endpoints lose the server error body.

### Known Gap

Most panel components check `isLoading` but not `isError`. If a fetch fails, the component shows loading state indefinitely. This affects AssetPanel, GroupPanel, AllEvaluationsPanel, and EvaluationDetailPage.

A single `ErrorBoundary` wraps the entire route outlet in `App.tsx`. No feature-level error boundaries exist.

## Cross-Feature Data Sharing

Features reference each other via barrel imports:

```
navigator → evaluations (detail components, action forms, hooks)
navigator → assets (hooks, domain types)
evaluations → navigator (heatmap types for SLO scope)
evaluations → assets (useAssets in TriggerEvaluationModal)
evaluations → note-categories (palette, categories)
registry → slos, slis, datasources, assets, slo-groups (all hooks)
assets ↔ slos (bidirectional: group assignments)
```

The registry feature is the most connected — it is a pure UI composition layer with no API of its own.

## Key Conventions

- **`key={identifier}` for full remount:** `AssetNavigatorPage` uses `key={selectedAsset}` on `AssetPanel` to force full unmount/remount on asset change, resetting all 10+ local state hooks cleanly.
- **Column-centric selection:** The Navigator treats evaluation columns (parent `evaluation_id`) as the primary selection unit, not individual SLO evaluation IDs.
- **Result normalisation:** Backend emits `result: string` + `invalidated: boolean` as separate fields. Mappers collapse them into a single `Outcome` or `HeatmapResult` union type. Components never branch on the `invalidated` boolean directly.
- **ISO string period:** `period` is `DateRange` (`{from: string, to: string}` ISO strings), not `Date` objects, because `from` values are used as Map/Set keys where object identity would break equality.
