# Trend + Re-evaluate URL Split

Date: 2026-04-19
Branch: `feat/contract-testing-phase-3-schemathesis`

## Context

Schemathesis (60 passed / 41 failed) flagged cross-field validators on two endpoints
as `RejectedPositiveData` drift. Both endpoints accept inputs that look
schema-valid to an OpenAPI consumer but get 422-rejected by a Pydantic
`@model_validator` that enforces "one of these combos, not the others."

This is an architectural smell: mutually-exclusive field combos in one
endpoint = multiple endpoints wearing a trench coat. Splitting them:
- eliminates the cross-field validator → schemathesis passes
- makes each variant self-documenting at the URL level
- yields content-addressable URLs (permalink-friendly)
- simplifies clients, tests, metrics, auth

Two endpoints fit this pattern:
1. `GET /trend` — `eval_id` XOR `(asset_name + slo_name)`
2. `POST /evaluations/re-evaluate` — `from_date` XOR `from_baseline` XOR `from_evaluation_id`

SLI definitions (`adapter_type`-dependent fields) do NOT fit — adapters are an
open plugin registry, not a closed set. That one stays single-endpoint with a
targeted schemathesis exclusion (handled in a later task).

This plan executes both URL splits. The UI time-range-in-URL permalink work
(Grafana-style) is a separate follow-up plan — the API changes here are a
prerequisite for it but don't deliver it.

## Goals

- Replace `GET /trend` with two RESTful resource paths
- Replace `POST /evaluations/re-evaluate` with three scope-specific endpoints
- Drop two `@model_validator` cross-field checks
- Keep integration tests at 265/265 throughout
- Reduce schemathesis failures from 41 → ~36 (estimated)

## Non-goals

- UI time-range permalink work (separate plan)
- SLI definitions refactor
- `meta/snapshots` uniqueItems (one-line change, do separately)
- Backwards-compatibility shims — all callers are in-repo, update atomically

---

## Part A: `GET /trend` split

### Current state

```python
@router.get('/trend', response_model=list[TrendPoint])
async def get_trend(
    metric: str,
    eval_id: uuid.UUID | None = None,
    asset_name: str | None = None,
    slo_name: str | None = None,
    from_ts: datetime = Query(alias='from'),
    to_ts: datetime | None = Query(default=None, alias='to'),
    ...
):
    # 30 lines of cross-field validation + branch that resolves eval_id → (asset, slo)
    # then calls trend_repo.get_trend_by_domain(...)
```

Cross-field rules enforced by handler:
- exactly one of (`eval_id`) or (`asset_name` + `slo_name`)
- if lookup by asset, both `asset_name` and `slo_name` required

### Target state

```python
@router.get('/assets/{asset_name}/slos/{slo_name}/trend', response_model=list[TrendPoint])
async def get_trend_by_asset_slo(
    asset_name: str,
    slo_name: str,
    metric: str,
    from_ts: AwareDatetime = Query(alias='from'),
    to_ts: AwareDatetime | None = Query(default=None, alias='to'),
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> list[TrendPoint]: ...

@router.get('/evaluations/{eval_id}/trend', response_model=list[TrendPoint])
async def get_trend_by_evaluation(
    eval_id: uuid.UUID,
    metric: str,
    from_ts: AwareDatetime = Query(alias='from'),
    to_ts: AwareDatetime | None = Query(default=None, alias='to'),
    repos: QualityGateRepos = Depends(get_qg_repos),
) -> list[TrendPoint]: ...
```

Both handlers are ~8 lines: resolve identifiers to `(asset_id, slo_name)`,
call existing `repos.trend_repo.get_trend_by_domain(...)`, return points.
`AwareDatetime` (from pydantic) rejects naive datetimes — matches Grafana
URL convention and tightens the schema.

### Callers to migrate (atomically in same commit)

| File | Change |
|---|---|
| `api/tropek/modules/quality_gate/router.py` | Replace `get_trend` with two new handlers; delete old route |
| `api/tests/quality_gate/test_router.py:58-93` | Delete 4 cross-field rejection tests (no longer apply); add smoke tests for each new path |
| `api/openapi.json` | Regen via `uv run --directory api python scripts/export-schema.py` |
| `clients/python/tropek_client/client.py:640-662` | `_Trend.by_asset` uses `/assets/{name}/slos/{slo}/trend`; `_Trend.by_eval` uses `/evaluations/{id}/trend`; **drop `limit` param** (server never honored it) |
| `ui/src/features/evaluations/api.ts:87-100` | `fetchTrend` takes `(asset, slo, metric, {from, to})` → `GET /assets/{asset}/slos/{slo}/trend?metric=...&from=...&to=...` |
| `ui/src/mocks/handlers/evaluations.ts:40-46` | Update MSW handler path + param extraction |
| `ui/src/generated/api.ts` | Regen via `just codegen` (or note as known drift if codegen is broken per next-steps.md) |

### Router tests to add (integration, not unit — they hit the DB)

- `GET /assets/{name}/slos/{slo}/trend` with valid asset/slo/metric/from → 200 + points
- `GET /assets/unknown/slos/unknown/trend?metric=x&from=...` → 404
- `GET /evaluations/{id}/trend` with valid eval_id → 200 + same points as asset/slo path for that eval's (asset, slo)
- `GET /evaluations/{random-uuid}/trend?metric=x&from=...` → 404

Cross-field rejection tests (`test_trend_rejects_both_eval_id_and_asset_name`
etc.) are deleted — the impossible inputs no longer exist at the URL layer.

### Verification

1. `./scripts/api-test.sh --tail 5 -m integration -v` → 265/265 (new tests replace the 4 deleted ones — net may shift by ±2)
2. `./scripts/ui-test.sh --tail 10` → all green
3. Schemathesis: `uv run --directory api pytest tests/schemathesis/test_schema.py` → `GET /trend` failures gone (~2-3 fewer failures)

---

## Part B: `POST /evaluations/re-evaluate` split

### Current state

Single `POST /evaluations/re-evaluate` with body:

```python
class ReEvaluateRequest(StrictInput):
    asset_name: str | None = None
    group_name: str | None = None
    slo_name: str | None = None
    evaluation_names: list[str] | None = None
    from_date: date | None = None
    from_baseline: bool | None = None
    from_evaluation_id: uuid.UUID | None = None
    # @model_validator exactly_one_scope — one of the three "from_*" fields
    # @model_validator slo_name_and_names_mutually_exclusive — pick one scope selector
```

Two cross-field validators. Schemathesis flags both.

Note: this endpoint is **already in `EXCLUDED_OPERATIONS`** in the schemathesis
harness (side-effect heavy — enqueues arq jobs). Schemathesis win is zero
for now. The design win is real, and doing the split lets us remove the
exclusion later.

### Target state — three scope-specific endpoints

```python
POST /evaluations/re-evaluate/from-date
Body: { asset_name | group_name, slo_name | evaluation_names, from_date }

POST /evaluations/re-evaluate/from-baseline
Body: { asset_name | group_name, slo_name | evaluation_names }

POST /evaluations/re-evaluate/from-evaluation/{evaluation_id}
Body: { asset_name | group_name, slo_name | evaluation_names }
```

Each endpoint gets its own request body schema (`ReEvaluateFromDateRequest`,
`ReEvaluateFromBaselineRequest`, `ReEvaluateFromEvaluationRequest`).

**Open design question** — the `slo_name XOR evaluation_names` cross-field
check is independent of scope and still applies. Options:

- **Option 1**: keep it as a validator (cheaper, one validator instead of two, still imperfect)
- **Option 2**: split each endpoint again by selector — 6 endpoints total. Too much.
- **Option 3**: replace `slo_name` / `evaluation_names` with a discriminated union in the body. Representable in OpenAPI, schemathesis happy, one endpoint per scope.

**Recommendation**: Option 3. Body becomes:

```python
class SloSelector(BaseModel):
    kind: Literal['slo']
    slo_name: str

class EvalNamesSelector(BaseModel):
    kind: Literal['evaluation_names']
    evaluation_names: list[str]

Selector = Annotated[SloSelector | EvalNamesSelector, Field(discriminator='kind')]

class ReEvaluateFromDateRequest(StrictInput):
    asset_name: str | None = None
    group_name: str | None = None  # one of asset_name/group_name still XOR — TODO below
    selector: Selector
    from_date: date
```

Still leaves `asset_name XOR group_name` as a soft constraint. Same
discriminator approach resolves it: `scope: AssetScope | GroupScope`. Worth
doing since we're here.

Final shape:

```python
class AssetScope(BaseModel):
    kind: Literal['asset']
    asset_name: str

class GroupScope(BaseModel):
    kind: Literal['group']
    group_name: str

Scope = Annotated[AssetScope | GroupScope, Field(discriminator='kind')]

class ReEvaluateFromDateRequest(StrictInput):
    scope: Scope
    selector: Selector
    from_date: date
```

Zero cross-field validators. Fully representable in OpenAPI.

### Callers to migrate

| File | Change |
|---|---|
| `api/tropek/modules/quality_gate/router.py` | Replace `re_evaluate_evaluations` with three handlers |
| `api/tropek/modules/quality_gate/schemas/re_evaluation.py` | Split `ReEvaluateRequest` into three requests + two discriminated-union types; delete both `@model_validator`s |
| `api/tropek/modules/quality_gate/workflows/re_evaluation/re_evaluation_service.py` | Adapt `re_evaluate(body, repos)` → take explicit `(scope, selector, from_spec)`; caller adapts shape |
| `api/tests/quality_gate/**/test_re_evaluation*.py` | Update all existing tests to new URLs + request shapes |
| `clients/python/tropek_client/client.py` | `ReEvaluations.from_date()`, `.from_baseline()`, `.from_evaluation(eval_id)` |
| `ui/src/features/evaluations/components/actions/ReEvaluateForm.tsx` | Update `fetch` URL + body shape to whichever variant the form produces |
| `ui/src/features/evaluations/components/actions/ReEvaluateForm.test.tsx` | Adapt |
| `ui/src/mocks/handlers/evaluations.ts` | Update MSW handler paths |
| `ui/src/generated/api.ts` | Regen |
| `api/openapi.json` | Regen |
| `api/tests/schemathesis/test_schema.py` `EXCLUDED_OPERATIONS` | Remove `POST /evaluations/re-evaluate`; add the three new paths if still needed (arq enqueue side-effects) |

### Verification

1. Full integration: 265/265
2. UI tests: all green — re-evaluate form path covered
3. Schemathesis: re-evaluate no longer in triage output for cross-field drift

---

## Sequencing

**Ship as two PRs** against branch `feat/contract-testing-phase-3-schemathesis`:

- **PR 1 (Part A — trend split)** — small, ~10 file touches, 1-2 hours. Ship first so schemathesis numbers move and we validate the pattern.
- **PR 2 (Part B — re-evaluate split)** — larger, ~15 file touches, discriminated unions add design risk. Do only after Part A lands cleanly.

Both PRs must keep integration tests green.

## Out of scope — follow-ups

These are explicitly NOT in this plan:

1. **UI time-range permalink** — move `TimeRangeProvider` state from localStorage to `?from=...&to=...` search params. Separate plan, larger UX surface.
2. **`meta/snapshots` uniqueItems** — one-line `json_schema_extra={'uniqueItems': True}` on `closed[]`. Do as a quick follow-up commit.
3. **SLI definitions schemathesis exclusion** — add per-operation `positive_data_acceptance` exclusion with plugin-registry rationale.
4. **Residual `AcceptedNegativeData` failures** — grep for remaining bool/int fields, apply `StrictBool`/`StrictInt` per-field.
5. **Compare-two-evaluations endpoint** — surfaced in design discussion as a future feature. Belongs in its own plan, not conflated with trend.

## Invariants

- `just test-int` → 265/265 after every commit
- Never re-enable global `strict=True` on `StrictInput` — breaks UUID/datetime string coercion
- Mappers run at fetch boundary only (see CLAUDE.md UI layering)
- No backwards-compat shims on deleted URLs — atomic migration in-repo
