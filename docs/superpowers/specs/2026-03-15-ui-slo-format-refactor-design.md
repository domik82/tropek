# UI SLO Format Refactor

**Date:** 2026-03-15
**Status:** Approved

## Summary

The backend replaced the opaque `slo_yaml: string` field on `SLODefinition` with structured
fields (`objectives[]`, `total_score_pass_pct`, `total_score_warning_pct`, `comparison`).
This spec covers the corresponding UI refactor: updating types, API calls, the YAML
parse/format utilities, all SLO feature components, and mock data.

YAML remains a supported import format (file upload) and a round-trip edit surface (Raw Edit
tab), but is never stored or transmitted as a blob. The UI parses YAML → structured, submits
structured to the API.

---

## Section 1: Types and API Layer

### `features/slos/types.ts`

`SloObjective` flattens the old Keptn-inherited nested criteria structure:

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

`SloValidationResult.objectives` updates to `SloObjective[] | undefined`.

`SliQuery` and `SloScoreThresholds` are deleted — they existed only to bridge the old YAML
blob workflow.

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
  comparison?: Record<string, unknown>
  display_name?: string
  notes?: string
  author?: string
}): Promise<SloDefinition>
```

`fetchSlos`, `fetchSloDetail`, `fetchSloVersions` — signatures unchanged; return types update
automatically via the new `SloDefinition`.

---

## Section 2: `lib/sloManifest.ts`

Replaces `lib/parseSloYaml.ts`. Exports two functions for YAML ↔ structured conversion.
Uses `js-yaml` for parsing and serialization (replacing the hand-rolled line parser).

### `parseSloManifest`

```typescript
export interface ParsedSloManifest {
  name: string
  display_name: string
  author: string
  notes: string
  objectives: SloObjective[]
  total_score_pass_pct: number
  total_score_warning_pct: number
  comparison: Record<string, unknown>
}

export type ParseSloManifestError =
  | { kind: 'multi_document' }
  | { kind: 'parse_error'; message: string }
  | { kind: 'invalid_structure'; message: string }

export function parseSloManifest(
  yaml: string
): { ok: true; value: ParsedSloManifest } | { ok: false; error: ParseSloManifestError }
```

- Detects `---` separator after the first line → returns `{ ok: false, error: { kind: 'multi_document' } }`
- Uses `js-yaml.load()` to parse the document
- Extracts fields from the new manifest format:
  - `metadata.name/display_name/author/notes` → top-level fields
  - `spec.total_score.pass_pct/warning_pct` → `total_score_pass_pct/warning_pct`
  - `spec.objectives[]` → `SloObjective[]` with `sort_order` assigned from array index
- Returns a typed result union instead of `null`, so callers can distinguish error kinds

### `toSloManifest`

```typescript
export function toSloManifest(slo: SloDefinition): string
```

Reconstructs a manifest YAML string from a `SloDefinition`. Used by:
- `SloYamlEditor` — populates the textarea on open
- `SloYamlViewer` — generates YAML for the `<pre>` display in history panel

Null metadata fields (`display_name`, `author`, `notes`) are emitted as empty strings, not
omitted. Objectives are emitted in `sort_order` order. Uses `js-yaml.dump()` with
`lineWidth: -1` to prevent unwanted line-wrapping of criteria strings.

Output format:

```yaml
api_version: tropek/v1
kind: SLO
metadata:
  name: http-availability-slo
  display_name: HTTP Availability SLO
  author: bootstrap
  notes: ""
spec:
  total_score:
    pass_pct: 90.0
    warning_pct: 75.0
  comparison: {}
  objectives:
    - sli: response_time_p99
      display_name: "Response Time P99"
      pass_criteria: ["<500"]
      warning_criteria: ["<800"]
      weight: 2
      key_sli: false
```

### Test file

`lib/parseSloYaml.test.ts` is deleted. `lib/sloManifest.test.ts` covers:
- Valid single-document parse → correct structured output
- Multi-document input → `{ kind: 'multi_document' }` error
- Missing required fields → `{ kind: 'invalid_structure' }` error
- Round-trip: `parseSloManifest(toSloManifest(slo))` produces equivalent objectives

---

## Section 3: Components

### `SloYamlUpload.tsx`

- Calls `parseSloManifest` (from `lib/sloManifest.ts`) instead of the old parser
- Multi-document error → shows "Multi-document files are not supported — upload one SLO at a time"
- Other parse errors → show the error message from the result
- Preview shows structured content: objectives table, score thresholds, comparison block
- On save: calls `createSloDefinition` with structured fields extracted from `ParsedSloManifest`

### `SloYamlEditor.tsx` (Raw Edit tab — round-trip)

- On open: calls `toSloManifest(slo)` to populate the textarea from the current structured definition
- On save: calls `parseSloManifest(editedText)`:
  - Parse error → show error, do not submit
  - Success → call `validateSlo(parsed)`, show validation errors if any
  - Valid → call `createSloDefinition` with structured fields (creates a new version)

### `SloYamlViewer.tsx`

- Prop changes: `sloYaml: string` → `slo: SloDefinition`
- Calls `toSloManifest(slo)` internally to produce the string for the `<pre>` block
- No other behavioral changes

### `SloHistoryPanel.tsx`

- Passes full `SloDefinition` version objects to the updated `SloYamlViewer`
- No other changes required

### `SloObjectiveTable.tsx`

- Reads `obj.pass_criteria` (flat `string[]`) directly instead of `obj.pass[0].criteria`
- Same for `warning_criteria`

### `SloObjectiveEditor.tsx`

- Objective form state uses flat `pass_criteria`/`warning_criteria` arrays
- Submits structured fields to `createSloDefinition` instead of rebuilding YAML

### `SloCreateForm.tsx`

- Drops the YAML-building step before submission — submits structured fields directly
- The "paste YAML" tab calls `parseSloManifest` instead of the old parser
- Internal form state uses flat `pass_criteria`/`warning_criteria`

### Pages

`SloRegistryPage.tsx` and `EvaluationDetailPage.tsx` — no structural changes. Both consume
`SloDefinition` and `SloObjective` which update transparently via the type changes.

---

## Section 4: Mocks

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
| `lib/parseSloYaml.ts` | Delete |
| `lib/parseSloYaml.test.ts` | Delete |
| `lib/sloManifest.ts` | Create |
| `lib/sloManifest.test.ts` | Create |
| `features/slos/components/SloYamlUpload.tsx` | Update |
| `features/slos/components/SloYamlEditor.tsx` | Update |
| `features/slos/components/SloYamlViewer.tsx` | Update |
| `features/slos/components/SloHistoryPanel.tsx` | Update |
| `features/slos/components/SloObjectiveTable.tsx` | Update |
| `features/slos/components/SloObjectiveEditor.tsx` | Update |
| `features/slos/components/SloCreateForm.tsx` | Update |
| `mocks/data/slo-definitions.json` | Update |
| `mocks/handlers/slos.ts` | Update |
| `pages/SloRegistryPage.tsx` | No change |
| `pages/EvaluationDetailPage.tsx` | No change |
