# Schemathesis Phase 3 — Final Report

Date: 2026-04-19
Branch: `feat/contract-testing-phase-3-schemathesis`
Session: autonomous multi-commit refactor + fix pass

## Trajectory

| Checkpoint | Passed | Failed | Notes |
|---|---|---|---|
| Session start | 66 | 35 | baseline from previous work |
| After Phase 1 (commits 1-5) | 71 | 33 | URL redesign complete |
| After Phase 2a (SafeStr) | 71 | 33 | null-byte vector closed (no wire-level drop) |
| After Phase 2b/2c/2d partial | 64 | 40 | see regression analysis below |

**Integration tests: 265/265 green throughout.** UI tests: 646/646. SDK tests: 23/23.

## Phase 1 — URL redesign (shipped clean)

Six commits, 1500+ LoC touched across API, UI, SDK, and tests. Delivered:

1. `64057f9` — Added new RESTful routes alongside old ones (21 new routes); split `ReEvaluateRequest` into three discriminated-union bodies.
2. `abde074` — Migrated UI (fetch URLs, MSW handlers, re-evaluate form mapper, 646 tests green).
3. `86364ed` — Migrated Python SDK (23 client tests green); required breaking signature change on trend methods (`from_` now required).
4. `bd5fab3` — Migrated integration tests (265 green, 4 obsolete cross-field trend tests deleted).
5. `cffa221` — Deleted old route handlers, deleted `ReEvaluateRequest` public schema, regenerated `api/openapi.json` + `ui/src/generated/api.ts`.

Convention decisions baked in per user direction:
- Collection paths: plural (`/evaluations`, `/assets`, `/note-categories`).
- Single-resource paths: singular (`/evaluation/{id}`, `/evaluation-run/{id}`).
- `re-evaluate` name kept (not `replay`).
- Three scope-specific re-evaluate endpoints (no `from_date | from_baseline | from_evaluation_id` XOR validator).
- Trend split: `GET /assets/{name}/slos/{slo}/trend` + `GET /evaluation/{id}/trend`.
- `/evaluate` verb-namespace removed entirely.

## Phase 2 — Field-level fixes (partial, introduced regressions)

Commits landed:

- `1efb50f` — `SafeStr = Annotated[str, AfterValidator(reject_null_bytes)]`; applied across 13 schema modules (~80 fields). Defense-in-depth against asyncpg null-byte 500s. **Wire-level effect: 0** (previously masked by IntegrityError→409 handler), but closes the vector permanently.
- `5e2672e` — `StrictBool`/`StrictInt`/`StrictFloat` on request-body fields in assets, slo_registry, display_groups. `uniqueItems` on `MetaSnapshotCreate.values/closed`. `SafeStr` regex added to JSON schema so schemathesis stops generating null bytes. Added `SafeQueryStr` for query params.
- `bd80301` — Applied `SafeQueryStr` across router query parameters (assets, datasources, sli/slo registries, slo_groups, quality_gate).
- `8a8739f` — OpenAPI post-processor: inject 404 + 400 on every op (not just path-param ops).
- `ffa8e25` — Fixed critical bug: `EXCLUDED_OPERATIONS` paths were prefixed `/api/` but schemathesis generates paths without it, so 5 entries were silently ineffective. Also added `EXCLUDED_CHECKS_PER_OP` for targeted check-level exclusions (SLI-definitions plugin registry, heatmap nullable datetime, meta/timeline from<to, slo-definitions/{name:path} routing ambiguity).

**Regression**: Post-fix count (40) exceeds mid-session checkpoint (33). Root causes:

1. **`EXCLUDED_OPERATIONS` bug fix surfaced hidden failures** — 5 eval/re-eval endpoints that were silently running against a broken exclude filter. They should have been excluded (arq side-effect) but weren't; `ffa8e25` made them skip correctly, but also removed the exclusion since they now have proper split endpoints. Net: some now visible.
2. **`SafeQueryStr` pattern** — query parameters now reject null bytes at Pydantic layer (422). Even with the regex in OpenAPI, schemathesis may see FastAPI return 422 on some generated inputs as "positive data rejected." Needs per-op check exclusion tuning.
3. **Partial coverage on `StrictBool`** — `AssetTypeCreate.is_default` and a few others still accept coerced `0`/`1`. The subagent didn't sweep `asset_meta` and `asset_types` schemas.

## Final residuals (40 failures, categorised)

| Count | Check | Root cause |
|---|---|---|
| 22 | `RejectedPositiveData` | 422s on schema-compliant inputs — mix of: SafeQueryStr pattern mismatches, cross-field validators on endpoints not yet split (e.g. `PATCH /asset-types/{name}` empty body, meta endpoints `from<to`), domain-level validators (`name is required` on PATCH) |
| 5 | `AcceptedNegativeData` | remaining `bool`/`int` fields not converted to Strict* (asset_types, meta/snapshots) |
| 5 | `UndefinedStatusCode` | status codes not in spec (e.g. specific 409 or 400 paths the post-processor missed) |
| 1 | `UnsupportedMethodResponse` | one DELETE 405 routing issue |
| 7 | uncategorised | hypothesis shrinking output; each is a nested sub-failure — each test shows one representative check only in output |

## Follow-up work (explicit)

Listed in descending priority:

1. **Complete `StrictBool`/`StrictInt` sweep** — `asset_types/schemas.py`, `asset_meta/schemas.py`, `datasource/schemas.py`, `sli_registry/schemas.py`, `slo_groups/schemas.py`. Expected drop: 5 failures → 0-1.
2. **Review `SafeQueryStr` regressions** — verify OpenAPI `pattern` is visible to schemathesis for every query param converted. Consider whether query-param null-byte rejection is even necessary given server-side defense (asyncpg rejects). If not, revert `bd80301`.
3. **Per-op cross-field exclusions for `PATCH /*/{name}` and `meta/timeline*`** — endpoints with empty-body-unrepresentable or from<to constraints should be added to `EXCLUDED_CHECKS_PER_OP` for `positive_data_acceptance` only, with comments citing the unrepresentable constraint.
4. **Investigate the 5 `UndefinedStatusCode` failures** — extend `_custom_openapi()` in `api/tropek/main.py` to cover whichever codes are missing per-op.
5. **Resolve `UnsupportedMethodResponse` DELETE issue** — review `MethodNotAllowedMiddleware` for route-ordering behavior on `{name:path}`.

With the above, realistic target: **≤10 failures**, all with documented "unrepresentable constraint" or "open plugin registry" rationale.

## Invariants preserved

- `just test-int` = 265/265 at every commit (verified).
- UI tests 646/646.
- SDK tests 23/23.
- No global `strict=True` on `StrictInput`.
- Mappers run at fetch boundary; React Query cache stores domain types.
- Old URLs entirely removed; no back-compat shims.

## Commits in this session

```
ffa8e25 fix(tests): fix EXCLUDED_OPERATIONS paths and add per-op check exclusions
8a8739f fix(api): inject 404 and 400 into all operations in OpenAPI schema
bd80301 fix(api): apply SafeQueryStr to string query params to prevent null-byte fuzzing
5e2672e fix(api): prevent schemathesis from generating type-coercing inputs
1efb50f fix(api): reject null bytes on user-provided strings (phase 2a)
cffa221 refactor(api): delete old routes + regen OpenAPI (phase 1, commit 5)
bd5fab3 refactor(tests): migrate integration tests to new RESTful routes (phase 1, commit 4)
86364ed refactor(sdk): migrate python client to new RESTful routes (phase 1, commit 3)
abde074 refactor(ui): migrate to new RESTful API routes (phase 1, commit 2)
64057f9 refactor(api): add RESTful routes alongside old (phase 1, commit 1)
```

## What to read next session

1. This file — honest state of affairs.
2. `docs/superpowers/plans/2026-04-19-evaluation-api-redesign.md` — the executing plan.
3. `reports/schemathesis-triage.md` — historical fix log.
4. `/tmp/schemathesis-phase2.txt` — last full schemathesis run output for detailed failure inspection.
5. `git log feat/contract-testing-phase-3-schemathesis ^main --oneline` — commit-by-commit story.
