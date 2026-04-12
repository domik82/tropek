# Contract Testing — Phase 3: Schemathesis + Test Audit

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the backend correctly implements its own OpenAPI spec across a wide range of inputs — including basic security checks (SQL injection, path traversal, XSS). After Schemathesis is green, audit the existing unit and integration test suite, remove tests that are now redundant with Pact+Schemathesis coverage, and flag gaps in business logic coverage for expansion.

**Architecture:** Schemathesis reads `api/openapi.json` and auto-generates property-based test cases using Hypothesis. The tests run against a real FastAPI instance using the existing integration test DB on port 5433. A wrapper script makes this a single auto-approved command in CI. After Schemathesis runs, a one-time audit script produces a Markdown table mapping each integration test to coverage source (Pact / Schemathesis / unique business logic).

**Tech Stack:** `schemathesis>=3.36`, pytest, FastAPI test client, existing test DB, the `api/openapi.json` file produced in Phase 1.

**Recommended subagent model (per task group):**

| Tasks | Model | Why |
|---|---|---|
| 1 (install), 2 (harness skeleton) | **Haiku** | `uv sync` + boilerplate conftest and test module. No reasoning required — the templates in the tasks are complete. |
| 3 (first run + triage) | **Sonnet** | The first Schemathesis run will surface real backend bugs. Each failure needs a triage decision: backend bug (fix), auth config missing (handle in Task 4), or legitimate exclusion (document why). Haiku would likely either silence findings or chase ghosts. |
| 4 (auth configuration) | **Sonnet** | Requires grepping the real auth setup in `tropek.main`, understanding `Depends` chains, and choosing between header injection vs session hooks. |
| 5 (security checks), 6 (stateful tests) | **Sonnet** | Schemathesis API surface varies between 3.x minor versions — agent must read docs and adapt. The task describes intent, not the exact current API. |
| 7 (wrapper script), 8 (CI job) | **Haiku** | Mechanical Bash + GitHub Actions YAML. |
| 9 (test audit — Phase 3.5) | **Opus** | The audit script is a proposal, not a final answer. The valuable work is reading every integration test, reasoning about what each verifies, and making judgment calls like "this test *looks* like an API-shape check but actually guards a subtle DB-state invariant — keep it." This is exactly the kind of nuanced reading+reasoning task where Opus outperforms Sonnet. Worth the cost because a wrong deletion silently loses coverage. |
| **Phase 3 verification gate** | **Sonnet** | Runs the full Schemathesis suite, confirms zero findings, and spot-checks a few generated test cases to ensure they look realistic. |

**Prerequisite:** Phase 1 complete (`api/openapi.json` exists and is fresh). Phase 2 recommended but not required — the audit task in Task 9 benefits from having pact interactions to cross-reference.

**Spec reference:** `docs/superpowers/specs/2026-04-12-contract-testing-design.md` (Phase 3 + Phase 3.5 sections).

---

### Task 1: Install Schemathesis

**Files:**
- Modify: `api/pyproject.toml`

- [ ] **Step 1: Add dependency**

Add `schemathesis>=3.36` to the `[dependency-groups].dev` list in `api/pyproject.toml`.

Run: `uv sync`

Expected: `schemathesis` installed. Verify with:

Run: `uv run --directory api schemathesis --version`
Expected: prints a version number.

- [ ] **Step 2: Commit**

```bash
git add api/pyproject.toml uv.lock
git commit -m "chore(contract): add schemathesis to dev dependencies"
```

---

### Task 2: Create the Schemathesis test harness

**Files:**
- Create: `api/tests/schemathesis/__init__.py`
- Create: `api/tests/schemathesis/conftest.py`
- Create: `api/tests/schemathesis/test_schema.py`

- [ ] **Step 1: Create empty init**

`api/tests/schemathesis/__init__.py` — empty file.

- [ ] **Step 2: Create conftest**

```python
"""Conftest for Schemathesis property-based tests.

Loads the committed OpenAPI schema from api/openapi.json and exposes it to
Schemathesis's pytest plugin. The real FastAPI app is mounted via ASGI so no
network port is needed and fixtures can stay inside the pytest event loop.
"""

from __future__ import annotations

from pathlib import Path

import schemathesis
from schemathesis.specs.openapi.schemas import BaseOpenAPISchema

from tropek.main import app

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / 'api' / 'openapi.json'


def load_schema() -> BaseOpenAPISchema:
    """Load the committed OpenAPI schema and bind it to the FastAPI app."""
    schema = schemathesis.from_path(SCHEMA_PATH, app=app)
    return schema


schema = load_schema()
```

- [ ] **Step 3: Create the test module**

```python
"""Single Schemathesis entry point — expands into hundreds of generated cases."""

from __future__ import annotations

import pytest

from tests.schemathesis.conftest import schema

# Endpoints excluded from fuzzing because they have production-style side effects
# that should not be triggered by property-based synthetic inputs.
#   - POST /api/evaluations: enqueues arq worker jobs
#   - POST /api/evaluations/re-evaluate: enqueues re-evaluation jobs
EXCLUDED_OPERATIONS = {
    ('POST', '/api/evaluations'),
    ('POST', '/api/evaluations/re-evaluate'),
}


@pytest.mark.schemathesis
@schema.parametrize()
def test_api_conforms_to_schema(case) -> None:  # type: ignore[no-untyped-def]
    """Verify every (method, path) pair returns responses conforming to the spec."""
    if (case.method.upper(), case.path) in EXCLUDED_OPERATIONS:
        pytest.skip('excluded from fuzzing (side-effect-heavy endpoint)')

    response = case.call_asgi()
    case.validate_response(response)
```

**Note:** `case.call_asgi()` uses the ASGI transport to dispatch into the FastAPI app directly — no network, no uvicorn, no separate thread. This is faster and more reliable than HTTP-based testing. If Schemathesis 3.x has renamed this to `case.call()` with an ASGI transport argument, check the current docs and adjust.

- [ ] **Step 4: Register the marker**

In `api/pyproject.toml`, extend the `[tool.pytest.ini_options].markers` list:

```toml
markers = [
    "integration: requires database and redis",
    "contract: provider contract verification (requires test DB)",
    "schemathesis: property-based OpenAPI conformance tests",
]
```

- [ ] **Step 5: Commit**

```bash
git add api/tests/schemathesis/ api/pyproject.toml
git commit -m "test(contract): add schemathesis property-based test harness"
```

---

### Task 3: First run (expect failures to fix)

**Files:**
- None yet — this is a discovery step.

- [ ] **Step 1: Run the suite**

```bash
just test-env
uv run --directory api pytest tests/schemathesis -m schemathesis -v --tb=short
```

Expected: Schemathesis generates test cases per endpoint. Some will almost certainly fail the first time. Typical failures:

- **Missing authentication:** some endpoints require auth headers. Schemathesis doesn't know about auth unless configured.
- **Unhandled 500s** on malformed inputs — a Pydantic validation gap, usually.
- **Response schema drift** — a route returns a field that's not documented in the Pydantic response model.

- [ ] **Step 2: Triage failures**

For each failure, decide:

1. **Backend bug** — fix the backend (missing validation, schema drift). This is the whole point of Schemathesis.
2. **Missing auth configuration** — handled in Task 4.
3. **Schemathesis limitation** — extremely rare. Only exclude an endpoint if there's a real reason, and document why in the exclusion.

Do not silence failures by lowering `--checks`. Fix the underlying bug.

- [ ] **Step 3: Note each fix in a commit message with clear attribution**

When you fix a backend bug surfaced by Schemathesis, mention it:

```bash
git commit -m "fix(evaluations): reject null asset_name (found by schemathesis fuzzing)"
```

---

### Task 4: Configure authentication for Schemathesis

**Files:**
- Modify: `api/tests/schemathesis/conftest.py`

Schemathesis must know which endpoints require auth and how to provide it. The exact mechanism depends on how auth is wired in `tropek.main`. Check if there's an API key header, bearer token, or session cookie.

- [ ] **Step 1: Read the existing auth setup**

Grep the codebase for `Depends`, `HTTPBearer`, `APIKeyHeader`, or similar. Find how the real backend authenticates requests.

- [ ] **Step 2: Add a hook that injects auth**

In `api/tests/schemathesis/conftest.py`, add:

```python
import schemathesis


@schemathesis.hook
def before_call(context, case) -> None:  # type: ignore[no-untyped-def]
    """Inject auth headers into every generated request."""
    headers = case.headers or {}
    headers.setdefault('X-API-Key', 'test-api-key-for-schemathesis')
    case.headers = headers
```

Adjust the header name and value to match the real auth mechanism. If the backend uses bearer tokens, use `Authorization: Bearer <token>`. If it uses session cookies, this approach needs a preliminary login step — consult the `pact-python` provider conftest from Phase 2 for how to seed an authenticated session.

If the test environment does not enforce auth (common for dev/test setups where `QG_SECRET_KEY` is a well-known value), this step may be unnecessary. Verify by re-running the suite after Step 3 below — if previously-failing endpoints now pass, auth was the missing piece.

- [ ] **Step 3: Re-run suite**

```bash
uv run --directory api pytest tests/schemathesis -m schemathesis -v --tb=short
```

Expected: any previously-auth-related failures now pass.

- [ ] **Step 4: Commit**

```bash
git add api/tests/schemathesis/conftest.py
git commit -m "test(contract): configure auth headers for schemathesis fuzzing"
```

---

### Task 5: Enable security checks

**Files:**
- Modify: `api/tests/schemathesis/test_schema.py`

- [ ] **Step 1: Enable the full check set**

Add to the top of `test_schema.py`:

```python
schema.checks.register_default_checks()
# Security-oriented checks — attempt SQLi, XSS, path traversal payloads
# against string-typed parameters and assert no unexpected 500s.
```

Then in the decorator:

```python
@pytest.mark.schemathesis
@schema.parametrize()
def test_api_conforms_to_schema(case) -> None:  # type: ignore[no-untyped-def]
    if (case.method.upper(), case.path) in EXCLUDED_OPERATIONS:
        pytest.skip('excluded from fuzzing (side-effect-heavy endpoint)')

    response = case.call_asgi()
    case.validate_response(
        response,
        checks=(
            *schema.checks.DEFAULT_CHECKS,
            # Add explicit security checks here — exact API depends on
            # the schemathesis version installed. Consult the docs for the
            # version in use: https://schemathesis.readthedocs.io/
        ),
    )
```

**Note:** The Schemathesis check registration API has changed between 3.x minor versions. If `DEFAULT_CHECKS` doesn't exist or the security checks are enabled differently in your installed version, consult `uv run --directory api schemathesis --help` and the version-specific docs. The intent is: **default conformance checks + explicit security checks**. Do not leave security checks off.

- [ ] **Step 2: Re-run and verify zero security findings**

```bash
uv run --directory api pytest tests/schemathesis -m schemathesis -v --tb=short
```

Expected: no SQL-injection or path-traversal findings. FastAPI + SQLAlchemy's parameterized queries should make this clean.

If any security check fails, STOP and fix the underlying code — that's a real vulnerability, not a test issue.

- [ ] **Step 3: Commit**

```bash
git add api/tests/schemathesis/test_schema.py
git commit -m "test(contract): enable security checks in schemathesis"
```

---

### Task 6: Add stateful testing

**Files:**
- Create: `api/tests/schemathesis/test_stateful.py`

Stateful testing chains requests into realistic sequences — POST a resource, GET it, DELETE it — and catches bugs that only appear in sequence.

- [ ] **Step 1: Write the stateful test**

```python
"""Stateful Schemathesis tests — chain requests to catch state-dependent bugs."""

from __future__ import annotations

import pytest

from tests.schemathesis.conftest import schema


@pytest.mark.schemathesis
class TestAPIStateMachine(schema.as_state_machine()):  # type: ignore[misc]
    """Exercise realistic request sequences generated by the state machine."""
```

That's the entire test — Schemathesis generates the state machine from the OpenAPI links in the spec. If your OpenAPI schema doesn't declare any operation links, this test will still run but won't exercise chains. The FastAPI-generated schema may not include operation links by default; Phase 3 accepts this as a known limitation and leaves adding explicit links as a future enhancement.

- [ ] **Step 2: Run stateful tests**

```bash
uv run --directory api pytest tests/schemathesis/test_stateful.py -m schemathesis -v
```

Expected: passes (even if minimal — the property-based engine finds whatever sequences it can).

- [ ] **Step 3: Commit**

```bash
git add api/tests/schemathesis/test_stateful.py
git commit -m "test(contract): add stateful schemathesis test for request chains"
```

---

### Task 7: Add wrapper script and just recipe

**Files:**
- Create: `scripts/schemathesis-run.sh`
- Modify: `justfile`

- [ ] **Step 1: Write the wrapper script**

```bash
#!/usr/bin/env bash
# Run Schemathesis fuzzing against the API. Single auto-approvable command.
#
# Usage:
#   ./scripts/schemathesis-run.sh
#   ./scripts/schemathesis-run.sh --tail 20   # show last 20 lines only

set -euo pipefail

TAIL_LINES=0
ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tail)
      TAIL_LINES="$2"
      shift 2
      ;;
    *)
      ARGS+=("$1")
      shift
      ;;
  esac
done

CMD=(uv run --directory api pytest tests/schemathesis -m schemathesis "${ARGS[@]}")

if [[ "$TAIL_LINES" -gt 0 ]]; then
  "${CMD[@]}" 2>&1 | tail -n "$TAIL_LINES"
else
  exec "${CMD[@]}"
fi
```

- [ ] **Step 2: Make executable**

Run: `chmod +x scripts/schemathesis-run.sh`

- [ ] **Step 3: Add just recipe**

Add to `justfile`, after `test-contracts-api`:

```makefile
# Run Schemathesis property-based + security fuzzing (requires test-env)
test-schema *args='-v':
    ./scripts/schemathesis-run.sh {{args}}
```

- [ ] **Step 4: Verify recipe works**

```bash
just test-env
just test-schema
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/schemathesis-run.sh justfile
git commit -m "chore(contract): add just test-schema recipe and wrapper script"
```

---

### Task 8: Wire Schemathesis into CI

**Files:**
- Modify or create: `.github/workflows/contract-verify.yml`

- [ ] **Step 1: Add a Schemathesis job**

Append to the existing `contract-verify.yml` workflow a new job that runs after `provider`:

```yaml
  schemathesis:
    runs-on: ubuntu-latest
    needs: provider
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
      - name: Apply migrations
        env:
          QG_DB_PASSWORD: test
          TEST_DATABASE_URL: postgresql+asyncpg://postgres:test@localhost:5433/tropek_test
        run: just migrate-test
      - name: Run Schemathesis
        env:
          QG_DB_PASSWORD: test
          TEST_DATABASE_URL: postgresql+asyncpg://postgres:test@localhost:5433/tropek_test
        run: just test-schema
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/contract-verify.yml
git commit -m "ci(contract): run schemathesis after provider verification"
```

---

### Task 9: Test audit (Phase 3.5)

**Files:**
- Create: `scripts/test-coverage-audit.py`
- Modify: `justfile`
- Create: `reports/test-audit.md`

**Recommended subagent model for this task:** **Opus**. This task involves reading every integration test, reasoning about what each verifies, and making judgment calls about redundancy. The kind of nuanced reading+reasoning where Opus earns its cost.

- [ ] **Step 1: Write the audit script**

```python
#!/usr/bin/env python3
"""One-time audit: map integration tests to Pact/Schemathesis coverage.

Reads:
  - ui/pacts/tropek-ui-tropek-api.json (Pact interactions)
  - api/openapi.json (list of all endpoints)
  - api/tests/**/test_*.py (existing integration tests)

Produces:
  - reports/test-audit.md — Markdown table: each integration test → coverage class
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACT_FILE = REPO_ROOT / 'ui' / 'pacts' / 'tropek-ui-tropek-api.json'
OPENAPI_FILE = REPO_ROOT / 'api' / 'openapi.json'
API_TESTS_DIR = REPO_ROOT / 'api' / 'tests'
REPORT_OUT = REPO_ROOT / 'reports' / 'test-audit.md'


@dataclass
class TestFunction:
    file: Path
    name: str
    docstring: str
    markers: list[str]
    body_text: str


def extract_pact_endpoints(pact_path: Path) -> set[tuple[str, str]]:
    """Return {(METHOD, path)} covered by Pact interactions."""
    if not pact_path.exists():
        return set()
    data = json.loads(pact_path.read_text())
    endpoints: set[tuple[str, str]] = set()
    for interaction in data.get('interactions', []):
        req = interaction.get('request', {})
        method = req.get('method', '').upper()
        path = req.get('path', '')
        if method and path:
            endpoints.add((method, path))
    return endpoints


def extract_all_endpoints(openapi_path: Path) -> set[tuple[str, str]]:
    """Return {(METHOD, path)} from the OpenAPI spec — Schemathesis coverage."""
    data = json.loads(openapi_path.read_text())
    endpoints: set[tuple[str, str]] = set()
    for path, methods in data.get('paths', {}).items():
        for method in methods:
            if method.lower() in {'get', 'post', 'put', 'patch', 'delete'}:
                endpoints.add((method.upper(), path))
    return endpoints


def find_test_functions(tests_dir: Path) -> list[TestFunction]:
    """Walk tests/ and collect every test function with docstring and markers."""
    functions: list[TestFunction] = []
    for test_file in tests_dir.rglob('test_*.py'):
        if 'schemathesis' in test_file.parts or 'contracts' in test_file.parts:
            continue  # don't audit the contract tests themselves
        try:
            tree = ast.parse(test_file.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith('test_'):
                    continue
                markers = [
                    decorator.attr
                    for decorator in node.decorator_list
                    if isinstance(decorator, ast.Attribute)
                    and isinstance(decorator.value, ast.Attribute)
                    and getattr(decorator.value, 'attr', None) == 'mark'
                ]
                functions.append(
                    TestFunction(
                        file=test_file.relative_to(REPO_ROOT),
                        name=node.name,
                        docstring=ast.get_docstring(node) or '',
                        markers=markers,
                        body_text=ast.unparse(node),
                    )
                )
    return functions


def classify(tf: TestFunction, pact_endpoints: set[tuple[str, str]]) -> str:
    """Heuristic classification. Final decision is human, this is a starting point."""
    body_lower = tf.body_text.lower()
    for method, path in pact_endpoints:
        # crude but useful first pass — look for the path literal in the test body
        path_fragment = path.split('{')[0].rstrip('/')
        if path_fragment and path_fragment in body_lower and method.lower() in body_lower:
            return 'covered-by-pact'
    if 'status_code' in body_lower and 'assert' in body_lower and 'response' in body_lower:
        return 'api-shape-check (candidate for schemathesis coverage)'
    if 'session.add' in body_lower or 'select(' in body_lower:
        return 'business-logic / db-state (keep)'
    return 'unclassified (human review)'


def main() -> None:
    pact_endpoints = extract_pact_endpoints(PACT_FILE)
    api_endpoints = extract_all_endpoints(OPENAPI_FILE)
    functions = find_test_functions(API_TESTS_DIR)

    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        '# Test Coverage Audit',
        '',
        f'- Pact interactions: {len(pact_endpoints)}',
        f'- OpenAPI endpoints: {len(api_endpoints)} (all covered by schemathesis unless excluded)',
        f'- Integration test functions inspected: {len(functions)}',
        '',
        '| File | Test | Classification | Docstring (first line) |',
        '| --- | --- | --- | --- |',
    ]
    for tf in sorted(functions, key=lambda x: (str(x.file), x.name)):
        doc_first_line = tf.docstring.split('\n', 1)[0] if tf.docstring else ''
        classification = classify(tf, pact_endpoints)
        lines.append(
            f'| `{tf.file}` | `{tf.name}` | {classification} | {doc_first_line} |'
        )
    lines.append('')
    lines.append('## Legend')
    lines.append('')
    lines.append('- **covered-by-pact**: Pact verifies the same endpoint shape. Candidate for removal if the integration test adds no business-logic value beyond shape.')
    lines.append('- **api-shape-check (candidate for schemathesis coverage)**: Asserts status codes or response shapes. Likely already covered by Schemathesis — candidate for removal.')
    lines.append('- **business-logic / db-state (keep)**: Exercises DB state, multi-step sequences, or computed values. Keep.')
    lines.append('- **unclassified (human review)**: Could not be auto-classified. Requires reading the test to decide.')
    lines.append('')
    lines.append('## Next step')
    lines.append('')
    lines.append('A human reviews every row, deletes the rows marked for removal, and expands the "keep" rows where business-logic assertions are thin.')

    REPORT_OUT.write_text('\n'.join(lines) + '\n')
    print(f'wrote {REPORT_OUT.relative_to(REPO_ROOT)}')


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Make executable**

Run: `chmod +x scripts/test-coverage-audit.py`

- [ ] **Step 3: Add just recipe**

```makefile
# Generate test coverage audit report
test-audit:
    uv run python scripts/test-coverage-audit.py
```

- [ ] **Step 4: Run the audit**

Run: `just test-audit`
Expected: `reports/test-audit.md` is created with a Markdown table classifying every integration test.

- [ ] **Step 5: Human review**

Read `reports/test-audit.md`. For each row:

1. **covered-by-pact** + test does nothing beyond shape assertions → delete the test
2. **api-shape-check** + test is pure shape → delete
3. **business-logic / db-state** → keep, and check if assertions are shallow — if they are, expand them
4. **unclassified** → read the test and decide manually

**Do not automate deletion.** The script is a proposal, not a commit. Every deletion is a human call.

- [ ] **Step 6: Action the review**

Delete redundant tests in small commits, one area at a time:

```bash
git rm api/tests/some/redundant_test.py
git commit -m "test(audit): remove redundant test — covered by pact contract for GET /api/evaluations/:id"
```

- [ ] **Step 7: Commit the audit report**

After the review is done, update `reports/test-audit.md` with a summary of decisions and commit:

```bash
git add scripts/test-coverage-audit.py justfile reports/test-audit.md
git commit -m "test(audit): add coverage audit script and initial report"
```

- [ ] **Step 8: Run the full test suite to make sure nothing broke**

```bash
./scripts/api-test.sh --tail 5
./scripts/api-test.sh --tail 5 -m integration
just test-contracts
just test-schema
```

All should pass. If any test you kept now fails, that's a real regression — fix it.

---

## Self-review gate

After all tasks complete:

```bash
just export-schema       # Phase 1 still fresh
just codegen
just test-contracts      # Phase 2
just test-schema         # Phase 3
just test-audit          # Phase 3.5 report regeneration
./scripts/api-test.sh --tail 5
./scripts/api-test.sh --tail 5 -m integration
./scripts/ui-test.sh --tail 10
```

Everything should pass. The repo should now have:

1. `schemathesis` running on every push via CI
2. Security checks enabled and green
3. Stateful tests exercising request chains
4. `reports/test-audit.md` committed showing the audit decisions
5. A leaner integration test suite focused on business logic, not API shape
6. Any real backend bugs surfaced during fuzzing have been fixed with commits attributing the finding to Schemathesis

Phase 3 is complete when Schemathesis is green in CI and the test audit has been actioned.
