# TROPEK

**Trend Reporting and Objective Evaluation toolkit**

A standalone quality gate and performance test evaluation platform. Evaluates SLI/SLO metrics from Prometheus, CSV files, JMeter results, or any source that can POST JSON -- and decides pass / warning / fail.

Inspired by [Keptn v1](https://keptn.sh)'s lighthouse-service, [Apache OTAVA](https://github.com/apache/otava) for change point detection, and the Nurkio project. Runs in Docker Compose. No Kubernetes required.

---

## What it does

- Evaluates metrics against **SLO criteria** (fixed thresholds and relative % change)
- Supports **key SLI veto** -- one critical metric failure fails the whole evaluation regardless of score
- Tracks **trend history** with TimescaleDB for relative comparisons (`<=+10%`)
- Three **ingestion modes**: pull from Prometheus, push metrics inline, or upload a file (CSV / JMeter)
- **Versioned SLO & SLI registries** -- every change is stored; evaluations record which version they used
- **SLO groups & templates** -- organise SLOs into reusable groups, assign them to assets
- **Display groups** -- control how SLI objectives are grouped and ordered in the UI
- **Asset & group registry** -- register VMs/services, organise into groups, bind SLOs to assets
- **Heatmap navigator** -- visual overview of evaluation results across assets and time
- **Evaluation batches** -- trigger evaluations for multiple assets in a single request
- **Annotations with categories** -- attach categorised contextual notes to evaluations
- **Invalidation & restore** -- mark evaluations as invalid and restore them without deleting data
- **Baseline pinning** -- pin a specific evaluation as the comparison baseline
- **Status overrides** -- manually override an evaluation's pass/warning/fail status
- **Re-evaluation** -- re-run an evaluation against updated SLO criteria
- **Multi-phase worker pipeline** -- arq workers with configurable concurrency (max_jobs=10)
- **Contract testing** -- OpenAPI codegen + Schemathesis property-based API conformance tests
- **Data source registry** -- register adapter instances (Prometheus, mock adapter for testing)

---

## Architecture

```
Docker Compose
├── api                  :8080   FastAPI — evaluation engine, registries, REST API
├── worker               arq job workers (max_jobs=10, same image, different entrypoint)
├── adapter-prometheus   :8081   Prometheus query adapter
├── adapter-mock         :8082   Mock adapter with data generator (for testing)
├── timescaledb          :5432   PostgreSQL + TimescaleDB (evaluations + time-series SLI values)
├── redis                :6379   Job queue (arq db 1) + response cache (db 0)
├── ui                   :3000   React SPA (nginx; dev server on :5173)
└── timescaledb-test     :5433   Test database (profile: test — not started by default)
```

The evaluation engine is a **pure Python function** -- zero I/O, fully unit-tested, ported from Keptn's Go implementation.

For detailed architecture documentation see:
- [docs/architecture/system-overview.md](docs/architecture/system-overview.md) -- Service topology and communication
- [docs/architecture/evaluation-lifecycle.md](docs/architecture/evaluation-lifecycle.md) -- Evaluation lifecycle and scoring
- [docs/architecture/data-model.md](docs/architecture/data-model.md) -- Database schema and design decisions
- [docs/architecture/configuration.md](docs/architecture/configuration.md) -- Configuration system
- [api/docs/](api/docs/) -- API layer, evaluation engine, database layer
- [ui/docs/](ui/docs/) -- Frontend architecture, features, mock system
- [adapters/prometheus/docs/](adapters/prometheus/docs/) -- Adapter architecture and contract

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/domik82/tropek.git
cd tropek

# 2. Configure
cp .env.example .env
# Edit .env — set passwords

# 3. Install dependencies
just install          # uv sync + pnpm install

# 4. Start all services (builds, migrates, starts)
just up               # docker compose up --build

# 5. Check health
curl http://localhost:8080/health
```

---

## Development setup

Requires: [uv](https://docs.astral.sh/uv/), Python 3.13, Docker, Node.js 18+, [pnpm](https://pnpm.io/), [just](https://github.com/casey/just)

### Backend (API + worker)

```bash
just install          # Install all workspace dependencies (uv sync + pnpm)
just test             # Unit tests (no infrastructure needed)
just lint             # Ruff linter
just typecheck        # MyPy strict mode
just check            # lint + format check + typecheck
```

### Integration tests

Integration tests use a **dedicated test database** on port 5433 -- completely separate from the dev database (port 5432). `.env.test` is committed with local defaults -- no setup needed.

```bash
just test-env         # Start test infrastructure (idempotent)
just test-int         # Run integration tests
just test-env-down    # Tear down when done
```

### Database migrations

```bash
just migrate          # Dev database
just migrate-test     # Test database (container must be running)
```

### UI

```bash
cd ui
pnpm install
```

#### With mocks (no backend needed)

```bash
pnpm dev
```

Starts on `http://localhost:5173` with MSW intercepting all API calls. Mock data is deterministic (seeded PRNG) -- 30 days of history, 40 asset/lab scenarios, 30 metrics. No backend services required.

#### Against the real API

```bash
# Option 1: dev server with HMR (disable mocks, proxy to running backend)
VITE_USE_MOCKS=false pnpm dev

# Option 2: production build
VITE_API_BASE=http://localhost:8080 pnpm build
pnpm preview
```

Requires the API service running on `:8080` (see Quick Start above).

#### UI tests

```bash
pnpm test        # Vitest unit tests
pnpm lint        # ESLint
```

---

## SLO format

TROPEK uses a superset of the [Keptn 1.0 SLO spec](https://github.com/keptn/spec/blob/master/service_level_objective.md). Existing Keptn SLOs work without modification.

The key difference: **SLI queries are embedded in the SLO file** under an `indicators` block -- no separate SLI file needed.

```yaml
spec_version: '1.0'

# Optional — comparison strategy for relative criteria (<=+10%)
comparison:
  compare_with: several_results        # single_result | several_results
  number_of_comparison_results: 3
  include_result_with_score: pass_or_warn  # pass | pass_or_warn | all
  aggregate_function: avg              # avg | p50 | p90 | p95 | p99
  scope_tags: [os, arch]              # TROPEK extension: scope baseline to matching asset tags

# SLI queries — one entry per metric (PromQL, SQL, or ignored for push/file mode)
indicators:
  response_time_p99: 'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{instance="$vm_ip"}[5m]))'
  error_rate: 'rate(http_requests_total{status=~"5..",instance="$vm_ip"}[5m])'

objectives:
  - sli: response_time_p99
    displayName: "Response Time P99 (ms)"
    pass:
      - criteria: ["<600", "<=+10%"]   # AND within a block
      - criteria: ["<400"]             # OR across blocks — any block passing = pass
    warning:
      - criteria: ["<800"]
    weight: 2
    key_sli: false                     # true = failure here fails the entire evaluation

  - sli: error_rate
    displayName: "Error Rate"
    pass:
      - criteria: ["=0"]
    weight: 3
    key_sli: true

total_score:
  pass: "90%"      # weighted score >= 90% → pass
  warning: "75%"   # weighted score >= 75% → warning
```

### Criteria syntax

| Pattern | Type | Meaning |
|---|---|---|
| `<600` | Fixed | value must be less than 600 |
| `<=600` | Fixed | value must be <= 600 |
| `=0` | Fixed | value must equal 0 |
| `>=10` | Fixed | value must be >= 10 |
| `<=+10%` | Relative | value <= baseline x 1.10 |
| `>=-5%` | Relative | value >= baseline x 0.95 |
| `<=+50` | Relative | value <= baseline + 50 (absolute delta) |

Relative criteria with no comparison history **always pass** -- no history means no penalty.

---

## Triggering an evaluation

### Push mode (metrics provided inline)

```bash
curl -X POST http://localhost:8080/evaluations \
  -H "Content-Type: application/json" \
  -d '{
    "name": "checkout-api-load-test",
    "start": "2026-03-12T10:00:00Z",
    "end": "2026-03-12T10:30:00Z",
    "slo_name": "http-api-slo",
    "metrics": {
      "response_time_p99": 450.3,
      "error_rate": 0.0
    },
    "metadata": {"os": "linux", "branch": "main"}
  }'
```

### Pull mode (Prometheus adapter)

```bash
curl -X POST http://localhost:8080/evaluations \
  -H "Content-Type: application/json" \
  -d '{
    "name": "compilation-test",
    "start": "2026-03-12T10:00:00Z",
    "end": "2026-03-12T10:45:00Z",
    "slo_name": "compilation-test-slo",
    "datasource": {"adapter": "prometheus"},
    "metadata": {"vm_ip": "10.0.1.15", "os": "windows-11", "arch": "x64"}
  }'
```

### File mode (CSV)

```bash
curl -X POST http://localhost:8080/evaluations/file \
  -F 'meta={"name":"network-test","start":"2026-03-12T09:00:00Z","end":"2026-03-12T09:20:00Z","slo_name":"network-slo","results_format":"csv","metadata":{}}' \
  -F "results_file=@results.csv"
```

CSV format:
```csv
metric_name,value,aggregation
response_time_p99,450.3,p99
error_rate,0.02,avg
```

---

## Project structure

```
tropek/
├── api/                          Python FastAPI service
│   ├── tropek/                   Application code
│   │   └── modules/
│   │       ├── assets/           Asset (project/service) group CRUD
│   │       ├── asset_meta/       Asset metadata and tags
│   │       ├── assignments/      SLO-to-asset assignments
│   │       ├── datasource/       Datasource (adapter) registry
│   │       ├── display_groups/   SLI display grouping and ordering
│   │       ├── quality_gate/     Evaluation router + layered architecture
│   │       │   └── evaluation_engine/  Pure scoring logic (zero I/O)
│   │       ├── sli_registry/     SLI definition CRUD
│   │       ├── slo_groups/       SLO group templates
│   │       └── slo_registry/     Versioned SLO CRUD
│   ├── alembic/                  Database migrations
│   ├── tests/                    Unit + integration tests
│   └── docs/                     API architecture docs
├── ui/                           React SPA
│   ├── src/                      Application code
│   └── docs/                     UI architecture docs
├── adapters/
│   ├── prometheus/               Prometheus query adapter
│   └── mock/                     Mock adapter with data generator
├── docs/
│   ├── architecture/             System-wide architecture docs
│   ├── modules/                  Per-module documentation
│   └── guides/                   How-to guides
├── scripts/                      Migration, test, and DB helper scripts
├── config.yaml                   Non-secret runtime config (safe to commit)
├── .env.example                  Secret config template
├── docker-compose.yml            All services + test profile
└── pyproject.toml                UV workspace root + ruff/mypy/pytest config
```

---

## Tech stack

### Backend

| Component | Technology |
|---|---|
| Language | Python 3.13 |
| Framework | FastAPI |
| ORM | SQLAlchemy 2 (async, asyncpg driver) |
| Database | PostgreSQL 16 + TimescaleDB |
| Migrations | Alembic (async, autogenerated) |
| Job queue | arq (Redis-backed) |
| Cache | Redis 7 |
| HTTP client | httpx (async) |
| Config | Pydantic Settings + YAML |
| Logging | structlog |
| Package manager | uv |

### Frontend

| Component | Technology |
|---|---|
| Framework | React 19 + TypeScript 5.9 |
| Build | Vite 8 |
| Styling | Tailwind CSS 4 + shadcn/ui (Base UI) |
| Charts | Apache ECharts 6 |
| Data fetching | TanStack React Query 5 |
| Routing | React Router 7 |
| Forms | React Hook Form 7 + Zod 4 |
| API mocking | MSW 2 |
| Testing | Vitest 4 + React Testing Library |
| Package manager | pnpm |

---

## Roadmap

### Shipped

- Evaluation engine with pure-function scoring (ported from Keptn Go)
- Prometheus adapter + mock adapter for testing
- REST API with versioned SLO & SLI registries
- Asset & group registry with metadata and tags
- SLO groups, templates, and asset assignments
- Display groups for SLI ordering in the UI
- Heatmap navigator with per-asset evaluation overview
- Evaluation batches, annotations (with categories), invalidation/restore
- Baseline pinning, status overrides, re-evaluation
- Multi-phase arq worker pipeline (max_jobs=10)
- Contract testing (OpenAPI codegen + Schemathesis)
- React SPA with trend charts, SLI breakdown, theme system
- Change point detection via [Apache OTAVA](https://github.com/apache/otava) (on branch)

### Next

- InfluxDB adapter
- Test catalog
- Cross-version comparison UI
- Grafana SimpleJSON endpoint
- OWASP ZAP security scanning

---

## Contributing

This project is open source. PRs welcome.

```bash
# Before submitting a PR:
just check            # lint + format check + typecheck
just test-all         # all tests (unit + UI)
```

---

## Documentation

- **Architecture**: [docs/architecture/](docs/architecture/) -- system overview, evaluation lifecycle, data model, configuration
- **Modules**: [docs/modules/](docs/modules/) -- assets, datasources, registries, SLO groups
- **Guides**: [docs/guides/](docs/guides/) -- adapter protocol, contract testing
- **API internals**: [api/docs/](api/docs/) -- API layer, evaluation engine, database layer
- **UI internals**: [ui/docs/](ui/docs/) -- frontend architecture, features, mock system
