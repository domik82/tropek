# API Extensions & UI Alignment — Implementation Overview

> **For agentic workers:** Read this document FIRST to understand context, then read your
> assigned stream task file. All streams can run in parallel worktrees. After all streams
> merge, run the validation plan in `2026-03-15-stream-v-validation.md`.

**Goal:** Extend TROPEK's API with trend-by-eval-id, time-range filters, SLO validation,
SLO testing, and a Python client SDK. Align the React UI to match the real API contract
instead of MSW mock assumptions.

**Spec:** `docs/superpowers/specs/2026-03-15-api-ui-alignment-design.md`

---

## What We're Building

TROPEK is a quality gate platform (Python/FastAPI/PostgreSQL). The API exists and works.
The UI was built against MSW mocks that diverge from the real API in paths, field names,
and response shapes. We need to:

1. Add 4 missing API capabilities the UI needs
2. Build a typed Python client SDK for 3rd-party integrations
3. Fix the UI to call the real API instead of mock-shaped endpoints

---

## Stream Dependency Graph

```
         ┌─── A. QG extensions (quality_gate/)
         │
         ├─── B. SLO validate + test (slo_registry/)
main ────┤
         ├─── C. SLI CRUD UI module (ui/src/features/slis/) — no API changes
         │
         └─── E. Python SDK (clients/python/) — greenfield

         ... after A+B+C merge ...

         └─── D. UI alignment (ui/) — wires UI to real API contract

         ... after all merge ...

         └─── V. Cross-stream validation
```

**A, B, C, E** run in parallel — zero file overlap.
**D** runs after A+B+C land (needs real endpoints to align against).
**V** runs after everything merges.

---

## Stream Summaries

### Stream A — Quality Gate Extensions
**Spec sections:** §2 (trend by eval_id), §3 (time-range filters)
**Files touched:** `api/app/modules/quality_gate/router.py`, `repository.py`
**What it does:** Adds `eval_id` as an alternative entry to `GET /trend` (resolves
asset+SLO from the evaluation record). Adds `from`/`to` datetime query params to
`GET /evaluations` (mutually exclusive with existing `date` prefix filter).
**Task file:** `2026-03-15-stream-a-qg-extensions.md`

### Stream B — SLO Validate + Test
**Spec sections:** §4 (validate), §5 (test/dry-run)
**Files touched:** `api/app/modules/slo_registry/router.py`, `schemas.py`
**What it does:** Adds `POST /slo-definitions/validate` (parse SLO YAML, return errors
or parsed objectives). Adds `POST /slo-definitions/test` (fetch real metrics from adapter,
evaluate against SLO criteria, return result without persisting).
**Task file:** `2026-03-15-stream-b-slo-validate-test.md`

### Stream C — SLI CRUD UI Module
**Spec sections:** §7 (SLI CRUD from SLO editor)
**Files touched:** `ui/src/features/slis/` (new module), `ui/src/mocks/handlers/slis.ts`,
`ui/src/mocks/data/sli-definitions.json`, `ui/src/mocks/handlers/index.ts`
**What it does:** Creates the SLI feature module in the UI — types, API functions, hooks,
MSW handlers, and mock data. The SLI CRUD API endpoints already exist; this is purely
UI work. No API changes.
**Task file:** `2026-03-15-stream-c-sli-crud-ui.md`

### Stream D — UI Alignment
**Spec sections:** §6 (paths + fields), §8 (SLO test UI), §9 (MSW mocks)
**Files touched:** `ui/src/features/evaluations/`, `ui/src/features/slos/`,
`ui/src/features/assets/`, `ui/src/mocks/handlers/*.ts`, `ui/src/mocks/generate.ts`,
`ui/src/mocks/data/slo-definitions.json`
**What it does:** Fixes all URL paths (`/api/slos` → `/api/slo-definitions`), field
names (`start` → `period_start`), response shape unwrapping (`PagedResponse.items`),
removes mock-only fields, updates MSW handlers and mock data generators.
**Depends on:** Streams A, B, C merged first. Uses SLI types/hooks created by Stream C.
**Task file:** `2026-03-15-stream-d-ui-alignment.md`

### Stream E — Python Client SDK
**Spec section:** §10
**Files touched:** `clients/python/` (new package)
**What it does:** Creates `tropek-client` package with typed `TropekClient`, Pydantic
models mirroring API schemas, YAML manifest loader, desired-state reconciler (`apply`
+ `dry_run`), and a `click` CLI (`tropek apply`, `tropek validate`).
**Task file:** `2026-03-15-stream-e-python-sdk.md`

### Stream V — Cross-Stream Validation
**Runs after:** All streams merged
**What it does:** End-to-end verification that all streams integrate correctly —
API endpoints respond as spec'd, UI builds without errors, SDK can call every endpoint,
MSW mocks match real API shapes.
**Task file:** `2026-03-15-stream-v-validation.md`

---

## Existing Codebase Patterns (Reference)

Agents implementing streams should follow these patterns found in the existing code:

### API Module Pattern
Each module in `api/app/modules/` has:
- `router.py` — FastAPI endpoints, imports `Depends(get_session)` for DI
- `repository.py` — SQLAlchemy async queries, takes `AsyncSession` in constructor
- `schemas.py` — Pydantic models: `*Create` (request), `*Read` (response with `from_attributes=True`)

### Router Registration
All routers imported in `api/app/main.py`, included with `app.include_router(router)`.
No prefix — each router defines full paths (e.g., `/slo-definitions`).

### Error Handling
- `raise_not_found(entity, name)` → 404 with `"{entity} '{name}' not found"`
- `raise_conflict(entity, name)` → 409
- Direct `HTTPException(status_code=422, detail=...)` for validation errors

### Pagination
`PagedResponse[T]` from `app.modules.common.schemas` — `{items: [...], total: N}`

### Versioned CRUD (SLI/SLO)
- `SELECT ... FOR UPDATE` to get max version, then `next_version = max + 1`
- Immutable after insert — new version = new row
- `deactivate(name)` soft-deletes all versions (`active=False`)
- `list_all()` uses `DISTINCT ON (name)` to get latest active version per name

### Test Pattern
- Pure engine tests in `api/tests/engine/` — no DB, no mocks
- Integration tests in `api/tests/db/` — marked `@pytest.mark.integration`
- Fixture `slo_data("filename.yaml")` loads from `api/tests/data/slo/`
- `asyncio_mode = "auto"` — async tests just work

### Config
- Non-secret: `config.yaml` loaded via `pydantic_settings`
- Secrets: `QG_*` env vars
- `get_settings()` returns cached `Settings` singleton

### UI Pattern (React 19 + TypeScript + TanStack Query)
- `features/<name>/api.ts` — fetch functions using `fetch()`
- `features/<name>/types.ts` — TypeScript interfaces
- `features/<name>/hooks.ts` — TanStack React Query hooks (`useQuery`, `useMutation`)
- `features/<name>/components/` — React components
- `mocks/handlers/<name>.ts` — MSW request handlers
- `mocks/data/<name>.json` — mock fixture data
