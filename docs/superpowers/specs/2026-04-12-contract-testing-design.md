# Contract Testing Between Backend and Frontend

**Date:** 2026-04-12
**Status:** Design approved — ready for implementation planning

## Problem

The TROPEK backend (FastAPI) and frontend (React/TypeScript) are out of sync in ways that only surface at runtime:

1. **Silent type drift** — renaming a backend field doesn't break the frontend build; it breaks at runtime when the user clicks the affected page.
2. **Missing endpoint coverage** — the backend exposes functionality the UI never exercises. Concrete example: the baseline-pin endpoint supports pinning individual SLOs, but the UI only offers "pin all SLOs for this evaluation." The divergence is invisible until someone reads the backend router.
3. **Mocks that lie** — the frontend MSW handlers in `ui/src/mocks/handlers/` are hand-written. Their shapes are maintained by whoever touched them last, not by the backend. A mock can pass every test while returning a structure the real API would never produce.
4. **No automated detection** — nothing in CI tells us when any of the above happens.

The goal is to make the backend the single source of truth for all API contracts, prove the frontend respects that contract, prove the backend delivers that contract, and have CI catch any divergence automatically.

## Non-goals

- Replacing existing MSW usage for component tests. MSW stays — it's the right tool for UI component isolation.
- End-to-end browser testing with Playwright/Cypress. Contract testing is not E2E testing; the two are complementary.
- Replacing integration tests. Integration tests exercise business logic and DB state — contract tests only verify the API contract.
- Pact broker infrastructure. File-based contracts in-repo are sufficient for a single-developer open-source project.

## Constraints

- **Single developer, no existing CI.** Solutions must be setup-light and runnable locally. CI will use GitHub Actions free tier on a private repository.
- **No paid services.** No PactFlow, no hosted brokers, no commercial scanners.
- **Python 3.13 / FastAPI / SQLAlchemy / asyncpg backend.** Port any Python tooling choice to this version.
- **React 19 / TypeScript 5.9 / Vite / Vitest frontend.** MSW already configured.
- **Existing test infrastructure.** Integration tests already use a dedicated test database on port 5433. Contract verification must reuse this, not build a parallel stack.

## Approach — phased rollout

The design is deliberately phased from lightest to heaviest. Each phase is independently valuable and can ship on its own. No phase depends on later phases being built.

```
Phase 1 — openapi-typescript type generation        (every push)
Phase 2 — Pact consumer + provider contracts        (every push)
Phase 3 — Schemathesis --checks=all fuzzing         (every push)
Phase 3.5 — test audit (one-time review gate)
Phase 4 — OWASP ZAP deep security scan              (weekly + manual)
```

---

## Phase 1 — OpenAPI type generation

**Outcome:** FastAPI is the single source of truth for all API types. Frontend types are generated from the live spec, never hand-written. TypeScript catches field renames at compile time.

### How it works

FastAPI already exposes `/openapi.json`. A new Python script imports the FastAPI `app` object directly, calls `app.openapi()`, and writes `api/openapi.json` — no server boot required. `openapi-typescript` then reads that file and writes `ui/src/generated/api.ts`, a full TypeScript type tree covering every request body, response, query parameter, and path.

Manually-maintained types in `ui/src/features/*/types.ts` are replaced incrementally with imports from `ui/src/generated/api.ts`. The existing mock data in `ui/src/mocks/generate.ts` keeps working — it just gets typed against generated types. `tsc --noEmit` catches any divergence.

### Files added

- `scripts/export-schema.py` — imports FastAPI `app`, writes `api/openapi.json`
- `ui/src/generated/api.ts` — generated, committed, never hand-edited
- `just export-schema` recipe — runs the Python script
- `just codegen` recipe — runs `openapi-typescript api/openapi.json -o ui/src/generated/api.ts`
- `just check-schema-fresh` recipe — regenerates schema + codegen, fails if `git diff` is non-empty

### Files changed

- `ui/src/features/*/types.ts` — progressively aliased to generated types. Migration is file-by-file, not a big bang.
- `ui/package.json` — add `openapi-typescript` as devDependency
- `api/pyproject.toml` — no new dependencies; FastAPI's `.openapi()` is built-in

### CI integration

A single step in the frontend job: run `just check-schema-fresh`. If the generated files are out of date relative to the backend, the job fails with a clear message to run codegen locally. This is the forcing function that keeps the two sides in lockstep.

### Why this first

It's mechanical, low-ceremony, and immediately eliminates an entire class of bugs. Even without Phase 2/3/4, Phase 1 alone fixes "silent type drift" — the largest source of current divergence. Everything else builds on having a committed `api/openapi.json` file, so this phase is a prerequisite anyway.

---

## Phase 2 — Pact consumer + provider contract testing

**Outcome:** The frontend formally declares what it expects from each endpoint. The backend proves it delivers exactly that. CI fails if either side breaks the contract. Coverage gaps between frontend usage and backend capability become explicit.

### How it works

**Consumer side (frontend):** A new test suite under `ui/src/contracts/` — separate from component tests — uses `@pact-foundation/pact`. Each test file covers one logical API area (evaluations, assets, SLOs). For each test, Pact spins up a local HTTP mock server, the frontend `fetch`-based API client makes real requests against it, and Pact records the interaction: "when the frontend calls `GET /api/evaluations/:id` with these headers, it expects this response shape." The output is a JSON pact file per consumer-provider pair, written to `ui/pacts/tropek-ui-tropek-api.json` and committed to the repository.

**Provider side (backend):** A new pytest marker `contract` in `api/tests/contracts/`. A single test uses `pact-python`'s `Verifier` to boot the actual FastAPI test app (reusing integration-test infrastructure — same port-5433 database) and replay every interaction from `ui/pacts/`. If the real backend returns a different shape, status code, missing field, or extra field the consumer didn't expect, the verifier fails loudly.

### Why two mock systems are fine

Pact's mock server is not a replacement for MSW. MSW stays as the dev-server and component-test mock. Pact only runs during contract tests. The two never overlap in practice, and keeping them separate is cleaner than trying to unify them.

### Files added

**Consumer (frontend):**

- `ui/src/contracts/evaluations.contract.test.ts`
- `ui/src/contracts/assets.contract.test.ts`
- `ui/src/contracts/slos.contract.test.ts`
- `ui/src/contracts/datasources.contract.test.ts`
- `ui/src/contracts/setup.ts` — shared Pact configuration, consumer/provider names, output directory
- `ui/pacts/tropek-ui-tropek-api.json` — generated, committed

**Provider (backend):**

- `api/tests/contracts/test_provider.py` — single verifier test, loops over all pact files
- `api/tests/contracts/conftest.py` — boots FastAPI test app, seeds fixture data needed by the consumer-declared preconditions

**Tooling:**

- `just test-contracts-ui` — runs consumer tests, writes pact files
- `just test-contracts-api` — runs provider verification against existing pact files
- `just test-contracts` — runs both in sequence

### Initial contract scope

The first wave covers the highest-value endpoints. Everything else gets added incrementally as endpoints are touched.

1. `GET /api/evaluations` — paginated list
2. `GET /api/evaluations/:id` — full detail including all SLO indicator groups
3. `POST /api/evaluations/re-evaluate` — complex response shape with the pin-conflict error case
4. `PATCH /api/evaluations/:id/pin-baseline` — the divergence already identified
5. `GET /api/assets` / `GET /api/asset-groups/tree`
6. `GET /api/slos` / `GET /api/slo-groups`

### Provider state handling

Some consumer interactions require the backend to be in a specific state ("given an evaluation exists with id X"). Pact supports this via provider states — named setup hooks on the backend side. The conftest defines a registry mapping state names to fixture functions that populate the test DB before each replay.

### CI integration

GitHub Actions workflow:

1. Consumer contract tests run in the frontend job → produces/updates `ui/pacts/*.json`
2. If the pact files have changed, fail the job and instruct the developer to commit them (same pattern as Phase 1 codegen freshness check)
3. Provider verification runs in the backend job, using the committed pact files
4. If the backend doesn't satisfy the contract, the job fails with Pact's detailed diff

### The coverage gap revelation

When the first `PATCH /api/evaluations/:id/pin-baseline` consumer test is written, the author must explicitly declare which fields are sent and which are expected back. This forces an explicit comparison with the backend router's supported payload. The "pin one SLO vs pin all SLOs" mismatch surfaces as a contract authoring decision, not a runtime surprise six months later.

---

## Phase 3 — Schemathesis property-based backend testing

**Outcome:** The backend is proven to correctly implement its own OpenAPI spec across a wide range of inputs — not just the happy path. Schema violations, unhandled 500s, and malformed error responses are caught automatically.

### How it works

Schemathesis reads `api/openapi.json` (produced in Phase 1) and auto-generates hundreds of test cases per endpoint using Hypothesis-driven property-based testing. Valid inputs, boundary values, wrong types, missing fields, oversized payloads. It sends them to a running FastAPI instance and asserts that every response conforms to the declared schema, no endpoint crashes with an unexpected 500, and declared error responses (422, 404, 409) match their declared shapes.

No test code is written — Schemathesis generates test cases from the spec. Configuration lives in `pyproject.toml` under `[tool.schemathesis]`.

### Stateful testing

Schemathesis stateful mode chains requests into realistic sequences — "POST creates an SLO, GET fetches it, DELETE removes it" — and verifies each step. This catches bugs that only appear when endpoints are called in sequence, which happy-path integration tests often miss.

### Security checks

The `--checks=all` flag enables built-in security checks:

- SQL injection payload attempts in string fields (`' OR 1=1 --` and variations)
- Path traversal sequences in path parameters (`../../etc/passwd`)
- XSS payloads in string inputs
- Oversized input attempts designed to provoke crashes

FastAPI + SQLAlchemy ORM gives strong default protection against SQL injection, so the expected result is zero findings. Running the checks anyway confirms the assumption and will catch any future raw-query or parameter-interpolation mistake.

### Files added

- `api/pyproject.toml` — add `schemathesis` to dev dependencies; add `[tool.schemathesis]` configuration block
- `api/tests/schemathesis/conftest.py` — boots FastAPI test app, provides auth headers, configures excluded endpoints
- `api/tests/schemathesis/test_schema.py` — single entry point that Schemathesis expands into hundreds of test cases
- `scripts/schemathesis-run.sh` — wrapper for CI that runs the full suite as a single auto-approved command
- `just test-schema` recipe

### Endpoint exclusions

Some endpoints are excluded from fuzzing where side effects would pollute the test environment:

- `POST /api/evaluations` — spawns arq worker jobs; the worker queue shouldn't be fuzzed with synthetic triggers
- `POST /api/evaluations/re-evaluate` — same reason

These endpoints stay covered by Pact (Phase 2) and existing integration tests.

### Performance assertion

Any endpoint taking longer than 2 seconds on test-scale data flags as a regression. Useful as an early warning for N+1 queries and unintentional full-table scans.

### CI integration

Runs in the backend job after provider verification. Uses the existing port-5433 test database. Total runtime is expected to be 30–90 seconds for the full suite given the current endpoint count.

---

## Phase 3.5 — Test audit (one-time review gate)

**Outcome:** Existing unit and integration tests are deduplicated against Phase 2/3 coverage. Redundant tests are removed. Genuine coverage gaps (business logic, multi-step sequences) are identified and expanded.

### The distinction to apply

| What covers it | Keep in integration tests? |
|---|---|
| API shape, field presence, status codes | No — Pact owns this now |
| Edge inputs, malformed requests, 422 handling | No — Schemathesis owns this |
| Business logic: "after trigger, score is computed correctly" | Yes — irreplaceable |
| Multi-step sequences: "create SLO → assign → evaluate → pin baseline" | Yes — neither Pact nor Schemathesis tests state chains |
| DB state assertions: "evaluation is persisted with correct relationships and tags" | Yes |
| Duplicate of a Pact interaction but exercised through a real DB | Remove |

### How to do it efficiently

A one-time audit script `scripts/test-coverage-audit.py`:

1. Reads all Pact interaction names from `ui/pacts/*.json`
2. Reads the Schemathesis run report (JSON output via `--report`)
3. Lists all integration test functions under `api/tests/` with their docstrings
4. Produces a Markdown table: each integration test → "covered by Pact" / "covered by Schemathesis" / "unique — keep"

The developer reviews the table, deletes the rows marked redundant, and expands the unique-but-thin rows where the business-logic assertions are shallow. The script is a one-time tool — runs once, output is actioned, done. The resulting report is committed as documentation of the decision.

### Files added

- `scripts/test-coverage-audit.py` — audit script
- `just test-audit` recipe
- `reports/test-audit.md` — committed after review, documents which tests were removed and why

### What this is not

This is not an automated deletion step. The script produces a proposal; a human reviews every row before deleting anything. Mistakes here silently lose coverage, so the human-in-the-loop is mandatory.

---

## Phase 4 — OWASP ZAP deep security scanning

**Outcome:** The API is actively probed for exploitable vulnerabilities — SQL injection beyond Schemathesis's basic checks, XSS, path traversal, broken authentication, insecure direct object references, and the rest of the OWASP API Top 10.

### How it works

OWASP ZAP (Zed Attack Proxy) is the standard open-source tool. It runs in Docker, reads `api/openapi.json` to learn every endpoint, and performs active scanning against a running test instance. Findings are classified by severity and written to an HTML/JSON report.

Unlike Phases 1–3, this does **not** run on every push. It runs:

- Manually before a release — `just security-scan`
- On a weekly GitHub Actions schedule, off-peak
- As a one-off whenever auth logic or a new endpoint is added

### Why not on every push

Active scanning is slow (10–30 minutes), generates false positives that need tuning, and its value is concentrated in periodic reviews, not per-commit feedback. Running it on every push would drown the signal and burn GitHub Actions minutes.

### Files added

- `scripts/security-scan.sh` — starts test app, runs ZAP in Docker, writes report to `reports/security/`
- `.github/workflows/security.yml` — weekly scheduled workflow, posts a GitHub issue if HIGH findings are detected
- `scripts/zap-context.xml` — ZAP authentication context (API key header, test user credentials)
- `scripts/zap-suppressions.yaml` — reviewed false-positive suppression list, committed
- `just security-scan` recipe
- `reports/security/` — gitignored; reports are archived as GitHub Actions artifacts instead

### Scope

- Passive scan always on — reads responses, never sends attack payloads, safe for any environment
- Active scan — SQL injection, XSS, path traversal, IDOR, broken auth probes. Runs against test DB only, never dev or prod, never a shared environment.
- Authenticated endpoints covered — ZAP context file supplies the API key header so protected routes are probed under real conditions.

### Acceptance criteria

The scan is considered green when:

- Zero HIGH or CRITICAL findings
- All MEDIUM findings are either fixed or explicitly acknowledged in `scripts/zap-suppressions.yaml` with a justification comment
- LOW and INFORMATIONAL findings are tracked in GitHub issues for batched triage

---

## Rollout order and success criteria

| Phase | Ships when | Success criterion |
|---|---|---|
| 1 | `just check-schema-fresh` passes in CI | Frontend builds fail on any backend field rename |
| 2 | First 6 contracts written, provider verification green | Pin-baseline coverage gap explicitly documented |
| 3 | Schemathesis runs green on every push | Backend proven conformant to its own spec |
| 3.5 | Audit report committed | Integration test suite is leaner and more business-logic focused |
| 4 | First weekly scan runs, suppressions tuned | Zero HIGH findings, documented triage process for MEDIUM |

Each phase is independently deployable. If implementation stalls after Phase 1, the project still benefits from eliminated type drift. If it stalls after Phase 2, the contract gap is closed. Nothing in the design requires all four phases to land.

## Open questions

None blocking implementation. Secondary decisions (specific Pact version, whether to use `pact-python` or the newer `pact-python-v3`, exact ZAP configuration for authenticated scanning) are deferred to the implementation plan for each phase.
