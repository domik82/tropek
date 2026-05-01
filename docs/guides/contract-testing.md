# Contract Testing

TROPEK uses a phased contract testing strategy to ensure the backend (FastAPI) and
frontend (React/TypeScript) stay in sync, the API conforms to its own OpenAPI spec,
and common security vulnerabilities are caught automatically. Each phase is
independent — it stands on its own value and does not require later phases to be built.

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

**Goal:** FastAPI is the single source of truth for all API types. Frontend types are
generated from the live OpenAPI spec. TypeScript catches field renames and type
mismatches at compile time — before they ever reach runtime.

### How it works

1. `scripts/export-schema.py` imports the FastAPI `app` object directly (no server
   boot) and writes `api/openapi.json`.
2. `openapi-typescript` reads that file and generates `ui/src/generated/api.ts` — a
   full TypeScript type tree covering every request body, response, query parameter,
   and path parameter.
3. Feature-level `domain.ts` files import or alias from those generated types. See the
   UI layering design at `docs/superpowers/specs/2026-04-12-ui-layering-design.md`.

### Commands

```bash
just export-schema        # Regenerate api/openapi.json from the FastAPI app
just codegen              # Regenerate ui/src/generated/api.ts from the OpenAPI spec
just check-schema-fresh   # CI gate: regen both, fail if git diff is non-empty
```

### CI

`.github/workflows/contract-freshness.yml` runs `just check-schema-fresh` on every
push to `main` and on PRs that touch backend code, the OpenAPI spec, or generated
types. The workflow fails if the regenerated files differ from what is committed —
ensuring the spec and generated types are never stale.

### What it catches

- Silent field renames: backend renames a field, frontend only discovers at runtime
- Missing response fields
- Type mismatches between Pydantic models and TypeScript interfaces

---

## Phase 2 — Schema Contract Tests

**Goal:** Prevent silent API contract breakage when backend Pydantic schemas change.
CI fails if field names, nested model types, or enum values drift from what the
frontend expects.

The original design spec called for `@pact-foundation/pact` consumer/provider testing.
What was implemented instead is a comprehensive suite of Pydantic schema contract tests
in `api/tests/common/test_openapi_postprocessor.py` and related files — a pragmatic
alternative that achieves the same goal without the Pact broker infrastructure overhead.

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

The Pact plan exists at
`docs/superpowers/plans/2026-04-12-contract-testing-phase-2-pact.md` if the project
grows to multiple contributors and the overhead becomes worthwhile.

---

## Phase 3 — Schemathesis Property-Based Testing

**Goal:** Prove the backend correctly implements its own OpenAPI spec across a wide
range of inputs — valid, boundary, malformed, and security-oriented — not just the
happy paths tested by integration tests.

### How it works

Schemathesis reads the OpenAPI spec from the live FastAPI app via ASGI transport (no
network port needed) and auto-generates hundreds of test cases per endpoint using
Hypothesis-driven property-based testing. For each generated request it verifies:

- **Response schema conformance** — every response matches its declared shape
- **No unhandled 500s** — `not_a_server_error` check catches validation gaps
- **Negative data rejection** — invalid inputs are rejected with appropriate 4xx codes
- **Positive data acceptance** — valid inputs are accepted (not rejected with 422)
- **Security probes** — SQL injection, path traversal, and XSS payloads in string
  fields (FastAPI + SQLAlchemy ORM provides strong defaults; Schemathesis confirms it)

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

`.github/workflows/schemathesis.yml` runs on every push to `main` and on PRs touching
backend code. Uses a TimescaleDB service container on port 5433 (same pattern as
integration tests).

### Test harness architecture

The conftest replaces the app's production lifespan with a test stub that:

- Uses **fakeredis** for the cache layer (no Redis dependency)
- Provides a **no-op arq pool** (worker jobs are not triggered)
- Creates a **fresh NullPool engine per request** to avoid event-loop conflicts
  (Hypothesis runs each example in its own event loop via anyio)

### Excluded operations

Some endpoints are excluded from fuzzing entirely because they enqueue arq worker jobs
or require pre-existing domain state that stateless fuzzing cannot set up:

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
cross-field constraint cannot be expressed in OpenAPI 3.1:

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

These are not bugs — they are legitimate validation rules. Schemathesis generates
inputs that pass JSON Schema but fail domain rules, causing false
`positive_data_acceptance` failures. Only that one check is disabled per endpoint; all
other checks (500 detection, response schema conformance, security probes) stay active.

### Backend fixes driven by Schemathesis

Schemathesis found real bugs and design issues during Phase 3. Fixes fall into several
categories:

#### URL redesign

The original URL structure had several problems Schemathesis surfaced. Six commits
delivered a full RESTful URL redesign:

- **Collection paths**: plural (`/evaluations`, `/assets`, `/note-categories`)
- **Single-resource paths**: singular (`/evaluation/{id}`, `/evaluation-run/{id}`)
- **Re-evaluate split**: the original `POST /evaluations/re-evaluate` with XOR body
  fields split into three scope-specific endpoints:
  - `POST /evaluations/re-evaluate/from-date`
  - `POST /evaluations/re-evaluate/from-baseline`
  - `POST /evaluations/re-evaluate/from-evaluation/{evaluation_id}`
- **Trend split**: `GET /assets/{name}/slos/{slo}/trend` + `GET /evaluation/{id}/trend`
- **SLO assignment URLs**: moved reference IDs from request body into URL path
  (`PUT /assets/{name}/slo-definitions/{slo_id}` instead of
  `POST /assets/{name}/slo-assignments` with `slo_definition_id` in body)

#### Input validation hardening

| Fix | File | What it prevents |
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
  so Schemathesis does not flag them as undocumented
- **`propertyNames.pattern`** injected from `patternProperties` in the schema export
  script, so Schemathesis generates keys matching tag/label constraints
- **`anyOf`** on `MetaSnapshotCreate` to surface the values-or-closed constraint
- **Nullable datetime fix** on query params — replaced `nullable: true` with `anyOf`
  containing only the datetime format
- **405 middleware fix** — `MethodNotAllowedMiddleware` now walks parameterized routes
  correctly, returning 405 instead of 404 for unsupported methods on `{name:path}`
  subroutes

### Trajectory from first run to green CI

| Checkpoint | Passed | Failed |
|---|---|---|
| First run (raw) | 11 | 90 |
| After URL redesign | 71 | 33 |
| After field-level fixes | 90 | 14 |
| After residual fix plan (Groups A-F) | 84 | 13 |
| After patterns α+β fixes | ~97 | ~6 |
| Final (CI green) | 97 | 0 |

Integration tests stayed at 265/265 throughout. UI tests at 646/646.

---

## Phase 4 — OWASP ZAP Deep Security Scanning

**Status: PLANNED — not yet implemented.**

Schemathesis already provides basic security probes (negative data rejection, SQL
injection payloads, path traversal) on every push. ZAP would add deeper scanning that
goes beyond Schemathesis:

- Multi-step SQL injection with nested payloads and encoding tricks
- Authentication bypass attempts (insecure direct object references)
- Session management probes
- Full OWASP API Top 10 coverage
- Active scanning that follows redirects and probes error pages

ZAP runs slowly (10-30 minutes) and generates false positives that need tuning, so it
is designed as a weekly/on-demand scan rather than per-push.

**What the implementation would involve:**

- ZAP running in Docker against a test instance with auth context (API key header
  injection)
- Suppression file for reviewed false positives
- Weekly GitHub Actions schedule + manual `just security-scan`
- Report parser that auto-opens GitHub issues for HIGH findings

**Plan:** `docs/superpowers/plans/2026-04-12-contract-testing-phase-4-owasp-zap.md`

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
