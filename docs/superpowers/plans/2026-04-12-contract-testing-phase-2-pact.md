# Contract Testing — Phase 2: Pact Consumer + Provider Contracts

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The frontend formally declares its expectations for each API endpoint. The backend proves it delivers exactly those expectations. CI fails if either side drifts from the contract. The existing baseline-pin divergence (UI pins all SLOs, backend supports per-SLO) is surfaced explicitly when that contract is written.

**Architecture:** Consumer contract tests live in `ui/src/contracts/` using `@pact-foundation/pact`. Each test spins up a local Pact mock HTTP server and makes real `fetch` calls against it. Running the suite produces `ui/pacts/tropek-ui-tropek-api.json` — committed to the repo. The backend runs a single pytest that uses `pact-python`'s `Verifier` to boot the real FastAPI test app, seed provider states, and replay every recorded interaction against the real code.

**Tech Stack:** `@pact-foundation/pact` (Node/TypeScript), `pact-python` (Python), Vitest, pytest, FastAPI test client, existing test DB on port 5433.

**Recommended subagent model:** **Sonnet**. Pact has a learning curve — the consumer DSL, matcher semantics (`like`, `eachLike`, `regex`), provider-state orchestration, and the two-sided verification loop all require reasoning about non-trivial interactions. Haiku is too shallow for this; Opus is overkill for file-by-file implementation of well-specified contracts. Sonnet is the right tradeoff.

**Prerequisite:** Phase 1 complete. `api/openapi.json` and `ui/src/generated/api.ts` exist and are fresh.

**Spec reference:** `docs/superpowers/specs/2026-04-12-contract-testing-design.md` (Phase 2 section).

---

### Task 1: Install Pact consumer dependency

**Files:**
- Modify: `ui/package.json`

- [ ] **Step 1: Install**

Run: `cd ui && pnpm add -D @pact-foundation/pact`

Expected: `@pact-foundation/pact` appears in devDependencies at version 15.x or later.

- [ ] **Step 2: Verify import works**

Create a throwaway file `ui/src/contracts/_import-check.ts`:

```typescript
import { PactV4, MatchersV3 } from '@pact-foundation/pact'
export const _ = { PactV4, MatchersV3 }
```

Run: `cd ui && pnpm exec tsc --noEmit -p tsconfig.app.json`
Expected: no errors.

- [ ] **Step 3: Delete the check file and commit**

```bash
rm ui/src/contracts/_import-check.ts
git add ui/package.json ui/pnpm-lock.yaml
git commit -m "chore(contract): add @pact-foundation/pact devDependency"
```

---

### Task 2: Set up contracts test directory and shared config

**Files:**
- Create: `ui/src/contracts/setup.ts`
- Create: `ui/pacts/.gitkeep`
- Create: `ui/src/contracts/README.md`
- Modify: `ui/vite.config.ts`

- [ ] **Step 1: Inspect current vitest config**

Read `ui/vite.config.ts`. Note the current `test` block, especially `include` / `exclude` patterns.

- [ ] **Step 2: Exclude contract tests from the default vitest run**

Contract tests spin up a real HTTP mock server and are slower than component tests. They should run separately. In `ui/vite.config.ts`, inside the existing `test` block, add:

```typescript
    exclude: [
      '**/node_modules/**',
      '**/dist/**',
      'src/contracts/**', // contract tests run separately via `just test-contracts-ui`
    ],
```

If there is already an `exclude` array, append `'src/contracts/**'` to it. Do NOT remove any existing patterns.

- [ ] **Step 3: Create `ui/src/contracts/setup.ts`**

```typescript
// Shared Pact configuration for all consumer contract tests.
// Every contract test imports `newPact()` to get a configured PactV4 instance.

import { PactV4, SpecificationVersion } from '@pact-foundation/pact'
import path from 'node:path'

const PACT_DIR = path.resolve(__dirname, '../../pacts')
const LOG_DIR = path.resolve(__dirname, '../../pacts/.logs')

export const CONSUMER = 'tropek-ui'
export const PROVIDER = 'tropek-api'

export function newPact(): PactV4 {
  return new PactV4({
    consumer: CONSUMER,
    provider: PROVIDER,
    dir: PACT_DIR,
    logLevel: 'warn',
    spec: SpecificationVersion.SPECIFICATION_VERSION_V4,
    logFile: path.join(LOG_DIR, 'pact.log'),
  })
}
```

- [ ] **Step 4: Create placeholder pact dir**

Run: `mkdir -p ui/pacts && touch ui/pacts/.gitkeep`

- [ ] **Step 5: Create `ui/src/contracts/README.md`**

```markdown
# Consumer Contract Tests

These tests run against a local Pact mock HTTP server, not MSW. They produce
`ui/pacts/tropek-ui-tropek-api.json`, which the backend verifies.

## Running

\`\`\`
just test-contracts-ui
\`\`\`

## Adding a new contract

1. Create a new `*.contract.test.ts` file in this directory.
2. Import `newPact()` from `./setup`.
3. Use `.addInteraction()` to declare one interaction per test.
4. Make the real fetch call inside `.executeTest()`.
5. Run the suite — the pact file will be regenerated.
6. Commit the updated `ui/pacts/tropek-ui-tropek-api.json` with your test changes.

## Matcher guidance

- Use `like(value)` for fields where the exact value doesn't matter but the type does.
- Use `eachLike(value)` for arrays — asserts at least one element matching the shape.
- Use `regex(pattern, value)` for structured strings (IDs, dates).
- Do NOT assert exact values unless they are part of the contract
  (enum values, known error codes, etc.).
```

- [ ] **Step 6: Commit**

```bash
git add ui/src/contracts/setup.ts ui/src/contracts/README.md ui/pacts/.gitkeep ui/vite.config.ts
git commit -m "chore(contract): scaffold ui/src/contracts/ and exclude from default vitest run"
```

---

### Task 3: Write the first consumer contract — GET /api/evaluations/:id

**Files:**
- Create: `ui/src/contracts/evaluations.contract.test.ts`

This is the reference contract. Every subsequent contract follows the same shape. Start here because the evaluation detail endpoint is the most frequently consumed and has the richest shape (SLO indicators, annotations, etc.).

- [ ] **Step 1: Look up the actual response shape**

Read `api/tropek/modules/quality_gate/schemas/evaluations.py` and `api/tropek/modules/quality_gate/router.py`. Find the Pydantic model used as the response for `GET /api/evaluations/{id}`. Note every field name, type, and whether it is optional. You will need this to write the Pact matchers accurately.

- [ ] **Step 2: Write the contract test**

```typescript
import { describe, it } from 'vitest'
import { MatchersV3 } from '@pact-foundation/pact'
import { newPact } from './setup'

const { like, eachLike, regex, integer, iso8601DateTimeWithMillis } = MatchersV3

describe('Evaluation detail contract', () => {
  it('GET /api/evaluations/:id returns full evaluation detail', async () => {
    const pact = newPact()

    await pact
      .addInteraction()
      .given('an evaluation exists with id 00000000-0000-0000-0000-000000000001')
      .uponReceiving('a request for evaluation detail')
      .withRequest('GET', '/api/evaluations/00000000-0000-0000-0000-000000000001')
      .willRespondWith(200, (builder) =>
        builder
          .headers({ 'Content-Type': regex('application/json.*', 'application/json') })
          .jsonBody({
            id: regex(
              '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
              '00000000-0000-0000-0000-000000000001',
            ),
            asset_name: like('service-a'),
            slo_name: like('p95-latency'),
            evaluation_name: like('nightly-run'),
            result: regex('pass|warning|fail', 'pass'),
            score: like(95.5),
            period_start: iso8601DateTimeWithMillis(),
            period_end: iso8601DateTimeWithMillis(),
            indicators: eachLike({
              name: like('response_time_p95'),
              value: like(420.5),
              result: regex('pass|warning|fail', 'pass'),
              score: like(2),
              pass_criteria: like('<500'),
              warning_criteria: like('<700'),
              comparison_value: like(400.0),
            }),
            invalidated: like(false),
          }),
      )
      .executeTest(async (mockServer) => {
        const res = await fetch(
          `${mockServer.url}/api/evaluations/00000000-0000-0000-0000-000000000001`,
        )
        if (!res.ok) throw new Error(`status ${res.status}`)
        const body = await res.json()
        if (!body.id) throw new Error('missing id')
        if (!Array.isArray(body.indicators)) throw new Error('indicators not array')
      })
  })
})
```

**IMPORTANT:** The field list above is a template. Adjust it to match the actual Pydantic response model you read in Step 1. Remove fields that don't exist, add fields that do, and change matchers to match the real types. The goal is that this test documents the real contract, not a fictional one.

- [ ] **Step 3: Add the just recipe**

Modify `justfile`, add after `codegen`:

```makefile
# Run Pact consumer contract tests (produces ui/pacts/*.json)
test-contracts-ui:
    cd ui && pnpm exec vitest run --config vite.config.ts src/contracts
```

- [ ] **Step 4: Run the contract test**

Run: `just test-contracts-ui`

Expected: test passes, `ui/pacts/tropek-ui-tropek-api.json` is created containing one interaction.

- [ ] **Step 5: Inspect the pact file**

Read `ui/pacts/tropek-ui-tropek-api.json`. Confirm it contains a `consumer`, `provider`, and `interactions` array with the interaction you just wrote. This file is the contract.

- [ ] **Step 6: Commit**

```bash
git add ui/src/contracts/evaluations.contract.test.ts justfile ui/pacts/tropek-ui-tropek-api.json
git commit -m "test(contract): add consumer contract for GET /api/evaluations/:id"
```

---

### Task 4: Add the remaining high-value consumer contracts

**Files:**
- Modify: `ui/src/contracts/evaluations.contract.test.ts`
- Create: `ui/src/contracts/assets.contract.test.ts`
- Create: `ui/src/contracts/slos.contract.test.ts`

For each interaction below, follow the same pattern as Task 3: read the real Pydantic schema → write matchers that reflect the real shape → run tests → commit pact file.

- [ ] **Step 1: Add GET /api/evaluations (list) to evaluations.contract.test.ts**

Add a second `it(...)` block inside the same describe:

```typescript
  it('GET /api/evaluations returns paginated list', async () => {
    const pact = newPact()
    await pact
      .addInteraction()
      .given('at least one evaluation exists')
      .uponReceiving('a request for the evaluation list')
      .withRequest('GET', '/api/evaluations', (builder) =>
        builder.query({ limit: '100', offset: '0' }),
      )
      .willRespondWith(200, (builder) =>
        builder.jsonBody({
          items: eachLike({
            id: like('00000000-0000-0000-0000-000000000001'),
            asset_name: like('service-a'),
            slo_name: like('p95-latency'),
            evaluation_name: like('nightly-run'),
            result: regex('pass|warning|fail', 'pass'),
            score: like(95.5),
            period_start: iso8601DateTimeWithMillis(),
            period_end: iso8601DateTimeWithMillis(),
          }),
          total: integer(42),
        }),
      )
      .executeTest(async (mockServer) => {
        const res = await fetch(`${mockServer.url}/api/evaluations?limit=100&offset=0`)
        if (!res.ok) throw new Error(`status ${res.status}`)
      })
  })
```

Adjust fields to match the real `EvaluationSummary` Pydantic model (different from detail — leaner shape).

- [ ] **Step 2: Add PATCH /api/evaluations/:id/pin-baseline**

This is the critical interaction — the one that will surface the UI-vs-backend coverage gap. Add to `evaluations.contract.test.ts`:

```typescript
  it('PATCH /api/evaluations/:id/pin-baseline pins the baseline', async () => {
    const pact = newPact()
    await pact
      .addInteraction()
      .given('an evaluation exists with id 00000000-0000-0000-0000-000000000001')
      .uponReceiving('a request to pin the baseline')
      .withRequest('PATCH', '/api/evaluations/00000000-0000-0000-0000-000000000001/pin-baseline', (builder) =>
        builder
          .headers({ 'Content-Type': 'application/json' })
          .jsonBody({
            reason: like('gold reference build'),
            author: like('alice'),
          }),
      )
      .willRespondWith(200, (builder) =>
        builder.jsonBody({
          id: like('00000000-0000-0000-0000-000000000001'),
          baseline_pinned: like(true),
          baseline_pin: {
            reason: like('gold reference build'),
            author: like('alice'),
          },
        }),
      )
      .executeTest(async (mockServer) => {
        const res = await fetch(
          `${mockServer.url}/api/evaluations/00000000-0000-0000-0000-000000000001/pin-baseline`,
          {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason: 'gold reference build', author: 'alice' }),
          },
        )
        if (!res.ok) throw new Error(`status ${res.status}`)
      })
  })
```

**Coverage gap note:** After writing this, read the real backend `pin-baseline` handler. If it supports a per-SLO pin (e.g. takes an `slo_name` query param or body field), the UI contract above is documenting the reduced feature set the UI actually uses. Leave a TODO comment above the test:

```typescript
// TODO(coverage-gap): backend supports per-SLO baseline pinning via ?slo_name=,
// but the UI only pins all SLOs at once. Expand this contract or the UI when
// per-SLO pinning is added to the frontend.
```

- [ ] **Step 3: Write assets.contract.test.ts**

Create a new file covering `GET /api/assets` and `GET /api/asset-groups/tree`. Follow the same pattern — read `api/tropek/modules/assets/schemas.py`, write matchers that reflect the real Pydantic shape, run the test.

- [ ] **Step 4: Write slos.contract.test.ts**

Cover `GET /api/slos` and `GET /api/slo-groups`. Same pattern — read `api/tropek/modules/slo_registry/schemas.py` first.

- [ ] **Step 5: Run full consumer suite**

Run: `just test-contracts-ui`
Expected: all contracts pass, `ui/pacts/tropek-ui-tropek-api.json` now contains ~6 interactions.

- [ ] **Step 6: Commit**

```bash
git add ui/src/contracts/ ui/pacts/tropek-ui-tropek-api.json
git commit -m "test(contract): add consumer contracts for evaluations, assets, slos"
```

---

### Task 5: Install Pact provider dependency

**Files:**
- Modify: `api/pyproject.toml`

- [ ] **Step 1: Add dependency**

Add `pact-python>=2.2` to the `[dependency-groups].dev` list in `api/pyproject.toml`.

Run: `uv sync`

Expected: `pact-python` installed. Note: `pact-python` 2.x uses the Rust-based FFI core and is the currently maintained version.

- [ ] **Step 2: Verify import**

Run: `uv run --directory api python -c "from pact import Verifier; print(Verifier)"`
Expected: prints the Verifier class without import errors.

- [ ] **Step 3: Commit**

```bash
git add api/pyproject.toml uv.lock
git commit -m "chore(contract): add pact-python to dev dependencies"
```

---

### Task 6: Write the provider verification test

**Files:**
- Create: `api/tests/contracts/__init__.py`
- Create: `api/tests/contracts/conftest.py`
- Create: `api/tests/contracts/test_provider.py`
- Create: `api/tests/contracts/provider_states.py`
- Modify: `api/pyproject.toml` (register `contract` marker)

- [ ] **Step 1: Register the pytest marker**

In `api/pyproject.toml`, find the `[tool.pytest.ini_options]` block (or create one). Add `contract` to the `markers` list:

```toml
[tool.pytest.ini_options]
markers = [
    "integration: requires database and redis",
    "contract: provider contract verification (requires test DB)",
]
```

If the markers list doesn't exist, create it. If it exists with other markers, append `contract` without removing existing entries.

- [ ] **Step 2: Create `api/tests/contracts/__init__.py`**

Empty file:

```python
```

- [ ] **Step 3: Create `api/tests/contracts/provider_states.py`**

This file maps provider-state strings (from the pact file) to setup functions that seed the DB accordingly.

```python
"""Provider state setup for Pact contract verification.

Each consumer interaction declares a `given` string (e.g. "an evaluation exists
with id X"). This module maps those strings to async functions that seed the
test DB so the real FastAPI app returns data matching the expected response.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import (
    Asset,
    AssetGroup,
    EvaluationRun,
    Slo,
)

StateSetup = Callable[[AsyncSession], Awaitable[None]]

FIXTURE_EVAL_ID = UUID('00000000-0000-0000-0000-000000000001')


async def _an_evaluation_exists(session: AsyncSession) -> None:
    """Seed a single deterministic evaluation with known id."""
    asset = Asset(name='service-a', type_name='service')
    session.add(asset)
    await session.flush()

    slo = Slo(name='p95-latency', version=1, spec={'indicators': []})
    session.add(slo)
    await session.flush()

    evaluation = EvaluationRun(
        id=FIXTURE_EVAL_ID,
        asset_name='service-a',
        slo_name='p95-latency',
        evaluation_name='nightly-run',
        result='pass',
        score=95.5,
        period_start=datetime(2026, 3, 10, 0, 0, 0, tzinfo=UTC),
        period_end=datetime(2026, 3, 10, 0, 30, 0, tzinfo=UTC),
        indicators=[],
        invalidated=False,
    )
    session.add(evaluation)
    await session.flush()


async def _at_least_one_evaluation_exists(session: AsyncSession) -> None:
    await _an_evaluation_exists(session)


PROVIDER_STATES: dict[str, StateSetup] = {
    'an evaluation exists with id 00000000-0000-0000-0000-000000000001': _an_evaluation_exists,
    'at least one evaluation exists': _at_least_one_evaluation_exists,
}
```

**IMPORTANT:** The exact field names and constructors above are templates. Before running, check `api/tropek/db/models.py` for the real `EvaluationRun`, `Asset`, and `Slo` model fields — adjust as needed. The test will fail loudly if constructors mismatch, so this is self-correcting.

- [ ] **Step 4: Create `api/tests/contracts/conftest.py`**

```python
"""Conftest for contract verification tests.

Boots a fresh FastAPI test app against the integration test DB (port 5433)
and exposes a fixture that returns its URL. The provider verification test
uses this URL as the `--provider-base-url` for pact-python.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator

import pytest
import uvicorn

from tropek.main import app

HOST = '127.0.0.1'
PORT = 8099


@pytest.fixture(scope='session')
def provider_url() -> Iterator[str]:
    """Start FastAPI on a dedicated port for the duration of the session."""
    config = uvicorn.Config(app, host=HOST, port=PORT, log_level='warning', loop='asyncio')
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for the server to be ready
    loop = asyncio.new_event_loop()

    async def _wait_ready() -> None:
        import httpx

        async with httpx.AsyncClient() as client:
            for _ in range(50):
                try:
                    response = await client.get(f'http://{HOST}:{PORT}/health')
                    if response.status_code == 200:
                        return
                except httpx.ConnectError:
                    pass
                await asyncio.sleep(0.1)
            raise RuntimeError('provider server did not become ready')

    loop.run_until_complete(_wait_ready())
    loop.close()

    yield f'http://{HOST}:{PORT}'

    server.should_exit = True
    thread.join(timeout=5)
```

- [ ] **Step 5: Create `api/tests/contracts/test_provider.py`**

```python
"""Provider verification — replay every consumer contract against the real app."""

from __future__ import annotations

from pathlib import Path

import pytest
from pact import Verifier
from sqlalchemy.ext.asyncio import AsyncSession

from tests.contracts.provider_states import PROVIDER_STATES

REPO_ROOT = Path(__file__).resolve().parents[3]
PACT_FILE = REPO_ROOT / 'ui' / 'pacts' / 'tropek-ui-tropek-api.json'


@pytest.mark.contract
async def test_provider_satisfies_ui_contracts(
    provider_url: str,
    db_session: AsyncSession,
) -> None:
    """Replay every pact interaction against the real FastAPI app."""
    assert PACT_FILE.exists(), f'pact file missing: {PACT_FILE}'

    async def state_handler(state_name: str) -> None:
        setup = PROVIDER_STATES.get(state_name)
        if setup is None:
            raise AssertionError(f'unknown provider state: {state_name!r}')
        await setup(db_session)
        await db_session.commit()

    verifier = Verifier(provider='tropek-api', provider_base_url=provider_url)
    output, logs = verifier.verify_pacts(
        str(PACT_FILE),
        provider_states_setup_url=None,
        state_handler=state_handler,
    )

    assert output == 0, f'pact verification failed:\n{logs}'
```

**Note on the pact-python API surface:** The exact signature of `Verifier.verify_pacts` may vary slightly by version. If the version installed doesn't accept `state_handler` as shown, read the pact-python 2.x API docs and adjust. The concept is always: point the verifier at the pact file, give it a base URL, and provide a mapping/callback from state name to DB setup. Keep the test function short — the logic belongs in `provider_states.py`.

- [ ] **Step 6: Add the just recipe**

Modify `justfile`, after `test-contracts-ui`:

```makefile
# Run Pact provider verification (requires test-env + up-to-date pacts)
test-contracts-api:
    uv run --directory api pytest tests/contracts -m contract -v

# Run full contract suite (consumer then provider)
test-contracts: test-contracts-ui test-contracts-api
```

- [ ] **Step 7: Run the provider verification**

```bash
just test-env
just test-contracts-api
```

Expected: provider test passes. If it fails, the error output from pact-python will point at the exact mismatch (missing field, wrong type, wrong status code). Fix the real backend or adjust the consumer contract to reflect reality — do not silence the error.

- [ ] **Step 8: Commit**

```bash
git add api/tests/contracts/ api/pyproject.toml justfile
git commit -m "test(contract): add pact provider verification for UI contracts"
```

---

### Task 7: Document the baseline-pin coverage gap

**Files:**
- Create: `docs/contract-coverage-gaps.md`

- [ ] **Step 1: Write the doc**

```markdown
# Contract Coverage Gaps

This file tracks cases where the consumer contract (frontend) deliberately
covers less than the provider capability (backend). Each entry is a candidate
for future expansion.

## Baseline pin — per-SLO granularity

**Contract:** `PATCH /api/evaluations/:id/pin-baseline`

**Consumer (UI):** Pins the baseline for the entire evaluation. Body contains
only `{ reason, author }`. No SLO scoping.

**Provider (API):** Supports per-SLO baseline pinning. (Verify this against the
current router implementation when reading this doc — if it has changed, update
this entry or remove it.)

**Why it matters:** A user cannot pin one SLO's baseline while leaving the
others floating. The backend supports the granularity; the UI does not expose it.

**Action:** Either expand the UI to use per-SLO pinning, or narrow the backend
endpoint to only accept the scope the UI actually uses. Decision pending.

---

## Adding new entries

When writing a consumer contract, if you notice the backend supports more than
your contract declares, add an entry here with:

- The endpoint
- What the consumer contract covers
- What the provider supports beyond that
- Why the gap exists (intentional narrowing? unfinished feature? historic drift?)
- What the resolution looks like
```

- [ ] **Step 2: Commit**

```bash
git add docs/contract-coverage-gaps.md
git commit -m "docs(contract): track coverage gaps between consumer and provider"
```

---

### Task 8: Wire provider verification into CI

**Files:**
- Modify: `.github/workflows/contract-freshness.yml` or create new workflow
- Create: `.github/workflows/contract-verify.yml`

- [ ] **Step 1: Create the verification workflow**

```yaml
name: Contract Verification

on:
  pull_request:
    paths:
      - 'ui/src/contracts/**'
      - 'ui/pacts/**'
      - 'api/tropek/**/*.py'
      - 'api/tests/contracts/**'
  push:
    branches: [main]

jobs:
  consumer:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with:
          version: 9
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm
          cache-dependency-path: ui/pnpm-lock.yaml
      - name: Install UI deps
        run: cd ui && pnpm install --frozen-lockfile
      - name: Run consumer contract tests
        run: just test-contracts-ui
      - name: Fail if pacts are stale
        run: git diff --exit-code ui/pacts/ || (echo "pact files stale — run just test-contracts-ui and commit" && exit 1)

  provider:
    runs-on: ubuntu-latest
    needs: consumer
    services:
      postgres:
        image: timescale/timescaledb:latest-pg16
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: tropek_test
        ports:
          - 5433:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv python install 3.13
      - run: uv sync --all-extras
      - name: Apply migrations to test DB
        env:
          QG_DB_PASSWORD: test
          TEST_DATABASE_URL: postgresql+asyncpg://postgres:test@localhost:5433/tropek_test
        run: just migrate-test
      - name: Run provider verification
        env:
          QG_DB_PASSWORD: test
          TEST_DATABASE_URL: postgresql+asyncpg://postgres:test@localhost:5433/tropek_test
        run: just test-contracts-api
```

**Note:** The environment variables above must match what `.env.test` provides locally. Check that file and adjust the workflow to mirror it. If `.env.test` has secrets that aren't in CI, you'll need to add them as GitHub Actions secrets.

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/contract-verify.yml
git commit -m "ci(contract): verify consumer contracts against real backend"
```

---

## Self-review gate

After all tasks complete, run the full loop locally:

```bash
just export-schema                  # Phase 1 — still fresh
just codegen                        # Phase 1 — still fresh
just test-contracts-ui              # Phase 2 — produces/updates pacts
just test-env                       # boot test DB
just test-contracts-api             # Phase 2 — verifies pacts against real app
./scripts/api-test.sh --tail 5      # existing unit tests still green
./scripts/ui-test.sh --tail 10      # existing UI tests still green
```

Everything should pass.

## Expected outcomes

1. `ui/pacts/tropek-ui-tropek-api.json` contains at least 6 interactions
2. The baseline-pin coverage gap is documented in `docs/contract-coverage-gaps.md`
3. CI workflow `contract-verify.yml` runs consumer then provider jobs
4. Any change to a backend response shape without matching pact update fails CI
5. Any change to a consumer contract without matching backend support fails CI

Phase 2 is a foundation — the initial 6 contracts are a starting set, not a complete coverage. Each subsequent PR that touches an API endpoint should add or update the corresponding contract.
