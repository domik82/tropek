# Mock System (MSW)

The UI uses [Mock Service Worker](https://mswjs.io/) (MSW 2) to intercept API calls
during development. No backend needed for UI development.

## How It Works

```
main.tsx
  -> enableMocking()           (only in dev mode)
    -> import('./mocks/browser')
    -> worker.start()          (intercepts fetch calls)
  -> render(<App />)
```

MSW intercepts all `fetch` calls matching `/api/*` patterns and returns
deterministic mock data. Unhandled requests (fonts, images, HMR) are bypassed.

## File Structure

```
src/mocks/
├── browser.ts          # MSW setupWorker entry point
├── generate.ts         # Deterministic data generator (seeded PRNG, ~800 lines)
├── data/
│   ├── assets.json          # Static asset fixtures
│   ├── evaluation-detail.json
│   ├── evaluations.json
│   ├── sli-definitions.json
│   ├── slo-definitions.json
│   └── trend.json
└── handlers/
    ├── index.ts         # Handler aggregator + /api/config/ui
    ├── evaluations.ts   # 14 endpoints (list, detail, heatmaps, trend, mutations)
    ├── assets.ts        # 7 endpoints (list, group tree, SLO links, group CRUD)
    ├── slos.ts          # 6 endpoints (list, detail, versions, validate, test, CRUD)
    └── slis.ts          # 5 endpoints (list, detail, versions, CRUD)
```

## Data Generator

`generate.ts` creates a complete, realistic dataset using a seeded PRNG
(linear congruential generator: `s = (s * 1664525 + 1013904223) & 0xffffffff`).
Each scenario gets its own seed for reproducible output across page reloads.

### What It Generates

| Data | Details |
|---|---|
| **Metrics** | 30 metrics across 5 tab groups (summary, timing, resources, network, errors). Each has baseline, pass/warn criteria, unit, key_sli flag, weight, higher_is_worse polarity. |
| **Scenarios** | 32 scenarios across 5 labs (monthly-lab, toolset-lab, ad-hoc-lab-1, performance-lab-1/2). Each has a seed, regression window config, and runs_per_day (1 or 2). |
| **History** | 30 days of evaluation data per scenario. |
| **Regressions** | Configurable multiplicative factors (1.12x–1.8x) in specified day windows. |
| **Annotations** | Story-driven notes on specific scenarios/days (invalidation events, JIRA references, disk failure investigations). |
| **Asset snapshots** | Tags (os, arch, lab) and variables (branch, build number, triggered_by). |

### Caching

Generated data is cached at the module level (`_cached` variable). Computed once
per module load via `generateAllEvaluations()`. Handlers use lazy
`import('../generate')` to tree-shake the generator in production builds.

### Generated Heatmap Data

Unlike evaluations, assets, and SLOs which use static JSON fixtures, heatmap data
is generated procedurally in `getGroupedMetricHeatmap()` using the seeded PRNG.
Produces 3 SLO groups (nginx/redis/postgres), 7 columns, randomized results.

## Handler Coverage

| Area | Endpoints | Key Operations |
|---|---|---|
| Evaluations | 14 | List, detail, heatmaps (single + grouped), trend, trigger, re-evaluate (3 modes), annotations (create, hide), invalidate, override, restore, pin baseline |
| Assets | 7 | List, group tree, SLO link CRUD, group CRUD |
| SLOs | 6 | List, detail, versions, validate, test, create, delete |
| SLIs | 5 | List, detail, versions, create, delete |
| Config | 1 | `/api/config/ui` → `{ maxEvaluations: 1000, pageSize: 200 }` |

### Handler Pattern

```typescript
import { http, HttpResponse } from 'msw'

async function gen() { return import('../generate') }

export const evaluationHandlers = [
  http.get('/api/evaluations', async ({ request }) => {
    const { getEvaluations } = await gen()
    const url = new URL(request.url)
    // filter, paginate, return
    return HttpResponse.json({ items: [...], total: n })
  }),
]
```

### Known Limitations

- SLO validate/test endpoints return **hardcoded static responses** regardless
  of input — wizard preview testing does not reflect actual validation logic.
- Config mock differs from `config.ts` defaults: returns `maxEvaluations: 1000`
  (default is 5000) and omits `heatmapSloGroupsExpandedByDefault`,
  `heatmapSlowThresholdDays`, `dataStartDate`.

## Switching Between Mock and Real API

```bash
# Mock mode (default in dev)
pnpm run dev

# Real API mode
VITE_USE_MOCKS=false pnpm run dev

# Production build (no mocks, real API)
VITE_API_BASE=http://localhost:8080 pnpm run build
```

MSW is only imported in development builds (`import.meta.env.DEV` guard).
Production bundles contain zero MSW code.

## Using MSW in Tests

Import handlers directly for component tests:

```typescript
import { handlers } from '@/mocks/handlers'
import { setupServer } from 'msw/node'

const server = setupServer(...handlers)
beforeAll(() => server.listen())
afterAll(() => server.close())
```

See [testing.md](testing.md) for the full testing guide including QueryClient
cleanup patterns.
