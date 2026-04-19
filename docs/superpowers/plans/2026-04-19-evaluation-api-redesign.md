# Evaluation API Redesign + Schemathesis Residual Fixes

Date: 2026-04-19
Branch: `feat/contract-testing-phase-3-schemathesis`
Supersedes: `2026-04-19-trend-and-reevaluate-url-split.md`

## Motivation

Schemathesis run (36 failures / 101 ops) surfaced both **schema drift** (fixable
with small per-field changes) and **architectural drift** (`/evaluate` vs
`/evaluations` namespaces, cross-field validators, inconsistent verb/noun use).

The two classes of work interact: fixing schema drift inside an incoherent URL
space just entrenches the incoherence. Fixing the URL space first makes the
residual schema work cleaner and the API corporate-adoptable.

This plan does both, in two phases:

- **Phase 1** — URL redesign (breaking, but in-repo consumers only)
- **Phase 2** — Field-level fixes (null-byte, StrictBool, uniqueItems, 405)

## Convention decisions (agreed)

1. **Collection endpoints use plural** — `/evaluations`, `/assets`, etc.
2. **Single-resource endpoints use singular** — `/evaluation/{id}/...` when
   operating on one resource. This is a deliberate departure from the more
   common "always plural" pattern (GitHub/Stripe style). Rationale: the path
   should read as a noun describing what's being addressed. "PATCH an
   evaluation" reads correctly as `PATCH /evaluation/{id}/invalidate`.
   "GET evaluation 123's trend" as `GET /evaluation/{id}/trend`.
3. **`re-evaluate`, not `replay`** — user pushback: "replay" implies repetition;
   "re-evaluate" means "do the evaluation scoring again" which is precisely
   what the operation does.
4. **No verb-namespace URLs** — `/evaluate` is gone. POSTs on
   `/evaluations` / sub-paths carry the "action" semantics via HTTP method +
   path suffix, not via a parallel verb-namespace.

## Non-goals

- Renaming single-resource endpoints in other modules (`/assets`, `/datasources`,
  `/slo-definitions`, etc.) — they're consistent today, skip for now.
- UI time-range-in-URL (Grafana permalink) — separate plan, but landing URL
  redesign unblocks it.
- Python SDK breaking-change version bump strategy — we update the SDK in
  lockstep since it's in-repo; real versioning discussion is out of scope.

---

## Phase 1: URL redesign

### Target URL map

```
# Collection — all plural, all nouns
GET    /evaluations                                 list
POST   /evaluations                                 trigger single (was POST /evaluate)
POST   /evaluations/batch                           trigger batch    (was POST /evaluate/batch)

# Bulk re-evaluate (one endpoint per scope, discriminated-union-free)
POST   /evaluations/re-evaluate/from-date           (was POST /evaluations/re-evaluate)
POST   /evaluations/re-evaluate/from-baseline       (was ...)
POST   /evaluations/re-evaluate/from-evaluation/{id} (was ...)

# Collection-level views
GET    /evaluations/heatmap                         grouped heatmap    (was /evaluate/metric-heatmap)
GET    /evaluations/heatmap/by-metric               per-metric heatmap (was /evaluations/metric-heatmap)
GET    /evaluations/names
GET    /evaluations/trend-annotations
GET    /evaluations/column-annotations

# Single-resource — SINGULAR
GET    /evaluation/{id}                             (was /evaluations/{eval_id})
GET    /evaluation/{id}/trend                       (was /trend?eval_id=...)
PATCH  /evaluation/{id}/invalidate                  (was /evaluations/{eval_id}/invalidate)
PATCH  /evaluation/{id}/restore
PATCH  /evaluation/{id}/pin-baseline
PATCH  /evaluation/{id}/unpin-baseline
PATCH  /evaluation/{id}/override-status
PATCH  /evaluation/{id}/restore-override
GET    /evaluation/{id}/annotations
POST   /evaluation/{id}/annotations
PATCH  /evaluation/{id}/annotations/{ann_id}
POST   /evaluation/{id}/annotations/{ann_id}/hide

# Run-level annotations (an EvaluationRun is a different resource)
POST   /evaluation-run/{run_id}/annotations         (was /evaluations/run/{run_id}/annotations)

# Trend by (asset, slo) — different root resource
GET    /assets/{name}/slos/{slo_name}/trend         (was /trend?asset_name=&slo_name=)
```

### What disappears

- `/evaluate` (entire verb-namespace)
- `/evaluate/batch`
- `/evaluate/metric-heatmap`
- `/evaluations/metric-heatmap` (renamed)
- `/evaluations/re-evaluate` (split into three)
- `/trend` (split into two)
- Every `/evaluations/{eval_id}/...` path with `{eval_id}` as URL segment
  moves to singular `/evaluation/{id}/...`

### Request/response body changes

- `ReEvaluateRequest` splits into three bodies:
  - `ReEvaluateFromDateRequest` — `{scope, selector, from_date}`
  - `ReEvaluateFromBaselineRequest` — `{scope, selector}`
  - `ReEvaluateFromEvaluationRequest` — `{scope, selector}` (eval id in path)
  - `scope` = `AssetScope | GroupScope` (discriminated union, `kind` field)
  - `selector` = `SloSelector | EvalNamesSelector` (discriminated union)
- Both `@model_validator`s on `ReEvaluateRequest` deleted.
- `EvaluateSingleRequest` and `EvaluateBatchRequest` stay as-is; only the URL
  changes. (Revisit if Phase 2 finds cross-field issues there.)
- Query-string aliases stay: `from` / `to` (not `from_ts` / `to_ts`).

### Files to touch (Phase 1)

Backend:

- `api/tropek/modules/quality_gate/router.py` — every route above
- `api/tropek/modules/quality_gate/schemas/re_evaluation.py` — split + unions
- `api/tropek/modules/quality_gate/workflows/re_evaluation/re_evaluation_service.py` — accept parsed scope/selector instead of `ReEvaluateRequest`
- `api/tropek/main.py` — `_custom_openapi()` path-iteration still works, just verifies
- `api/tests/quality_gate/test_router.py` — delete 4 trend cross-field tests; update all paths
- `api/tests/quality_gate/endpoints/test_annotation_endpoints.py` — update paths
- `api/tests/quality_gate/workflows/**/test_*.py` — update URL references
- `api/tests/schemathesis/test_schema.py` — update `EXCLUDED_OPERATIONS` entries
- `api/tests/test_schema_contracts.py:374-388` — update path refs
- `api/openapi.json` — regen via `uv run --directory api python scripts/export-schema.py`

UI:

- `ui/src/features/evaluations/api.ts` — every `fetch()` URL
- `ui/src/features/evaluations/hooks.ts` — query keys may include path
- `ui/src/mocks/handlers/evaluations.ts` — every `http.<verb>(PATH, ...)` path
- `ui/src/mocks/generate.ts` — fixture helpers (only if URL is baked in)
- `ui/src/generated/api.ts` — regen via `just codegen` if available; otherwise
  flag as follow-up per `reports/schemathesis-next-steps.md`
- Component tests referencing URLs (search for `/evaluate`, `/evaluations/`,
  `/trend`)

SDK:

- `clients/python/tropek_client/client.py` — every method that builds a URL
  under `/evaluate*`, `/evaluations/*`, `/trend*`, `/re-evaluate`
- `clients/python/tests/*.py` if present

### Migration sequence (single branch, staged commits)

1. **Add new routes alongside old** — both old and new respond with the same
   handler. Zero downtime; every integration test still passes.
2. **Switch UI to new routes** — atomic commit. Run UI tests + dev server
   smoke test.
3. **Switch Python SDK to new routes** — atomic commit.
4. **Switch integration tests to new routes** — atomic commit.
5. **Delete old routes** — final cleanup commit.
6. **Regen `openapi.json`** — last.

Commits 1-5 each keep `just test-int` at 265/265. Commit 5 also flips the
`/evaluations/re-evaluate` schema split (cross-field validators deleted) and
the `/trend` disappearance — schemathesis failures drop here.

### Phase 1 schemathesis impact

Failures eliminated by Phase 1 alone:
- `GET /trend` (cross-field) → split into 2 clean routes
- `POST /evaluations/re-evaluate` (cross-field) → split into 3 clean routes,
  plus discriminated unions remove the `slo_name`/`evaluation_names` and
  `asset_name`/`group_name` cross-field checks

Expected: 36 → ~32 failures after Phase 1. The architectural cleanup is
the main deliverable; the numeric win is modest.

---

## Phase 2: Field-level fixes (high-leverage, cheap)

Phase 2 is where the bulk of the schemathesis numeric win comes from. Each
item is small; sequenced by leverage.

### 2a. Null-byte (`\x00`) rejection — biggest single lever (~15 failures)

**Root cause:** Pydantic's default `str` accepts `\x00`. Downstream:
- asyncpg raises `CharacterNotInRepertoireError` on insert → 500
- Starlette's JSON body parser chokes on raw `\x00` in input bytes → 400
  "There was an error parsing the body" (undocumented status)

**Fix:** Introduce a reusable Pydantic validator type that rejects null bytes:

```python
from typing import Annotated
from pydantic import AfterValidator

def _reject_null_bytes(v: str) -> str:
    if '\x00' in v:
        raise ValueError('null bytes are not allowed')
    return v

SafeStr = Annotated[str, AfterValidator(_reject_null_bytes)]
```

Apply to every user-provided string field on request bodies and to every
string query parameter that reaches the DB. Conservative grep target:
schemas files + query-param declarations on any endpoint that surfaced a
null-byte failure.

Endpoints affected (will pass after fix):
`POST /assets`, `PATCH /assets/{name}`, `POST /datasources`,
`PATCH /datasources/{name}`, `POST /sli-definitions`,
`POST /note-categories`, `PATCH /evaluation/{id}/annotations/{ann_id}`,
`GET /assets?type_name=...`, `GET /{sli,slo,assets,datasources}*/tag-values`,
`GET /slo-groups?tag_key=...`, `GET /sli-definitions`,
`GET /evaluations/names`, `GET /evaluations/trend-annotations`,
`GET /evaluations/column-annotations`.

### 2b. `StrictBool` / `StrictInt` per field — 5 failures

Apply per-field (never globally — broke 35 integration tests last time):

- `AssetTypeCreate.is_default: StrictBool`
- `AssetGroupCreate.subgroups[].weight: StrictInt`
- `SLODefinitionCreate.sli_version: StrictInt`
- `SLODefinitionValidateRequest.comparison.number_of_comparison_results: StrictInt`
- `SLODisplayGroupCreate.sort_order: StrictInt`

### 2c. `uniqueItems` on closed-set arrays — 1 failure

`MetaSnapshotCreate.closed: list[MetaClosureInput]` — items are single-field
(`{path: [...]}`) so whole-item equality works. Add
`json_schema_extra={'uniqueItems': True}`.

`MetaSnapshotCreate.values[]` can't use this (items have a second `value`
field) — leave as residual, or schemathesis-exclude.

### 2d. `MethodNotAllowedMiddleware` — 1 failure

`DELETE /slo-definitions/{name}/versions` returns 404 instead of 405.
Current middleware snapshots literal paths; extend to handle this templated
sibling collision.

### 2e. Residual cross-field validators — case-by-case

Remaining `RejectedPositiveData` after Phase 1 + 2a:

- `GET /assets/{id}/meta/timeline` + `/summary` — need to read the validator
- `POST /evaluate`, `POST /evaluate/batch` — need to read the validator
- `GET /evaluations/heatmap` / `/heatmap/by-metric` — need to read
- `POST /slo-groups` — need to read
- `POST /sli-definitions` — adapter-dependent fields (OPEN plugin registry)
  → schemathesis-exclude `positive_data_acceptance` for this op only
- `PATCH /asset-types/{name}` — empty-body PATCH behavior — investigate

Each gets a judgment call: URL split, schema annotation, or targeted
exclusion. Not batched — resolve individually after Phase 2a-d are in.

### 2f. `UndefinedStatusCode` cleanup — ~2 residual failures

After 2a eliminates null-byte-induced 400s, residual undocumented statuses
are real documentation gaps. Add to `_custom_openapi()` or to per-route
`responses=...`.

### Expected trajectory

- Phase 1 only: 36 → ~32
- Phase 1 + 2a (null-byte): ~32 → ~15
- Phase 1 + 2a + 2b (StrictBool/Int): ~15 → ~10
- Phase 1 + 2a + 2b + 2c (uniqueItems): ~10 → ~9
- Phase 1 + 2a + 2b + 2c + 2d (405 middleware): ~9 → ~8
- Phase 2e (case-by-case): targets the residual ~8 individually

---

## Invariants

- `just test-int` → 265/265 after every commit (Phase 1 migration sequence
  makes this non-trivial; stage commits so each is green).
- Never re-enable global `strict=True` on `StrictInput`.
- Mappers run at fetch boundary only (see CLAUDE.md UI layering).
- No backwards-compat shims on deleted URLs — atomic migration in-repo;
  old routes exist only during the intermediate staged commits.
- Commit messages reference this plan (`docs/superpowers/plans/2026-04-19-evaluation-api-redesign.md`).

## Execution model — subagent delegation

To preserve the orchestrator's context across this multi-commit refactor:

- **Opus (orchestrator)** owns design decisions, commit boundaries, verification
  (reads diffs, checks schemathesis failure counts), and final review.
- **Sonnet subagents** execute each bounded commit. One subagent per commit, with
  a self-contained prompt: goal, files to touch, success criteria (`just test-int`
  265/265, UI tests green, specific URLs/shapes). Subagents return a concise diff
  summary; orchestrator verifies via `git diff` and targeted test runs before
  moving on.
- **Explore / Haiku subagents** handle mechanical sweeps: grep for remaining
  `/evaluate` / `/trend` URL references across UI + SDK + tests; count residual
  schemathesis failures; audit MSW handlers for URL drift.
- **Never delegate understanding** — each subagent prompt must name exact file
  paths, exact URL strings, and exact success criteria derived in advance by
  the orchestrator.

Per-commit subagent briefs get drafted just-in-time (not pre-written in this
plan) so they reflect the state after the previous commit landed.

## Sequencing recommendation

**Ship as a single PR** against `feat/contract-testing-phase-3-schemathesis`
with carefully staged commits:

1. Phase 1 routes-alongside + UI/SDK/tests migration (commits 1-5 above)
2. Phase 1 old-route deletion + openapi regen (commit 6)
3. Phase 2a null-byte fix
4. Phase 2b StrictBool/StrictInt batch
5. Phase 2c uniqueItems
6. Phase 2d 405 middleware
7. Phase 2e case-by-case investigation (separate plan if it grows)
8. Update `reports/schemathesis-next-steps.md` with final residuals and
   `reports/schemathesis-triage.md` with fix log

PR reviewer should be able to walk commits in order and see the number of
schemathesis failures drop monotonically.

## Follow-ups explicitly deferred

1. UI time-range-in-URL (Grafana permalink) — `TimeRangeProvider` reads/writes
   `?from=&to=` search params. Separate plan; URL redesign here unblocks it.
2. Compare-two-evaluations endpoint (surfaced in design discussion as a
   possible future feature). Own plan.
3. SLI definitions adapter-dependent field validation — the targeted
   schemathesis exclusion in 2e is the immediate fix; a longer-term
   "discriminated union per adapter via plugin-registered schemas" is
   another plan.
4. Singular/plural convention extended to `/asset/{id}`, `/datasource/{id}`,
   `/slo-definition/{name}` etc. — only if users endorse the singular
   convention in practice here.
