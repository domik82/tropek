# TROPEK API Extensions & UI Alignment

**Date:** 2026-03-15
**Status:** Draft
**Scope:** API extensions for SLO validation/testing, trend-by-eval-id, time-range filters.
UI alignment to match real API paths, fields, and response shapes.
**Depends on:** `2026-03-14-api-layer-crud-design.md` (CRUD endpoints),
`2026-03-14-tropek-domain-redesign.md` (domain model)
**Supersedes:** Nothing — additive to existing specs.

---

## 1. Background

The UI was built with MSW mocks that diverge from the real API in three ways:

1. **URL paths** — UI uses `/api/slos`, API uses `/slo-definitions`
2. **Field names** — UI uses `start`/`end`, API uses `period_start`/`period_end`
3. **Missing endpoints** — UI needs SLO validation, SLO testing, and trend-by-eval-id

This spec defines four API additions and a comprehensive UI realignment. The guiding
principle is **clean API, adjust UI** — the API should not expose unusual endpoints or
response shapes to accommodate mock assumptions.

---

## 2. API Extension 1 — Trend by Evaluation ID

### Problem

The UI's evaluation detail page already calls `fetchTrend(evalId, metric)` — it
passes `eval_id` as a query parameter. The current API trend endpoint only accepts
`asset_name + slo_name + metric`, so this UI calling convention has no backend support.

### Solution

Add `eval_id` as an alternative entry point to `GET /trend`. The API resolves
`asset_id` and `slo_name` from the evaluation record internally. This fills in the
existing UI contract rather than creating a new one.

```
GET /trend?eval_id={uuid}&metric={name}&limit=50
GET /trend?asset_name={name}&slo_name={name}&metric={name}&limit=50
```

**Validation:** Exactly one of `eval_id` or `(asset_name + slo_name)` must be provided.
If both or neither are present, return 422.

**Implementation:** When `eval_id` is provided, load the evaluation via
`EvaluationRepository.get_by_id()`, extract `asset_id` and `slo_name`, then delegate
to the existing `get_trend_by_domain()` method.

**Schema change in `quality_gate/router.py`:**

```python
@router.get("/trend", response_model=list[TrendPoint])
async def get_trend(
    metric: str,
    eval_id: uuid.UUID | None = None,
    asset_name: str | None = None,
    slo_name: str | None = None,
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[TrendPoint]:
```

---

## 3. API Extension 2 — Time-Range Filters on Evaluations

### Problem

The UI filters evaluations by day (heatmap column = one date) and by exact timestamp
(clicking a heatmap cell = one time slot). The API supports `date` prefix filtering
but has no way to filter by precise time range.

### Solution

Add `from` and `to` query parameters (ISO 8601 timestamps) to `GET /evaluations`.
The existing `date` prefix filter remains for convenience.

```
GET /evaluations?group_name=monthly-lab&date=2026-03-01
GET /evaluations?group_name=monthly-lab&from=2026-03-01T18:00:00Z&to=2026-03-01T18:45:00Z
```

**Implementation:** Add two optional datetime parameters to `list_with_counts()`:

```python
if from_ts:
    q = q.where(Evaluation.period_start >= from_ts)
if to_ts:
    q = q.where(Evaluation.period_start <= to_ts)
```

`date` and `from/to` are mutually exclusive — return 422 if both provided.

**UI mapping:** The current mock `slot` parameter becomes `from` + `to` in the real API.
For exact-timestamp slot filtering, the UI sends a 1-second window:
`from=2026-03-01T18:00:00Z&to=2026-03-01T18:00:01Z`. The API compares at full
timestamp precision — it does not truncate to seconds.

---

## 4. API Extension 3 — SLO YAML Validation

### Problem

The SLO editor needs server-side validation before saving. The UI currently validates
client-side via `parseSloYaml.ts`, but server-side validation catches additional errors:
indicator names referencing non-existent SLI definitions, invalid criteria syntax, etc.

### Endpoint

```
POST /slo-definitions/validate
```

**Request:**

```python
class SLOValidateRequest(BaseModel):
    slo_yaml: str
```

**Response:**

```python
class SLOValidationError(BaseModel):
    field: str       # e.g. "objectives[2].pass[0].criteria"
    message: str     # e.g. "invalid operator in criteria string '>>5'"

class SLOValidationResult(BaseModel):
    valid: bool
    errors: list[SLOValidationError]
    objectives: list[dict[str, Any]] | None = None  # parsed objectives if valid
    # Serialised as dicts (not SLOObjective) because the engine models are internal.
    # The UI's existing SloObjective TypeScript interface is compatible with this shape.
```

**Validation steps:**

1. Parse YAML syntax — catch `yaml.YAMLError`
2. Parse SLO structure via `slo_parser.parse_slo()` — catch `SLOParseError`
3. Validate all criteria strings via `criteria.parse_criteria_string()` — catch parse errors
4. Validate total_score percentages are 0–100
5. Return parsed objectives on success (so UI can preview the structure)

**Note:** This endpoint does NOT check whether referenced indicator names exist in any
SLI definition. That cross-entity validation happens at evaluation trigger time when
the SLO+SLI binding is resolved. The validate endpoint is purely about SLO YAML
structural correctness.

**Route ordering:** Register `POST /slo-definitions/validate` before
`GET /slo-definitions/{name}` to prevent FastAPI from matching `"validate"` as a name
path parameter.

---

## 5. API Extension 4 — SLO Test (Dry-Run Evaluation)

### Problem

Users need to verify that a new or modified SLO produces sensible results before
deploying it. This means: fetching real metrics from an adapter, evaluating them
against the SLO criteria, and showing the result — without persisting anything.

The challenge is relative criteria (`<=+10%`) which require baseline values from
previous evaluations. A new SLO has no history.

### Endpoint

```
POST /slo-definitions/test
```

**Request:**

```python
class BaselineConfig(BaseModel):
    mode: Literal["none", "asset_history", "manual"]
    # asset_history mode: fetch last N completed evals for this asset
    limit: int = 3
    # manual mode: user-provided baseline values
    values: dict[str, float] | None = None  # metric_name → baseline value

class SLOTestRequest(BaseModel):
    slo_yaml: str
    sli_name: str                 # SLI definition — always resolves to latest active version
    data_source_name: str         # which adapter to query
    asset_name: str               # target asset (provides $variables)
    period_start: datetime
    period_end: datetime
    baseline: BaselineConfig | None = None  # default: no baseline
    metadata: dict[str, str] = Field(default_factory=dict)  # additional $variable substitutions
```

**Response:**

```python
class SLOTestResult(BaseModel):
    result: str                      # pass | warning | fail | error
    score: float                     # 0.0–100.0
    indicator_results: list[IndicatorResult]  # reuses quality_gate IndicatorResult schema
    baseline_mode: str               # "none" | "asset_history" | "manual"
    metrics_fetched: dict[str, float]    # raw values from adapter
    fetch_errors: dict[str, str]         # metric_name → error message (partial results OK)
    compared_values: dict[str, float] | None  # resolved baseline values used
```

### Execution Flow

1. **Validate** SLO YAML via `parse_slo()`
2. **Resolve SLI** — fetch latest active version of `sli_name` from `SLIRepository`
3. **Resolve DataSource** — fetch `data_source_name` from `DataSourceRepository`
4. **Resolve Asset** — fetch asset by name, build variable dict (`$asset_name`,
   `$vm_ip` from labels, `$period_start`, `$period_end`, + caller metadata)
5. **Substitute variables** in SLI queries via `variables.substitute_variables()`
6. **Query adapter** — POST to `adapter_url/query` with resolved queries
7. **Resolve baselines** based on mode:
   - `none` → empty baselines (relative criteria get status `info`)
   - `asset_history` → `EvaluationRepository.get_baselines()` for this asset
   - `manual` → construct synthetic single-evaluation baseline from provided values
8. **Evaluate** via `evaluator.evaluate(slo_yaml, metrics, baselines)`
9. **Return result** — no DB write, no SLI values stored, no cache update

### Baseline Modes Explained

**`none` (default):** First-evaluation semantics. Fixed criteria (`<600`, `=0`) are
evaluated normally. Relative criteria (`<=+10%`) produce status `info` with a message
"no baseline available". This is how the engine already behaves when baselines are empty.

**`asset_history`:** Fetches the last `limit` completed, non-invalidated evaluations
for this asset + SLO combination. Uses them exactly as real evaluations do — aggregate
function (avg, p90, etc.) applied per the SLO's `comparison` block. Requires that the
asset has previous evaluation history.

**`manual`:** User provides a dict of `{metric_name: value}`. These values are wrapped
into a synthetic baseline structure that the engine treats as a single previous
evaluation. Relative criteria are evaluated against these values. Missing metrics
in the dict produce status `info` for that indicator.

### Error Handling

| Error | Status | Message |
|---|---|---|
| Invalid SLO YAML | 422 | Validation errors (same as `/validate`) |
| SLI definition not found | 404 | `"sli definition '{name}' not found"` |
| DataSource not found | 404 | `"data source '{name}' not found"` |
| Asset not found | 404 | `"asset '{name}' not found"` |
| Adapter unreachable | 502 | `"could not reach adapter at {url}"` |
| Adapter query timeout | 504 | `"adapter query timed out after {n}s"` |
| Partial adapter failure | 200 | Result returned with `fetch_errors` populated |

### Not Persisted

The test endpoint writes nothing to the database. No `Evaluation` record, no
`SLIValue` rows, no cache entries. The result exists only in the HTTP response.

---

## 6. UI Path & Field Alignment

All changes below are in the UI codebase (`ui/src/`). The API does not change — the
UI adapts to match the real API contract.

### 6.1 URL Path Changes

| UI File | Current Path | Target Path |
|---|---|---|
| `features/slos/api.ts` | `GET /api/slos` | `GET /api/slo-definitions` |
| `features/slos/api.ts` | `GET /api/slos/{name}` | `GET /api/slo-definitions/{name}` |
| `features/slos/api.ts` | `POST /api/slos` | `POST /api/slo-definitions` |
| `features/slos/api.ts` | `DELETE /api/slos/{name}` | `DELETE /api/slo-definitions/{name}` |
| `features/slos/api.ts` | `GET /api/slos/{name}/versions` | `GET /api/slo-definitions/{name}/versions` |
| `features/slos/api.ts` | `POST /api/slos/validate` | `POST /api/slo-definitions/validate` |
| `features/assets/api.ts` | `GET /api/asset-groups` | `GET /api/asset-groups/tree` |

### 6.2 Field Name Changes in `features/evaluations/types.ts`

**`EvaluationSummary`:**

| Current Field | Target Field | Notes |
|---|---|---|
| `start: string` | `period_start: string` | Matches API |
| `end: string` | `period_end: string` | Matches API |
| `metadata?: Record<string, string>` | `evaluation_metadata: Record<string, string>` | Matches API column name |
| `asset_snapshot.tags` | `asset_snapshot.tags` | Keep as `tags` — see note below |
| missing | `sli_name: string \| null` | New field from domain redesign |
| missing | `sli_version: number \| null` | New field from domain redesign |
| missing | `data_source_name: string \| null` | New field from domain redesign |

**`EvaluationDetail`** inherits all renames above. Additionally:

| Current Field | Target Field | Notes |
|---|---|---|
| `metadata: Record<string, string>` | `evaluation_metadata: Record<string, string>` | Same rename as parent, but required (not optional) |

**`asset_snapshot.tags` vs `labels`:** The Asset model was renamed from `tags` to
`labels` in the domain redesign. However, `asset_snapshot` is a JSONB snapshot captured
at evaluation trigger time. The snapshot key is `tags` in all existing data. New
evaluations will also write `tags` into the snapshot (the snapshot format is independent
of the Asset model — it captures what was relevant at trigger time, including OS, arch,
lab, etc.). The UI reads `asset_snapshot.tags` and this does not need to change.

**`FailingIndicator`:**

| Current Field | Target Field | Notes |
|---|---|---|
| `unit: string` | (remove) | Not in API response |

**`Annotation`:**

| Current Field | Target Field | Notes |
|---|---|---|
| `link?: { href, label }` | (remove) | Not in API response; UI can derive links from `meta` |

**`EvaluationFilters`:**

| Current Field | Target Field | Notes |
|---|---|---|
| `lab?: string` | `group_name?: string` | Matches API param |
| `slot?: string` | `from?: string; to?: string` | See Section 3 |

**`TriggerEvaluationPayload`:**

| Current Field | Target Field | Notes |
|---|---|---|
| `asset_group: string` | `group_name: string` | Matches API |
| `start: string` | `period_start: string` | Matches API |
| `end: string` | `period_end: string` | Matches API |

### 6.3 Response Shape Changes

**`fetchEvaluations()`:** Currently returns `EvaluationSummary[]`. The real API returns
`PagedResponse<EvaluationSummary>` — `{ items: [...], total: N }`. The UI must
unwrap `.items` from the response.

**`invalidateEvaluation()`:** Two mismatches:
- **Request body:** UI sends `{ note }`, API expects `{ invalidation_note }`.
  Change UI to send `{ invalidation_note: note }`.
- **Response:** UI expects `{ id, invalidated }`, API returns full `EvaluationSummary`.
  Change UI to accept the full response and extract what it needs.

**`uploadSloYaml()`:** Currently sends `{ yaml }`. The real API expects
`SLODefinitionCreate` — `{ name, slo_yaml, display_name?, notes?, author?, meta? }`.
The UI must extract `name` from the YAML (already parsed client-side) and send the
structured payload.

### 6.4 SLO Type Changes in `features/slos/types.ts`

**`SloDefinition`:**

| Current Field | Notes |
|---|---|
| `sli_queries?: SliQuery[]` | Remove — not returned by API. Fetch SLI separately. |
| `objectives?: SloObjective[]` | Remove — parse from `slo_yaml` client-side. |
| `score_thresholds?: SloScoreThresholds` | Remove — parse from `slo_yaml` client-side. |

The API returns `SLODefinitionRead` which has `slo_yaml` as raw text. The UI parses
YAML client-side (via existing `lib/parseSloYaml.ts`) to derive objectives and
thresholds for display. This keeps the API clean — it stores YAML, does not
interpret it for read endpoints.

**New `SliDefinition` type** (add to `features/slos/types.ts` or new `features/slis/types.ts`):

```typescript
interface SliDefinition {
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
```

---

## 7. SLI CRUD from SLO Editor

### Problem

When editing an SLO, users need to view and modify the SLI queries referenced by
the SLO objectives. The SLI definitions are separate entities with their own CRUD
endpoints. The UI must wire the SLO editor to call SLI endpoints.

### UI Flow

**Viewing SLO detail:**
1. `GET /slo-definitions/{name}` → get SLO with raw YAML
2. Parse YAML client-side → extract objective `sli_name` references
3. `GET /sli-definitions/{sli_name}` → fetch linked SLI to show queries alongside objectives

**Editing SLI from SLO editor:**
1. User clicks "Edit Queries" on an SLI referenced by the SLO
2. UI shows indicator query editor (metric_name → query_string pairs)
3. On save: `POST /sli-definitions` with updated indicators → creates new version
4. SLO itself unchanged (it references by name, always resolves to latest version)

**Creating new SLI:**
1. User clicks "New SLI Definition" in the SLO editor
2. Enters name, adds indicator queries
3. `POST /sli-definitions` → creates version 1
4. User references the new SLI name in SLO objectives

**Browsing available SLIs (template picker):**
1. `GET /sli-definitions` → list all active SLI definitions
2. User picks indicators from existing definitions to populate SLO objectives
3. UI pre-fills objective rows with `sli_name` values from the selected SLI

**Deleting SLI:**
1. `DELETE /sli-definitions/{name}` → soft-deactivates all versions
2. UI warns if any active SLO references this SLI name (check client-side by
   comparing SLO objective `sli_name` values against the SLI being deleted)

### New UI API Functions

```typescript
// features/slis/api.ts (new file)
fetchSliDefinitions(): Promise<PagedResponse<SliDefinition>>   // GET /api/sli-definitions
fetchSliDetail(name: string): Promise<SliDefinition>            // GET /api/sli-definitions/{name}
createSliDefinition(payload: SliDefinitionCreate): Promise<SliDefinition>  // POST /api/sli-definitions
deleteSliDefinition(name: string): Promise<void>                // DELETE /api/sli-definitions/{name}
fetchSliVersions(name: string): Promise<SliDefinition[]>        // GET /api/sli-definitions/{name}/versions
```

### No API Changes

The SLI CRUD endpoints already exist. All work is on the UI side.

---

## 8. SLO Test UI Flow

### Test Modal

Triggered from the SLO editor/detail page via "Test SLO" button.

**Form fields:**
1. **Asset** — select from `GET /assets` (required)
2. **Data Source** — select from `GET /datasources` (required)
3. **SLI Definition** — select from `GET /sli-definitions` (required)
4. **Time Window** — start/end datetime pickers (required)
5. **Baseline Mode** — radio group:
   - "No baseline (first run)" — default
   - "Use asset history (last N runs)" — number input for N
   - "Manual baseline values" — shows row per indicator from SLO, user fills values

**On submit:** `POST /slo-definitions/test` with the form data.

**Result display:** Inline panel showing:
- Overall result badge (pass/warning/fail) + score
- Per-indicator table (same component as `SLIBreakdownTable`)
- For `info` status indicators: grey badge with "no baseline" tooltip
- `fetch_errors` shown as warning banners per metric
- "Re-test" button to iterate on thresholds

### Iteration Workflow

1. User writes/edits SLO YAML
2. Clicks "Validate" → `POST /slo-definitions/validate` → fix errors
3. Clicks "Test" → fills test modal → `POST /slo-definitions/test`
4. Reviews results → adjusts thresholds → re-tests
5. Satisfied → "Save" → `POST /slo-definitions` (creates new version)

---

## 9. MSW Mock Updates

All MSW handlers in `ui/src/mocks/handlers/` must be updated to match the real API
contract so that development mode continues to work correctly.

### Handler Changes

**`handlers/evaluations.ts`:**
- `GET /api/evaluations` → accept `group_name`, `from`, `to` params (not `lab`, `slot`)
- `PATCH /api/evaluations/:id/invalidate` → accept `{ invalidation_note }` (not `{ note }`)
- Response wrapped in `{ items: [...], total: N }`

**`handlers/slos.ts`:**
- All paths change from `/api/slos/*` to `/api/slo-definitions/*`
- `POST /api/slo-definitions/validate` → use `parseSloYaml.ts` for validation
- `POST /api/slo-definitions` → accept structured `SLODefinitionCreate` payload
- Add `POST /api/slo-definitions/test` → return mock test result

**`handlers/assets.ts`:**
- `GET /api/asset-groups` → `GET /api/asset-groups/tree`
- Add `GET /api/assets` → return `{ items: [...], total: N }` (currently returns bare array)

**New `handlers/slis.ts`:**
- `GET /api/sli-definitions` → return mock SLI definitions from fixture data
- `GET /api/sli-definitions/{name}` → single SLI lookup
- `POST /api/sli-definitions` → create new version
- `DELETE /api/sli-definitions/{name}` → soft-delete

### Mock Data Changes

**`mocks/generate.ts`:**
- Evaluation summaries use `period_start`/`period_end` (not `start`/`end`)
- `evaluation_metadata` (not `metadata`)
- Remove `unit` from `FailingIndicator`
- Remove `link` from `Annotation`
- Add `sli_name`, `sli_version`, `data_source_name` to summaries

**`mocks/data/slo-definitions.json`:**
- Remove embedded `sli_queries` — SLI data moves to a new `sli-definitions.json` fixture
- Remove embedded `objectives` and `score_thresholds` — UI parses from `slo_yaml`
- Match `SLODefinitionRead` shape: `{ id, name, display_name, version, slo_yaml, notes, author, meta, active, created_at }`

**New `mocks/data/sli-definitions.json`:**
- Extract indicator queries from the old SLO fixtures into standalone SLI definitions
- Match `SLIDefinitionRead` shape

---

## 10. Summary of All Changes

### API Changes (4 items)

| # | Change | File | Type |
|---|---|---|---|
| 1 | `GET /trend` accepts `eval_id` as alternative | `quality_gate/router.py` | Extend endpoint |
| 2 | `GET /evaluations` accepts `from`/`to` params | `quality_gate/router.py`, `repository.py` | Extend endpoint |
| 3 | `POST /slo-definitions/validate` | `slo_registry/router.py`, `schemas.py` | New endpoint |
| 4 | `POST /slo-definitions/test` | `slo_registry/router.py`, `schemas.py` | New endpoint |

### UI Changes

| # | Change | Files |
|---|---|---|
| 1 | SLO paths `/api/slos/*` → `/api/slo-definitions/*` | `features/slos/api.ts`, `mocks/handlers/slos.ts` |
| 2 | Asset groups path → `/api/asset-groups/tree` | `features/assets/api.ts`, `mocks/handlers/assets.ts` |
| 3 | Field renames: `start`→`period_start`, `end`→`period_end`, etc. | `features/evaluations/types.ts`, all consuming components |
| 4 | Filter params: `lab`→`group_name`, `slot`→`from`+`to` | `features/evaluations/types.ts`, `api.ts`, heatmap components |
| 5 | Response unwrapping: `PagedResponse` → `.items` | `features/evaluations/api.ts`, `features/slos/api.ts`, `features/assets/api.ts` |
| 6 | SLO create structured payload | `features/slos/api.ts` |
| 7 | Remove mock-only fields (`unit`, `link`, embedded SLI queries) | `features/evaluations/types.ts`, `features/slos/types.ts` |
| 8 | New SLI CRUD API + types + hooks | `features/slis/` (new module) |
| 9 | SLO editor → SLI picker + inline SLI editing | `features/slos/components/` |
| 10 | SLO test modal | `features/slos/components/SloTestModal.tsx` (new) |
| 11 | MSW mock handlers updated to match real API | `mocks/handlers/*.ts`, `mocks/generate.ts` |

---

## 11. What This Spec Does NOT Cover

- `POST /evaluations` evaluation trigger — separate spec (chunk 4/5 plans)
- Worker module implementation — separate spec
- Prometheus adapter `/query` endpoint — separate spec (chunk 6 plan)
- Evaluation batch trigger and status — deferred
- Redis caching layer — deferred
- Authentication / authorization — deferred
