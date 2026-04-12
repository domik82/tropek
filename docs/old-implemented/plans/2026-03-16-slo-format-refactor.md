# SLO Format Refactor — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align all UI types, API calls, components, and mock data with the new structured SLO backend format (no more `slo_yaml` blob).

**Architecture:** Update the data layer first (types → API → hooks → mocks), then components bottom-up (display-only → editors → pages). Delete all YAML-specific files last.

**Tech Stack:** React 19, TypeScript, react-hook-form + Zod, TanStack Query, MSW mocks, Vitest, Vite

**Spec:** `docs/superpowers/specs/2026-03-15-ui-slo-format-refactor-design.md`

**Verify command (run after every task):**
```bash
npx --prefix ui tsc -b --noEmit
```

---

## Chunk 1: Data Layer (Types, API, Hooks, Mocks)

### Task 1: Update types

**Files:**
- Modify: `ui/src/features/slos/types.ts`

- [ ] **Step 1: Replace the entire file with the new types**

```typescript
// src/features/slos/types.ts

export interface SloObjective {
  sli: string
  display_name: string
  pass_criteria: string[]
  warning_criteria: string[]
  weight: number
  key_sli: boolean
  sort_order: number
}

export interface SloDefinition {
  id: string
  name: string
  version: number
  display_name: string | null
  author: string | null
  notes: string | null
  meta: Record<string, unknown>
  created_at: string
  active: boolean
  objectives: SloObjective[]
  total_score_pass_pct: number
  total_score_warning_pct: number
  comparison: Record<string, unknown>
}

export interface SloValidationResult {
  valid: boolean
  errors: { field: string; message: string }[]
  objectives?: SloObjective[]
}
```

Deleted: `SliQuery`, `SloScoreThresholds` — no longer needed.

- [ ] **Step 2: Verify — expect type errors (downstream files still use old types)**

Run: `npx --prefix ui tsc -b --noEmit 2>&1 | head -30`

Expected: Type errors in files that reference `slo_yaml`, `pass`, `warning`, `tab_group`, etc. This is correct — we fix them in subsequent tasks.

- [ ] **Step 3: Commit**

```
git add ui/src/features/slos/types.ts
git commit -m "refactor(ui): update SloObjective and SloDefinition types to structured format"
```

---

### Task 2: Update API functions

**Files:**
- Modify: `ui/src/features/slos/api.ts`

- [ ] **Step 1: Replace the entire file**

```typescript
// src/features/slos/api.ts
import type { SloDefinition, SloObjective, SloValidationResult } from './types'

const BASE = '/api'

export async function fetchSlos(): Promise<SloDefinition[]> {
  const res = await fetch(`${BASE}/slo-definitions`)
  if (!res.ok) throw new Error(`fetchSlos: ${res.status}`)
  const data: { items: SloDefinition[]; total: number } = await res.json()
  return data.items
}

export async function fetchSloDetail(name: string): Promise<SloDefinition> {
  const res = await fetch(`${BASE}/slo-definitions/${encodeURIComponent(name)}`)
  if (!res.ok) throw new Error(`fetchSloDetail: ${res.status}`)
  return res.json()
}

export async function validateSlo(payload: {
  objectives: SloObjective[]
  total_score_pass_pct: number
  total_score_warning_pct: number
  comparison: Record<string, unknown>
}): Promise<SloValidationResult> {
  const res = await fetch(`${BASE}/slo-definitions/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`validateSlo: ${res.status}`)
  return res.json()
}

export async function createSloDefinition(payload: {
  name: string
  objectives: SloObjective[]
  total_score_pass_pct: number
  total_score_warning_pct: number
  comparison: Record<string, unknown>
  display_name?: string
  notes?: string
  author?: string
}): Promise<SloDefinition> {
  const res = await fetch(`${BASE}/slo-definitions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`createSloDefinition: ${res.status}`)
  return res.json()
}

export async function deleteSlo(name: string): Promise<void> {
  const res = await fetch(`${BASE}/slo-definitions/${encodeURIComponent(name)}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`deleteSlo: ${res.status}`)
}

export async function fetchSloVersions(name: string): Promise<SloDefinition[]> {
  const res = await fetch(`${BASE}/slo-definitions/${encodeURIComponent(name)}/versions`)
  if (!res.ok) throw new Error(`fetchSloVersions: ${res.status}`)
  return res.json()
}
```

Key changes: `validateSloYaml(yaml: string)` → `validateSlo(payload)` with structured fields. `createSloDefinition` drops `slo_yaml`, takes structured fields. `SloObjective` imported for use in payload types.

- [ ] **Step 2: Verify — expect type errors in downstream files**

Run: `npx --prefix ui tsc -b --noEmit 2>&1 | head -30`

Expected: Type errors in hooks.ts (references old `validateSloYaml`) and components that call old API functions. This is correct — fixed in subsequent tasks.

- [ ] **Step 3: Commit**

```
git add ui/src/features/slos/api.ts
git commit -m "refactor(ui): update SLO API functions to use structured payloads"
```

---

### Task 3: Update hooks

**Files:**
- Modify: `ui/src/features/slos/hooks.ts`

- [ ] **Step 1: Replace the entire file**

```typescript
// src/features/slos/hooks.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { sloKeys } from '@/lib/queryKeys'
import { fetchSlos, fetchSloDetail, validateSlo, createSloDefinition, deleteSlo, fetchSloVersions } from './api'

export function useSlos() {
  return useQuery({
    queryKey: sloKeys.all,
    queryFn: fetchSlos,
  })
}

export function useSloDetail(name: string) {
  return useQuery({
    queryKey: sloKeys.detail(name),
    queryFn: () => fetchSloDetail(name),
    enabled: !!name,
  })
}

export function useSloValidation() {
  return useMutation({
    mutationFn: validateSlo,
  })
}

export function useCreateSlo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof createSloDefinition>[0]) => createSloDefinition(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: sloKeys.all })
    },
  })
}

export function useDeleteSlo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteSlo,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: sloKeys.all })
    },
  })
}

export function useSloVersions(name: string, enabled: boolean) {
  return useQuery({
    queryKey: [...sloKeys.detail(name), 'versions'],
    queryFn: () => fetchSloVersions(name),
    enabled: enabled && !!name,
  })
}
```

Key changes: `validateSloYaml` → `validateSlo`. `useUploadSlo` renamed to `useCreateSlo` (it creates structured SLOs, not uploads). Note: renaming `useUploadSlo` → `useCreateSlo` will cause a missing-export error in `SloCreateForm.tsx` (not just type mismatches) — fixed in Task 9.

- [ ] **Step 2: Verify — expect type errors in downstream components**

Run: `npx --prefix ui tsc -b --noEmit 2>&1 | head -30`

Expected: Import errors in components referencing `useUploadSlo` (now `useCreateSlo`) and `useSloValidation` signature changes. This is correct — fixed in Chunk 2 tasks.

- [ ] **Step 3: Commit**

```
git add ui/src/features/slos/hooks.ts
git commit -m "refactor(ui): update SLO hooks for structured API"
```

---

### Task 4: Update mock data

**Files:**
- Modify: `ui/src/mocks/data/slo-definitions.json`

- [ ] **Step 1: Replace the entire file with structured SLO entries**

Each entry drops `slo_yaml` and gains `objectives[]`, `total_score_pass_pct`, `total_score_warning_pct`, `comparison`. The objectives are extracted from the old YAML blobs.

The file is long — here is the full replacement content. Each of the 5 SLOs has its objectives expanded from the old YAML blob into flat `pass_criteria`/`warning_criteria` arrays with `sort_order` assigned by index.

```json
{
  "items": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567801",
      "name": "compilation-test-windows",
      "version": 2,
      "display_name": "Compilation Test — Windows",
      "author": "jane.smith",
      "notes": "Added memory_peak_mb indicator in v2",
      "meta": { "review_status": "approved", "tags": ["windows", "compilation"] },
      "created_at": "2026-03-01T09:00:00Z",
      "active": true,
      "total_score_pass_pct": 90.0,
      "total_score_warning_pct": 75.0,
      "comparison": {
        "compare_with": "several_results",
        "number_of_comparison_results": 3,
        "include_result_with_score": "pass_or_warn",
        "aggregate_function": "avg"
      },
      "objectives": [
        { "sli": "compilation_errors", "display_name": "Compilation Errors", "pass_criteria": ["=0"], "warning_criteria": [], "weight": 3, "key_sli": true, "sort_order": 0 },
        { "sli": "compilation_duration_s", "display_name": "Compilation Duration", "pass_criteria": ["<=+10%"], "warning_criteria": ["<=+20%"], "weight": 2, "key_sli": false, "sort_order": 1 },
        { "sli": "error_rate", "display_name": "Error Rate", "pass_criteria": ["<1.0"], "warning_criteria": ["<2.0"], "weight": 3, "key_sli": true, "sort_order": 2 },
        { "sli": "cpu_usage_avg", "display_name": "CPU Usage Avg", "pass_criteria": ["<80"], "warning_criteria": ["<90"], "weight": 2, "key_sli": false, "sort_order": 3 },
        { "sli": "memory_peak_mb", "display_name": "Peak Memory", "pass_criteria": ["<2048"], "warning_criteria": [], "weight": 2, "key_sli": false, "sort_order": 4 },
        { "sli": "link_errors", "display_name": "Link Errors", "pass_criteria": ["=0"], "warning_criteria": [], "weight": 3, "key_sli": true, "sort_order": 5 },
        { "sli": "test_failures", "display_name": "Test Failures", "pass_criteria": ["=0"], "warning_criteria": [], "weight": 3, "key_sli": true, "sort_order": 6 }
      ]
    },
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567802",
      "name": "compilation-test-linux",
      "version": 1,
      "display_name": "Compilation Test — Linux",
      "author": "john.doe",
      "notes": "Linux variant with swap and disk I/O tracking",
      "meta": { "review_status": "approved", "tags": ["linux", "compilation"] },
      "created_at": "2026-03-02T10:00:00Z",
      "active": true,
      "total_score_pass_pct": 90.0,
      "total_score_warning_pct": 75.0,
      "comparison": {
        "compare_with": "several_results",
        "number_of_comparison_results": 3,
        "include_result_with_score": "pass_or_warn",
        "aggregate_function": "avg"
      },
      "objectives": [
        { "sli": "compilation_errors", "display_name": "Compilation Errors", "pass_criteria": ["=0"], "warning_criteria": [], "weight": 3, "key_sli": true, "sort_order": 0 },
        { "sli": "compilation_duration_s", "display_name": "Compilation Duration", "pass_criteria": ["<=+10%"], "warning_criteria": ["<=+20%"], "weight": 2, "key_sli": false, "sort_order": 1 },
        { "sli": "swap_usage_mb", "display_name": "Swap Usage", "pass_criteria": ["<256"], "warning_criteria": [], "weight": 1, "key_sli": false, "sort_order": 2 },
        { "sli": "disk_io_write_mbps", "display_name": "Disk Write", "pass_criteria": ["<100"], "warning_criteria": [], "weight": 1, "key_sli": false, "sort_order": 3 },
        { "sli": "link_errors", "display_name": "Link Errors", "pass_criteria": ["=0"], "warning_criteria": [], "weight": 3, "key_sli": true, "sort_order": 4 }
      ]
    },
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567803",
      "name": "compilation-test-macos",
      "version": 1,
      "display_name": "Compilation Test — macOS",
      "author": "jane.smith",
      "notes": "macOS ARM64 variant",
      "meta": { "review_status": "approved", "tags": ["macos", "arm64", "compilation"] },
      "created_at": "2026-03-05T08:00:00Z",
      "active": true,
      "total_score_pass_pct": 90.0,
      "total_score_warning_pct": 75.0,
      "comparison": {
        "compare_with": "several_results",
        "number_of_comparison_results": 3,
        "include_result_with_score": "pass_or_warn",
        "aggregate_function": "avg"
      },
      "objectives": [
        { "sli": "compilation_errors", "display_name": "Compilation Errors", "pass_criteria": ["=0"], "warning_criteria": [], "weight": 3, "key_sli": true, "sort_order": 0 },
        { "sli": "compilation_duration_s", "display_name": "Compilation Duration", "pass_criteria": ["<=+15%"], "warning_criteria": ["<=+25%"], "weight": 2, "key_sli": false, "sort_order": 1 },
        { "sli": "cpu_usage_avg", "display_name": "CPU Usage Avg", "pass_criteria": ["<85"], "warning_criteria": ["<95"], "weight": 2, "key_sli": false, "sort_order": 2 },
        { "sli": "link_errors", "display_name": "Link Errors", "pass_criteria": ["=0"], "warning_criteria": [], "weight": 3, "key_sli": true, "sort_order": 3 }
      ]
    },
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567804",
      "name": "load-test-linux",
      "version": 3,
      "display_name": "Load Test — Linux",
      "author": "ops-team",
      "notes": "Performance load test for Linux nodes. v3 adds network metrics.",
      "meta": { "review_status": "approved", "tags": ["linux", "load-test", "performance"] },
      "created_at": "2026-02-15T12:00:00Z",
      "active": true,
      "total_score_pass_pct": 90.0,
      "total_score_warning_pct": 75.0,
      "comparison": {
        "compare_with": "several_results",
        "number_of_comparison_results": 5,
        "include_result_with_score": "pass_or_warn",
        "aggregate_function": "avg"
      },
      "objectives": [
        { "sli": "response_time_p95", "display_name": "Response Time P95", "pass_criteria": ["<550"], "warning_criteria": ["<700"], "weight": 2, "key_sli": true, "sort_order": 0 },
        { "sli": "response_time_p99", "display_name": "Response Time P99", "pass_criteria": ["<=+10%"], "warning_criteria": ["<900"], "weight": 2, "key_sli": true, "sort_order": 1 },
        { "sli": "throughput_rps", "display_name": "Throughput", "pass_criteria": [">1200"], "warning_criteria": [">1000"], "weight": 2, "key_sli": false, "sort_order": 2 },
        { "sli": "error_rate", "display_name": "Error Rate", "pass_criteria": ["<1.0"], "warning_criteria": ["<2.0"], "weight": 3, "key_sli": true, "sort_order": 3 },
        { "sli": "packet_loss_pct", "display_name": "Packet Loss", "pass_criteria": ["<0.1"], "warning_criteria": ["<0.5"], "weight": 2, "key_sli": true, "sort_order": 4 },
        { "sli": "connection_errors", "display_name": "Connection Errors", "pass_criteria": ["=0"], "warning_criteria": [], "weight": 2, "key_sli": true, "sort_order": 5 }
      ]
    },
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567805",
      "name": "load-test-windows",
      "version": 2,
      "display_name": "Load Test — Windows",
      "author": "ops-team",
      "notes": "Performance load test for Windows nodes",
      "meta": { "review_status": "approved", "tags": ["windows", "load-test", "performance"] },
      "created_at": "2026-02-18T12:00:00Z",
      "active": true,
      "total_score_pass_pct": 90.0,
      "total_score_warning_pct": 75.0,
      "comparison": {
        "compare_with": "several_results",
        "number_of_comparison_results": 5,
        "include_result_with_score": "pass_or_warn",
        "aggregate_function": "avg"
      },
      "objectives": [
        { "sli": "response_time_p95", "display_name": "Response Time P95", "pass_criteria": ["<600"], "warning_criteria": ["<750"], "weight": 2, "key_sli": true, "sort_order": 0 },
        { "sli": "response_time_p99", "display_name": "Response Time P99", "pass_criteria": ["<=+10%"], "warning_criteria": ["<950"], "weight": 2, "key_sli": true, "sort_order": 1 },
        { "sli": "throughput_rps", "display_name": "Throughput", "pass_criteria": [">1100"], "warning_criteria": [">900"], "weight": 2, "key_sli": false, "sort_order": 2 },
        { "sli": "error_rate", "display_name": "Error Rate", "pass_criteria": ["<1.5"], "warning_criteria": ["<3.0"], "weight": 3, "key_sli": true, "sort_order": 3 },
        { "sli": "crash_count", "display_name": "Crashes", "pass_criteria": ["=0"], "warning_criteria": [], "weight": 3, "key_sli": true, "sort_order": 4 }
      ]
    }
  ]
}
```

- [ ] **Step 2: Verify — JSON is valid**

Run: `npx --prefix ui tsc -b --noEmit 2>&1 | head -10`

Expected: Same type errors as before (mock JSON is consumed at runtime, not type-checked directly). No new errors introduced.

- [ ] **Step 3: Commit**

```
git add ui/src/mocks/data/slo-definitions.json
git commit -m "refactor(ui): convert mock SLO data from slo_yaml to structured format"
```

---

### Task 5: Update mock handlers

**Files:**
- Modify: `ui/src/mocks/handlers/slos.ts`

- [ ] **Step 1: Replace the entire file**

```typescript
// src/mocks/handlers/slos.ts
import { http, HttpResponse } from 'msw'

async function gen() {
  return import('../generate')
}

export const sloHandlers = [
  http.post('/api/slo-definitions/validate', async ({ request }) => {
    await request.json()
    return HttpResponse.json({
      valid: true,
      errors: [],
      objectives: [
        { sli: 'response_time_p95', display_name: 'Response Time P95', pass_criteria: ['<500'], warning_criteria: ['<800'], weight: 1, key_sli: false, sort_order: 0 },
        { sli: 'error_rate', display_name: 'Error Rate', pass_criteria: ['<=0.5%'], warning_criteria: ['<=2%'], weight: 1, key_sli: false, sort_order: 1 },
      ],
    })
  }),

  http.post('/api/slo-definitions/test', async () => {
    return HttpResponse.json({
      result: 'pass',
      score: 91.5,
      indicator_results: [],
      baseline_mode: 'none',
      metrics_fetched: {},
      fetch_errors: {},
      compared_values: null,
    })
  }),

  http.get('/api/slo-definitions', async () => {
    const { getSloDefinitions } = await gen()
    const items = getSloDefinitions()
    return HttpResponse.json({ items, total: (items as unknown[]).length })
  }),

  http.get('/api/slo-definitions/:name/versions', async ({ params }) => {
    const { getSloDefinitions } = await gen()
    const all = getSloDefinitions() as { name: string; version: number; created_at: string; author?: string | null; notes?: string | null; active: boolean }[]
    const current = all.find(s => s.name === params.name)
    if (!current) return HttpResponse.json({ error: 'Not found' }, { status: 404 })
    const history = [
      { ...current },
      {
        ...current,
        version: current.version - 1,
        active: false,
        notes: current.version > 1 ? `Previous v${current.version - 1}` : null,
        created_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
      },
    ].filter(v => v.version > 0)
    return HttpResponse.json(history)
  }),

  http.get('/api/slo-definitions/:name', async ({ params }) => {
    const { getSloDefinitions } = await gen()
    const all = getSloDefinitions()
    const slo = (all as { name: string }[]).find(s => s.name === params.name)
    if (!slo) return HttpResponse.json({ error: 'Not found' }, { status: 404 })
    return HttpResponse.json(slo)
  }),

  http.delete('/api/slo-definitions/:name', async ({ params }) => {
    console.log('[mock] soft-delete SLO:', params.name)
    return new HttpResponse(null, { status: 204 })
  }),

  http.post('/api/slo-definitions', async ({ request }) => {
    const body = await request.json() as {
      name: string
      objectives: unknown[]
      total_score_pass_pct: number
      total_score_warning_pct: number
      comparison: Record<string, unknown>
      display_name?: string
      notes?: string
      author?: string
    }
    return HttpResponse.json({
      id: crypto.randomUUID(),
      name: body.name,
      version: 1,
      display_name: body.display_name ?? null,
      author: body.author ?? null,
      notes: body.notes ?? null,
      active: true,
      meta: {},
      created_at: new Date().toISOString(),
      objectives: body.objectives,
      total_score_pass_pct: body.total_score_pass_pct,
      total_score_warning_pct: body.total_score_warning_pct,
      comparison: body.comparison,
    }, { status: 201 })
  }),
]
```

Key changes: validate response uses flat `pass_criteria`/`warning_criteria`. Create handler reads structured fields instead of `slo_yaml`. Versions handler type annotation drops `slo_yaml`.

- [ ] **Step 2: Verify**

Run: `npx --prefix ui tsc -b --noEmit 2>&1 | head -10`

Expected: Same downstream type errors as before (component files not yet updated). No new errors from this file.

- [ ] **Step 3: Commit**

```
git add ui/src/mocks/handlers/slos.ts
git commit -m "refactor(ui): update mock SLO handlers for structured format"
```

---

## Chunk 2: Components

### Task 6: Rewrite SloObjectiveTable

**Files:**
- Modify: `ui/src/features/slos/components/SloObjectiveTable.tsx`

- [ ] **Step 1: Replace the entire file**

The old version parsed `slo.slo_yaml` via `parseSloYaml` to extract objectives. The new version reads `slo.objectives`, `slo.total_score_pass_pct`, `slo.total_score_warning_pct` directly.

```typescript
// src/features/slos/components/SloObjectiveTable.tsx
import type { SloDefinition } from '../types'

interface Props {
  slo: SloDefinition
}

export function SloObjectiveTable({ slo }: Props) {
  if (slo.objectives.length === 0) {
    return <p className="text-xs text-slate-500 italic">No objectives defined.</p>
  }

  return (
    <div>
      <div className="overflow-x-auto rounded-lg border border-slate-700">
        <table className="w-full text-sm text-left">
          <thead className="text-xs uppercase text-slate-400 bg-slate-800/60 border-b border-slate-700">
            <tr>
              <th className="px-2 py-2 text-center w-6 text-cyan-500/70" title="Key SLI">◆</th>
              <th className="px-3 py-2">Indicator</th>
              <th className="px-3 py-2 text-center">Pass</th>
              <th className="px-3 py-2 text-center">Warning</th>
              <th className="px-3 py-2 text-center w-16">Weight</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {slo.objectives.map(obj => (
              <tr key={obj.sli} className="hover:bg-slate-800/40 transition-colors">
                <td className="px-2 py-2 text-center">
                  {obj.key_sli
                    ? <span className="text-cyan-400 text-xs" title="Key SLI">◆</span>
                    : <span className="text-slate-700">—</span>
                  }
                </td>
                <td className="px-3 py-2">
                  <div className="font-mono text-xs text-[#7dc540]">{obj.sli}</div>
                  {obj.display_name && obj.display_name !== obj.sli && (
                    <div className="text-xs text-slate-400">{obj.display_name}</div>
                  )}
                </td>
                <td className="px-3 py-2 text-center text-xs text-[#7dc540]">
                  {obj.pass_criteria.join(', ') || '—'}
                </td>
                <td className="px-3 py-2 text-center text-xs text-[#e6be00]">
                  {obj.warning_criteria.join(', ') || '—'}
                </td>
                <td className="px-3 py-2 text-center text-slate-400">{obj.weight}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex flex-wrap gap-6 text-sm text-slate-400">
        <span>Total pass: <strong className="text-[#7dc540]">{slo.total_score_pass_pct}%</strong></span>
        <span>Total warning: <strong className="text-[#e6be00]">{slo.total_score_warning_pct}%</strong></span>
      </div>
    </div>
  )
}
```

Removed: `parseSloYaml` import, `useMemo` for parsing, `sliQueryMap`, `scoreThresholds`, SLI Query column, Group column.

- [ ] **Step 2: Verify**

Run: `npx --prefix ui tsc -b --noEmit`

Expected: No errors (this file no longer references deleted types or `slo_yaml`).

- [ ] **Step 3: Commit**

```
git add ui/src/features/slos/components/SloObjectiveTable.tsx
git commit -m "refactor(ui): SloObjectiveTable reads structured objectives directly"
```

---

### Task 7: Rewrite SloObjectiveEditor

**Files:**
- Modify: `ui/src/features/slos/components/SloObjectiveEditor.tsx`

- [ ] **Step 1: Replace the entire file**

The old version parsed `slo.slo_yaml` to get default values and rebuilt YAML on save. The new version reads `slo.objectives` directly and submits structured data via `useCreateSlo`.

```typescript
// src/features/slos/components/SloObjectiveEditor.tsx
import { useState } from 'react'
import { useFieldArray, useForm, Controller } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { useCreateSlo, useSloValidation } from '../hooks'
import type { SloDefinition } from '../types'

const objectiveSchema = z.object({
  sli: z.string().min(1),
  display_name: z.string(),
  pass_criteria: z.string(),
  warning_criteria: z.string(),
  weight: z.coerce.number().min(0),
  key_sli: z.boolean(),
})

const formSchema = z.object({
  total_score_pass_pct: z.coerce.number().min(0).max(100),
  total_score_warning_pct: z.coerce.number().min(0).max(100),
  objectives: z.array(objectiveSchema),
})
type FormValues = z.infer<typeof formSchema>

interface Props {
  slo: SloDefinition
  onCancel: () => void
  onSaved: () => void
}

function IndicatorCombobox({
  value,
  onChange,
  indicators,
}: {
  value: string
  onChange: (v: string) => void
  indicators: string[]
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const filtered = indicators.filter(i => i.toLowerCase().includes(search.toLowerCase()))

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="w-full text-left px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-xs font-mono text-[#7dc540] hover:border-slate-500 truncate"
      >
        {value || <span className="text-slate-500">Select indicator…</span>}
      </button>
      {open && (
        <div className="absolute z-10 mt-1 w-full bg-slate-800 border border-slate-600 rounded shadow-lg max-h-48 overflow-y-auto">
          <input
            className="w-full px-2 py-1.5 bg-slate-900 border-b border-slate-700 text-xs text-slate-200 placeholder-slate-500 focus:outline-none"
            placeholder="Filter…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            autoFocus
          />
          {filtered.map(ind => (
            <button
              key={ind}
              type="button"
              className="w-full text-left px-2 py-1.5 text-xs font-mono text-[#7dc540] hover:bg-slate-700"
              onClick={() => { onChange(ind); setOpen(false); setSearch('') }}
            >
              {ind}
            </button>
          ))}
          {filtered.length === 0 && (
            <p className="px-2 py-1.5 text-xs text-slate-500">No indicators found</p>
          )}
        </div>
      )}
    </div>
  )
}

export function SloObjectiveEditor({ slo, onCancel, onSaved }: Props) {
  const create = useCreateSlo()
  const validate = useSloValidation()
  const availableIndicators = slo.objectives.map(o => o.sli)

  const defaultObjectives = slo.objectives.map(obj => ({
    sli: obj.sli,
    display_name: obj.display_name,
    pass_criteria: obj.pass_criteria.join(', '),
    warning_criteria: obj.warning_criteria.join(', '),
    weight: obj.weight,
    key_sli: obj.key_sli,
  }))

  const { register, control, handleSubmit } = useForm<FormValues, unknown, FormValues>({
    resolver: zodResolver(formSchema) as import('react-hook-form').Resolver<FormValues>,
    defaultValues: {
      total_score_pass_pct: slo.total_score_pass_pct,
      total_score_warning_pct: slo.total_score_warning_pct,
      objectives: defaultObjectives,
    },
  })

  const { fields, append, remove } = useFieldArray({ control, name: 'objectives' })

  function buildPayload(values: FormValues) {
    return {
      objectives: values.objectives.map((obj, i) => ({
        sli: obj.sli,
        display_name: obj.display_name || obj.sli,
        pass_criteria: obj.pass_criteria ? obj.pass_criteria.split(',').map(s => s.trim()).filter(Boolean) : [],
        warning_criteria: obj.warning_criteria ? obj.warning_criteria.split(',').map(s => s.trim()).filter(Boolean) : [],
        weight: obj.weight,
        key_sli: obj.key_sli,
        sort_order: i,
      })),
      total_score_pass_pct: values.total_score_pass_pct,
      total_score_warning_pct: values.total_score_warning_pct,
      comparison: slo.comparison ?? {},
    }
  }

  function onSubmit(values: FormValues) {
    const payload = buildPayload(values)
    validate.mutate(payload, {
      onSuccess: (result) => {
        if (!result.valid) return
        create.mutate(
          {
            name: slo.name,
            display_name: slo.display_name ?? undefined,
            author: slo.author ?? undefined,
            notes: slo.notes ?? undefined,
            ...payload,
          },
          { onSuccess: () => onSaved() },
        )
      },
    })
  }

  const inp = 'w-full px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500'

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
      {/* Score thresholds */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-slate-500 mb-1">Total Pass %</label>
          <input {...register('total_score_pass_pct')} type="number" min={0} max={100} className={inp} />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Total Warning %</label>
          <input {...register('total_score_warning_pct')} type="number" min={0} max={100} className={inp} />
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-700">
        <table className="w-full text-sm">
          <thead className="text-xs uppercase text-slate-400 bg-slate-800/60 border-b border-slate-700">
            <tr>
              <th className="text-left px-2 py-2 min-w-[160px]">Indicator</th>
              <th className="text-left px-2 py-2 min-w-[140px]">Display Name</th>
              <th className="text-left px-2 py-2 min-w-[120px]">Pass Criteria</th>
              <th className="text-left px-2 py-2 min-w-[120px]">Warn Criteria</th>
              <th className="text-center px-2 py-2 w-16">Weight</th>
              <th className="text-center px-2 py-2 w-10">Key</th>
              <th className="w-8"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {fields.map((field, i) => (
              <tr key={field.id} className="hover:bg-slate-800/40">
                <td className="px-2 py-1.5">
                  <Controller
                    control={control}
                    name={`objectives.${i}.sli`}
                    render={({ field: f }) => (
                      <IndicatorCombobox
                        value={f.value}
                        onChange={f.onChange}
                        indicators={availableIndicators}
                      />
                    )}
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    {...register(`objectives.${i}.display_name`)}
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                    placeholder="Human name"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    {...register(`objectives.${i}.pass_criteria`)}
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                    placeholder="e.g. <=+10%"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    {...register(`objectives.${i}.warning_criteria`)}
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                    placeholder="optional"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    {...register(`objectives.${i}.weight`)}
                    type="number"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-xs text-slate-200 text-center focus:outline-none focus:border-indigo-500"
                  />
                </td>
                <td className="px-2 py-1.5 text-center">
                  <input
                    type="checkbox"
                    {...register(`objectives.${i}.key_sli`)}
                    className="accent-cyan-400"
                  />
                </td>
                <td className="px-2 py-1.5 text-center">
                  <button type="button" onClick={() => remove(i)} className="text-red-400 hover:text-red-300 text-xs">✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button
        type="button"
        onClick={() => append({
          sli: availableIndicators[0] ?? '',
          display_name: '',
          pass_criteria: '',
          warning_criteria: '',
          weight: 1,
          key_sli: false,
        })}
        className="px-3 py-1.5 text-xs rounded border border-slate-600 text-slate-300 hover:border-slate-400 hover:text-slate-100 transition-colors"
      >
        + Add Objective
      </button>

      {validate.data && !validate.data.valid && (
        <div className="text-xs text-red-400 space-y-0.5">
          {validate.data.errors.map((e, i) => (
            <p key={i}>{e.field}: {e.message}</p>
          ))}
        </div>
      )}
      {create.isError && (
        <p className="text-xs text-red-400">Failed to save — please try again.</p>
      )}

      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 text-xs rounded border border-slate-600 text-slate-400 hover:text-slate-200 transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={validate.isPending || create.isPending}
          className="px-3 py-1.5 text-xs font-medium rounded bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {validate.isPending ? 'Validating…' : create.isPending ? 'Saving…' : 'Save Changes'}
        </button>
      </div>
    </form>
  )
}
```

Removed: `parseSloYaml` import, `useMemo` for parsing, `buildYamlFromObjectives` function, `tab_group` column. Added: `useSloValidation` (validates before save per spec), editable `total_score_pass_pct`/`total_score_warning_pct` inputs. On submit: validates → splits comma-separated criteria strings into arrays → assigns `sort_order` from index → creates new version.

- [ ] **Step 2: Verify**

Run: `npx --prefix ui tsc -b --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```
git add ui/src/features/slos/components/SloObjectiveEditor.tsx
git commit -m "refactor(ui): SloObjectiveEditor submits structured data instead of YAML"
```

---

### Task 8: Rewrite SloHistoryPanel

**Files:**
- Modify: `ui/src/features/slos/components/SloHistoryPanel.tsx`

- [ ] **Step 1: Replace the entire file**

The old version showed expandable raw YAML per version. The new version shows an expandable `SloObjectiveTable` per version.

```typescript
// src/features/slos/components/SloHistoryPanel.tsx
import { useState } from 'react'
import { useSloVersions } from '../hooks'
import { SloObjectiveTable } from './SloObjectiveTable'

interface Props {
  name: string
}

export function SloHistoryPanel({ name }: Props) {
  const { data: versions, isLoading, isError } = useSloVersions(name, true)
  const [expanded, setExpanded] = useState<number | null>(null)

  if (isLoading) return <p className="text-slate-500 text-sm py-2">Loading history…</p>
  if (isError || !versions) return <p className="text-red-400 text-sm py-2">Failed to load history.</p>
  if (versions.length === 0) return <p className="text-slate-600 text-sm py-2">No version history found.</p>

  return (
    <div className="space-y-2">
      {versions.map(v => (
        <div key={v.version} className="border border-slate-700 rounded-lg overflow-hidden">
          <div className="flex items-center gap-3 px-4 py-3 bg-slate-800/40">
            <span className="text-slate-300 font-mono text-sm font-semibold">v{v.version}</span>
            {v.active
              ? <span className="text-xs bg-pass/20 text-pass border border-pass/30 px-1.5 py-0.5 rounded-full">active</span>
              : <span className="text-xs bg-slate-700/40 text-slate-500 border border-slate-600/40 px-1.5 py-0.5 rounded-full">inactive</span>
            }
            {v.author && <span className="text-xs text-slate-500">{v.author}</span>}
            {v.notes && <span className="text-xs text-slate-600 italic truncate max-w-xs">{v.notes}</span>}
            <span className="ml-auto text-xs text-slate-600">{v.created_at.slice(0, 16).replace('T', ' ')}</span>
            <button
              onClick={() => setExpanded(prev => prev === v.version ? null : v.version)}
              className="text-xs text-slate-400 hover:text-slate-200 transition-colors shrink-0"
            >
              {expanded === v.version ? 'Hide ▲' : 'Details ▼'}
            </button>
          </div>
          {expanded === v.version && (
            <div className="px-4 py-3 border-t border-slate-700">
              <SloObjectiveTable slo={v} />
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
```

Removed: raw YAML viewer, `v.slo_yaml` checks. Added: `SloObjectiveTable` import, renders per-version objectives in structured table.

- [ ] **Step 2: Verify**

Run: `npx --prefix ui tsc -b --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```
git add ui/src/features/slos/components/SloHistoryPanel.tsx
git commit -m "refactor(ui): SloHistoryPanel shows structured objectives instead of YAML"
```

---

### Task 9: Rewrite SloCreateForm

**Files:**
- Modify: `ui/src/features/slos/components/SloCreateForm.tsx`

- [ ] **Step 1: Replace the entire file**

The old version had a YAML paste tab, labels, SLI queries section, and built a YAML string before submission. The new version is a pure structured form — no YAML tab, no labels, no SLI queries (those belong to SLI definitions, not SLOs). It submits structured fields directly via `useCreateSlo`.

```typescript
// src/features/slos/components/SloCreateForm.tsx
import { useForm, useFieldArray } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { useCreateSlo } from '../hooks'

// ── Schema ─────────────────────────────────────────────────────────────────────

const objSchema = z.object({
  sli: z.string().min(1),
  display_name: z.string(),
  pass_criteria: z.string(),
  warning_criteria: z.string(),
  weight: z.coerce.number().min(0),
  key_sli: z.boolean(),
})

const formSchema = z.object({
  name: z.string().min(1, 'Required').regex(/^[a-z0-9-]+$/, 'Lowercase, numbers and hyphens only'),
  display_name: z.string(),
  author: z.string(),
  notes: z.string(),
  compare_with: z.string(),
  number_of_comparison_results: z.coerce.number().min(1),
  include_result_with_score: z.string(),
  aggregate_function: z.string(),
  total_score_pass_pct: z.coerce.number().min(0).max(100),
  total_score_warning_pct: z.coerce.number().min(0).max(100),
  objectives: z.array(objSchema),
})

type FormValues = z.infer<typeof formSchema>

const DEFAULTS: FormValues = {
  name: '', display_name: '', author: '', notes: '',
  compare_with: 'several_results',
  number_of_comparison_results: 3,
  include_result_with_score: 'pass_or_warn',
  aggregate_function: 'avg',
  total_score_pass_pct: 90,
  total_score_warning_pct: 75,
  objectives: [],
}

// ── Shared styles ──────────────────────────────────────────────────────────────

const inp = 'w-full px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500'
const sel = inp + ' cursor-pointer'

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">{children}</h3>
}

// ── Main component ─────────────────────────────────────────────────────────────

interface Props {
  onCancel: () => void
  onSaved: () => void
}

export function SloCreateForm({ onCancel, onSaved }: Props) {
  const create = useCreateSlo()

  const { register, control, handleSubmit, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(formSchema) as import('react-hook-form').Resolver<FormValues>,
    defaultValues: DEFAULTS,
  })

  const objectives = useFieldArray({ control, name: 'objectives' })

  function onSubmit(values: FormValues) {
    create.mutate(
      {
        name: values.name,
        display_name: values.display_name || undefined,
        notes: values.notes || undefined,
        author: values.author || undefined,
        objectives: values.objectives.map((obj, i) => ({
          sli: obj.sli,
          display_name: obj.display_name || obj.sli,
          pass_criteria: obj.pass_criteria ? obj.pass_criteria.split(',').map(s => s.trim()).filter(Boolean) : [],
          warning_criteria: obj.warning_criteria ? obj.warning_criteria.split(',').map(s => s.trim()).filter(Boolean) : [],
          weight: obj.weight,
          key_sli: obj.key_sli,
          sort_order: i,
        })),
        total_score_pass_pct: values.total_score_pass_pct,
        total_score_warning_pct: values.total_score_warning_pct,
        comparison: {
          compare_with: values.compare_with,
          number_of_comparison_results: values.number_of_comparison_results,
          include_result_with_score: values.include_result_with_score,
          aggregate_function: values.aggregate_function,
        },
      },
      { onSuccess: () => onSaved() },
    )
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">

      {/* Basic info */}
      <div className="space-y-3">
        <SectionLabel>Basic Info</SectionLabel>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-slate-500 mb-1">Name <span className="text-red-400">*</span></label>
            <input {...register('name')} className={inp} placeholder="my-slo-name" />
            {errors.name && <p className="text-xs text-red-400 mt-0.5">{errors.name.message}</p>}
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Display Name</label>
            <input {...register('display_name')} className={inp} placeholder="My SLO" />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Author</label>
            <input {...register('author')} className={inp} placeholder="jane.doe" />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Notes</label>
            <input {...register('notes')} className={inp} placeholder="What changed in this version…" />
          </div>
        </div>
      </div>

      {/* Comparison */}
      <div className="space-y-3">
        <SectionLabel>Comparison</SectionLabel>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-slate-500 mb-1">Compare With</label>
            <select {...register('compare_with')} className={sel}>
              <option value="single_result">single_result</option>
              <option value="several_results">several_results</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1"># Comparison Results</label>
            <input {...register('number_of_comparison_results')} type="number" min={1} className={inp} />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Include Results With Score</label>
            <select {...register('include_result_with_score')} className={sel}>
              <option value="pass">pass</option>
              <option value="pass_or_warn">pass_or_warn</option>
              <option value="all">all</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Aggregate Function</label>
            <select {...register('aggregate_function')} className={sel}>
              <option value="avg">avg</option>
              <option value="p50">p50</option>
              <option value="p90">p90</option>
              <option value="p95">p95</option>
              <option value="p99">p99</option>
            </select>
          </div>
        </div>
      </div>

      {/* Score thresholds */}
      <div className="space-y-3">
        <SectionLabel>Score Thresholds</SectionLabel>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-slate-500 mb-1">Total Pass %</label>
            <input {...register('total_score_pass_pct')} type="number" min={0} max={100} className={inp} />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Total Warning %</label>
            <input {...register('total_score_warning_pct')} type="number" min={0} max={100} className={inp} />
          </div>
        </div>
      </div>

      {/* Objectives */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <SectionLabel>Objectives</SectionLabel>
          <button
            type="button"
            onClick={() => objectives.append({
              sli: '', display_name: '', pass_criteria: '', warning_criteria: '',
              weight: 1, key_sli: false,
            })}
            className="text-xs text-slate-400 hover:text-slate-200 transition-colors"
          >
            + Add objective
          </button>
        </div>
        {objectives.fields.length === 0 && (
          <p className="text-xs text-slate-600 italic">No objectives yet.</p>
        )}
        {objectives.fields.length > 0 && (
          <div className="rounded-lg border border-slate-700 overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-slate-800/60 border-b border-slate-700 text-slate-400 uppercase">
                <tr>
                  <th className="text-left px-2 py-2 min-w-[140px]">Indicator</th>
                  <th className="text-left px-2 py-2 min-w-[120px]">Display Name</th>
                  <th className="text-left px-2 py-2 min-w-[110px]">Pass</th>
                  <th className="text-left px-2 py-2 min-w-[110px]">Warning</th>
                  <th className="text-center px-2 py-2 w-14">Weight</th>
                  <th className="text-center px-2 py-2 w-10">Key</th>
                  <th className="w-8"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {objectives.fields.map((f, i) => (
                  <tr key={f.id} className="hover:bg-slate-800/30">
                    <td className="px-2 py-1.5">
                      <input {...register(`objectives.${i}.sli`)} className={inp + ' font-mono text-[#7dc540]'} placeholder="indicator" />
                    </td>
                    <td className="px-2 py-1.5">
                      <input {...register(`objectives.${i}.display_name`)} className={inp} placeholder="Human name" />
                    </td>
                    <td className="px-2 py-1.5">
                      <input {...register(`objectives.${i}.pass_criteria`)} className={inp} placeholder="<=+10%" />
                    </td>
                    <td className="px-2 py-1.5">
                      <input {...register(`objectives.${i}.warning_criteria`)} className={inp} placeholder="optional" />
                    </td>
                    <td className="px-2 py-1.5">
                      <input {...register(`objectives.${i}.weight`)} type="number" className={inp + ' text-center'} />
                    </td>
                    <td className="px-2 py-1.5 text-center">
                      <input type="checkbox" {...register(`objectives.${i}.key_sli`)} className="accent-cyan-400" />
                    </td>
                    <td className="px-2 py-1.5 text-center">
                      <button type="button" onClick={() => objectives.remove(i)} className="text-red-400 hover:text-red-300">✕</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {create.isError && (
        <p className="text-xs text-red-400">Failed to save — please try again.</p>
      )}

      <div className="flex justify-end gap-2 pt-1">
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 text-xs rounded border border-slate-600 text-slate-400 hover:text-slate-200 transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={create.isPending}
          className="px-3 py-1.5 text-xs font-medium rounded bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {create.isPending ? 'Saving…' : 'Create SLO'}
        </button>
      </div>
    </form>
  )
}
```

Removed: YAML tab, `parseSloYaml` import, `buildYaml` function, labels section, SLI queries section, `rawYaml` state, `parseAndFill` function, `labelSchema`, `querySchema`. Score thresholds now numeric inputs (was string like `"90%"`). Note: comparison fields are kept in SloCreateForm for better UX (the spec says comparison UI is "out of scope" but the existing code already had them and they provide meaningful defaults).

- [ ] **Step 2: Verify**

Run: `npx --prefix ui tsc -b --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```
git add ui/src/features/slos/components/SloCreateForm.tsx
git commit -m "refactor(ui): SloCreateForm is pure structured form, no YAML tab"
```

---

### Task 10: Update SloRegistryPage

**Files:**
- Modify: `ui/src/pages/SloRegistryPage.tsx`

- [ ] **Step 1: Replace the entire file**

Removes "Upload YAML" and "Raw Edit" tabs. Removes imports for deleted components. Default mode is now `'view'` with only "Edit Rows" and "History" tabs.

```typescript
// src/pages/SloRegistryPage.tsx
import { useState } from 'react'
import { useSlos, useSloDetail, useDeleteSlo } from '@/features/slos/hooks'
import { SloObjectiveTable } from '@/features/slos/components/SloObjectiveTable'
import { SloObjectiveEditor } from '@/features/slos/components/SloObjectiveEditor'
import { SloHistoryPanel } from '@/features/slos/components/SloHistoryPanel'
import { SloCreateForm } from '@/features/slos/components/SloCreateForm'

type Mode = 'view' | 'edit-rows' | 'history'

function TabBtn({ active, onClick, children }: {
  active: boolean; onClick: () => void; children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 text-xs font-medium rounded transition-colors border ${
        active
          ? 'bg-indigo-600/20 border-indigo-500/50 text-indigo-300'
          : 'bg-transparent border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200'
      }`}
    >
      {children}
    </button>
  )
}

function SloDetail({ name }: { name: string }) {
  const { data: slo, isLoading, isError } = useSloDetail(name)
  const [mode, setMode] = useState<Mode>('view')

  if (isLoading) return <p className="text-slate-500 text-sm py-3">Loading…</p>
  if (isError || !slo) return <p className="text-red-400 text-sm py-3">Failed to load.</p>

  return (
    <div className="border-t border-slate-800 mt-3 pt-4 space-y-4">
      <div className="flex gap-2 flex-wrap">
        <TabBtn active={mode === 'view'} onClick={() => setMode('view')}>View</TabBtn>
        <TabBtn active={mode === 'edit-rows'} onClick={() => setMode('edit-rows')}>Edit Rows</TabBtn>
        <TabBtn active={mode === 'history'} onClick={() => setMode('history')}>History</TabBtn>
        <button
          disabled
          title="Coming soon"
          className="px-3 py-1.5 text-xs font-medium rounded border border-slate-800 text-slate-600 cursor-not-allowed"
        >
          Test SLO
        </button>
      </div>

      {mode === 'view' && <SloObjectiveTable slo={slo} />}
      {mode === 'edit-rows' && (
        <SloObjectiveEditor slo={slo} onCancel={() => setMode('view')} onSaved={() => setMode('view')} />
      )}
      {mode === 'history' && <SloHistoryPanel name={name} />}
    </div>
  )
}

// ── Delete confirm inline ──────────────────────────────────────────────────────

function DeleteConfirm({ name, onDone }: { name: string; onDone: () => void }) {
  const del = useDeleteSlo()

  return (
    <div className="flex items-center gap-2 bg-red-900/20 border border-red-700/40 rounded-lg px-3 py-2">
      <span className="text-xs text-red-300">Deactivate <strong>{name}</strong>? All versions will be marked inactive.</span>
      <button
        onClick={() => del.mutate(name, { onSuccess: onDone })}
        disabled={del.isPending}
        className="px-2.5 py-1 text-xs font-medium rounded bg-red-700 text-white hover:bg-red-600 disabled:opacity-40 transition-colors shrink-0"
      >
        {del.isPending ? 'Deactivating…' : 'Confirm'}
      </button>
      <button
        onClick={onDone}
        className="px-2.5 py-1 text-xs rounded border border-slate-600 text-slate-400 hover:text-slate-200 transition-colors shrink-0"
      >
        Cancel
      </button>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function SloRegistryPage() {
  const { data: slos, isLoading, isError } = useSlos()
  const [expandedSlo, setExpandedSlo] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)

  if (isLoading) return <p className="p-6 text-slate-400">Loading…</p>
  if (isError || !slos) return <p className="p-6 text-red-400">Failed to load.</p>

  return (
    <div className="p-6 space-y-4">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-100">SLO Registry</h1>
        <button
          onClick={() => setShowCreate(v => !v)}
          className={`px-3 py-1.5 text-sm font-medium rounded border transition-colors ${
            showCreate
              ? 'bg-indigo-600/20 border-indigo-500/50 text-indigo-300'
              : 'bg-indigo-600 border-indigo-600 text-white hover:bg-indigo-500'
          }`}
        >
          {showCreate ? '✕ Cancel' : '+ Create SLO'}
        </button>
      </div>

      {/* Inline create panel */}
      {showCreate && (
        <div className="bg-[#111827] border border-indigo-700/40 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-slate-200 mb-4">Create New SLO</h2>
          <SloCreateForm
            onCancel={() => setShowCreate(false)}
            onSaved={() => setShowCreate(false)}
          />
        </div>
      )}

      {/* SLO list */}
      <div className="space-y-2">
        {slos.map(slo => {
          const tags = (slo.meta?.tags as string[] | undefined) ?? []
          const isExpanded = expandedSlo === slo.name
          const isConfirmingDelete = confirmDelete === slo.name

          return (
            <div
              key={slo.name}
              className={`bg-[#111827] border rounded-xl overflow-hidden transition-colors ${
                slo.active ? 'border-slate-700' : 'border-slate-800 opacity-60'
              }`}
            >
              {/* Header row */}
              <div className="px-5 py-4 flex items-center gap-4">
                <button
                  onClick={() => setExpandedSlo(prev => prev === slo.name ? null : slo.name)}
                  className="text-slate-500 text-xs w-3 shrink-0 hover:text-slate-300 transition-colors"
                >
                  {isExpanded ? '▼' : '▶'}
                </button>

                <div
                  className="flex items-center gap-2 min-w-0 flex-1 cursor-pointer"
                  onClick={() => setExpandedSlo(prev => prev === slo.name ? null : slo.name)}
                >
                  <span className="font-semibold text-slate-100 truncate">
                    {slo.display_name ?? slo.name}
                  </span>
                  <span className="text-xs text-slate-500 shrink-0">v{slo.version}</span>
                  {slo.active
                    ? <span className="text-xs bg-pass/20 text-pass border border-pass/30 px-1.5 py-0.5 rounded-full shrink-0">active</span>
                    : <span className="text-xs bg-slate-700/40 text-slate-500 border border-slate-600/40 px-1.5 py-0.5 rounded-full shrink-0">inactive</span>
                  }
                </div>

                {tags.length > 0 && (
                  <div className="flex items-center gap-1 flex-wrap">
                    {tags.map(tag => (
                      <span key={tag} className="text-xs bg-slate-700/60 text-slate-300 px-1.5 py-0.5 rounded">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}

                <div className="ml-auto flex items-center gap-4 text-xs text-slate-500 shrink-0">
                  {slo.author && <span>{slo.author}</span>}
                  {slo.notes && (
                    <span className="max-w-xs truncate text-slate-600 italic" title={slo.notes}>
                      {slo.notes}
                    </span>
                  )}
                  <span className="text-slate-600">{slo.created_at.slice(0, 10)}</span>

                  {slo.active && (
                    <button
                      onClick={e => { e.stopPropagation(); setConfirmDelete(slo.name) }}
                      className="text-xs text-slate-600 hover:text-red-400 transition-colors border border-transparent hover:border-red-700/40 px-1.5 py-0.5 rounded"
                      title="Deactivate SLO"
                    >
                      Deactivate
                    </button>
                  )}
                </div>
              </div>

              {isConfirmingDelete && (
                <div className="px-5 pb-3">
                  <DeleteConfirm name={slo.name} onDone={() => setConfirmDelete(null)} />
                </div>
              )}

              {isExpanded && (
                <div className="px-5 pb-5">
                  <SloDetail name={slo.name} />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
```

Removed imports: `SloYamlViewer`, `SloYamlEditor`, `SloYamlUpload`. Removed modes: `'edit-yaml'`, `'upload'`. Removed tabs: "Upload YAML", "Raw Edit". Added: "View" tab so the user can return to the read-only objectives table from any tab.

- [ ] **Step 2: Verify**

Run: `npx --prefix ui tsc -b --noEmit`

Expected: No errors — all YAML component imports are removed.

- [ ] **Step 3: Commit**

```
git add ui/src/pages/SloRegistryPage.tsx
git commit -m "refactor(ui): remove YAML tabs from SloRegistryPage"
```

---

## Chunk 3: Cleanup

### Task 11: Delete YAML files

**Files:**
- Delete: `ui/src/features/slos/components/SloYamlUpload.tsx`
- Delete: `ui/src/features/slos/components/SloYamlEditor.tsx`
- Delete: `ui/src/features/slos/components/SloYamlViewer.tsx`
- Delete: `ui/src/lib/parseSloYaml.ts`
- Delete: `ui/src/lib/parseSloYaml.test.ts`

- [ ] **Step 1: Delete all 5 files**

```bash
git rm ui/src/features/slos/components/SloYamlUpload.tsx
git rm ui/src/features/slos/components/SloYamlEditor.tsx
git rm ui/src/features/slos/components/SloYamlViewer.tsx
git rm ui/src/lib/parseSloYaml.ts
git rm ui/src/lib/parseSloYaml.test.ts
```

- [ ] **Step 2: Verify TypeScript compiles clean**

Run: `npx --prefix ui tsc -b --noEmit`

Expected: No errors. All imports to these files were removed in Tasks 6–10.

- [ ] **Step 3: Run existing tests to verify nothing broke**

Run: `npx --prefix ui vitest run`

Expected: All remaining tests pass. The deleted `parseSloYaml.test.ts` tests are gone; no other tests depend on it.

- [ ] **Step 4: Commit**

```
git commit -m "refactor(ui): delete all YAML components and parser"
```

---

### Task 12: Final verification

- [ ] **Step 1: Run full build**

Run: `npx --prefix ui tsc -b && npx --prefix ui vite build`

Expected: Build succeeds with no errors.

- [ ] **Step 2: Run all tests**

Run: `npx --prefix ui vitest run`

Expected: All tests pass.

- [ ] **Step 3: Spot-check dev server**

Run: `npx --prefix ui vite --host` (manual — open browser, navigate to SLO Registry page)

Verify:
- SLO list loads with structured data (no YAML blobs visible)
- Expanding an SLO shows the objectives table with pass/warning criteria
- "Edit Rows" tab works — objectives display with flat criteria
- "History" tab shows version details with structured objectives table
- "Upload YAML" and "Raw Edit" tabs are gone
- "+ Create SLO" form works — structured form, no YAML tab
