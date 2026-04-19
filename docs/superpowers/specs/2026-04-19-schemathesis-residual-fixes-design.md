# Schemathesis Residual Fixes — Design

Date: 2026-04-19
Branch: `feat/contract-testing-phase-3-schemathesis`

## Context

After Phase 1 (URL redesign) and Phase 2 (field-level fixes), schemathesis is at
**14 failed / 90 passed** — down from 40/64. The remaining 14 cluster into six
groups, each with a clear root cause. This spec designs the minimal set of changes
to take the suite to zero (or documented) failures.

See `reports/schemathesis-phase3-final.md` for the trajectory. This spec is the
execution plan for the follow-up work listed there.

## Goals

- Drive schemathesis to **0 failures** (or clearly-documented residuals with
  "unrepresentable constraint" rationale).
- Keep integration tests at 265/265, UI at 646/646, SDK at 23/23 after every
  commit.
- Where a failure reveals an architectural smell, fix the architecture — not the
  schemathesis expectation.

## Non-goals

- Adding new schemathesis checks (security, stateful) — tracked as separate tasks.
- Backwards-compat shims. All callers in-repo; migrate atomically.
- Broader refactors beyond what the failures point to.

## The 14 failures, grouped

### A. JSONB null bytes in dict keys/values (3)

- `POST /assets` — `tags: {"\u0000": ""}`
- `PATCH /assets/{name}` — same
- `PATCH /evaluation/{eval_id}/annotations/{ann_id}` — same

`SafeStr` covers top-level strings but not keys/values inside `tags` / `variables`
JSONB dicts. Postgres rejects `\u0000` in text at the asyncpg layer → 500.

**Fix:** a `SafeJsonDict` validator (Annotated `dict[str, str | None]` + AfterValidator)
that walks keys and values rejecting `\u0000`. Apply to every `tags` and `variables`
field on request bodies.

### B. Strict type gaps (3)

- `DELETE /asset-groups/{name}?deactivate_slos=0` — bool query param accepts `0`/`1`.
- `POST /slo-definitions` with `comparable_from_version: false` — int field accepts bool.
- `POST /slo-definitions/validate` with `total_score_warning_threshold: false` —
  float field accepts bool.

**Fix:** `StrictBool` on `deactivate_slos` (via `Query(..., strict=True)` or
annotation), `StrictInt` on `comparable_from_version`, `StrictFloat` on both
`total_score_*_threshold` fields. Sweep `slo_definitions/schemas.py` for any others.

### C. Int32 overflow (1)

- `POST /slo-display-groups` with `sort_order: 2147483648` — DB column is `INTEGER`
  (32-bit) but Pydantic accepts arbitrary-size int → asyncpg DataError.

**Fix:** `sort_order: Annotated[int, Field(ge=-(2**31), le=2**31 - 1)]` on
`DisplayGroupCreate` / `DisplayGroupUpdate`.

### D. Architectural refactors + schema constraints (5)

Three of these are the same pattern — a referenced resource lives in the request
*body* rather than the URL, so a missing-reference produces 422 "X not found"
which schemathesis reads as `RejectedPositiveData`:

- `POST /asset-groups/{name}/slo-assignments` — body `slo_definition_id`
- `POST /assets/{name}/slo-group-assignments` — body `slo_group_name`
- `POST /asset-groups/{name}/slo-group-assignments` — same

**Fix (URL refactor):** move the reference into the URL using the standard
assignment-link REST shape. Assignments become idempotent PUTs:

```
PUT    /asset-groups/{name}/slo-definitions/{slo_definition_id}
DELETE /asset-groups/{name}/slo-definitions/{slo_definition_id}
PUT    /assets/{name}/slo-groups/{slo_group_name}
DELETE /assets/{name}/slo-groups/{slo_group_name}
PUT    /asset-groups/{name}/slo-groups/{slo_group_name}
DELETE /asset-groups/{name}/slo-groups/{slo_group_name}
```

Request body becomes `{data_source_name: str}` or empty where not needed. Missing
URL references naturally return 404 — no custom 422 handling needed.

The other two are cross-field rules currently enforced by handler code:

- `POST /assets/{asset_id}/meta/snapshots` — "must contain values or closed".
  **Fix:** split into `SnapshotValues | SnapshotClosed` discriminated union on a
  `kind` field. Both cases become schema-representable.
- `POST /slo-definitions/test` — "objectives list is empty".
  **Fix:** `objectives: Annotated[list[Objective], MinLen(1)]` — single line.

### E. Datetime query param nullability (1)

- `GET /evaluations?to=null` returns 422. OpenAPI marks `to` as a datetime query
  param; schemathesis generates the literal string `"null"` as a test for
  "nullable datetime." The handler signature is `to_ts: datetime | None = Query(default=None)`
  but the OpenAPI schema renders it as a nullable string rather than an optional
  omit-this-param.

**Fix:** investigate whether the issue is `nullable: true` vs absence on the
query parameter object. The cleanest answer is to require omission for "no upper
bound" rather than accepting null. Remove `| None` on the query signature if the
current contract never intends `?to=` to be sent literally.

### F. 405 middleware routing (1)

- `DELETE /slo-definitions/{name}/versions` returns 404 instead of 405.
  `MethodNotAllowedMiddleware` doesn't match when the subpath has a segment after
  `{name:path}`.

**Fix:** review `api/tropek/modules/common/method_not_allowed.py` — likely
needs to match prefix-then-suffix rather than exact path, or the middleware
is running after FastAPI's 404 has already been committed for this shape.

## Commit sequence

Cheap, contained commits first. Each commit keeps `just test-int` green.

1. **StrictBool/Int/Float sweep** (Group B) — 3 fields in 2 schema files.
2. **`sort_order` int32 bound** (Group C) — one Field constraint.
3. **JSONB null-byte validator** (Group A) — `SafeJsonDict` in
   `common/schemas.py`; apply to `tags`/`variables` across asset, annotation,
   and slo-definition schemas.
4. **Cross-field schema constraints** (Group D partial) — `MinLen(1)` on
   `objectives`; discriminated union on `MetaSnapshotCreate` (values|closed).
5. **Slo-assignment URL refactor** (Group D URLs) — cross-stack:
   - API router: add new PUT/DELETE routes; delete old POST/DELETE.
   - Schemas: slim body to `{data_source_name}` or drop entirely.
   - Integration tests: migrate assignment tests to new URLs.
   - Python SDK: update `_AssignSlo*` / `_AssignSloGroup*` methods.
   - UI: update fetch URLs in `features/registry` and `features/assets`.
   - MSW handlers: update assignment paths.
   - Regen `api/openapi.json` + `ui/src/generated/api.ts`.
6. **`/evaluations` `to` nullability fix** (Group E).
7. **`MethodNotAllowedMiddleware` routing fix** (Group F).
8. **Final run + report update** — re-run schemathesis; if zero failures or only
   documented residuals, update `reports/schemathesis-phase3-final.md` with final
   trajectory and close out the plan.

## Risks

- **Commit 5 is cross-stack.** Highest risk. Follow the Phase 1 pattern: API
  first with tests, then SDK, then UI+MSW, then regen.
- **`SafeJsonDict` could break legitimate callers** using exotic whitespace in
  keys. Low risk — no test fixture uses null bytes; integration tests are the
  safety net.
- **Middleware fix (F) could have route-ordering side effects.** Verify
  `test-int` passes after the change; review any 404/405 tests specifically.

## Invariants

- `just test-int` → 265/265 after every commit.
- UI tests 646/646 after commit 5.
- SDK tests 23/23 after commit 5.
- No global `strict=True` on `StrictInput`.
- No back-compat shims on deleted URLs — in-repo atomic migration.
- No `EXCLUDED_OPERATIONS` / `EXCLUDED_CHECKS_PER_OP` additions unless a residual
  failure is genuinely unrepresentable in OpenAPI (expected: none after this plan).

## Follow-ups (explicitly out of scope)

- Task 5: enable schemathesis security checks.
- Task 6: add stateful testing.
- Task 9: Phase 3.5 test audit.
