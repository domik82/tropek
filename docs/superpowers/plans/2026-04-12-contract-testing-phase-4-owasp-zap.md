# Contract Testing — Phase 4: OWASP ZAP Deep Security Scan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Actively probe the API for exploitable vulnerabilities beyond what Schemathesis catches — SQL injection with deep payload dictionaries, XSS, path traversal, broken authentication, insecure direct object references, and the rest of the OWASP API Top 10. Does NOT run on every push; runs weekly on a schedule and on demand before releases.

**Architecture:** OWASP ZAP runs in a Docker container, reads `api/openapi.json` to learn every endpoint, and performs an active scan against a running test instance of the FastAPI app. A wrapper script boots the test stack, invokes ZAP with the right context (auth headers, suppressions), writes a report to `reports/security/`, and exits non-zero if any HIGH findings are present. A scheduled GitHub Actions workflow runs this weekly and opens a GitHub issue when HIGH findings appear.

**Tech Stack:** OWASP ZAP (Docker image `zaproxy/zap-stable`), Docker Compose, Python script for report parsing, existing test DB + Redis, GitHub Actions.

**Recommended subagent model:** **Sonnet**. ZAP integration is ops-heavy — Docker networking between the scanner and the test app, context file authoring, false-positive suppression tuning. Not a reasoning-heavy task but not mechanical either (auth contexts have a lot of moving pieces and ZAP error messages can be oblique). Sonnet is the right choice. Haiku would struggle with the ZAP context XML and the report parsing nuances.

**Prerequisite:** Phase 1 complete (`api/openapi.json` exists). Phases 2 and 3 are not strictly required but strongly recommended — if the API already has a Schemathesis-clean baseline, ZAP findings will be signal rather than noise.

**Spec reference:** `docs/superpowers/specs/2026-04-12-contract-testing-design.md` (Phase 4 section).

---

### Task 1: Create the scan script

**Files:**
- Create: `scripts/security-scan.sh`

- [ ] **Step 1: Write the wrapper script**

```bash
#!/usr/bin/env bash
# OWASP ZAP active scan against the TROPEK API test instance.
#
# Preconditions:
#   - `just test-env` has started the test database
#   - api/openapi.json is fresh (run `just export-schema` first)
#
# Behaviour:
#   - Starts a dedicated test-only FastAPI instance on port 8099
#   - Runs ZAP in a Docker container pointed at that instance
#   - Writes reports/security/report-YYYY-MM-DD.html and .json
#   - Exits non-zero if HIGH findings are present
#
# Usage:
#   ./scripts/security-scan.sh
#   ./scripts/security-scan.sh --fail-on medium   # stricter (default: high)

set -euo pipefail

FAIL_ON="high"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --fail-on) FAIL_ON="$2"; shift 2 ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${REPO_ROOT}/reports/security"
REPORT_DATE="$(date +%Y-%m-%d)"
REPORT_HTML="${REPORT_DIR}/report-${REPORT_DATE}.html"
REPORT_JSON="${REPORT_DIR}/report-${REPORT_DATE}.json"
ZAP_CONTEXT="${REPO_ROOT}/scripts/zap-context.xml"
ZAP_SUPPRESSIONS="${REPO_ROOT}/scripts/zap-suppressions.yaml"

mkdir -p "${REPORT_DIR}"

# Target URL — host.docker.internal resolves to the host from inside the ZAP container.
# On Linux, add --add-host host.docker.internal:host-gateway.
TARGET_HOST="host.docker.internal"
TARGET_PORT=8099
TARGET_URL="http://${TARGET_HOST}:${TARGET_PORT}"

echo "→ starting FastAPI test instance on :${TARGET_PORT}"
uv run --directory api python -m uvicorn tropek.main:app \
    --host 0.0.0.0 --port "${TARGET_PORT}" --log-level warning &
API_PID=$!
trap 'kill ${API_PID} 2>/dev/null || true' EXIT

# Wait for health
for _ in $(seq 1 30); do
    if curl -sf "http://localhost:${TARGET_PORT}/health" >/dev/null; then
        echo "→ API is ready"
        break
    fi
    sleep 0.5
done

echo "→ running OWASP ZAP active scan"
docker run --rm \
    --add-host host.docker.internal:host-gateway \
    -v "${REPO_ROOT}:/zap/wrk:rw" \
    zaproxy/zap-stable \
    zap-api-scan.py \
        -t "${TARGET_URL}/openapi.json" \
        -f openapi \
        -r "wrk/reports/security/report-${REPORT_DATE}.html" \
        -J "wrk/reports/security/report-${REPORT_DATE}.json" \
        -n "wrk/scripts/zap-context.xml" \
        -I  # do not fail on warnings, we parse the report ourselves

echo "→ parsing findings"
uv run python "${REPO_ROOT}/scripts/parse-zap-report.py" \
    "${REPORT_JSON}" \
    --suppressions "${ZAP_SUPPRESSIONS}" \
    --fail-on "${FAIL_ON}"

echo "→ scan complete. Report: ${REPORT_HTML}"
```

- [ ] **Step 2: Make executable**

Run: `chmod +x scripts/security-scan.sh`

- [ ] **Step 3: Commit**

```bash
git add scripts/security-scan.sh
git commit -m "chore(security): add OWASP ZAP scan wrapper script"
```

---

### Task 2: Create the ZAP context file

**Files:**
- Create: `scripts/zap-context.xml`

ZAP uses an XML "context" file to learn about authentication, URL scoping, and session handling. This file tells ZAP: "here's how to authenticate, here's the base URL, here's what to include/exclude from scanning."

- [ ] **Step 1: Write a minimal context**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!-- OWASP ZAP context for TROPEK API scanning.
     Scope: http://host.docker.internal:8099/api/*
     Auth: X-API-Key header injected via replacer rules -->
<configuration>
    <context>
        <name>tropek-api</name>
        <desc>TROPEK API active scan context</desc>
        <inscope>true</inscope>
        <incregexes>
            <regex>http://host\.docker\.internal:8099/api/.*</regex>
            <regex>http://host\.docker\.internal:8099/health</regex>
            <regex>http://host\.docker\.internal:8099/openapi\.json</regex>
        </incregexes>
        <excregexes>
            <!-- Exclude endpoints that spawn worker jobs — ZAP should not trigger
                 them with synthetic payloads. These are covered by Pact + Schemathesis. -->
            <regex>http://host\.docker\.internal:8099/api/evaluations$</regex>
            <regex>http://host\.docker\.internal:8099/api/evaluations/re-evaluate</regex>
        </excregexes>
        <tech>
            <include>Db.PostgreSQL</include>
            <include>Language.Python</include>
            <include>OS.Linux</include>
        </tech>
        <authentication>
            <type>0</type>
            <strategy>EACH_RESP</strategy>
        </authentication>
    </context>
    <replacer>
        <rules>
            <rule>
                <description>Inject API key header on every request</description>
                <isEnabled>true</isEnabled>
                <matchType>REQ_HEADER</matchType>
                <matchString>X-API-Key</matchString>
                <replacement>test-api-key-for-security-scan</replacement>
            </rule>
        </rules>
    </replacer>
</configuration>
```

**IMPORTANT:** Adjust the replacer rule to match the real auth mechanism of the TROPEK API. If it uses `Authorization: Bearer <token>`, change `matchString` to `Authorization` and `replacement` to `Bearer <test-token>`. If it uses cookies, the replacer approach won't work — you'll need ZAP's full scripted authentication, which is more involved. Check `api/tropek/main.py` and any auth dependencies before settling on the format.

- [ ] **Step 2: Commit**

```bash
git add scripts/zap-context.xml
git commit -m "chore(security): add ZAP context file for TROPEK API scanning"
```

---

### Task 3: Create the suppressions file

**Files:**
- Create: `scripts/zap-suppressions.yaml`

The suppressions file lets reviewers silence known-false-positive findings without losing track of them.

- [ ] **Step 1: Write the initial file**

```yaml
# OWASP ZAP finding suppressions.
#
# Every entry must have a comment explaining WHY it is suppressed.
# Do not add entries without justification — unreviewed suppressions become
# silent security blind spots over time.
#
# Format:
#   - rule_id: <ZAP plugin id, e.g. 10020>
#     url_pattern: <regex matching the URL where this finding should be suppressed>
#     justification: |
#       Multi-line explanation of why this is a false positive or accepted risk.
#       Include date and reviewer.

suppressions: []
```

- [ ] **Step 2: Commit**

```bash
git add scripts/zap-suppressions.yaml
git commit -m "chore(security): add empty ZAP suppressions file with format docs"
```

---

### Task 4: Write the report parser

**Files:**
- Create: `scripts/parse-zap-report.py`

- [ ] **Step 1: Write the parser**

```python
#!/usr/bin/env python3
"""Parse the ZAP JSON report and exit non-zero if findings exceed the threshold.

Usage:
    parse-zap-report.py REPORT.json --suppressions FILE --fail-on high
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

SEVERITY_ORDER = {'informational': 0, 'low': 1, 'medium': 2, 'high': 3}


def load_suppressions(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text()) or {}
    return data.get('suppressions', []) or []


def is_suppressed(
    rule_id: str,
    url: str,
    suppressions: list[dict[str, str]],
) -> bool:
    for entry in suppressions:
        if str(entry.get('rule_id', '')) != rule_id:
            continue
        pattern = entry.get('url_pattern', '')
        if pattern and re.search(pattern, url):
            return True
    return False


def normalise_severity(raw: str) -> str:
    """ZAP uses 'High', 'Medium', 'Low', 'Informational'."""
    return raw.strip().lower()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('report', type=Path, help='ZAP JSON report path')
    parser.add_argument('--suppressions', type=Path, required=True)
    parser.add_argument(
        '--fail-on',
        choices=['low', 'medium', 'high'],
        default='high',
        help='Minimum severity that causes a non-zero exit.',
    )
    args = parser.parse_args()

    if not args.report.exists():
        print(f'ERROR: report not found: {args.report}', file=sys.stderr)
        return 2

    report = json.loads(args.report.read_text())
    suppressions = load_suppressions(args.suppressions)
    threshold = SEVERITY_ORDER[args.fail_on]

    findings: list[dict[str, str]] = []
    sites = report.get('site', [])
    if isinstance(sites, dict):
        sites = [sites]
    for site in sites:
        for alert in site.get('alerts', []):
            rule_id = str(alert.get('pluginid', ''))
            severity = normalise_severity(alert.get('riskdesc', '').split(' ')[0])
            name = alert.get('name', 'unknown')
            instances = alert.get('instances', [])
            for instance in instances:
                url = instance.get('uri', '')
                if is_suppressed(rule_id, url, suppressions):
                    continue
                findings.append({
                    'rule_id': rule_id,
                    'severity': severity,
                    'name': name,
                    'url': url,
                })

    by_severity: dict[str, int] = {'high': 0, 'medium': 0, 'low': 0, 'informational': 0}
    for finding in findings:
        by_severity[finding['severity']] = by_severity.get(finding['severity'], 0) + 1

    print('ZAP findings summary (after suppressions):')
    for severity in ('high', 'medium', 'low', 'informational'):
        print(f'  {severity:>14}: {by_severity.get(severity, 0)}')

    breaching = [
        f for f in findings
        if SEVERITY_ORDER.get(f['severity'], 0) >= threshold
    ]
    if breaching:
        print('', file=sys.stderr)
        print(f'FAIL: {len(breaching)} finding(s) at or above severity "{args.fail_on}":', file=sys.stderr)
        for finding in breaching[:20]:
            print(
                f'  [{finding["severity"]:>6}] rule={finding["rule_id"]} '
                f'{finding["name"]} — {finding["url"]}',
                file=sys.stderr,
            )
        if len(breaching) > 20:
            print(f'  ... and {len(breaching) - 20} more', file=sys.stderr)
        return 1

    print('OK: no findings at or above severity threshold')
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 2: Make executable**

Run: `chmod +x scripts/parse-zap-report.py`

- [ ] **Step 3: Ensure PyYAML is available**

The script uses `yaml`. Check if PyYAML is already a dependency (it is — grep `api/pyproject.toml` for `pyyaml`). Since the script lives in `scripts/`, running it with `uv run python` uses the root-workspace environment. If needed, add `pyyaml` to the root `pyproject.toml` dev deps.

- [ ] **Step 4: Commit**

```bash
git add scripts/parse-zap-report.py
git commit -m "chore(security): add ZAP report parser with suppression support"
```

---

### Task 5: Add the just recipe and gitignore

**Files:**
- Modify: `justfile`
- Modify: `.gitignore`

- [ ] **Step 1: Add recipe**

Add to `justfile`, after `test-audit`:

```makefile
# Run OWASP ZAP active security scan (requires Docker)
security-scan *args='':
    ./scripts/security-scan.sh {{args}}
```

- [ ] **Step 2: Gitignore reports**

Append to `.gitignore`:

```
# ZAP security scan reports (uploaded as CI artifacts instead)
reports/security/
```

- [ ] **Step 3: Commit**

```bash
git add justfile .gitignore
git commit -m "chore(security): add just security-scan recipe and gitignore reports"
```

---

### Task 6: Test the scan locally

**Files:**
- None (verification step)

- [ ] **Step 1: Boot dependencies**

```bash
just test-env
just export-schema    # ensures api/openapi.json is fresh
```

- [ ] **Step 2: Run the scan**

Run: `just security-scan`

Expected timeline: 5–20 minutes. The scan downloads the ZAP image (first run only), starts the API on port 8099, performs the active scan, writes the report, and parses it.

Expected result: script exits cleanly with "no findings at or above severity threshold" OR with a list of findings to triage.

- [ ] **Step 3: Triage findings**

For each HIGH/MEDIUM finding:

1. **Real vulnerability** — fix the backend code. Do not suppress real findings.
2. **False positive** (ZAP misidentifies safe behavior as a vuln) — add a suppression entry to `scripts/zap-suppressions.yaml` with a justification and your name + date.
3. **Accepted risk** (e.g. an intentional design choice) — add a suppression with a longer justification explaining why the risk is accepted.

Commit each fix separately. Fixes should reference the finding:

```bash
git commit -m "fix(api): sanitize tag key parameter (ZAP finding 40018 SQLi probe)"
```

Suppressions go in a separate commit:

```bash
git add scripts/zap-suppressions.yaml
git commit -m "chore(security): suppress ZAP 10020 false positive on /api/health"
```

- [ ] **Step 4: Re-run until green**

Keep running `just security-scan` until it exits cleanly. Each iteration should have fewer findings.

---

### Task 7: Create the scheduled GitHub Actions workflow

**Files:**
- Create: `.github/workflows/security.yml`

- [ ] **Step 1: Write the workflow**

```yaml
name: Security Scan

on:
  schedule:
    # Every Monday at 03:00 UTC
    - cron: '0 3 * * 1'
  workflow_dispatch:

jobs:
  zap:
    runs-on: ubuntu-latest
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
      redis:
        image: redis:7
        ports:
          - 6379:6379
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

      - name: Regenerate schema
        run: just export-schema

      - name: Run security scan
        env:
          QG_DB_PASSWORD: test
          TEST_DATABASE_URL: postgresql+asyncpg://postgres:test@localhost:5433/tropek_test
          QG_REDIS_URL: redis://localhost:6379
        run: |
          set +e
          ./scripts/security-scan.sh
          echo "EXIT_CODE=$?" >> $GITHUB_ENV

      - name: Upload report artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: zap-report-${{ github.run_id }}
          path: reports/security/
          retention-days: 90

      - name: Create issue on HIGH findings
        if: env.EXIT_CODE != '0'
        uses: actions/github-script@v7
        with:
          script: |
            const date = new Date().toISOString().slice(0, 10)
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: `Security scan HIGH findings — ${date}`,
              body: [
                '## OWASP ZAP active scan reported HIGH findings',
                '',
                `Run: ${context.serverUrl}/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}`,
                '',
                'Download the `zap-report-*` artifact from that run for the full report.',
                '',
                '### Triage checklist',
                '- [ ] Review every HIGH finding',
                '- [ ] Fix real vulnerabilities in a dedicated PR',
                '- [ ] Add suppression entries for false positives with justification',
                '- [ ] Re-run `just security-scan` locally to confirm green',
              ].join('\n'),
              labels: ['security', 'automated']
            })

      - name: Fail job if HIGH findings present
        if: env.EXIT_CODE != '0'
        run: exit 1
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/security.yml
git commit -m "ci(security): add weekly OWASP ZAP scan with issue creation"
```

---

### Task 8: Document the security scan workflow

**Files:**
- Create: `docs/security-scanning.md`

- [ ] **Step 1: Write the doc**

```markdown
# Security Scanning

TROPEK uses OWASP ZAP to actively probe the API for vulnerabilities.
This document explains when scans run, how to read reports, and how to
respond to findings.

## When scans run

- **Weekly** — every Monday at 03:00 UTC via GitHub Actions
- **On demand** — `just security-scan` locally, or the "Security Scan"
  workflow manual dispatch in GitHub Actions
- **Before a release** — recommended as a pre-release check

Scans do **not** run on every push. Active scanning is slow (~10 minutes)
and its value is concentrated in periodic reviews, not per-commit feedback.

## Responding to HIGH findings

When the weekly scan reports HIGH findings, a GitHub issue is automatically
created with a link to the run and the report artifact. Triage the issue
within 48 hours.

### For each HIGH finding

1. **Download the report** from the GitHub Actions run artifact
2. **Read the finding details** — URL, payload, response excerpt
3. **Reproduce it locally** — `curl` the same URL with the same payload
4. **Classify it**
   - **Real vulnerability:** fix the backend, reference the ZAP rule ID in
     the commit message, re-run the scan to confirm green
   - **False positive:** add an entry to `scripts/zap-suppressions.yaml` with
     justification, rule ID, and URL pattern
   - **Accepted risk:** same as false positive but the justification explains
     why the risk is intentional

## Suppression format

`scripts/zap-suppressions.yaml`:

\`\`\`yaml
suppressions:
  - rule_id: "10020"
    url_pattern: "/api/health$"
    justification: |
      ZAP flags missing X-Frame-Options on /health. The health endpoint
      returns JSON and is not intended for browser rendering, so
      clickjacking mitigation does not apply.
      — reviewed 2026-04-15 by @domik
\`\`\`

Every entry MUST have a justification. Unreviewed suppressions become
silent security blind spots over time.

## Manual deep scan

To run a deeper scan with stricter thresholds:

\`\`\`bash
just security-scan --fail-on medium
\`\`\`

This fails on MEDIUM findings too, useful before a release.

## Excluded endpoints

`scripts/zap-context.xml` excludes these endpoints from active scanning:

- `POST /api/evaluations` — spawns arq worker jobs
- `POST /api/evaluations/re-evaluate` — spawns re-evaluation jobs

These are covered by Pact contract tests and Schemathesis fuzzing instead.
```

- [ ] **Step 2: Commit**

```bash
git add docs/security-scanning.md
git commit -m "docs(security): document OWASP ZAP scan workflow"
```

---

## Self-review gate

After all tasks complete:

```bash
just test-env
just export-schema
just security-scan
```

Expected: scan completes, report lands in `reports/security/`, parser exits cleanly (assuming no real findings).

Manual checks:

- [ ] `.github/workflows/security.yml` exists and is syntactically valid
- [ ] `scripts/zap-context.xml` has the right auth mechanism
- [ ] `scripts/zap-suppressions.yaml` has no unjustified entries
- [ ] `docs/security-scanning.md` documents the full workflow
- [ ] The weekly cron has been verified in the Actions tab (manually dispatch once to confirm it works)

## Expected outcomes

1. Weekly automated OWASP ZAP scan runs in CI
2. HIGH findings auto-open a GitHub issue within minutes of scan completion
3. Report artifacts are retained for 90 days
4. Local `just security-scan` reproduces the CI scan exactly
5. Suppression system keeps known false positives silenced without losing audit trail

Phase 4 is complete when a full scheduled run has executed at least once in CI and either reported zero HIGH findings or all findings have been triaged.

## Out of scope (future work)

- **DAST beyond ZAP** — tools like Burp Suite Enterprise, Checkmarx, Snyk Code. Paid products; not considered for an open-source single-dev setup.
- **Dependency scanning** — `pip-audit`, `npm audit`, Dependabot. These are orthogonal to API contract testing and should be added separately.
- **Secret scanning** — GitHub's built-in push protection covers this.
- **SAST** — Bandit for Python, ESLint security rules for TypeScript. Separate track.
