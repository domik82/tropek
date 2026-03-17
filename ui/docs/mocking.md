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
mocks/
  browser.ts          -- MSW setupWorker (entry point)
  handlers/
    index.ts          -- Aggregates all handler modules
    evaluations.ts    -- GET/POST/PATCH /api/evaluations, /api/trend
    assets.ts         -- GET/POST /api/assets, /api/asset-groups
    slos.ts           -- GET/POST/DELETE /api/slo-definitions, groups, links
    slis.ts           -- GET/POST/DELETE /api/sli-definitions
  generate.ts         -- Deterministic data generator (~1600 lines)
```

## Data Generator

`generate.ts` creates a complete, realistic dataset using a seeded PRNG
(linear congruential generator). The same seed produces identical data on every
page reload.

### What It Generates

| Data | Details |
|------|---------|
| **Metrics** | 30 metrics across 5 tabs (summary, timing, resources, network, errors). Each has a baseline, pass/warn criteria, unit, and key_sli flag. |
| **Scenarios** | 30+ test/asset combinations (monthly-lab, toolset-lab, ad-hoc, performance). Each has a seed, optional regression window, and runs_per_day. |
| **History** | 30 days of evaluation data with configurable evaluations per day. |
| **Regressions** | Days 5-26 may have 1.2-1.8x metric scaling in specified regression windows. |

### Caching

Generated data is cached at the module level. The `gen()` function lazily initializes
the generator on first handler call, avoiding circular imports and redundant computation.

## Handler Pattern

Each handler module follows the same pattern:

```typescript
import { http, HttpResponse } from 'msw'
import { gen } from '../generate'

export const evaluationHandlers = [
  http.get('/api/evaluations', ({ request }) => {
    const url = new URL(request.url)
    const data = gen()
    // filter, paginate, return
    return HttpResponse.json({ items: [...], total: n })
  }),
]
```

## Switching Between Mock and Real API

```bash
# Mock mode (default in dev)
npm run dev

# Real API mode
VITE_USE_MOCKS=false npm run dev

# Production build (no mocks, real API)
VITE_API_BASE=http://localhost:8080 npm run build
```

MSW is only imported in development builds (`import.meta.env.DEV` guard).
Production bundles contain zero MSW code.
