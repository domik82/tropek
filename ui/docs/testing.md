# Testing

Guide to writing and running UI tests in TROPEK.

## Test Stack

- **Vitest** — test runner (configured in `vite.config.ts` `test` block)
- **React Testing Library** — component rendering and queries
- **happy-dom** — browser environment (NOT jsdom)
- **MSW (Mock Service Worker)** — API mocking
- **@testing-library/jest-dom/vitest** — DOM matchers (loaded via `src/test-setup.ts`)

## Running Tests

```bash
# All UI tests (from repo root)
just test-ui

# Specific file
just test-ui src/features/.../Foo.test.tsx

# Watch mode (from ui/ directory)
cd ui && pnpm exec vitest run --watch

# Agent-friendly (summary only)
./scripts/ui-test.sh --tail 10
./scripts/ui-test.sh --tail 10 src/features/.../Foo.test.tsx
```

**Important:** Vitest requires `vite.config.ts` for the happy-dom environment config. Running `pnpm exec vitest` from the repo root (outside `ui/`) will fail with `document is not defined`. Always use `just test-ui` or `cd ui` first.

## Configuration

**Vitest config** (`ui/vite.config.ts` → `test` block):
- Environment: `happy-dom`
- Setup: `./src/test-setup.ts`
- Globals: `true`
- Pool: `forks`
- Excludes: `node_modules`, `.claude`

**Test setup** (`ui/src/test-setup.ts`): Imports `@testing-library/jest-dom/vitest` to load DOM matchers.

## QueryClient Cleanup (Required)

Happy-dom aborts all in-flight fetches on teardown, causing `DOMException: AbortError` noise. **Every test file that renders a component using React Query hooks** (`useQuery`, `useQueries`, `useMutation`) must follow this pattern:

```tsx
let queryClient: QueryClient

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
})

afterEach(() => {
  queryClient.cancelQueries()
  queryClient.clear()
  cleanup()
})
```

Wrap the component under test in `<QueryClientProvider client={queryClient}>`.

See `src/features/evaluations/components/NoteEntry.test.tsx` for a complete example.

## File Placement

Place test files next to the component they test:

```
features/evaluations/components/
├── ResultBadge.tsx
├── ResultBadge.test.tsx
├── SLIBreakdownTable.tsx
└── SLIBreakdownTable.test.tsx
```

## MSW Mock System

**Files:** `src/mocks/`

MSW provides API mocking for both development and tests.

### Setup

```
src/mocks/
├── browser.ts          # MSW worker setup
├── generate.ts         # Deterministic mock data generator (~800 lines)
├── data/               # Static JSON fixtures (assets, evaluations, SLOs, SLIs, trends)
├── handlers/
│   ├── index.ts        # Handler aggregator + /api/config/ui
│   ├── evaluations.ts  # 14 evaluation endpoints
│   ├── assets.ts       # 7 asset endpoints
│   ├── slos.ts         # 6 SLO endpoints
│   └── slis.ts         # 5 SLI endpoints
```

### Mock Data Generator

`generate.ts` uses a seeded PRNG (linear congruential generator) for reproducible data across page reloads. It produces 32 scenarios across 5 labs with:
- 30 metrics in 5 tab groups (summary, timing, resources, network, errors)
- Configurable regression windows with multiplicative factors
- Story-driven annotations (invalidation events, JIRA references)
- Asset snapshots with tags (os, arch, lab) and variables (branch, build number)

Handlers use lazy `import('../generate')` to tree-shake the generator in production builds.

### Handler Coverage

| Area | Endpoints | Notes |
|---|---|---|
| Evaluations | 14 | List, detail, heatmaps, trend, trigger, re-evaluate, annotations, invalidate/override/restore/pin |
| Assets | 7 | List, group tree, SLO links CRUD, group CRUD |
| SLOs | 6 | List, detail, versions, validate, test, create, delete |
| SLIs | 5 | List, detail, versions, create, delete |
| Config | 1 | `/api/config/ui` with maxEvaluations: 1000 |

### Using MSW in Tests

MSW is started automatically in dev mode (`VITE_USE_MOCKS !== 'false'`). For tests, import handlers directly:

```tsx
import { handlers } from '@/mocks/handlers'
import { setupServer } from 'msw/node'

const server = setupServer(...handlers)
beforeAll(() => server.listen())
afterAll(() => server.close())
```

## Writing a New Test

1. Create `ComponentName.test.tsx` next to the component
2. Import the component and testing utilities:
   ```tsx
   import { render, screen, cleanup } from '@testing-library/react'
   import userEvent from '@testing-library/user-event'
   ```
3. If the component uses React Query, set up the QueryClient pattern (above)
4. If the component fetches data, set up MSW handlers
5. Wrap in necessary providers (QueryClientProvider, ThemeProvider, etc.)
6. Test the golden path and edge cases

## Current Coverage

### Well-Tested Areas

- All asset dialogs (7 dialog components)
- All evaluation action forms (5 forms + SloScope components)
- All registry detail views (6 views)
- Most registry forms (8 form components)
- Shared components (BindingChainBreadcrumb, SearchableComboBox, StructuredCriteriaInput, TagFilterBar, VariableResolutionPanel, TreeFilter, TreeNode)
- All pages (AssetNavigatorPage, AssetsPage, EvaluationDetailPage, SloRegistryPage)
- Meta-timeline (all 4 components)

### Coverage Gaps (~40 untested components)

**High priority:**
- `HeatmapChart.tsx` — core shared component (451 lines)
- `EvaluationTable.tsx` — core data display (167 lines)
- `MetricTrendBlock.tsx` — complex chart rendering (254 lines)
- `AssetPanelHeatmapView.tsx` — complex heatmap orchestration (336 lines)
- `SloObjectiveEditor.tsx` — complex form (290 lines)
- `AssetTree.tsx` — main tree component (311 lines, only node+context menu tested)

**Medium priority:**
- Navigator sub-components: GroupPanel, AllEvaluationsPanel, AssetScoreChart, GroupScoreChart, SloMiniHeatmap, AssetPanelChartView
- Evaluation display: EvaluationHeader, EvaluationHeatmap, NoteGroup, AddNoteForm, TriggerEvaluationModal
- SLO components: SloObjectiveTable, SloHistoryPanel
- Note categories: CategoryManagementPage, CategoryRow
- Wizard steps: WizardStepComparison, WizardStepIdentity, WizardStepPickSli

**Low priority:**
- Small UI components: ViewToggle, TruncationWarning, AnnotationCell, EvaluationTabs
- Utility components: LazyHeatmap, MetricGroupFilter, ErrorBoundary
- Asset dialogs: GroupEditDialog, GroupDeleteDialog

### Untested Non-Component Files

Utility and hook files without tests:
- `features/navigator/utils.ts`, `features/navigator/components/treeUtils.ts`
- `features/registry/forms/criteriaUtils.ts`, `features/registry/forms/tagUtils.ts`
- `features/evaluations/components/actions/invalidate-column-queries.ts`
- `features/evaluations/components/actions/slo-scope/useSloScope.ts`
- `lib/useChartAreaClick.ts`, `lib/entity-colors.ts`, `lib/validation.ts`

## Common Pitfalls

1. **Running vitest from repo root** — fails with `document is not defined`. Always run from `ui/` or use `just test-ui`.
2. **Forgetting QueryClient cleanup** — causes `DOMException: AbortError` noise and potentially flaky tests.
3. **Not wrapping in providers** — components using React Query, theme context, or time range context need their respective providers.
4. **SLO validate/test mocks are hardcoded** — mock handlers return static responses regardless of input, so wizard preview testing does not reflect actual validation.
