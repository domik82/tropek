# Evaluation Redesign UI Gaps Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all UI gaps from the evaluation redesign audit: `name` → `evaluation_name` rename across types/mocks/components, add `comparable_from_version` to SLO/SLI types and UI, add re-evaluate MSW handler, and improve re-evaluation display in evaluation detail.

**Architecture:** Pure frontend changes across TypeScript types, React components, MSW mock handlers, and JSON fixture data. No backend changes needed — the API already returns `evaluation_name` and `comparable_from_version`. The UI just needs to match.

**Tech Stack:** React 18, TypeScript, TanStack Query, MSW 2, Zod, react-hook-form

**Spec:** `docs/superpowers/specs/2026-03-18-evaluation-redesign-design.md`

---

## File Map

### Modified files

| File | Changes |
|------|---------|
| `ui/src/features/evaluations/types.ts` | Rename `EvaluationSummary.name` → `evaluation_name`, `TriggerEvaluationPayload.test_name` → `evaluation_name` |
| `ui/src/features/evaluations/components/TriggerEvaluationModal.tsx` | Update form schema and field from `test_name` → `evaluation_name`, update label |
| `ui/src/features/evaluations/components/EvaluationTable.tsx` | Update `ev.name` references → `ev.evaluation_name` |
| `ui/src/pages/EvaluationDetailPage.tsx` | Update `ev.name` references → `ev.evaluation_name`, add re-evaluation badge |
| `ui/src/mocks/generate.ts` | Change `name: scenario.test` → `evaluation_name: scenario.test` in evaluation builder |
| `ui/src/mocks/data/evaluations.json` | Rename all `"name"` keys → `"evaluation_name"` |
| `ui/src/mocks/handlers/evaluations.ts` | Add `http.post('/api/evaluations/re-evaluate', ...)` handler |
| `ui/src/features/slos/types.ts` | Add `comparable_from_version: number` to `SloDefinition`, add `SliDefinition.comparable_from_version` |
| `ui/src/features/slis/types.ts` | Add `comparable_from_version` to `SliDefinition` and `SliDefinitionCreate` |
| `ui/src/features/slos/api.ts` | Add `comparable_from_version?: number` to `createSloDefinition` payload |
| `ui/src/features/slos/components/SloHistoryPanel.tsx` | Show `comparable_from_version` badge per version |
| `ui/src/features/slos/components/SloCreateForm.tsx` | Add `comparable_from_version` input field |
| `ui/src/features/slos/components/SloObjectiveEditor.tsx` | Add `comparable_from_version` input field |
| `ui/src/mocks/data/slo-definitions.json` | Add `comparable_from_version` to all mock entries |
| `ui/src/mocks/data/sli-definitions.json` | Add `comparable_from_version` to all mock entries |

---

## Chunk 1: Rename `name` → `evaluation_name` Across UI

### Task 1: Update TypeScript types

**Files:**
- Modify: `ui/src/features/evaluations/types.ts:21-51` (EvaluationSummary)
- Modify: `ui/src/features/evaluations/types.ts:101-108` (TriggerEvaluationPayload)

- [ ] **Step 1: Rename `name` to `evaluation_name` in `EvaluationSummary`**

In `ui/src/features/evaluations/types.ts`, change line 23:

```typescript
// Change:
name: string
// To:
evaluation_name: string
```

- [ ] **Step 2: Rename `test_name` to `evaluation_name` in `TriggerEvaluationPayload`**

In `ui/src/features/evaluations/types.ts`, change line 103:

```typescript
// Change:
test_name: string
// To:
evaluation_name: string
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `npx tsc --noEmit --project ui/tsconfig.json 2>&1 | head -30`

Expected: Type errors in components that reference `ev.name` or `test_name` — these are fixed in the next tasks.

- [ ] **Step 4: Commit**

```
git add ui/src/features/evaluations/types.ts
git commit -m "refactor(ui): rename EvaluationSummary.name to evaluation_name and TriggerEvaluationPayload.test_name to evaluation_name"
```

---

### Task 2: Update EvaluationTable component

**Files:**
- Modify: `ui/src/features/evaluations/components/EvaluationTable.tsx:47-51`

- [ ] **Step 1: Replace `ev.name` with `ev.evaluation_name`**

In `ui/src/features/evaluations/components/EvaluationTable.tsx`, replace all occurrences of `ev.name` with `ev.evaluation_name`. There are two occurrences at lines 47 and 51:

```typescript
// Line 47, change:
{ev.name}
// To:
{ev.evaluation_name}

// Line 51, change:
{ev.name}
// To:
{ev.evaluation_name}
```

- [ ] **Step 2: Commit**

```
git add ui/src/features/evaluations/components/EvaluationTable.tsx
git commit -m "refactor(ui): update EvaluationTable to use evaluation_name"
```

---

### Task 3: Update EvaluationDetailPage

**Files:**
- Modify: `ui/src/pages/EvaluationDetailPage.tsx:69-74`

- [ ] **Step 1: Replace `ev.name` with `ev.evaluation_name`**

In `ui/src/pages/EvaluationDetailPage.tsx`, there are two occurrences at lines 69 and 74:

```typescript
// Line 69, change:
<span className="text-slate-200">{ev.name}</span>
// To:
<span className="text-slate-200">{ev.evaluation_name}</span>

// Line 74, change:
title={ev.name}
// To:
title={ev.evaluation_name}
```

- [ ] **Step 2: Commit**

```
git add ui/src/pages/EvaluationDetailPage.tsx
git commit -m "refactor(ui): update EvaluationDetailPage to use evaluation_name"
```

---

### Task 4: Update TriggerEvaluationModal

**Files:**
- Modify: `ui/src/features/evaluations/components/TriggerEvaluationModal.tsx:19-76`

- [ ] **Step 1: Update Zod schema field name**

In `ui/src/features/evaluations/components/TriggerEvaluationModal.tsx`, change line 21:

```typescript
// Change:
test_name: z.string().min(1, 'Required'),
// To:
evaluation_name: z.string().min(1, 'Required'),
```

- [ ] **Step 2: Update label text**

Change line 74:

```typescript
// Change:
<label className="text-xs text-gray-400">Test Name</label>
// To:
<label className="text-xs text-gray-400">Evaluation Name</label>
```

- [ ] **Step 3: Update form register and error references**

Change line 75-76:

```typescript
// Change:
<Input {...register('test_name')} placeholder="e.g. perf-test-linux" className="mt-1" />
{errors.test_name && <p className="text-red-400 text-xs mt-1">{errors.test_name.message}</p>}
// To:
<Input {...register('evaluation_name')} placeholder="e.g. nightly-build" className="mt-1" />
{errors.evaluation_name && <p className="text-red-400 text-xs mt-1">{errors.evaluation_name.message}</p>}
```

- [ ] **Step 4: Commit**

```
git add ui/src/features/evaluations/components/TriggerEvaluationModal.tsx
git commit -m "refactor(ui): update TriggerEvaluationModal to use evaluation_name"
```

---

### Task 5: Update mock data and generator

**Files:**
- Modify: `ui/src/mocks/generate.ts:316`
- Modify: `ui/src/mocks/generate.ts:571`
- Modify: `ui/src/mocks/data/evaluations.json`

- [ ] **Step 1: Update generate.ts evaluation builder**

In `ui/src/mocks/generate.ts`, change line 316:

```typescript
// Change:
name: scenario.test,
// To:
evaluation_name: scenario.test,
```

- [ ] **Step 2: Update generate.ts trend function**

In `ui/src/mocks/generate.ts`, change line 571:

```typescript
// Change:
return generateTrendData(ev.name, metric, ev.asset_snapshot.name, allEvals())
// To:
return generateTrendData(ev.evaluation_name, metric, ev.asset_snapshot.name, allEvals())
```

- [ ] **Step 3: Update evaluations.json mock data**

In `ui/src/mocks/data/evaluations.json`, rename every `"name"` key to `"evaluation_name"` on the evaluation objects. There are 11 occurrences (lines 5, 21, 37, 53, 70, 86, 102, 118, 134, 150, 166). Do NOT rename `"name"` keys inside `asset_snapshot` — those are asset names, not evaluation names.

Example for the first entry:

```json
// Change:
"name": "compilation-test",
// To:
"evaluation_name": "compilation-test",
```

Apply this change to all 11 evaluation entries. Leave `asset_snapshot.name` unchanged.

- [ ] **Step 4: Verify TypeScript compiles cleanly**

Run: `npx tsc --noEmit --project ui/tsconfig.json`

Expected: No type errors.

- [ ] **Step 5: Commit**

```
git add ui/src/mocks/generate.ts ui/src/mocks/data/evaluations.json
git commit -m "refactor(ui): rename name to evaluation_name in mock data and generator"
```

---

## Chunk 2: MSW Handler for Re-evaluate + Re-evaluation Badge

### Task 6: Add re-evaluate MSW mock handler

**Files:**
- Modify: `ui/src/mocks/handlers/evaluations.ts:8-94`

- [ ] **Step 1: Add the handler**

In `ui/src/mocks/handlers/evaluations.ts`, add the following handler inside the `evaluationHandlers` array, after the `http.post('/api/evaluations', ...)` handler (after line 47):

```typescript
  http.post('/api/evaluations/re-evaluate', async ({ request }) => {
    const body = await request.json() as {
      asset_name: string
      slo_name: string
      from_date?: string
      from_baseline?: boolean
      dry_run?: boolean
    }
    return HttpResponse.json({
      affected_evaluations: 3,
      slo_version_used: 2,
      results: [
        {
          id: crypto.randomUUID(),
          evaluation_name: 'nightly-run',
          period_start: body.from_date ?? '2026-03-10T00:00:00Z',
          period_end: '2026-03-10T00:30:00Z',
          old_result: 'fail',
          new_result: 'pass',
          old_score: 45.0,
          new_score: 92.0,
        },
        {
          id: crypto.randomUUID(),
          evaluation_name: 'nightly-run',
          period_start: '2026-03-11T00:00:00Z',
          period_end: '2026-03-11T00:30:00Z',
          old_result: 'fail',
          new_result: 'pass',
          old_score: 52.0,
          new_score: 88.0,
        },
        {
          id: crypto.randomUUID(),
          evaluation_name: 'nightly-run',
          period_start: '2026-03-12T00:00:00Z',
          period_end: '2026-03-12T00:30:00Z',
          old_result: 'warning',
          new_result: 'pass',
          old_score: 71.0,
          new_score: 95.0,
        },
      ],
    })
  }),
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `npx tsc --noEmit --project ui/tsconfig.json`

Expected: No errors.

- [ ] **Step 3: Commit**

```
git add ui/src/mocks/handlers/evaluations.ts
git commit -m "feat(ui): add MSW mock handler for POST /evaluations/re-evaluate"
```

---

### Task 7: Improve re-evaluation display in EvaluationDetailPage

**Files:**
- Modify: `ui/src/pages/EvaluationDetailPage.tsx:101-116`

The current code shows "Status overridden" for both manual overrides and re-evaluations.
The `original_result` field is set by both features, but re-evaluations store
`job_stats.re_evaluated_at` (not exposed in the current API response). The simplest
distinction: if `override_reason` and `override_author` are present, it was a manual
override. If `original_result` is present but those are null, it was a re-evaluation.

- [ ] **Step 1: Add re-evaluation badge distinct from override**

In `ui/src/pages/EvaluationDetailPage.tsx`, replace lines 101-116:

```tsx
// Change the entire block:
{ev.original_result && (
  <div className="mt-2 flex flex-col gap-1">
    <span className="text-xs text-amber-300 bg-amber-900/20 border border-amber-700/30 px-2 py-1 rounded inline-flex flex-wrap items-center gap-x-1.5">
      <span className="font-medium">Status overridden</span>
      <span className="text-amber-500">
        {ev.original_result} → {ev.result}
      </span>
      {ev.override_author && (
        <span>by <span className="text-amber-200">{ev.override_author}</span></span>
      )}
      {ev.override_reason && (
        <span className="text-amber-400/80">— {ev.override_reason}</span>
      )}
    </span>
  </div>
)}
```

With:

```tsx
{ev.original_result && ev.override_author && (
  <div className="mt-2 flex flex-col gap-1">
    <span className="text-xs text-amber-300 bg-amber-900/20 border border-amber-700/30 px-2 py-1 rounded inline-flex flex-wrap items-center gap-x-1.5">
      <span className="font-medium">Status overridden</span>
      <span className="text-amber-500">
        {ev.original_result} → {ev.result}
      </span>
      <span>by <span className="text-amber-200">{ev.override_author}</span></span>
      {ev.override_reason && (
        <span className="text-amber-400/80">— {ev.override_reason}</span>
      )}
    </span>
  </div>
)}
{ev.original_result && !ev.override_author && (
  <div className="mt-2 flex flex-col gap-1">
    <span className="text-xs text-purple-300 bg-purple-900/20 border border-purple-700/30 px-2 py-1 rounded inline-flex flex-wrap items-center gap-x-1.5">
      <span className="font-medium">Re-evaluated</span>
      <span className="text-purple-400">
        {ev.original_result} → {ev.result}
      </span>
    </span>
  </div>
)}
```

- [ ] **Step 2: Commit**

```
git add ui/src/pages/EvaluationDetailPage.tsx
git commit -m "feat(ui): distinguish re-evaluation badge from manual override in evaluation detail"
```

---

## Chunk 3: `comparable_from_version` in Types, Mocks, and API

### Task 8: Add `comparable_from_version` to SLO and SLI types

**Files:**
- Modify: `ui/src/features/slos/types.ts:13-27` (SloDefinition)
- Modify: `ui/src/features/slos/types.ts:67-76` (SliDefinition in slos/types.ts)
- Modify: `ui/src/features/slis/types.ts:3-14` (SliDefinition)
- Modify: `ui/src/features/slis/types.ts:16-23` (SliDefinitionCreate)

- [ ] **Step 1: Add to `SloDefinition` in `slos/types.ts`**

In `ui/src/features/slos/types.ts`, add after `version: number` (line 16):

```typescript
comparable_from_version: number
```

- [ ] **Step 2: Add to `SliDefinition` in `slos/types.ts`**

In `ui/src/features/slos/types.ts`, the `SliDefinition` at lines 67-76 is used by the
SLO link dialog. Add after `version: number` (line 72):

```typescript
comparable_from_version: number
```

- [ ] **Step 3: Add to `SliDefinition` in `slis/types.ts`**

In `ui/src/features/slis/types.ts`, add after `version: number` (line 7):

```typescript
comparable_from_version: number
```

- [ ] **Step 4: Add to `SliDefinitionCreate` in `slis/types.ts`**

In `ui/src/features/slis/types.ts`, add to `SliDefinitionCreate` (after line 19):

```typescript
comparable_from_version?: number
```

- [ ] **Step 5: Commit**

```
git add ui/src/features/slos/types.ts ui/src/features/slis/types.ts
git commit -m "feat(ui): add comparable_from_version to SLO and SLI type definitions"
```

---

### Task 9: Update mock data with `comparable_from_version`

**Files:**
- Modify: `ui/src/mocks/data/slo-definitions.json`
- Modify: `ui/src/mocks/data/sli-definitions.json`

- [ ] **Step 1: Add `comparable_from_version` to SLO mock data**

In `ui/src/mocks/data/slo-definitions.json`, add `"comparable_from_version"` after `"version"` in each SLO entry:

| SLO | version | comparable_from_version |
|-----|---------|------------------------|
| `compilation-test-windows` | 2 | 1 |
| `compilation-test-linux` | 1 | 1 |
| `compilation-test-macos` | 1 | 1 |
| `load-test-linux` | 3 | 2 |
| `load-test-windows` | 2 | 1 |

Example for the first entry (after line 7):

```json
"comparable_from_version": 1,
```

For `load-test-linux` (version 3, line 86), use `2` to show a version gap:

```json
"comparable_from_version": 2,
```

- [ ] **Step 2: Add `comparable_from_version` to SLI mock data**

In `ui/src/mocks/data/sli-definitions.json`, add `"comparable_from_version"` after `"version"` in each entry:

| SLI | version | comparable_from_version |
|-----|---------|------------------------|
| `linux-compilation-sli` | 2 | 1 |
| `api-performance-sli` | 1 | 1 |

- [ ] **Step 3: Verify TypeScript compiles**

Run: `npx tsc --noEmit --project ui/tsconfig.json`

Expected: No errors.

- [ ] **Step 4: Commit**

```
git add ui/src/mocks/data/slo-definitions.json ui/src/mocks/data/sli-definitions.json
git commit -m "feat(ui): add comparable_from_version to SLO and SLI mock data"
```

---

### Task 10: Add `comparable_from_version` to SLO create API

**Files:**
- Modify: `ui/src/features/slos/api.ts:39-56` (createSloDefinition payload type)

- [ ] **Step 1: Add the field to the payload type**

In `ui/src/features/slos/api.ts`, add to the `createSloDefinition` payload type
(after line 47):

```typescript
comparable_from_version?: number
```

The updated payload type becomes:

```typescript
export async function createSloDefinition(payload: {
  name: string
  objectives: SloObjective[]
  total_score_pass_pct: number
  total_score_warning_pct: number
  comparison: Record<string, unknown>
  display_name?: string
  notes?: string
  author?: string
  comparable_from_version?: number
}): Promise<SloDefinition> {
```

- [ ] **Step 2: Commit**

```
git add ui/src/features/slos/api.ts
git commit -m "feat(ui): add comparable_from_version to SLO create API payload"
```

---

## Chunk 4: `comparable_from_version` in SLO UI Components

### Task 11: Show `comparable_from_version` in SloHistoryPanel

**Files:**
- Modify: `ui/src/features/slos/components/SloHistoryPanel.tsx:22-27`

- [ ] **Step 1: Add comparable_from_version badge**

In `ui/src/features/slos/components/SloHistoryPanel.tsx`, add a badge after the
active/inactive badge (after line 27). The badge should only show when
`comparable_from_version` differs from `1` (i.e., when there's an interesting
version gap):

```tsx
// After line 27 (after the active/inactive span), add:
{v.comparable_from_version > 1 && (
  <span className="text-xs bg-indigo-900/30 text-indigo-300 border border-indigo-700/30 px-1.5 py-0.5 rounded-full">
    comparable from v{v.comparable_from_version}
  </span>
)}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `npx tsc --noEmit --project ui/tsconfig.json`

Expected: No errors — `v` is a `SloDefinition` which now has `comparable_from_version`.

- [ ] **Step 3: Commit**

```
git add ui/src/features/slos/components/SloHistoryPanel.tsx
git commit -m "feat(ui): show comparable_from_version badge in SLO version history"
```

---

### Task 12: Add `comparable_from_version` input to SloCreateForm

**Files:**
- Modify: `ui/src/features/slos/components/SloCreateForm.tsx:23-50` (schema + defaults)
- Modify: `ui/src/features/slos/components/SloCreateForm.tsx:79-108` (onSubmit payload)
- Modify: `ui/src/features/slos/components/SloCreateForm.tsx:174-187` (Score Thresholds section)

- [ ] **Step 1: Add to Zod schema**

In `ui/src/features/slos/components/SloCreateForm.tsx`, add to the `formSchema` object
(after line 33, before `objectives`):

```typescript
comparable_from_version: z.coerce.number().min(1).optional(),
```

- [ ] **Step 2: Update `onSubmit` to include the field**

In the `onSubmit` function, add to the payload passed to `create.mutate()` (after
line 105, before the closing `}` of the payload):

```typescript
comparable_from_version: values.comparable_from_version || undefined,
```

- [ ] **Step 3: Add UI input field**

In the "Score Thresholds" section (after line 187, after the total warning % div),
add a new row:

```tsx
<div>
  <label className="block text-xs text-slate-500 mb-1">Comparable From Version</label>
  <input {...register('comparable_from_version')} type="number" min={1} className={inp} placeholder="defaults to previous" />
  <p className="text-[10px] text-slate-600 mt-0.5">Baselines from versions before this are excluded</p>
</div>
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `npx tsc --noEmit --project ui/tsconfig.json`

Expected: No errors.

- [ ] **Step 5: Commit**

```
git add ui/src/features/slos/components/SloCreateForm.tsx
git commit -m "feat(ui): add comparable_from_version input to SLO create form"
```

---

### Task 13: Add `comparable_from_version` input to SloObjectiveEditor

**Files:**
- Modify: `ui/src/features/slos/components/SloObjectiveEditor.tsx:106-140`

The `SloObjectiveEditor` is used when editing an existing SLO (creating a new version).
This is the primary place users need to set `comparable_from_version`, since version
bumps happen here.

- [ ] **Step 1: Add to the form schema**

The `SloObjectiveEditor` uses a local `formSchema` defined earlier in the file. Find it
and add `comparable_from_version`:

```typescript
// Add to the formSchema:
comparable_from_version: z.coerce.number().min(1).optional(),
```

- [ ] **Step 2: Add to `buildPayload`**

In the `buildPayload` function (lines 106-121), add after `comparison`:

```typescript
comparable_from_version: values.comparable_from_version || undefined,
```

- [ ] **Step 3: Add UI input**

In the form JSX, add after the score thresholds section (before the objectives table):

```tsx
{/* Version compatibility */}
<div className="grid grid-cols-2 gap-3">
  <div>
    <label className="block text-[10px] text-slate-500 mb-0.5">Comparable From Version</label>
    <input {...register('comparable_from_version')} type="number" min={1} className={inp} placeholder={`${slo.version}`} />
    <p className="text-[10px] text-slate-600 mt-0.5">Baselines from older versions are excluded</p>
  </div>
</div>
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `npx tsc --noEmit --project ui/tsconfig.json`

Expected: No errors.

- [ ] **Step 5: Commit**

```
git add ui/src/features/slos/components/SloObjectiveEditor.tsx
git commit -m "feat(ui): add comparable_from_version input to SLO objective editor"
```

---

## Chunk 5: Final Verification

### Task 14: TypeScript and lint check

- [ ] **Step 1: Run TypeScript check**

Run: `npx tsc --noEmit --project ui/tsconfig.json`

Expected: No errors.

- [ ] **Step 2: Run ESLint**

Run: `npx eslint ui/src --ext .ts,.tsx --max-warnings 0 2>&1 | tail -20`

Expected: No errors (or only pre-existing ones).

- [ ] **Step 3: Fix any issues and commit**

If any step above fails, fix and commit:

```
fix(ui): resolve lint and type issues from evaluation redesign UI gaps
```

---

## Task Dependency Graph

```
Task 1 (types rename)
  ├── Task 2 (EvaluationTable)
  ├── Task 3 (EvaluationDetailPage)
  ├── Task 4 (TriggerEvaluationModal)
  └── Task 5 (mock data + generator)

Task 6 (MSW re-evaluate handler — independent)
Task 7 (re-evaluation badge — independent, but Task 3 edits same file)

Task 8 (SLO/SLI types + comparable_from_version)
  ├── Task 9 (mock data)
  ├── Task 10 (SLO create API)
  ├── Task 11 (SloHistoryPanel)
  ├── Task 12 (SloCreateForm)
  └── Task 13 (SloObjectiveEditor)

Task 14 (final verification — needs all above)
```

**Parallelizable groups:**
- Group A: Tasks 2, 3, 4, 5 (all depend on Task 1, independent of each other — but Task 3 and Task 7 touch the same file, so run Task 7 after Task 3)
- Group B: Tasks 6 (fully independent)
- Group C: Tasks 9, 10, 11, 12, 13 (all depend on Task 8, independent of each other)
