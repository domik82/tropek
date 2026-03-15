# Stream D: UI Alignment

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Read first:** `docs/superpowers/plans/2026-03-15-api-ui-alignment-overview.md`
>
> **Depends on:** Streams A, B, C must be merged before starting this stream.

**Goal:** Fix all UI code to match the real API contract — paths, field names, response shapes,
and MSW mock handlers.

**Architecture:** Systematic find-and-replace across UI feature modules. No API changes.
All changes are in `ui/src/`. MSW handlers updated to match real API responses so dev mode
continues working.

**Tech Stack:** React 19, TypeScript, MSW

**Spec:** `docs/superpowers/specs/2026-03-15-api-ui-alignment-design.md` §6, §8, §9

**Important dependency:** The UI's `fetchTrend()` calls `GET /trend?eval_id=...` which
requires the `eval_id` parameter added by Stream A. Verify Stream A is merged before
testing trend-related UI code.

---

## File Structure

| Action | File | Responsibility |
|---|---|---|
| Modify | `ui/src/features/evaluations/types.ts` | Field renames, remove mock-only fields |
| Modify | `ui/src/features/evaluations/api.ts` | Filter params, response unwrapping |
| Modify | `ui/src/features/slos/types.ts` | Remove embedded SLI/objectives fields |
| Modify | `ui/src/features/slos/api.ts` | Path fixes, structured create payload |
| Modify | `ui/src/features/assets/api.ts` | Path fix for asset-groups/tree |
| Modify | `ui/src/mocks/handlers/evaluations.ts` | Match real API params + response shape |
| Modify | `ui/src/mocks/handlers/slos.ts` | Fix paths, request/response shapes |
| Modify | `ui/src/mocks/handlers/assets.ts` | Fix asset-groups path |
| Modify | `ui/src/mocks/generate.ts` | Update field names in generated data |
| Modify | `ui/src/mocks/data/slo-definitions.json` | Remove embedded SLI queries/objectives |
| Modify | All components importing changed types | Update field references |

---

### Task 1: Evaluation Types — Field Renames

**Files:**
- Modify: `ui/src/features/evaluations/types.ts`

- [ ] **Step 1: Apply field renames and remove mock-only fields**

In `types.ts`, make these changes:

1. `FailingIndicator`: remove `unit: string`
2. `Annotation`: remove `link?: { href: string; label: string }`
3. `EvaluationSummary`:
   - `start: string` → `period_start: string`
   - `end: string` → `period_end: string`
   - `metadata?: Record<string, string>` → `evaluation_metadata: Record<string, string>`
   - Add: `sli_name: string | null`
   - Add: `sli_version: number | null`
   - Add: `data_source_name: string | null`
4. `EvaluationDetail`:
   - `metadata: Record<string, string>` → `evaluation_metadata: Record<string, string>`
5. `EvaluationFilters`:
   - `lab?: string` → `group_name?: string`
   - `slot?: string` → remove, add `from?: string` and `to?: string`
6. `TriggerEvaluationPayload`:
   - `asset_group: string` → `group_name: string`
   - `start: string` → `period_start: string`
   - `end: string` → `period_end: string`
   - Leave `metadata?: Record<string, string>` as-is — trigger endpoint spec is pending

- [ ] **Step 2: Search for all usages of renamed fields in components**

Use grep/search to find all files referencing `\.start`, `\.end`, `\.metadata`, `.lab`,
`.slot`, `.asset_group`, `.unit` (on FailingIndicator), `.link` (on Annotation).
Update each reference.

- [ ] **Step 3: Verify build**

```bash
cd ui && npm run build
```

Fix any type errors that surface.

- [ ] **Step 4: Commit**

```bash
git add ui/src/features/evaluations/
git commit -m "fix(ui): rename evaluation fields to match API contract"
```

---

### Task 2: Evaluation API — Filter Params + Response Unwrapping

**Files:**
- Modify: `ui/src/features/evaluations/api.ts`

- [ ] **Step 1: Update `toParams` to use new filter names**

```typescript
function toParams(filters: EvaluationFilters): string {
  const p = new URLSearchParams()
  if (filters.group_name) p.set('group_name', filters.group_name)
  if (filters.date) p.set('date', filters.date)
  if (filters.from) p.set('from', filters.from)
  if (filters.to) p.set('to', filters.to)
  return p.toString()
}
```

- [ ] **Step 2: Unwrap PagedResponse in `fetchEvaluations`**

```typescript
export async function fetchEvaluations(
  filters: EvaluationFilters = {}
): Promise<EvaluationSummary[]> {
  const qs = toParams(filters)
  const res = await fetch(`${BASE}/evaluations${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error(`fetchEvaluations: ${res.status}`)
  const data: { items: EvaluationSummary[]; total: number } = await res.json()
  return data.items
}
```

- [ ] **Step 3: Fix `invalidateEvaluation` request body**

Change `{ note }` to `{ invalidation_note: note }` and accept full `EvaluationSummary` response:

```typescript
export async function invalidateEvaluation(
  evalId: string,
  note: string
): Promise<EvaluationSummary> {
  const res = await fetch(`${BASE}/evaluations/${evalId}/invalidate`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ invalidation_note: note }),
  })
  if (!res.ok) throw new Error(`invalidateEvaluation: ${res.status}`)
  return res.json()
}
```

- [ ] **Step 4: Commit**

```bash
git add ui/src/features/evaluations/api.ts
git commit -m "fix(ui): align evaluation API calls with real endpoint contract"
```

---

### Task 3: SLO Types — Remove Mock-Only Fields

**Files:**
- Modify: `ui/src/features/slos/types.ts`

- [ ] **Step 1: Remove embedded fields not returned by API**

Remove from `SloDefinition`:
- `sli_queries?: SliQuery[]`
- `objectives?: SloObjective[]`
- `score_thresholds?: SloScoreThresholds`

Add `id: string` and `slo_yaml: string` (required, not optional). Change `display_name`,
`author`, `notes` from `?: string` (optional/undefined) to `string | null` (always present,
nullable) to match the API `SLODefinitionRead` schema:

```typescript
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
  slo_yaml: string
}
```

Keep `SliQuery`, `SloObjective`, `SloScoreThresholds` interfaces — they're used for
client-side YAML parsing results, not API responses. Just remove them from `SloDefinition`.

- [ ] **Step 2: Update any components that read `slo.objectives` or `slo.sli_queries`**

These components need to parse `slo.slo_yaml` client-side instead using the existing
`lib/parseSloYaml.ts` utility.

- [ ] **Step 3: Commit**

```bash
git add ui/src/features/slos/types.ts
git commit -m "fix(ui): remove mock-only fields from SloDefinition type"
```

---

### Task 4: SLO API — Path Fixes + Structured Create

**Files:**
- Modify: `ui/src/features/slos/api.ts`

- [ ] **Step 1: Fix all URL paths from `/slos` to `/slo-definitions`**

Replace every occurrence:
- `/api/slos` → `/api/slo-definitions`
- `/api/slos/validate` → `/api/slo-definitions/validate`
- `/api/slos/${name}` → `/api/slo-definitions/${name}`
- `/api/slos/${name}/versions` → `/api/slo-definitions/${name}/versions`

- [ ] **Step 2: Fix `validateSloYaml` request body**

Change `{ yaml }` to `{ slo_yaml: yaml }`:

```typescript
export async function validateSloYaml(yaml: string): Promise<SloValidationResult> {
  const res = await fetch(`${BASE}/slo-definitions/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slo_yaml: yaml }),
  })
  if (!res.ok) throw new Error(`validateSloYaml: ${res.status}`)
  return res.json()
}
```

- [ ] **Step 3: Fix `uploadSloYaml` to send structured payload**

The API expects `SLODefinitionCreate` — `{ name, slo_yaml, display_name?, ... }`.
The function needs to accept the structured payload:

```typescript
export async function createSloDefinition(payload: {
  name: string
  slo_yaml: string
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
```

- [ ] **Step 4: Unwrap PagedResponse in `fetchSlos`**

```typescript
export async function fetchSlos(): Promise<SloDefinition[]> {
  const res = await fetch(`${BASE}/slo-definitions`)
  if (!res.ok) throw new Error(`fetchSlos: ${res.status}`)
  const data: { items: SloDefinition[]; total: number } = await res.json()
  return data.items
}
```

- [ ] **Step 5: Update callers of `uploadSloYaml` → `createSloDefinition`**

Search for `uploadSloYaml` in components and update to pass structured payload.

- [ ] **Step 6: Commit**

```bash
git add ui/src/features/slos/
git commit -m "fix(ui): align SLO API paths and payloads with real endpoints"
```

---

### Task 5: Assets API — Path Fix

**Files:**
- Modify: `ui/src/features/assets/api.ts`

- [ ] **Step 1: Fix asset-groups path**

Change `/api/asset-groups` to `/api/asset-groups/tree`:

```typescript
export async function fetchAssetGroupTree(): Promise<AssetGroupTree> {
  const res = await fetch(`${BASE}/asset-groups/tree`)
  if (!res.ok) throw new Error(`fetchAssetGroupTree: ${res.status}`)
  return res.json()
}
```

- [ ] **Step 2: Unwrap PagedResponse in `fetchAssets`**

```typescript
export async function fetchAssets(): Promise<Asset[]> {
  const res = await fetch(`${BASE}/assets`)
  if (!res.ok) throw new Error(`fetchAssets: ${res.status}`)
  const data: { items: Asset[]; total: number } = await res.json()
  return data.items
}
```

- [ ] **Step 3: Commit**

```bash
git add ui/src/features/assets/api.ts
git commit -m "fix(ui): fix asset-groups path and unwrap paged response"
```

---

### Task 6: MSW Handlers — Match Real API

**Files:**
- Modify: `ui/src/mocks/handlers/evaluations.ts`
- Modify: `ui/src/mocks/handlers/slos.ts`
- Modify: `ui/src/mocks/handlers/assets.ts`

- [ ] **Step 1: Update evaluation handlers**

In `evaluations.ts`:
- Change param extraction from `lab`/`slot` to `group_name`/`from`/`to`
- Wrap response in `{ items: [...], total: N }`
- `PATCH /invalidate` handler: read request body (currently ignored entirely),
  accept `{ invalidation_note }`, return full summary shape with `invalidated: true`

- [ ] **Step 2: Update SLO handlers**

In `slos.ts`:
- All paths from `/api/slos` → `/api/slo-definitions`
- `POST /api/slo-definitions`: accept structured `{ name, slo_yaml, ... }` instead of `{ yaml }`
- `POST /api/slo-definitions/validate`: accept `{ slo_yaml }` instead of implicitly
- Add `POST /api/slo-definitions/test` handler returning mock test result
- Wrap list response in `{ items: [...], total: N }`

- [ ] **Step 3: Update asset handlers**

In `assets.ts`:
- Change `/api/asset-groups` → `/api/asset-groups/tree`
- Wrap `/api/assets` response in `{ items: [...], total: N }`

- [ ] **Step 4: Update mock data generation**

In `generate.ts`:
- Use `period_start`/`period_end` instead of `start`/`end` — update both
  `generateEvaluationSummary()` and `generateEvaluationDetail()` locations
- Use `evaluation_metadata` instead of `metadata` — appears in both summary
  and detail generators
- Remove `unit` from `FailingIndicator` objects
- Remove `link` from `Annotation` objects — appears in `generateEvaluationDetail()`
  (both inline and in `latest_annotation` objects within summaries)
- Add `sli_name`, `sli_version`, `data_source_name` to evaluation summaries
- Rename `EvaluationListFilters` interface: `lab` → `group_name`, remove `slot`,
  add `from`/`to` fields
- Update `getEvaluations()` function: filter on `group_name` instead of `lab`,
  filter on `from`/`to` using `.period_start` instead of `.start`

- [ ] **Step 5: Update SLO mock data**

In `mocks/data/slo-definitions.json`:
- Remove `sli_queries` field (present in JSON fixture — `objectives` and
  `score_thresholds` exist only in the TypeScript type, not in the JSON data)
- Add `id` field (UUID string) — this is a NEW required field not in current data
- Ensure `slo_yaml` is present on every entry
- Match `SLODefinitionRead` shape exactly

- [ ] **Step 6: Verify build + dev mode**

```bash
cd ui && npm run build
cd ui && npm run dev  # manual check: pages load, mock data renders
```

- [ ] **Step 7: Commit**

```bash
git add ui/src/mocks/
git commit -m "fix(ui): update MSW handlers and mock data to match real API contract"
```

---

### Task 7: Component Updates — Find and Fix All References

- [ ] **Step 1: Search for all broken references**

Search the entire `ui/src/` for these patterns and fix each:
- `.start` on evaluation objects → `.period_start`
- `.end` on evaluation objects → `.period_end`
- `.metadata` on evaluation objects → `.evaluation_metadata`
- `.unit` on FailingIndicator objects → remove
- `.link` on Annotation objects → remove
- `lab` in filter objects → `group_name`
- `slot` in filter objects → `from`/`to`
- `asset_group` in trigger payload → `group_name`
- `uploadSloYaml` → `createSloDefinition`
- `slo.objectives` (direct access) → parse from `slo.slo_yaml`
- `slo.sli_queries` → fetch from SLI API separately

- [ ] **Step 2: Verify build passes clean**

```bash
cd ui && npm run build
```

- [ ] **Step 3: Run any existing tests**

```bash
cd ui && npm test -- --run
```

- [ ] **Step 4: Commit**

```bash
git add ui/src/
git commit -m "fix(ui): update all component references to match new API field names"
```
