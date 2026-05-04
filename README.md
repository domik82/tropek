# TROPEK

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

**Trend Reporting and Objective Evaluation toolkit**

A standalone quality gate and performance test evaluation platform. Evaluates SLI/SLO metrics collected from data adapters (currently Prometheus). Any source that can serve scalar metrics — CSV files, JMeter results, custom databases — can be wrapped in an adapter.

Tropek decides if the collected data is pass / warning / fail based on historical trends and SLO criteria.


Inspired by [Keptn v1](https://keptn.sh)'s lighthouse-service, [Apache OTAVA](https://github.com/apache/otava) for change point detection, and the Nurkio project. Runs in Docker Compose. No Kubernetes required.

---

## What it does

- Evaluates metrics against **SLO criteria** (fixed thresholds and relative % change)
- Supports **key SLI veto** - one critical metric failure fails the whole evaluation regardless of score
- Tracks **trend history** with TimescaleDB for relative comparisons (`<=+10%`)
- **Adapter-based data ingestion** — pull metrics from any adapter (Prometheus shipped; custom adapters for CSV, JMeter, etc. can be added)
- **Versioned SLO & SLI registries** - every change is stored; evaluations record which version they used
- **SLO groups & templates** - organise SLOs into reusable groups, assign them to assets
- **Display groups** - control how SLI objectives are grouped and ordered in the UI
- **Asset & group registry** - register VMs/services, organise into groups, bind SLOs to assets
- **Heatmap navigator** - visual overview of evaluation results across assets and time
- **Evaluation batches** - trigger evaluations for multiple assets in a single request
- **Annotations with categories** - attach categorised contextual notes to evaluations
- **Invalidation & restore** - mark evaluations as invalid and restore them without deleting data
- **Baseline pinning** - pin a specific evaluation as the new comparison baseline
- **Status overrides** - manually override an evaluation's pass/warning/fail status
- **Re-evaluation** - re-run an evaluation against updated SLO criteria
- **Multi-phase worker pipeline** - arq workers with configurable concurrency (max_jobs=10)
- **Contract testing** - OpenAPI codegen + Schemathesis property-based API conformance tests
- **Data source registry** - register adapter instances (Prometheus, mock adapter for testing)

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

## Deploy (pre-built images)

Run TROPEK without cloning the repo — just download the compose file and start:

```bash
# 1. Download deployment files
curl -LO https://github.com/domik82/tropek/releases/latest/download/docker-compose.yml
curl -LO https://github.com/domik82/tropek/releases/latest/download/.env.example

# 2. Configure
cp .env.example .env
# Edit .env — set TK_DB_PASSWORD, TK_REDIS_PASSWORD, TK_SECRET_KEY, PROMETHEUS_URL

# 3. Start
docker compose up -d

# 4. Open
# UI:       http://localhost:3000
# API docs: http://localhost:8080/docs
```

For the full deployment guide see [docs/getting-started.md](docs/getting-started.md).

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

## SLO / SLI format

TROPEK's evaluation criteria are split into two manifest kinds: **SLI definitions** (indicator queries) and **SLO definitions** (thresholds and scoring). The scoring engine is inspired by [Keptn v1](https://github.com/keptn/spec/blob/master/service_level_objective.md) but uses its own YAML schema.

### SLI definition

```yaml
api_version: tropek/v1
kind: SLI
metadata:
  name: http-service-sli
  display_name: HTTP Service Indicators
spec:
  adapter_type: prometheus
  indicators:
    response_time_p99: 'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{job="$job"}[5m]))'
    error_rate: 'rate(http_requests_total{job="$job",status=~"5.."}[5m]) / rate(http_requests_total{job="$job"}[5m])'
    availability: 'avg_over_time(up{job="$job"}[5m])'
```

### SLO definition

```yaml
api_version: tropek/v1
kind: SLO
metadata:
  name: http-availability-slo
  display_name: HTTP Availability SLO
spec:
  sli_name: http-service-sli          # references the SLI definition above
  sli_version: 1
  kind: standard                      # standard | template
  comparison:
    compare_with: several_results     # single_result | several_results
    number_of_comparison_results: 3
    include_result_with_score: pass_or_warn
    aggregate_function: avg           # avg | p50 | p90 | p95 | p99
  total_score:
    pass_threshold: 90.0              # weighted score >= 90% → pass
    warning_threshold: 75.0           # weighted score >= 75% → warning
  objectives:
    - sli: response_time_p99
      display_name: "Response Time P99 (ms)"
      pass_threshold: [">0", "<500", "<=+10%"]
      warning_threshold: [">0", "<800", "<=+15%"]
      weight: 2
      change_point:
        max_pvalue: 0.01              # more permissive than default (0.001)
        min_magnitude: 0.05           # ignore changes smaller than 5%
    - sli: error_rate
      display_name: "Error Rate"
      pass_threshold: [">0", "<0.01", "<=+10%"]
      warning_threshold: [">0", "<0.05", "<=+15%"]
      weight: 3
      key_sli: true                   # failure here fails the entire evaluation
    - sli: availability
      display_name: "Availability"
      pass_threshold: [">=0.999"]
      warning_threshold: [">=0.99"]
      weight: 2
      change_point:
        higher_is_better: true        # decrease in availability = regression
```

See `dev_setup/mock/` for complete working examples including template SLOs with `$__gen_` variable expansion and aggregated-mode SLIs.

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

### Change point detection (Apache OTAVA)

TROPEK uses the [E-Divisive](https://github.com/apache/otava) algorithm to automatically detect statistically significant shifts in metric time series. Detection runs after each evaluation and results appear as markers on trend charts and heatmap cells.

Configuration is per-objective via the `change_point:` block. All fields are optional — omitted fields inherit the global defaults shown below:

```yaml
objectives:
  - sli: response_time_p99
    pass_threshold: ["<500"]
    change_point:
      enabled: true            # default: true — set false to disable for this metric
      higher_is_better: false  # default: false — false = increase is regression (latency)
                               #                  true  = decrease is regression (throughput)
      window_size: 30          # default: 30 — sliding window length for the algorithm
      max_pvalue: 0.001        # default: 0.001 — significance threshold (lower = stricter)
      min_magnitude: 0.0       # default: 0.0 — minimum relative change (%) to report
      min_sample_size: 10      # default: 10 — skip detection with fewer data points
```

| Field | Default | Description |
|---|---|---|
| `enabled` | `true` | Enable/disable detection for this objective |
| `higher_is_better` | `false` | Directionality: `false` for latency-like metrics (increase = bad), `true` for throughput-like metrics (decrease = bad) |
| `window_size` | `30` | Number of data points in the sliding window. Larger = less sensitive to short-term noise |
| `max_pvalue` | `0.001` | P-value threshold for the merge-phase t-test. A higher value (e.g. 0.01 vs 0.001) is more permissive — it accepts weaker statistical evidence, so it will detect more change points, including ones that might be noise. Lower values require stronger evidence and produce fewer, higher-confidence detections |
| `min_magnitude` | `0.0` | Minimum relative change (as a fraction, e.g. `0.05` = 5%) to keep a detected change point. Filters out statistically significant but practically irrelevant shifts |
| `min_sample_size` | `10` | Minimum number of evaluations before detection runs. Prevents false positives from small data sets |

**When it runs:** Change point detection runs automatically after each evaluation completes, as a fault-isolated step in the worker pipeline. If detection fails (e.g. not enough data points), the evaluation result is still saved — detection is non-blocking.

**Triage workflow:** New change points start with status `unprocessed`. You can triage them individually or in bulk via the API — set a status (e.g. `acknowledged`, `investigating`, `resolved`, `expected`), attach a note, and optionally link a ticket. Triage status is free-form text, so you can use whatever workflow labels fit your team.

**Deduplication:** The E-Divisive algorithm re-analyzes the full time series on every evaluation, so it will repeatedly detect the same change point. TROPEK applies two layers of deduplication before persisting:

1. **Positional dedup** — if a change point already exists within ±1 ordinal position in the time series, the new detection is skipped (same shift detected at a slightly different boundary).
2. **Same-regime suppression** — if the new change point has the same direction (regression/improvement) as the most recent one for that metric, and the post-segment mean falls within 2 standard deviations of the previous change point's post-segment, it is suppressed. The metric hasn't meaningfully shifted to a new regime — it's just noise within the same level.

Only genuinely new regime shifts are saved. Detected change points are classified as **regression** or **improvement** based on the `higher_is_better` setting and can be triaged (acknowledged, investigated, or linked to tickets) via the API.

---

## Triggering an evaluation

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

The API enqueues the evaluation; a worker pulls metrics from the configured adapter (Prometheus), runs the scoring engine, and stores results in TimescaleDB.

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
- Change point detection via [Apache OTAVA](https://github.com/apache/otava)

### Next

- InfluxDB adapter
- Test catalog
- Cross-version comparison UI
- Grafana SimpleJSON endpoint
- OWASP ZAP security scanning

---

## Python client

A typed Python client with CLI is available (not yet on PyPI):

```bash
pip install git+https://github.com/domik82/tropek.git#subdirectory=clients/python
tropek --help
```

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

---

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
