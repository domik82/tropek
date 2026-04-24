# Contract Testing in TROPEK

## Overview

TROPEK uses a phased contract testing strategy to ensure the backend (FastAPI) and
frontend (React/TypeScript) stay in sync, the API conforms to its own OpenAPI spec,
and common security vulnerabilities are caught automatically. The strategy is designed
as four independent phases — each is valuable on its own and does not depend on later
phases being built.

```
Phase 1 — OpenAPI type generation           ✅ Implemented (every push)
Phase 2 — Schema contract tests             ✅ Implemented (pragmatic alternative to Pact)
Phase 3 — Schemathesis property-based fuzz  ✅ Implemented (every push)
Phase 3.5 — Integration test audit          ✅ Completed (one-time)
Phase 4 — OWASP ZAP deep security scan     ❌ Not started
```

**Design spec:** `docs/superpowers/specs/2026-04-12-contract-testing-design.md`

---

## Phase 1 — OpenAPI Type Generation

**Goal:** FastAPI is the single source of truth for all API types. Frontend types
are generated from the live OpenAPI spec. TypeScript catches field renames at compile
time.

### How it works

1. `scripts/export-schema.py` imports the FastAPI `app` object directly (no server
   boot) and writes `api/openapi.json`.
2. `openapi-typescript` reads that file and generates `ui/src/generated/api.ts` — a
   full TypeScript type tree covering every request body, response, query parameter,
   and path parameter.
3. Feature-level `types.ts` files are progressively replaced with aliases pointing
   at generated types (see `ui/src/features/assets/types.ts` for the pattern).

### Commands

```bash
just export-schema        # Regenerate api/openapi.json from the FastAPI app
just codegen              # Regenerate ui/src/generated/api.ts from the OpenAPI spec
just check-schema-fresh   # CI gate: regen both, fail if git diff is non-empty
```

### CI

`.github/workflows/contract-freshness.yml` runs `just check-schema-fresh` on every
push to `main` and on PRs that touch backend code, the OpenAPI spec, or generated
types.

### What it catches

- Silent field renames (backend renames a field, frontend only discovers at runtime)
- Missing response fields
- Type mismatches between Pydantic models and TypeScript interfaces

---

## Phase 3 — Schemathesis Property-Based Testing

**Goal:** Prove the backend correctly implements its own OpenAPI spec across a wide
range of inputs — valid, boundary, malformed, and security-oriented — not just the
happy paths tested by integration tests.

### How it works

Schemathesis reads the OpenAPI spec from the live FastAPI app (via ASGI transport,
no network port needed) and auto-generates hundreds of test cases per endpoint using
Hypothesis-driven property-based testing. For each generated request it verifies:

- **Response schema conformance** — every response matches its declared shape
- **No unhandled 500s** — `not_a_server_error` check catches validation gaps
- **Negative data rejection** — invalid inputs are rejected with appropriate 4xx codes
- **Positive data acceptance** — valid inputs are accepted (not rejected with 422)
- **Security probes** — SQL injection, path traversal, and XSS payloads in string
  fields (FastAPI + SQLAlchemy ORM provides strong defaults, Schemathesis confirms it)

### Files

```
api/tests/schemathesis/
├── __init__.py
├── conftest.py          # ASGI schema loader, test lifespan (fakeredis, no-op arq)
├── test_schema.py       # Main entry point — expands into hundreds of cases
└── test_stateful.py     # State machine tests for request chains
```

### Commands

```bash
just test-schema                    # Full run (requires just test-env first)
just test-schema -k 'POST /assets'  # Filter to specific operations
```

### CI

`.github/workflows/schemathesis.yml` runs on every push to `main` and on PRs
touching backend code. Uses a TimescaleDB service container on port 5433 (same
pattern as integration tests).

### Test harness architecture

The conftest replaces the app's production lifespan with a test stub that:

- Uses **fakeredis** for the cache layer (no Redis dependency)
- Provides a **no-op arq pool** (worker jobs are not triggered)
- Creates a **fresh NullPool engine per request** to avoid event-loop conflicts
  (Hypothesis runs each example in its own event loop via anyio)

### Excluded operations

Some endpoints are excluded from fuzzing entirely because they enqueue arq worker
jobs or require pre-existing domain state that stateless fuzzing cannot set up:

| Operation | Reason |
|---|---|
| `POST /evaluations` | Enqueues arq worker jobs |
| `POST /evaluations/batch` | Enqueues arq worker jobs |
| `POST /evaluations/re-evaluate/*` (3 endpoints) | Trigger re-scoring with DB side effects |
| `POST /slo-groups` | Requires existing template SLO |
| `PATCH /asset-types/{name}` | Empty body is schema-valid but always domain-rejected |

### Per-operation check exclusions

Some operations have specific checks disabled while keeping all other conformance
checks active. The common pattern is `positive_data_acceptance` excluded when a
**cross-field constraint cannot be expressed in OpenAPI 3.1**:

| Operation | Excluded check | Reason |
|---|---|---|
| `POST /sli-definitions` | `positive_data_acceptance` | Open adapter plugin registry — mode fields vary by adapter_type |
| `GET /assets/{id}/meta/timeline*` | `positive_data_acceptance` | `from` must be before `to` (cross-field) |
| `POST /assets/{id}/meta/snapshots` | `positive_data_acceptance` | Values-or-closed XOR constraint |
| `POST /slo-definitions` | `positive_data_acceptance` | Objective SLI must reference a key in indicators dict |
| `POST /slo-definitions/test` | `positive_data_acceptance` | Requires existing datasource + SLI definition + asset |
| `GET /evaluations` | `positive_data_acceptance` | Mutually exclusive date/from/to query params |
| `PATCH /assets/{name}` | `positive_data_acceptance` | Opaque heatmap_config with nested null-byte constraint |
| `POST /slo-display-groups` | `positive_data_acceptance` | Self-referential FK (parent_id) |
| `PATCH /assets/{name}/slo-assignments/{id}` | `positive_data_acceptance` | Cross-resource FK dependency |

### Backend fixes driven by Schemathesis

Schemathesis found real bugs and design issues that were fixed during Phase 3. The
fixes fall into several categories:

#### URL redesign (Phase 1 of Schemathesis work)

The original URL structure had several problems that Schemathesis surfaced. Six
commits delivered a full RESTful URL redesign:

- **Collection paths**: plural (`/evaluations`, `/assets`, `/note-categories`)
- **Single-resource paths**: singular (`/evaluation/{id}`, `/evaluation-run/{id}`)
- **Re-evaluate split**: `POST /evaluations/re-evaluate` with XOR body fields split
  into three scope-specific endpoints:
  - `POST /evaluations/re-evaluate/from-date`
  - `POST /evaluations/re-evaluate/from-baseline`
  - `POST /evaluations/re-evaluate/from-evaluation/{evaluation_id}`
- **Trend split**: `GET /assets/{name}/slos/{slo}/trend` + `GET /evaluation/{id}/trend`
- **SLO assignment URLs**: moved reference IDs from request body into URL path
  (`PUT /assets/{name}/slo-definitions/{slo_id}` instead of
  `POST /assets/{name}/slo-assignments` with `slo_definition_id` in body)

#### Input validation hardening

| Fix | Files | What it prevents |
|---|---|---|
| `SafeStr` type | `api/tropek/modules/common/schemas.py` | Null bytes in string fields → asyncpg 500 |
| `SafeJsonDict` validator | Same file | Null bytes in JSONB dict keys/values (recursive walker) |
| `IntNotBool` / `FloatNotBool` | Same file | Pydantic coercing `true`→`1` or `false`→`0` |
| `StrictQueryBool` | Same file | FastAPI coercing `0`/`1` in query params |
| `sort_order` int32 bound | `display_groups/schemas.py` | Int64 overflow on INTEGER column |
| `MinLen(1)` on objectives | `quality_gate/schemas/trigger.py` | Empty objectives list passing validation |
| K8s-style `TagKey`/`TagValue` | `common/schemas.py` | Unrestricted tag formats in JSONB |
| `IdentifierKey` type | Same file | Null bytes in identifier-style string fields |

#### OpenAPI spec improvements

- **Custom OpenAPI post-processor** injects 404 and 400 responses on all operations
  (not just path-param ops) so Schemathesis doesn't flag them as undocumented
- **`propertyNames.pattern`** injected from `patternProperties` in the schema export
  script, so Schemathesis generates keys matching tag/label constraints
- **`anyOf`** on `MetaSnapshotCreate` to surface the values-or-closed constraint
- **Nullable datetime fix** on query params — replaced `nullable: true` with `anyOf`
  containing only the datetime format
- **405 middleware fix** — `MethodNotAllowedMiddleware` now walks parameterized
  routes correctly, returning 405 instead of 404 for unsupported methods on
  `{name:path}` subroutes

---

## Phase 3.5 — Integration Test Audit

**Goal:** Classify all existing integration tests against Schemathesis coverage to
identify redundancy and confirm business-logic tests are kept.

**Result:** All ~164 integration tests were kept. No tests removed.

### Rationale

14 tests overlap in coverage area with Schemathesis (status codes, input validation),
but they are **designed tests pinned to specific scenarios** while Schemathesis probes
heuristically with random inputs. Both layers provide complementary value:

- **Designed tests** pin expected behavior and won't drift if the schema changes
- **Schemathesis** explores the input space heuristically but not deterministically

The remaining ~150 tests exercise repository-layer logic (direct DB calls, not HTTP)
or multi-step business workflows that Schemathesis cannot reach.

**Full report:** `reports/test-audit.md`

---

## Phase 2 — Schema Contract Tests

**Goal:** Prevent silent API contract breakage when backend Pydantic schemas change.
CI fails if field names, nested model types, or enum values drift from what the
frontend expects.

The original design spec called for `@pact-foundation/pact` consumer/provider
testing. What was implemented instead is a comprehensive suite of **Pydantic schema
contract tests** in `api/tests/test_schema_contracts.py` — a pragmatic alternative
that achieves the same goal (CI catches backend/frontend contract drift) without the
Pact broker infrastructure overhead.

### What it tests

| Test class | What it guards |
|---|---|
| `TestAssetSchemaContract` | `tags` (not `labels`), `variables` field on assets |
| `TestDataSourceSchemaContract` | `tags`, `has_token` presence, `token` exclusion |
| `TestSLISchemaContract` | `tags` (not `meta`) on SLI definitions |
| `TestSLOSchemaContract` | `tags`, `variables` (not `meta`) on SLO definitions |
| `TestEvaluationSchemaContract` | `variables` (not `evaluation_metadata`) on evaluations |
| `TestEvaluationNestedTypes` | `AssetSnapshot`, `SliMetadata`, `PassTarget` are typed models (not `dict[str, Any]`) |
| `TestHeatmapNestedTypes` | `PassTarget`/`SliMetadata` reused in heatmap schemas; `SloGroup` renamed to `HeatmapSloGroupSection` |
| `TestSloRegistryNestedTypes` | `ComparisonConfig`, `MethodCriteriaOverride` typed; `tags`/`variables` constrained; round-trip validation |
| `TestAnnotationSchemaContract` | `tags`, embedded `category`, `note_group_*`, `hidden_*` fields |
| `TestAnnotationCategorySchemaContract` | Palette fields, `CategoryColor` enum matches UI's 8 tokens |
| `TestTrendAnnotationsRoute` | Route registered with correct query params |
| `TestStrictInputEnforcement` | Every request body model inherits `StrictInput` (rejects unknown fields) |

### Why not Pact

Pact's value is strongest in multi-team environments where consumer and provider are
maintained by different teams. For a single-developer project:

- Schema contract tests run as normal pytest (no broker, no extra tooling)
- Phase 1 codegen already catches type-level drift at the TypeScript layer
- The `StrictInputEnforcement` test walks all API routes automatically — no manual
  contract authoring per endpoint

The Pact plan exists at `docs/superpowers/plans/2026-04-12-contract-testing-phase-2-pact.md`
if the project grows to multiple contributors and the overhead becomes worthwhile.

---

## What Is NOT Implemented (Scoped Out)

### Phase 4 — OWASP ZAP Deep Security Scanning

**Status:** Planned but not started.

**What it would add:** Active security scanning beyond Schemathesis's basic checks —
deep SQL injection, XSS, path traversal, broken authentication, insecure direct
object references, OWASP API Top 10.

**Why not yet:** Schemathesis already provides basic security probes (negative data
rejection, SQL injection payloads, path traversal). ZAP adds deeper scanning but
runs slowly (10-30 minutes) and requires tuning. Designed as a weekly/on-demand scan,
not per-push.

**Plan:** `docs/superpowers/plans/2026-04-12-contract-testing-phase-4-owasp-zap.md`

**What it would involve:**
- ZAP running in Docker against a test instance
- Suppression file for reviewed false positives
- Weekly GitHub Actions schedule + manual `just security-scan`
- Auto-opening GitHub issues for HIGH findings

### Schemathesis stateful testing

Schemathesis can chain requests into realistic sequences — POST to create a resource,
use the returned ID to GET it, then DELETE it. To do this automatically it relies on
OpenAPI "links" — declarations like "the `id` in the POST /assets response can be
fed into GET /assets/{id}." FastAPI doesn't generate these links by default, and we
haven't added them manually to the schema export script. So `test_stateful.py` exists
and runs, but the state machine has nothing to chain and doesn't exercise meaningful
multi-step sequences. Adding explicit link declarations would enable this.

### Schemathesis per-operation exclusions

10 endpoints have the `positive_data_acceptance` check disabled. These are cases
where the API rejects inputs that are technically valid JSON Schema, but violate
domain rules that OpenAPI 3.1 cannot express. Examples:

- **Cross-field ordering:** `from` query param must be before `to` — OpenAPI has no
  way to say "parameter A < parameter B"
- **Conditional XOR:** the body must have non-empty `values` OR non-empty `closed`,
  but not both empty — no conditional XOR exists in OpenAPI
- **Cross-field references:** the `sli` field inside each objective must reference a
  key from the `indicators` dict — cross-object reference constraints don't exist
- **Open plugin registry:** SLI definitions have adapter-specific fields that vary by
  `adapter_type` — adapters are discovered at runtime so the valid field set can't be
  expressed in a static schema
- **Self-referential FKs:** `parent_id` on display groups references another display
  group — Schemathesis generates random UUIDs that don't exist

These aren't bugs — they're legitimate validation rules. Schemathesis generates
inputs that pass JSON Schema but fail these rules, causing false
`positive_data_acceptance` failures. Only that one check is disabled per endpoint;
all other checks (500 detection, response schema conformance, security probes) stay
active.

---

## Future Options

Things that could be added to deepen contract/security testing. Roughly ordered by
value-to-effort ratio. Each section describes what it would achieve, what's needed to
implement it, and what existing work it builds on.

### 1. Schemathesis stateful testing via OpenAPI links

**What exists:** `test_stateful.py` runs but doesn't chain requests (no links declared).

**What to do:** Add link declarations to the OpenAPI export script
(`scripts/export-schema.py`) so Schemathesis can auto-generate multi-step sequences.
High-value chains:

| POST (create) | GET (read) | DELETE (remove) |
|---|---|---|
| `POST /assets` | `GET /assets/{name}` | `DELETE /assets/{name}` |
| `POST /slo-definitions` | `GET /slo-definitions/{name}` | `DELETE /slo-definitions/{name}` |
| `POST /sli-definitions` | `GET /sli-definitions/{name}` | `DELETE /sli-definitions/{name}` |
| `POST /datasources` | `GET /datasources/{name}` | `DELETE /datasources/{name}` |
| `POST /note-categories` | `GET /note-categories` | `DELETE /note-categories/{id}` |
| `POST /evaluation/{id}/annotations` | `GET /evaluation/{id}` | `PATCH .../annotations/{id}` (hide) |

**Effort:** Medium. Declare links in the post-processor that already exists in
`tropek/main.py`. Each link maps a response field (e.g. `name`) to a path parameter
on another operation. No new dependencies.

**What it catches:** Bugs that only appear in sequence — e.g. creating then
immediately reading a resource returns stale data, or deleting a resource that has
dependent rows causes an unhandled FK violation.

### 2. Remove per-operation check exclusions

**What exists:** 10 endpoints have `positive_data_acceptance` disabled due to
cross-field constraints OpenAPI can't express.

**What to do per endpoint:**

| Endpoint | How to remove the exclusion |
|---|---|
| `GET /assets/{id}/meta/timeline*` | Add a Schemathesis `@hook` that ensures generated `from` < `to` |
| `POST /assets/{id}/meta/snapshots` | Split into `POST .../meta/values` + `POST .../meta/closures` (two endpoints, no XOR) |
| `POST /slo-definitions` | Add a hook that populates `objective.sli` from the generated `indicators` dict |
| `POST /slo-definitions/test` | Seed test fixtures (datasource, SLI, asset) in the schemathesis conftest; remove exclusion |
| `GET /evaluations` | Add a hook that avoids sending both `date` and `from`/`to` simultaneously |
| `POST /sli-definitions` | Only removable if adapter plugin fields are moved to a separate endpoint per adapter type |
| `PATCH /assets/{name}` | Type `heatmap_config` as a concrete model instead of `dict[str, Any]` |
| `POST /slo-display-groups` | Seed a parent display group in fixtures; hook injects its real ID as `parent_id` |
| `PATCH .../slo-assignments/{id}` | Seed an SLO definition in fixtures; hook injects its real ID |

**Effort:** Varies per endpoint. Hooks are cheap (1-2 hours each). Endpoint splits
are larger refactors. Some exclusions (SLI plugin registry) may be permanent by design.

### 3. Pact consumer/provider contracts

**What exists:** Schema contract tests in `api/tests/test_schema_contracts.py` verify
field names and types. Phase 1 codegen catches type drift at the TypeScript layer.

**What Pact would add:** The frontend explicitly declares which endpoints it calls,
with which parameters, and what response shape it expects. The backend replays those
recorded interactions against the real app. This catches a class of bug that schema
tests and Schemathesis both miss: **the frontend uses an endpoint in a way the
backend doesn't expect** (wrong query param combination, missing header, unexpected
field interaction).

**When it becomes worth it:** When TROPEK has multiple contributors or external API
consumers. For a single developer, the current schema tests + codegen + Schemathesis
combination covers the same ground with less ceremony.

**What's already planned:** Full implementation plan at
`docs/superpowers/plans/2026-04-12-contract-testing-phase-2-pact.md`. Covers:
- `@pact-foundation/pact` consumer tests in `ui/src/contracts/` (6 initial contracts)
- `pact-python` provider verification in `api/tests/contracts/`
- Provider state hooks for fixture seeding
- CI workflow with freshness check on generated pact files

### 4. OWASP ZAP deep security scanning

**What exists:** Schemathesis runs basic security probes (SQL injection payloads,
path traversal, XSS) on every push. FastAPI + SQLAlchemy parameterised queries make
these clean.

**What ZAP would add:** Deeper, slower scanning that goes beyond Schemathesis:
- Multi-step SQL injection with nested payloads and encoding tricks
- Authentication bypass attempts (insecure direct object references)
- Session management probes
- Full OWASP API Top 10 coverage
- Active scanning that follows redirects and probes error pages

**When it becomes worth it:** Before any public deployment or when handling sensitive
data. The scan takes 10-30 minutes and generates false positives that need tuning, so
it's designed as a weekly/on-demand check, not per-push.

**What's already planned:** Full implementation plan at
`docs/superpowers/plans/2026-04-12-contract-testing-phase-4-owasp-zap.md`. Covers:
- ZAP in Docker with auth context (API key header injection)
- Suppression file for reviewed false positives
- Weekly GitHub Actions schedule
- Report parser that auto-opens GitHub issues for HIGH findings
- `just security-scan` recipe for local runs

### 5. Schemathesis custom checks

**What exists:** All built-in checks are enabled (`load_all_checks()`).

**What custom checks would add:** Project-specific invariants verified on every
generated request. Examples:

- **Pagination consistency:** every paginated list endpoint returns `total` >= length
  of `items`, and `offset + len(items) <= total`
- **Idempotency:** PUT endpoints return the same response on repeated calls
- **Soft-delete consistency:** DELETEd resources return 404 on subsequent GET (not 200
  with stale data)
- **Cache header correctness:** responses that should be cached have appropriate
  `Cache-Control` headers

**Effort:** Low per check. Schemathesis supports registering custom check functions
via `schemathesis.check` decorator. Each check receives the response and case, and
raises `AssertionError` on failure.

### 6. E2E contract smoke tests

**What exists:** `scripts/e2e_tests.py` runs during `just dev` and verifies basic
endpoint availability. Integration tests cover business logic with a real DB.

**What E2E contract tests would add:** A lightweight Playwright or HTTP-client test
suite that boots the full stack (API + worker + adapter + UI) and runs through
critical user journeys: trigger an evaluation, wait for completion, verify the
heatmap updates, add an annotation, verify it appears. This catches integration bugs
between services that unit/integration tests miss (e.g. worker doesn't write results
in the shape the UI expects, or the Redis cache returns stale data).

**Effort:** High (full stack boot, async waiting, flake management). Most valuable
after the core contract testing layers are solid.

---

## Trajectory

The Schemathesis journey from first run to green CI:

| Checkpoint | Passed | Failed |
|---|---|---|
| First run (raw) | 11 | 90 |
| After URL redesign (Phase 1) | 71 | 33 |
| After field-level fixes (Phase 2) | 90 | 14 |
| After residual fix plan (Groups A-F) | 84 | 13 |
| After patterns α+β fixes | ~97 | ~6 |
| Final (CI green) | 97 | 0 |

Integration tests stayed at 265/265 throughout. UI tests at 646/646. SDK tests at
23/23.

---

## Quick Reference

| What | Command |
|---|---|
| Run Schemathesis locally | `just test-env && just test-schema` |
| Run specific operation | `just test-schema -k 'POST /assets'` |
| Regenerate OpenAPI spec | `just export-schema` |
| Regenerate TypeScript types | `just codegen` |
| CI freshness check | `just check-schema-fresh` |
| View test audit | `reports/test-audit.md` |
| View Schemathesis reports | `reports/schemathesis-phase3-final.md` |
| Design spec | `docs/superpowers/specs/2026-04-12-contract-testing-design.md` |
