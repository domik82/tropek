# TROPEK

**Trend Reporting and Objective Evaluation toolkit**

A standalone quality gate and performance test evaluation platform. Evaluates SLI/SLO metrics from Prometheus, CSV files, JMeter results, or any source that can POST JSON — and decides pass / warning / fail.

Extracted and rewritten from [Keptn's](https://keptn.sh) lighthouse-service. Runs in Docker Compose. No Kubernetes required.

---

## What it does

- Evaluates metrics against **SLO criteria** (fixed thresholds and relative % change)
- Supports **key SLI veto** — one critical metric failure fails the whole evaluation regardless of score
- Tracks **trend history** with TimescaleDB for relative comparisons (`<=+10%`)
- Three **ingestion modes**: pull from Prometheus, push metrics inline, or upload a file (CSV / JMeter)
- **Versioned SLO registry** — every change to an SLO is stored; evaluations record which version they used
- **Annotations** — attach contextual notes to evaluations ("kernel updated before this test")
- **Invalidation** — mark evaluations as invalid without deleting them
- **Soft / hard rerun** — resume a partial job or replace all results from scratch

---

## Architecture

```
Docker Compose
├── api                  :8080   FastAPI — evaluation engine, SLO registry, REST API
├── worker                       arq job workers (same image, different entrypoint)
├── adapter-prometheus   :8081   Prometheus query adapter
├── timescaledb          :5432   PostgreSQL + TimescaleDB (evaluations + time-series SLI values)
├── redis                :6379   Job queue (arq) + response cache
└── ui                   :3000   React SPA (Phase 1 — in progress)
```

The evaluation engine is a **pure Python function** — zero I/O, fully unit-tested, ported from Keptn's Go implementation.

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/domik82/tropek.git
cd tropek

# 2. Configure
cp .env.example .env
# Edit .env — set passwords

# 3. Start infrastructure
docker compose up timescaledb redis -d

# 4. Run migrations
cd api && uv run alembic upgrade head && cd ..

# 5. Start all services
docker compose up --build

# 6. Check health
curl http://localhost:8080/health
```

---

## Development setup

Requires: [uv](https://docs.astral.sh/uv/), Python 3.13, Docker, Node.js 18+

### Backend (API + worker)

```bash
# Install all workspace dependencies
uv sync

# Run all unit tests (no infrastructure needed)
uv run pytest api/tests/ -m "not integration" -q

# Run integration tests (requires timescaledb + redis running)
uv run pytest api/tests/ -m integration -v

# Lint
uv run ruff check api/ adapters/

# Type check
uv run mypy api/app adapters/prometheus/app
```

### UI

```bash
cd ui
npm install
```

#### With mocks (no backend needed)

```bash
npm run dev
```

Starts on `http://localhost:5173` with MSW intercepting all API calls. Mock data is deterministic (seeded PRNG) — 30 days of history, 40 asset/lab scenarios, 30 metrics. No backend services required.

#### Against the real API

```bash
# Option 1: dev server with HMR (disable mocks, proxy to running backend)
VITE_USE_MOCKS=false npm run dev

# Option 2: production build
VITE_API_BASE=http://localhost:8080 npm run build
npm run preview
```

Requires the API service running on `:8080` (see Quick Start above).

#### UI tests

```bash
npm run test     # Vitest unit tests
npm run lint     # ESLint
```

---

## SLO format

TROPEK uses a superset of the [Keptn 1.0 SLO spec](https://github.com/keptn/spec/blob/master/service_level_objective.md). Existing Keptn SLOs work without modification.

The key difference: **SLI queries are embedded in the SLO file** under an `indicators` block — no separate SLI file needed.

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
| `<=600` | Fixed | value must be ≤ 600 |
| `=0` | Fixed | value must equal 0 |
| `>=10` | Fixed | value must be ≥ 10 |
| `<=+10%` | Relative | value ≤ baseline × 1.10 |
| `>=-5%` | Relative | value ≥ baseline × 0.95 |
| `<=+50` | Relative | value ≤ baseline + 50 (absolute delta) |
| `  <=+10   %` | Relative | whitespace is normalised |

Relative criteria with no comparison history **always pass** — no history means no penalty.

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
├── api/                        Python FastAPI service
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py           Pydantic Settings — loads config.yaml + env vars
│   │   ├── worker.py           arq job worker (evaluation jobs + watchdog)
│   │   ├── db/                 SQLAlchemy models + Alembic migrations
│   │   ├── cache/              Redis cache helpers
│   │   ├── adapters/           HTTP client for adapter services
│   │   └── modules/
│   │       ├── quality_gate/
│   │       │   ├── engine/     Pure evaluation logic (zero I/O)
│   │       │   │   ├── slo_parser.py   Parse + validate SLO YAML
│   │       │   │   ├── criteria.py     Parse criteria strings, evaluate, aggregate
│   │       │   │   ├── scoring.py      Per-objective scoring, total score calculation
│   │       │   │   ├── evaluator.py    Top-level evaluate() function
│   │       │   │   └── variables.py    $variable substitution in SLI queries
│   │       │   ├── router.py   /evaluations endpoints
│   │       │   ├── service.py  Orchestration (resolve SLO, enqueue job)
│   │       │   └── repository.py  DB queries
│   │       └── slo_registry/
│   │           ├── router.py   /slos endpoints
│   │           └── repository.py
│   └── tests/
│       ├── data/slo/           SLO YAML test fixtures (human-readable)
│       ├── data/results/       CSV / JMeter test fixtures
│       └── engine/             Unit tests for pure evaluation logic
├── ui/                         React SPA (Vite + TypeScript)
│   ├── src/
│   │   ├── features/           Feature modules (evaluations, assets, navigator, SLOs, SLIs)
│   │   ├── components/         Shared UI (shadcn/ui) and chart components (ECharts)
│   │   ├── pages/              Route handlers (Navigator, SLO Registry, Evaluation Detail)
│   │   ├── mocks/              MSW handlers + deterministic data generator
│   │   └── lib/                Theme, query keys, formatting utilities
│   └── package.json
├── adapters/
│   └── prometheus/             Standalone Prometheus query adapter
├── config.yaml                 Non-secret runtime configuration
├── .env.example                Secret configuration template
└── docker-compose.yml
```

---

## Configuration

Non-secret settings live in `config.yaml` (safe to commit). Secrets come from environment variables or Vault — never from the YAML file.

See `.env.example` for required secrets and `config.yaml` for all tuneable parameters (timeouts, concurrency limits, cache TTLs, etc.).

---

## Roadmap

- **Phase 1** (current): Evaluation engine, Prometheus adapter, REST API, basic UI
- **Phase 2**: Asset registry (VM / service registration, version snapshots), group evaluations with weighted multi-VM rollup
- **Phase 3**: Test catalog, cross-version comparison UI, Grafana SimpleJSON endpoint, InfluxDB adapter
- **Post Phase 3**: Change point detection via [Apache OTAVA](https://github.com/apache/otava)

---

## Contributing

This project is open source. PRs welcome.

```bash
# Before submitting a PR:
uv run ruff check api/ adapters/
uv run mypy api/app adapters/prometheus/app
uv run pytest api/tests/ -m "not integration" -q
```
