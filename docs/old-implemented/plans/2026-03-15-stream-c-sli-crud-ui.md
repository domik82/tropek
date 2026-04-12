# Stream C: SLI CRUD UI Wiring

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Read first:** `docs/superpowers/plans/2026-03-15-api-ui-alignment-overview.md`

**Goal:** Create the SLI feature module in the React UI — types, API functions, hooks, MSW
handlers, and mock data. The SLI CRUD API endpoints already exist; this is purely UI work.

**Architecture:** New `features/slis/` module following the existing pattern (`api.ts`, `types.ts`,
`hooks.ts`). New MSW handler + mock data for dev mode. No API changes needed.

**Tech Stack:** React 19, TypeScript, TanStack React Query, MSW, Vite

**Spec:** `docs/superpowers/specs/2026-03-15-api-ui-alignment-design.md` §7

---

## File Structure

| Action | File | Responsibility |
|---|---|---|
| Create | `ui/src/features/slis/types.ts` | `SliDefinition` TypeScript interface |
| Create | `ui/src/features/slis/api.ts` | Fetch functions for SLI CRUD endpoints |
| Create | `ui/src/features/slis/hooks.ts` | TanStack Query hooks for SLI data |
| Modify | `ui/src/lib/queryKeys.ts` | Add `sliKeys` query key factory |
| Create | `ui/src/mocks/handlers/slis.ts` | MSW request handlers for SLI endpoints |
| Create | `ui/src/mocks/data/sli-definitions.json` | Mock SLI fixture data |
| Modify | `ui/src/mocks/handlers/index.ts` | Register new SLI handlers |
| Modify | `ui/src/mocks/generate.ts` | Add `getSliDefinitions()` data accessor |

---

### Task 1: SLI Types

**Files:**
- Create: `ui/src/features/slis/types.ts`

- [ ] **Step 1: Add `PagedResponse<T>` to shared types (if not already present)**

Check if `ui/src/lib/types.ts` exists. If not, create it. Add the generic paged response
type used across feature modules:

```typescript
// src/lib/types.ts
export interface PagedResponse<T> {
  items: T[]
  total: number
}
```

If the file already exists, just add the `PagedResponse` interface to it.

- [ ] **Step 2: Add `sliKeys` to query key factory**

In `ui/src/lib/queryKeys.ts`, add the SLI key factory following the existing pattern
(`sloKeys`, `evaluationKeys`):

```typescript
export const sliKeys = {
  all: ['sli-definitions'] as const,
  detail: (name: string) => [...sliKeys.all, name] as const,
  versions: (name: string) => [...sliKeys.detail(name), 'versions'] as const,
}
```

- [ ] **Step 3: Create the SLI type definition**

```typescript
// src/features/slis/types.ts

export interface SliDefinition {
  id: string
  name: string
  display_name: string | null
  version: number
  indicators: Record<string, string>  // metric_name → query_string
  notes: string | null
  author: string | null
  meta: Record<string, unknown>
  active: boolean
  created_at: string
}

export interface SliDefinitionCreate {
  name: string
  display_name?: string
  indicators: Record<string, string>
  notes?: string
  author?: string
  meta?: Record<string, unknown>
}
```

- [ ] **Step 4: Commit**

```bash
git add ui/src/lib/types.ts ui/src/lib/queryKeys.ts ui/src/features/slis/types.ts
git commit -m "feat(ui): add SLI definition TypeScript types and query keys"
```

---

### Task 2: SLI API Functions

**Files:**
- Create: `ui/src/features/slis/api.ts`

- [ ] **Step 1: Create fetch functions matching the real API**

```typescript
// src/features/slis/api.ts
import type { PagedResponse } from '@/lib/types'
import type { SliDefinition, SliDefinitionCreate } from './types'

const BASE = '/api'

export async function fetchSliDefinitions(): Promise<PagedResponse<SliDefinition>> {
  const res = await fetch(`${BASE}/sli-definitions`)
  if (!res.ok) throw new Error(`fetchSliDefinitions: ${res.status}`)
  return res.json()
}

export async function fetchSliDetail(name: string): Promise<SliDefinition> {
  const res = await fetch(`${BASE}/sli-definitions/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`fetchSliDetail: ${res.status}`)
  return res.json()
}

export async function createSliDefinition(
  payload: SliDefinitionCreate
): Promise<SliDefinition> {
  const res = await fetch(`${BASE}/sli-definitions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`createSliDefinition: ${res.status}`)
  return res.json()
}

export async function deleteSliDefinition(name: string): Promise<void> {
  const res = await fetch(`${BASE}/sli-definitions/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`deleteSliDefinition: ${res.status}`)
}

export async function fetchSliVersions(name: string): Promise<SliDefinition[]> {
  const res = await fetch(
    `${BASE}/sli-definitions/${encodeURIComponent(name)}/versions`
  )
  if (!res.ok) throw new Error(`fetchSliVersions: ${res.status}`)
  return res.json()
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/src/features/slis/api.ts
git commit -m "feat(ui): add SLI CRUD API functions"
```

---

### Task 3: SLI Hooks

**Files:**
- Create: `ui/src/features/slis/hooks.ts`

- [ ] **Step 1: Create TanStack Query hooks**

```typescript
// src/features/slis/hooks.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { sliKeys } from '@/lib/queryKeys'
import {
  fetchSliDefinitions,
  fetchSliDetail,
  createSliDefinition,
  deleteSliDefinition,
  fetchSliVersions,
} from './api'
import type { SliDefinitionCreate } from './types'

export function useSliDefinitions() {
  return useQuery({
    queryKey: sliKeys.all,
    queryFn: fetchSliDefinitions,
  })
}

export function useSliDetail(name: string) {
  return useQuery({
    queryKey: sliKeys.detail(name),
    queryFn: () => fetchSliDetail(name),
    enabled: !!name,
  })
}

export function useSliVersions(name: string) {
  return useQuery({
    queryKey: sliKeys.versions(name),
    queryFn: () => fetchSliVersions(name),
    enabled: !!name,
  })
}

export function useCreateSli() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: SliDefinitionCreate) => createSliDefinition(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sliKeys.all })
    },
  })
}

export function useDeleteSli() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => deleteSliDefinition(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sliKeys.all })
    },
  })
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/src/features/slis/hooks.ts
git commit -m "feat(ui): add SLI TanStack Query hooks"
```

---

### Task 4: MSW Mock Data + Handlers

**Files:**
- Create: `ui/src/mocks/data/sli-definitions.json`
- Create: `ui/src/mocks/handlers/slis.ts`
- Modify: `ui/src/mocks/handlers/index.ts`

- [ ] **Step 1: Create mock SLI data**

```json
[
  {
    "id": "a1b2c3d4-0001-4000-8000-000000000001",
    "name": "linux-compilation-sli",
    "display_name": "Linux Compilation Indicators",
    "version": 2,
    "indicators": {
      "compilation_duration_s": "avg_over_time(compilation_duration_seconds{instance=\"$vm_ip\"}[5m])",
      "compilation_errors": "compilation_errors_total{instance=\"$vm_ip\"}",
      "cpu_usage_avg": "avg_over_time(process_cpu_seconds_total{instance=\"$vm_ip\"}[$duration])"
    },
    "notes": "Added cpu_usage_avg indicator",
    "author": "j.kowalski",
    "meta": {},
    "active": true,
    "created_at": "2026-03-10T14:00:00Z"
  },
  {
    "id": "a1b2c3d4-0002-4000-8000-000000000002",
    "name": "api-performance-sli",
    "display_name": "API Performance Indicators",
    "version": 1,
    "indicators": {
      "response_time_p95": "histogram_quantile(0.95, rate(http_duration_seconds_bucket{service=\"$service_name\"}[5m]))",
      "error_rate": "rate(http_requests_total{status=~\"5..\", service=\"$service_name\"}[5m]) / rate(http_requests_total{service=\"$service_name\"}[5m])",
      "throughput": "rate(http_requests_total{service=\"$service_name\"}[5m])"
    },
    "notes": "Initial version",
    "author": "a.smith",
    "meta": {},
    "active": true,
    "created_at": "2026-03-08T10:30:00Z"
  }
]
```

- [ ] **Step 2: Create MSW handlers for SLI endpoints**

```typescript
// src/mocks/handlers/slis.ts
import { http, HttpResponse } from 'msw'

// Follow the established lazy-import pattern used by other handlers
async function gen() {
  return import('../generate')
}

export const sliHandlers = [
  http.get('/api/sli-definitions', async () => {
    const { getSliDefinitions } = await gen()
    const data = getSliDefinitions()
    return HttpResponse.json({ items: data, total: data.length })
  }),

  http.get('/api/sli-definitions/:name', async ({ params }) => {
    const { getSliDefinitions } = await gen()
    const sli = getSliDefinitions().find(s => s.name === params.name)
    if (!sli) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    return HttpResponse.json(sli)
  }),

  http.get('/api/sli-definitions/:name/versions', async ({ params }) => {
    const { getSliDefinitions } = await gen()
    const current = getSliDefinitions().find(s => s.name === params.name)
    if (!current) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    const history = [
      { ...current },
      {
        ...current,
        id: crypto.randomUUID(),
        version: current.version - 1,
        active: false,
        notes: current.version > 1 ? `Previous v${current.version - 1}` : undefined,
        created_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
      },
    ].filter(v => v.version > 0)
    return HttpResponse.json(history)
  }),

  http.post('/api/sli-definitions', async ({ request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json(
      {
        id: crypto.randomUUID(),
        version: 1,
        active: true,
        meta: {},
        created_at: new Date().toISOString(),
        ...body,
      },
      { status: 201 }
    )
  }),

  http.delete('/api/sli-definitions/:name', ({ params }) => {
    console.log('[mock] soft-delete SLI:', params.name)
    return new HttpResponse(null, { status: 204 })
  }),
]
```

**Note:** Also add a `getSliDefinitions()` function to `ui/src/mocks/generate.ts`:

```typescript
import sliData from './data/sli-definitions.json'

export function getSliDefinitions() {
  return sliData
}
```

This follows the pattern established by `getSloDefinitions()` and other data accessors
in `generate.ts`.

- [ ] **Step 3: Register handlers in index.ts**

Add import and spread `sliHandlers` in `ui/src/mocks/handlers/index.ts`:

```typescript
import { sliHandlers } from './slis'
// ... in the handlers array:
...sliHandlers,
```

- [ ] **Step 4: Verify build**

```bash
cd ui && npm run build
```

Expected: Build succeeds with no type errors.

- [ ] **Step 5: Commit**

```bash
git add ui/src/mocks/data/sli-definitions.json ui/src/mocks/handlers/slis.ts ui/src/mocks/handlers/index.ts ui/src/mocks/generate.ts
git commit -m "feat(ui): add SLI MSW mock handlers and fixture data"
```
