# UI SLO Format Refactor

**Date:** 2026-03-15
**Status:** Approved (revised 2026-03-16 — YAML components dropped)

## Summary

The backend replaced the opaque `slo_yaml: string` field on `SLODefinition` with structured
fields (`objectives[]`, `total_score_pass_pct`, `total_score_warning_pct`, `comparison`).
This spec covers the corresponding UI refactor: updating types, API calls, all SLO feature
components, and mock data.

YAML import/export is handled by the Python CLI — the UI does not need a YAML upload or
round-trip edit surface. All YAML-related UI components are deleted. The UI works exclusively
with structured data.

---

## Section 1: Types and API Layer

### `features/slos/types.ts`

`SloObjective` flattens the old Keptn-inherited nested criteria structure. `tab_group` and
`labels` are dropped — they have no equivalent in the new backend schema:

```typescript
export interface SloObjective {
  sli: string
  display_name: string
  pass_criteria: string[]       // was: pass: { criteria: string[] }[]
  warning_criteria: string[]    // was: warning?: { criteria: string[] }[]
  weight: number
  key_sli: boolean
  sort_order: number            // new: preserves server-defined order
}
```

`SloDefinition` drops `slo_yaml` and gains structured fields:

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
  objectives: SloObjective[]
  total_score_pass_pct: number
  total_score_warning_pct: number
  comparison: Record<string, unknown>
}
```

`SloValidationResult` full updated interface:

```typescript
export interface SloValidationResult {
  valid: boolean
  errors: { field: string; message: string }[]
  objectives?: SloObjective[]   // was: SloObjective[] using old nested criteria shape
}
```

`SliQuery` and `SloScoreThresholds` are deleted — they existed only to bridge the old YAML
blob workflow.

`comparison` on `SloDefinition` stays typed as `Record<string, unknown>` — no dedicated
`SloComparison` TypeScript interface is introduced. The comparison UI is out of scope for this
refactor; the opaque type is intentional and sufficient.

### `features/slos/api.ts`

`validateSloYaml(yaml: string)` is replaced by `validateSlo(payload)` with structured fields:

```typescript
export async function validateSlo(payload: {
  objectives: SloObjective[]
  total_score_pass_pct: number
  total_score_warning_pct: number
  comparison: Record<string, unknown>
}): Promise<SloValidationResult>
```

`createSloDefinition` drops `slo_yaml` and sends structured fields:

```typescript
export async function createSloDefinition(payload: {
  name: string
  objectives: SloObjective[]
  total_score_pass_pct: number
  total_score_warning_pct: number
  comparison: Record<string, unknown>   // required; pass {} for all-default comparison settings
  display_name?: string
  notes?: string
  author?: string
}): Promise<SloDefinition>
```

`comparison: {}` is a valid payload — the backend treats an empty dict as all-default
comparison settings (`compare_with: single_result`, `number_of_comparison_results: 3`, etc.).

`fetchSlos`, `fetchSloDetail`, `fetchSloVersions` — signatures unchanged; return types update
automatically via the new `SloDefinition`.

---

## Section 2: Components

### `SloYamlUpload.tsx` — **Deleted**

YAML import is handled by the Python CLI. This component is removed entirely.

### `SloYamlEditor.tsx` — **Deleted**

YAML round-trip editing is removed. Users edit SLOs through the structured "Edit Rows" form only.

### `SloYamlViewer.tsx` — **Deleted**

No longer needed. `SloHistoryPanel` displays version details using structured fields directly.

### `SloHistoryPanel.tsx`

- Removes its dependency on `SloYamlViewer`
- Each version entry shows: version number, active badge, author, notes, timestamp
- Expandable section per version shows the objectives using `SloObjectiveTable` (read-only)
  plus the `total_score_pass_pct`, `total_score_warning_pct` values as plain text

### `SloObjectiveTable.tsx`

- Reads `obj.pass_criteria` (flat `string[]`) directly instead of `obj.pass[0].criteria`
- Same for `warning_criteria`
- Columns: **Indicator** (`sli`), **Display Name**, **Pass Criteria**, **Warning Criteria**,
  **Weight**, **Key SLI**. `tab_group` and `sort_order` columns removed.

### `SloObjectiveEditor.tsx`

Props: receives the full `SloDefinition` being edited plus an `onSave` callback. Internally
manages a list of `SloObjective` items with flat `pass_criteria`/`warning_criteria` arrays.
On save: calls `createSloDefinition` with the SLO's existing metadata fields plus the updated
objectives list, `total_score_pass_pct`, `total_score_warning_pct`, and `comparison` —
creates a new version.

### `features/slos/hooks.ts`

`useSloValidation` currently calls `validateSloYaml`. Update it to call `validateSlo` with
the structured payload shape:

```typescript
// Before
useSloValidation(yaml: string)  →  calls validateSloYaml(yaml)

// After
useSloValidation(payload: {
  objectives: SloObjective[]
  total_score_pass_pct: number
  total_score_warning_pct: number
  comparison: Record<string, unknown>
})  →  calls validateSlo(payload)
```

Caller: `SloObjectiveEditor` passes the structured payload directly.

### `SloCreateForm.tsx`

- Pure structured form — the YAML paste tab is removed entirely
- Submits structured fields directly to `createSloDefinition`
- Internal form state uses flat `pass_criteria`/`warning_criteria`

### Pages

`SloRegistryPage.tsx` — remove the "Upload YAML" and "Raw Edit" tabs from the SLO detail
view (they hosted `SloYamlUpload` and `SloYamlEditor` respectively). Remaining tabs: "Edit
Rows" (`SloObjectiveEditor`) and "History" (`SloHistoryPanel`).

`EvaluationDetailPage.tsx` — no structural changes. Consumes `SloDefinition` and
`SloObjective` which update transparently via the type changes.

---

## Section 3: Mocks

### `mocks/data/slo-definitions.json`

All 5 entries replace `slo_yaml` with structured fields. Shape per entry:

```json
{
  "id": "...",
  "name": "compilation-test-windows",
  "version": 2,
  "display_name": "Compilation Test — Windows",
  "author": "jane.smith",
  "notes": "Added memory_peak_mb indicator in v2",
  "meta": {},
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
    {
      "sli": "compilation_errors",
      "display_name": "Compilation Errors",
      "pass_criteria": ["=0"],
      "warning_criteria": [],
      "weight": 3,
      "key_sli": true,
      "sort_order": 0
    }
  ]
}
```

### `mocks/handlers/slos.ts`

- `POST /api/slo-definitions/validate` response: `objectives` uses flat
  `pass_criteria`/`warning_criteria`, drops old `pass: [{criteria: []}]` shape
- `POST /api/slo-definitions` request: expects structured fields (no `slo_yaml`); response
  echoes back a full `SloDefinition` with `objectives[]`, `total_score_pass_pct`, etc.
- `GET` handlers: no changes (serve from updated `slo-definitions.json`)

---

## File Change Summary

| File | Action |
|---|---|
| `features/slos/types.ts` | Update |
| `features/slos/api.ts` | Update |
| `features/slos/hooks.ts` | Update (`useSloValidation` wired to new `validateSlo`) |
| `lib/parseSloYaml.ts` | Delete |
| `lib/parseSloYaml.test.ts` | Delete |
| `features/slos/components/SloYamlUpload.tsx` | Delete |
| `features/slos/components/SloYamlEditor.tsx` | Delete |
| `features/slos/components/SloYamlViewer.tsx` | Delete |
| `features/slos/components/SloHistoryPanel.tsx` | Update |
| `features/slos/components/SloObjectiveTable.tsx` | Update |
| `features/slos/components/SloObjectiveEditor.tsx` | Update |
| `features/slos/components/SloCreateForm.tsx` | Update |
| `pages/SloRegistryPage.tsx` | Update (remove Upload YAML + Raw Edit tabs) |
| `mocks/data/slo-definitions.json` | Update |
| `mocks/handlers/slos.ts` | Update |
| `pages/EvaluationDetailPage.tsx` | No change |
