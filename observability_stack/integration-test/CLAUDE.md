# CLAUDE.md — SLO Integration Test Environment

## What This Is
Integration testing environment for `grafana2slo` + SLO quality gate testing.

Provides:
- Docker Compose stack (Prometheus + InfluxDB + TimescaleDB + Grafana)
- Python data generator (pandas-based) populating all 3 backends
- Grafana dashboards for Prometheus, InfluxDB, and TimescaleDB

## Architecture

Three-layer pipeline: Scenario → Shaper → Adapter

- **Scenarios** produce abstract profile DataFrames (throughput, latency, error rate, CPU, memory)
- **Shapers** transform profiles into backend-specific metric DataFrames (downsampling, cumulative counters, histograms)
- **Adapters** handle pure I/O (file writing, network sends)

## Common Commands

```bash
just up              # full stack
just down            # stop
just reset           # wipe + restart
just dashboard       # regenerate all 3 dashboard JSONs
just test            # run generator unit tests
just gen-csv         # generate CSV files locally
just gen-om          # generate OpenMetrics files locally
just gen healthy     # generate a single scenario
```

## Timeline Mode

Generate composed timelines with events placed at specific timestamps:

```bash
just gen-timeline timelines/quick-test.yaml        # CSV output for inspection
just gen-timeline timelines/evaluation-30d.yaml     # 30-day quality gate test
just gen-timeline timelines/change-detection-60d.yaml  # change point detection
```

Timeline YAML files define a healthy baseline with events spliced in:

```yaml
timeline:
  start: "2026-03-14T00:00:00Z"
  duration: 168h
  resolution: 30s
  events:
    - type: outage
      at: 160h
      duration: 30m
      resolution: 5s
```

Available event types: `outage`, `degradation`, `memory_leak`, `traffic_spike`,
`step_change`, `polska`.

## File Map

```
docker-compose.yml
justfile

timelines/
  quick-test.yaml             1-week test with outage at end
  evaluation-30d.yaml         30-day quality gate test scenario
  change-detection-60d.yaml   60-day change point detection scenario
  easter-egg.yaml             polska event

generator/
  pyproject.toml              uv project, pandas/numpy/click deps
  src/slo_generator/
    cli.py                    Click CLI entry point
    pipeline.py               Scenario → Shaper → Adapter wiring
    constants.py              SERVICES, HOSTS, PROFILE_COLUMNS
    scenarios/
      base.py                 BaseScenario ABC (chunked generation)
      healthy.py              Diurnal variation
      outage.py               Sudden failure + recovery
      degradation.py          Deployment regression
      csv_input.py            CSV file input
    shapers/
      base.py                 BaseShaper ABC
      prometheus.py           Downsample, cumulative, histograms
      influxdb.py             1s resolution, delta+rate
      timescaledb.py          1s, summary histograms
      raw.py                  Passthrough for CSV
    adapters/
      base.py                 BaseAdapter ABC
      prometheus.py           OpenMetrics file writer
      influxdb.py             Line protocol batch writer
      timescaledb.py          psycopg COPY writer
      csv.py                  CSV file writer
  tests/
    conftest.py               Shared fixtures
    test_scenarios.py
    test_shapers.py
    test_adapters.py
    test_pipeline.py
    test_csv_input.py

grafana/
  dashboard_config.yaml       Panel definitions (queries for all 3 datasources)
  generate_dashboard.py       Renders 3 dashboard JSONs
  templates/dashboard.json.j2
  dashboards/                 Generated JSON (don't edit)
  provisioning/               Grafana auto-provisioning
```

## Supported Backends

| Backend | Format | Target |
|---|---|---|
| `prometheus` | OpenMetrics text | promtool TSDB backfill |
| `influxdb` | Line protocol | InfluxDB v2 HTTP API |
| `timescaledb` | COPY stream | PostgreSQL + TimescaleDB |
| `csv` | CSV files | Local inspection / offline testing |

## Metrics Generated

All metrics have labels: `service` ∈ {frontend, api, backend}, `host` ∈ {host1, host2}

- `http_requests_total` — counter
- `http_errors_total` — counter
- `http_request_duration_seconds_{bucket,sum,count}` — histogram
- `cpu_usage_percent` — gauge (0–100)
- `memory_usage_bytes` — gauge

## Gotchas

- Generator must complete before Prometheus starts (`service_completed_successfully`)
- InfluxDB must be healthy before generator writes to it (`healthcheck` gate)
- `--storage.tsdb.allow-overlapping-blocks` is required on Prometheus when
  loading backfilled TSDB blocks alongside live scrape data
- Dashboard JSON must have `"uid"` set — Grafana uses it for stable linking
- Never run `just reset` with the stack running — always `just down` first
- Generator uses `uv run slo-generate` — no `python main.py` or `requirements.txt`
