# Schemathesis Phase 3 — handoff for next session

## Current state

- Branch: `feat/contract-testing-phase-3-schemathesis`
- Schemathesis: **60 passed / 41 failed** (up from 11/90 on first run)
- Integration tests: **265/265 passing**
- Fix commits landed: `f154179`, `bc3c02f`, `20e74c9`, `411d0e0`, `789e3f3`, `42d64da`, `05b839f`
- Uncommitted: nothing; tree clean on the branch

Residual failure breakdown (approximate, from last run):
- ~24 `RejectedPositiveData` — cross-field validators (design smell)
- ~4 `UndefinedStatusCode` — stray codes the post-processor didn't predict
- ~3 `AcceptedNegativeData` — bool/int coercion elsewhere (apply `StrictBool` per-field)
- ~10 scattered (assignments, display-groups)

The full triage narrative lives in `reports/schemathesis-triage.md`.
This file captures only the **design decisions** we reached in conversation,
so the next session can execute without re-deriving them.

## Design decisions reached

Schemathesis flagged four classes of cross-field drift. We classified each one
and decided how to fix it:

| # | Area | Verdict | Reason |
|---|---|---|---|
| 1 | `POST /evaluations/re-evaluate` — `exactly_one_scope` (from_date / from_baseline / from_evaluation_id) | **Split into multiple endpoints** | The three scopes are a closed, server-implemented set. Each scope is conceptually a different operation. URL-level split removes the validator, self-documents, simplifies clients + tests + auth + metrics. |
| 2 | `GET /trend` — `eval_id XOR (asset_name + slo_name)` | **Split into multiple endpoints + bake time range into URL** | Same reasoning as (1); PLUS the user needs permalink-style URLs that include the time range so they can be shared with colleagues (Grafana-style). |
| 3 | `POST /sli-definitions` — `validate_mode_fields` (adapter-specific fields) | **Keep single endpoint, schemathesis-exclude this operation** | Adapters are an OPEN plugin registry (discovered at runtime, grown by dropping new adapter services into docker-compose). Promoting `adapter_type` to the URL would hardcode a plugin list into the core API. The per-adapter config validation is correctly behind the plugin boundary — out-of-band by design, not schema drift. |
| 4 | `POST /meta/snapshots` — per-list uniqueness by path | **`json_schema_extra={'uniqueItems': True}` where applicable** | `closed[]` items are single-field (`{path: [...]}`) so whole-item equality works — declare it in schema. `values[]` items have an extra `value` field so `uniqueItems` doesn't help there — schemathesis-exclude or leave as known drift. |

## The grafana-style URL requirement (new)

The user wants to paste an evaluation-detail URL to a colleague such that
**the URL alone** fully reproduces the view, including the time range.
Equivalent to Grafana dashboard permalinks: `?from=...&to=...` in the URL,
shareable, bookmarkable, reload-safe.

Implication for (2) above: the refactor is not just "split by lookup kind,"
it should also **accept the time range as URL parameters (query or path)**,
not only as body/state. A date picker in the UI mutates the URL; the URL
drives the fetch.

Proposed shapes (to validate next session — don't just implement blind):

```
# By specific evaluation (single point in time, already permalinkable via id)
GET /evaluations/{eval_id}/trend
    ?from=2026-03-01T00:00:00Z&to=2026-03-07T00:00:00Z

# By (asset, slo) pair (what the sidebar tree navigates)
GET /assets/{name}/slos/{slo_name}/trend
    ?from=2026-03-01T00:00:00Z&to=2026-03-07T00:00:00Z

# Maybe needed: by asset-group + slo
GET /asset-groups/{name}/slos/{slo_name}/trend
    ?from=...&to=...
```

Time range: query params `from` / `to` as RFC-3339 UTC (AwareDatetime in
Pydantic). No relative shortcuts like `now-7d` for v1 — keep the URL
content-addressable. Relative shortcuts can live in the UI and resolve to
absolute timestamps before navigating.

## Concrete next-session plan

In priority order:

### 1. `GET /trend` redesign + time-range-in-URL
- Grep for every caller: UI (`features/evaluations/trend*`), scripts, tests.
- Design the new URL shapes (above) — confirm with user.
- Implement as new routes; delete `GET /trend` outright (not shipped to
  third parties yet per the user's context).
- Migrate UI to read/write `from`/`to` on the URL via router state; date
  picker updates the URL, URL drives the query.
- Regen `api/openapi.json` + UI types; update layering-rule compliant code.
- Schemathesis should drop 2 operations' worth of failures.

### 2. `POST /evaluations/re-evaluate` split
- Three endpoints:
  - `POST /evaluations/re-evaluate/from-date` (body: asset_name, from_date, …)
  - `POST /evaluations/re-evaluate/from-baseline` (body: asset_name, …)
  - `POST /evaluations/re-evaluate/from-evaluation/{evaluation_id}` (body: …)
- This endpoint is already in `EXCLUDED_OPERATIONS` in the schemathesis
  harness, so the schemathesis win is zero — but the design win is real
  and should be done in the same pass so the exclusion can be removed.
- Drop the `exactly_one_scope` + `slo_name_and_names_mutually_exclusive`
  validators once split.

### 3. `meta/snapshots` `uniqueItems` on `closed[]`
- One-line change: `closed: list[MetaClosureInput] = Field(..., json_schema_extra={'uniqueItems': True})`
- Drops one schemathesis failure; the `values[]` one stays.

### 4. SLI definitions — schemathesis exclusion
- Add `POST /sli-definitions` to a new per-operation exclusion set in
  `tests/schemathesis/test_schema.py`, with a comment citing the open
  plugin registry rationale.
- NOT the same as `EXCLUDED_OPERATIONS` (which skips the whole test);
  use schemathesis config to exclude only the `positive_data_acceptance`
  check for this endpoint. All other checks stay active.

### 5. Assignments / display-groups residual failures
- Spot-check each one. Expected mix of: missing `uniqueItems`, missing
  `404`/`409` in the post-processor's heuristic (e.g. `DELETE /x/{id}/members/{sub}`
  has path params but maybe the sub-path isn't hit), and possibly more
  cross-field validators.
- Apply category-appropriate fix per the table above.

### 6. Residual `AcceptedNegativeData`
- Grep for remaining `bool` fields on request bodies, apply `StrictBool`.
- Same treatment for any `int` fields that accept string coercion where
  schemathesis flags it (`StrictInt`).

## Invariants to preserve

- `just test-int` must stay 265/265 after every change.
- Don't re-enable `strict=True` globally on `StrictInput` — it broke 35
  integration tests because UUID/datetime fields legitimately need string
  coercion from JSON clients. Apply strict per-field only.
- Mappers in the UI run at the fetch boundary (see CLAUDE.md UI layering
  section) — when URL shape changes, update `api.ts` and `mappers.ts`,
  not component code.
- `reports/schemathesis-triage.md` is the historical narrative; this file
  (`schemathesis-next-steps.md`) is the forward-looking plan. Keep them
  both; delete this one once every item above is landed.

## Files most likely to change next session

```
api/tropek/modules/quality_gate/router.py         # /trend, /re-evaluate routes
api/tropek/modules/quality_gate/schemas/re_evaluation.py
api/tropek/modules/asset_meta/schemas.py          # uniqueItems
api/tests/schemathesis/test_schema.py             # per-check exclusions
ui/src/features/evaluations/api.ts + mappers.ts   # trend URL shape
ui/src/features/evaluations/components/Trend*.tsx # URL <-> date picker
```

Regenerate after every API change:

```bash
uv run --directory api python scripts/export-schema.py
# UI codegen is currently broken (openapi-typescript not installed in
# ui node_modules on this worktree) — not blocking API work.
```

## What to read first when resuming

1. This file.
2. `reports/schemathesis-triage.md` — the fix log and residual categorisation.
3. `api/tropek/modules/quality_gate/router.py` — most of the remaining
   redesign surface lives here.
4. `git log feat/contract-testing-phase-3-schemathesis ^main --oneline` —
   see every fix that landed, in order.
