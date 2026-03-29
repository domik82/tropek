# SLO Integration Test Environment

Integration testing environment for the `grafana2slo` parser. Provides a fully
self-contained Prometheus + Grafana + InfluxDB stack pre-loaded with synthetic
metric data covering all query patterns the parser needs to handle.

## Architecture

```
docker compose up
        │
        ├── influxdb        starts first (healthcheck gate)
        │
        ├── generator       runs once, then exits
        │     ├── generates 3 scenarios (healthy / outage / degradation)
        │     ├── writes OpenMetrics files → promtool TSDB backfill → /prometheus_data
        │     └── pushes same data to InfluxDB
        │
        ├── prometheus      starts after generator exits, picks up TSDB blocks
        │
        └── grafana         starts after prometheus, auto-imports dashboard
```

### Service URLs

| Service    | URL                       | Credentials          |
|------------|---------------------------|----------------------|
| Grafana    | http://localhost:3000     | admin / admin        |
| Prometheus | http://localhost:9090     | —                    |
| InfluxDB   | http://localhost:8086     | admin / adminpassword |

---

## Quick Start

```bash
# 1. Regenerate dashboard JSON from config (only needed after editing panels)
make dashboard

# 2. Build images, generate data, start all services
make up

# 3. Tail logs to watch generator progress (takes 1–3 min on first run)
make logs-generator

# 4. Open Grafana
open http://localhost:3000
```

To stop: `make down`
To wipe all data and restart: `make reset`

---

## Directory Structure

```
integration-test/
│
├── docker-compose.yml          Stack definition
├── Makefile                    Common operations
│
├── generator/                  Python data generator
│   ├── Dockerfile              Includes promtool for TSDB backfill
│   ├── requirements.txt
│   ├── main.py                 CLI entry point (click)
│   ├── models.py               Sample / MetricFamily / ScenarioWindow types
│   │
│   ├── scenarios/
│   │   ├── base.py             BaseScenario + ServiceProfile + generation loop
│   │   ├── healthy.py          Flat baseline with diurnal variation
│   │   ├── outage.py           Sudden failure with ramp-in and recovery
│   │   └── degradation.py      Deployment regression — latency creep, stable throughput
│   │
│   └── adapters/
│       ├── base.py             BaseAdapter interface
│       ├── prometheus_adapter.py   OpenMetrics text format writer
│       ├── influxdb_adapter.py     InfluxDB v2 line protocol writer
│       └── csv_adapter.py          CSV writer (one file per metric family)
│
├── grafana/
│   ├── dashboard_config.yaml   ← EDIT THIS to change panels
│   ├── generate_dashboard.py   Jinja2 renderer: YAML → dashboard JSON
│   ├── templates/
│   │   └── dashboard.json.j2   Grafana dashboard Jinja2 template
│   ├── dashboards/
│   │   └── slo_test.json       Generated — do not edit directly
│   └── provisioning/
│       ├── datasources/all.yml Prometheus + InfluxDB auto-provisioned
│       └── dashboards/all.yml  Dashboard folder provisioning
│
└── prometheus/
    └── prometheus.yml          Scrape config
```

---

## Data Generator

### Scenarios

#### `healthy` — Baseline
- All services running normally
- Mild diurnal variation (±15% throughput over 24h cycle)
- Error rate: ~0.1%, P99 latency: ~80ms, CPU: ~40%
- Purpose: baseline for SLO comparison

#### `outage` — Sudden Failure
- Configurable duration (default: 30 min)
- Ramps in over 2 minutes, then recovers over 10 minutes
- Error rate: up to 80%, P99 latency: up to 10s, throughput: drops 90%
- Purpose: validate that quality gate correctly rejects this run

#### `degradation` — Deployment Regression
- Throughput stays the same (application still accepts requests)
- P99 latency grows 5× (e.g. 80ms → 400ms)
- Error rate grows 5× (0.1% → 0.5%)
- CPU increases ~35%, memory unchanged
- Purpose: simulate a bad deployment that isn't an outage

### Metrics Generated

| Metric | Type | Labels |
|--------|------|--------|
| `http_requests_total` | counter | `service`, `host`, `status_code` |
| `http_errors_total` | counter | `service`, `host` |
| `http_request_duration_seconds_bucket` | histogram | `service`, `host`, `le` |
| `http_request_duration_seconds_sum` | counter | `service`, `host` |
| `http_request_duration_seconds_count` | counter | `service`, `host` |
| `cpu_usage_percent` | gauge | `service`, `host` |
| `memory_usage_bytes` | gauge | `service`, `host` |

Services: `frontend`, `api`, `backend`
Hosts per service: `host1`, `host2`

### Running the Generator Locally (without Docker)

```bash
cd generator
pip install -r requirements.txt

# CSV only (fastest, no backends needed)
python main.py --scenario all --days 7 --resolution 30 \
    --output-dir ./output --skip-influxdb --skip-prometheus

# With OpenMetrics output for manual promtool backfill
python main.py --scenario outage --outage-duration 60 \
    --days 3 --resolution 15 --output-dir ./output --skip-influxdb

# All flags
python main.py --help
```

### CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--scenario` | `all` | `healthy`, `outage`, `degradation`, or `all` |
| `--days` | `7` | History window in days |
| `--resolution` | `30` | Sample interval in seconds |
| `--outage-duration` | `30` | Outage length in minutes |
| `--output-dir` | `./output` | Directory for CSV and `.om` files |
| `--skip-influxdb` | false | Skip InfluxDB writes |
| `--skip-prometheus` | false | Skip OpenMetrics file generation |
| `--csv-only` | false | CSV only, skip all remote backends |
| `--run-promtool` | false | Run `promtool tsdb create-blocks-from openmetrics` after generation |

---

## Dashboard

The Grafana dashboard is defined in `grafana/dashboard_config.yaml` and rendered
to JSON via a Jinja2 template. **Never edit `dashboards/slo_test.json` directly.**

### Adding or Changing Panels

1. Edit `grafana/dashboard_config.yaml`
2. Run `make dashboard` (or `python grafana/generate_dashboard.py`)
3. Commit both the YAML and the generated JSON
4. Grafana auto-reloads from the provisioned path

### Panel Query Types (for parser test coverage)

| Type | Description | Example |
|------|-------------|---------|
| `C` | Simple scalar, no grouping | `sum(rate(errors[5m]))` |
| `A` | Grafana template variable | `sum(rate(errors{service="$service"}[5m]))` |
| `B` | Aggregation grouping, no variable | `sum by (service) (rate(errors[5m]))` |
| `COMPLEX` | Subquery / nested — MANUAL_REQUIRED | `max_over_time(...[30m:1m])` |

Current panel coverage: 6× Type C, 6× Type A, 3× Type B, 2× COMPLEX, 1× multi-target edge case.

---

## Extending

### Adding a New Scenario

1. Create `generator/scenarios/my_scenario.py` subclassing `BaseScenario`
2. Implement `profile_at(t, service, host) -> ServiceProfile`
3. Add import to `generator/scenarios/__init__.py`
4. Add the `elif` branch in `generator/main.py`

### Adding a New Adapter

1. Create `generator/adapters/my_adapter.py` subclassing `BaseAdapter`
2. Implement `write(families)` and `close()`
3. Add import to `generator/adapters/__init__.py`

### Adding a New Metric

Add to `BaseScenario._init_families()` and instrument in `generate()`.
The adapter layer picks up all families automatically — no adapter changes needed.
