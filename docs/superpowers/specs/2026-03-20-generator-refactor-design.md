# SLO Test Data Generator — Refactor Design

> **Status:** Approved
> **Date:** 2026-03-20
> **Author:** Dominik + Claude

---

## 1. Problem Statement

The existing data generator in `observability_stack/integration-test/generator/` has
several issues preventing it from working:

### Bugs
- **Dockerfile breaks**: `apt-get remove -y curl tar` cascades to remove `tar`, a core dpkg dependency (already hotfixed — `tar` removal dropped)
- **Histogram OpenMetrics format wrong**: bucket/sum/count not grouped by label set + timestamp — promtool may reject
- **Counter monotonicity not guaranteed**: jitter is unclamped and can theoretically produce negative deltas, especially for low-volume counters like errors
- **Dead code**: `make_histogram_samples()` in `models.py` is imported in `base.py` but never called; `base.py` inlines duplicate histogram logic with different bucketing thresholds
- **Unused imports** throughout

### Design Problems
- **High memory usage**: builds all samples as Python dataclass objects in memory before writing — may cause OOM on constrained Docker containers (7-day × 30s × 3 scenarios ≈ 5M Sample objects)
- **Speed**: ~88 seconds before crashing (Python object-per-sample overhead)
- **Tangled concerns**: scenario logic, metric formatting, and backend I/O mixed in `base.py:generate()`
- **Single backend shape**: all backends get Prometheus-shaped data, but InfluxDB expects 1s granularity (Micrometer-style) and Prometheus expects 15-30s aggregated scrapes
- **Grafana InfluxDB datasource configured for Flux**: spec requires InfluxQL (already hotfixed in provisioning YAML)
- **No TimescaleDB support**: desired for experimentation
- **No CSV input**: can't hand-craft edge-case scenarios
- **No dashboards for InfluxDB/TimescaleDB**: data is written but can't be visualized

## 2. Goals

- Reliable data generation that actually works in Docker
- Pandas-based data model — vectorized ops, bounded memory via chunked streaming
- Clean three-layer architecture: Scenario → Shaper → Adapter
- Backend-specific metric shaping (resolution, labels, counter style)
- CSV input as a first-class scenario source
- TimescaleDB as an additional backend
- Dashboards for all three datasources (Prometheus, InfluxDB, TimescaleDB)
- Follow DRY, SOLID, YAGNI

## 3. Architecture

### Three Layers

```
Scenario → Profile DataFrame → Shaper → Shaped DataFrame → Adapter → Backend
```

**Scenarios** produce abstract operational profiles: "at time T, service S on host H
had throughput X, error rate Y, latency Z." No backend concepts.

**Shapers** transform profiles into backend-specific metric DataFrames: adding labels
like `instance`/`job` for Prometheus, controlling temporal resolution (1s for InfluxDB,
30s for Prometheus), expanding histograms into bucket rows.

**Adapters** handle pure I/O: writing shaped DataFrames to OpenMetrics files, InfluxDB
line protocol, TimescaleDB COPY, or CSV files.

### Why Three Layers

The current code tangles "what data exists" with "how does Prometheus want it formatted."
This causes:
- Histogram bucket logic duplicated between `models.py` and `base.py`
- OpenMetrics output grouped wrong (all buckets, then all sums, then all counts — should be interleaved per label set)
- No way to shape data differently for InfluxDB vs Prometheus

With three layers:
- Scenario logic is pure math, testable without any backend
- Shaper logic is pure DataFrame transformation, testable without I/O
- Adapter logic is pure I/O, thin and hard to get wrong

## 4. Data Model

### Profile DataFrame (Scenario output)

One row per `(timestamp, service, host)`. This is the universal format — all scenarios
(built-in and CSV input) produce this.

| Column | Type | Description |
|---|---|---|
| `timestamp` | `datetime64[s, UTC]` | Sample time |
| `service` | `category` | Service name |
| `host` | `category` | Host name |
| `throughput_rps` | `float64` | Requests per second |
| `error_rate` | `float64` | Error fraction 0.0–1.0 |
| `p50_latency` | `float64` | Median latency (seconds) |
| `p99_latency` | `float64` | P99 latency (seconds) |
| `cpu_percent` | `float64` | CPU usage 0–100 |
| `memory_bytes` | `float64` | Memory usage bytes |

Base resolution is **1 second** internally — this is the highest granularity any backend
needs (InfluxDB/Micrometer-style). Shapers downsample as needed (e.g. Prometheus to 30s).
The 1s resolution means 7 days = 604,800 rows per service-host combo. With chunked
streaming (1 hour per chunk = 3,600 × 6 combos = 21,600 rows ≈ 1.5 MB per chunk),
memory stays bounded regardless of `--days`.

### Shaped DataFrame (Shaper output)

Backend-specific. Examples:

**Prometheus**: `timestamp, metric, value, service, host, instance, job, le, status_code`
**InfluxDB**: `timestamp, measurement, service, host, value, rate, le, status_code`
**TimescaleDB**: `timestamp, metric, service, host, value`

## 5. Scenarios

### Built-in Scenarios

Each yields profile DataFrames in **chunks** (e.g. 1 hour of data per chunk) to bound memory.

```python
class BaseScenario:
    def generate(self, resolution_seconds: int = 1) -> Iterator[pd.DataFrame]:
        """Yield profile DataFrames in chunks."""
```

- **HealthyScenario**: diurnal variation (±15% throughput over 24h), per-service/host factors
- **OutageScenario**: three phases (healthy → outage with 2-min ramp → 10-min recovery)
- **DegradationScenario**: two phases (healthy → sustained regression: 5× latency, 5× error rate, throughput unchanged)

Same math as the current code, vectorized with pandas + numpy instead of per-sample Python loops.

### CSV Scenario

```python
class CSVScenario:
    def __init__(self, csv_path: Path): ...
    def generate(self, resolution_seconds: int = 1) -> Iterator[pd.DataFrame]: ...
```

Reads a CSV with the profile DataFrame schema. Validates columns on load. Yields in chunks.
This allows hand-crafting edge-case scenarios (e.g. a specific spike pattern at an exact time)
without writing Python code.

**CSV validation rules:**
- Required columns: all profile DataFrame columns (timestamp through memory_bytes)
- Timestamps must be ISO 8601 or Unix epoch, parsed to `datetime64[s, UTC]`
- Timestamps must be sorted ascending
- Resolution is inferred from the first two rows' timestamp delta
- If timestamps are irregular (gap varies > 10%), a warning is emitted but data is accepted as-is — shapers handle whatever resolution they receive

## 6. Shapers

### Interface

```python
class BaseShaper:
    def shape(self, profile_chunk: pd.DataFrame) -> Iterator[pd.DataFrame]:
        """Transform a profile chunk into backend-specific metric DataFrames."""

    def finalize(self) -> Iterator[pd.DataFrame]:
        """Flush accumulated state (e.g. counter accumulators)."""
```

Shapers are **stateful** — counters accumulate across chunks.

### PrometheusShaper

- **Resolution**: downsamples to configurable scrape interval (default 30s)
- **Downsampling strategy per metric type**:
  - Counters: sum deltas over the window, then accumulate into cumulative value
  - Gauges: take last value in the window (mimics Prometheus instant scrape)
  - Histograms: sum bucket count deltas over the window, then accumulate
- **Counters**: cumulative, monotonically increasing. Jitter clamped to `max(0, delta)`
- **Histograms**: expands `(p50, p99, throughput)` into bucket/sum/count rows with `le` labels
- **Labels added**: `instance` (e.g. `frontend-host1:8080`), `job` (e.g. `app`)
- **Output**: `timestamp, metric, value, service, host, instance, job, le, status_code`

### InfluxDBShaper

- **Resolution**: keeps 1s (Micrometer-style high granularity)
- **Counters**: raw delta per interval as `value`, plus cumulative as `cumulative` field, plus `rate` field
- **Histograms**: expanded to bucket rows, non-cumulative counts per bucket
- **Labels**: `service`, `host` as tags. No `instance`/`job`
- **Output**: `timestamp, measurement, service, host, value, rate, le, status_code`

### TimescaleDBShaper

- **Resolution**: configurable (default 1s)
- **Counters**: as deltas (rate-style), gauges as-is
- **Histograms**: stored as p50/p99/avg summary rows (simpler for SQL queries)
- **Output**: `timestamp, metric, service, host, value`

### RawShaper (CSV output)

- Passes through profile DataFrame unchanged
- No metric expansion, no counter accumulation
- The "what happened" view — for inspection and re-import

### Factory

```python
def get_shaper(backend: str, **config) -> BaseShaper:
    shapers = {
        "prometheus": PrometheusShaper,
        "influxdb": InfluxDBShaper,
        "timescaledb": TimescaleDBShaper,
        "csv": RawShaper,
    }
    return shapers[backend](**config)
```

## 7. Adapters

Thin I/O wrappers. No data transformation logic.

### Interface

```python
class BaseAdapter:
    def write_chunk(self, df: pd.DataFrame) -> None:
        """Write one chunk to the backend."""

    def close(self) -> None:
        """Flush and release resources."""

    def __enter__ / __exit__  # context manager
```

### PrometheusAdapter

- Writes OpenMetrics text format
- Groups output by `(label_set, timestamp)` — all buckets + sum + count together
- Writes `# EOF` marker after all chunks
- Separate step: runs `promtool tsdb create-blocks-from openmetrics`

### InfluxDBAdapter

- Converts chunks to line protocol via vectorized string ops
- Batch writes to InfluxDB v2 API
- Creates DBRP mapping on first write (for InfluxQL compatibility)

### TimescaleDBAdapter

- Uses `psycopg` COPY protocol for fast bulk insert
- Creates hypertable on first write if it doesn't exist

### CSVAdapter

- `df.to_csv()` — one file per scenario

## 8. Pipeline Wiring

```python
shapers_and_adapters = [
    (get_shaper("prometheus", scrape_interval=30), PrometheusAdapter(om_file)),
    (get_shaper("influxdb"), InfluxDBAdapter(url, token, ...)),
    (get_shaper("timescaledb"), TimescaleDBAdapter(dsn)),
]

for chunk in scenario.generate():
    for shaper, adapter in shapers_and_adapters:
        for shaped in shaper.shape(chunk):
            adapter.write_chunk(shaped)

for shaper, adapter in shapers_and_adapters:
    for shaped in shaper.finalize():
        adapter.write_chunk(shaped)
    adapter.close()
```

### Per-Scenario Output

When `--scenario all` is used, each scenario is processed independently through the full
pipeline. File-based outputs (OpenMetrics, CSV) produce **one file per scenario**
(e.g. `healthy_metrics.om`, `outage_metrics.om`). Database backends (InfluxDB, TimescaleDB)
write all scenarios into the same bucket/table — the data is distinguished by time windows.

### Error Handling

Adapter errors are **best-effort per backend** — if InfluxDB fails, Prometheus and
TimescaleDB still proceed. Each backend's failure is logged with Rich console output.
The generator exits with code 0 if at least one backend succeeded, code 1 if all failed.
This matches the existing behavior where InfluxDB errors are non-fatal.

## 9. Dashboards

Three dashboards generated from the **same `dashboard_config.yaml`**. Each panel definition
includes queries for all three datasources:

```yaml
- id: 1
  title: "Global Throughput"
  panel_type: stat
  queries:
    prometheus: "sum(rate(http_requests_total[5m]))"
    influxql: >
      SELECT sum("rate") FROM "http_requests_total"
      WHERE $timeFilter GROUP BY time($__interval)
    sql: >
      SELECT time_bucket('5m', timestamp) AS t, sum(value)
      FROM metrics WHERE metric = 'http_requests_total' GROUP BY t
```

The Jinja2 template renders three separate JSON files — one per datasource:

| Dashboard | File | Datasource | Query Language |
|---|---|---|---|
| SLO Test — Prometheus | `slo_test_prometheus.json` | Prometheus | PromQL |
| SLO Test — InfluxDB | `slo_test_influxdb.json` | InfluxDB | InfluxQL |
| SLO Test — TimescaleDB | `slo_test_timescaledb.json` | TimescaleDB (PostgreSQL) | SQL |

All three show the same panels and layout. If the visualizations match across dashboards,
the shapers are producing equivalent data.

### Grafana Datasource Provisioning

```yaml
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    isDefault: true

  - name: InfluxDB
    type: influxdb
    url: http://influxdb:8086
    basicAuth: true
    basicAuthUser: admin
    jsonData:
      version: InfluxQL
      dbName: slo-metrics
      httpMode: GET
    secureJsonData:
      basicAuthPassword: slo-test-token

  - name: TimescaleDB
    type: postgres
    url: timescaledb-metrics:5432
    database: slo_metrics
    user: metrics
    jsonData:
      sslmode: disable
      timescaledb: true
    secureJsonData:
      password: metrics
```

## 10. Docker Compose

### New Service

```yaml
timescaledb-metrics:
  image: timescale/timescaledb:latest-pg16
  container_name: slo_timescaledb
  environment:
    POSTGRES_USER: metrics
    POSTGRES_PASSWORD: metrics
    POSTGRES_DB: slo_metrics
  ports:
    - "5434:5432"     # 5434 avoids tropek dev (5432) and test (5433)
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U metrics"]
    interval: 5s
    retries: 10
```

### Updated Generator

```yaml
generator:
  build:
    context: ./generator
  command:
    - "--scenario=all"
    - "--days=7"
    - "--backends=prometheus,influxdb,timescaledb"
    - "--prometheus-data-dir=/prometheus_data"
    - "--influxdb-url=http://influxdb:8086"
    - "--timescaledb-url=postgresql://metrics:metrics@timescaledb-metrics:5432/slo_metrics"
    - "--run-promtool"
  depends_on:
    influxdb:
      condition: service_healthy
    timescaledb-metrics:
      condition: service_healthy
```

### Port Summary

| Service | Port | Purpose |
|---|---|---|
| Prometheus | 9090 | Metrics backend |
| InfluxDB | 8086 | Metrics backend |
| TimescaleDB (metrics) | 5434 | Metrics backend (new) |
| Grafana | 3000 | Visualization |

## 11. Package Structure

```
generator/
├── pyproject.toml
├── Dockerfile
│
├── src/
│   └── slo_generator/
│       ├── __init__.py
│       ├── cli.py
│       │
│       ├── scenarios/
│       │   ├── __init__.py       # factory: get_scenario()
│       │   ├── base.py           # BaseScenario + profile schema
│       │   ├── healthy.py
│       │   ├── outage.py
│       │   ├── degradation.py
│       │   └── csv_input.py
│       │
│       ├── shapers/
│       │   ├── __init__.py       # factory: get_shaper()
│       │   ├── base.py           # BaseShaper interface
│       │   ├── prometheus.py
│       │   ├── influxdb.py
│       │   ├── timescaledb.py
│       │   └── raw.py
│       │
│       └── adapters/
│           ├── __init__.py       # factory: get_adapter()
│           ├── base.py           # BaseAdapter interface
│           ├── prometheus.py
│           ├── influxdb.py
│           ├── timescaledb.py
│           └── csv.py
```

## 12. CLI

```bash
# Full stack (Docker default)
slo-generate --scenario all --days 7 --backends prometheus,influxdb,timescaledb

# CSV input — custom scenario
slo-generate --csv-input ./my-edge-case.csv --backends prometheus,influxdb

# CSV output only (quick inspection)
slo-generate --scenario healthy --days 1 --backends csv --output-dir ./output

# Run promtool backfill separately
slo-generate backfill --om-file ./output/healthy.om --tsdb-dir /prometheus_data
```

## 13. Dependencies

```toml
[project]
dependencies = [
    "pandas>=2.2",
    "numpy>=1.26",
    "click>=8.1",
    "rich>=13.7",
]

[project.optional-dependencies]
influxdb = ["influxdb-client>=1.41"]
timescaledb = ["psycopg[binary]>=3.1"]
all = ["slo-generator[influxdb,timescaledb]"]
```

## 14. What Gets Deleted / Replaced

**Deleted:**
- `models.py` — replaced by pandas DataFrames + shaper layer
- `requirements.txt` — replaced by `pyproject.toml`

**Rewritten:**
- All scenarios — same math, vectorized with pandas
- All adapters — stripped to pure I/O

**New:**
- `shapers/` — entire new layer
- `scenarios/csv_input.py`
- `adapters/timescaledb.py`
- Multi-datasource dashboard generation

**Extended:**
- `grafana/generate_dashboard.py` — updated to render three dashboards (one per datasource) from the same YAML config
- `grafana/dashboard_config.yaml` — panel definitions extended with per-datasource queries
- `grafana/provisioning/datasources/all.yml` — TimescaleDB datasource added

**Untouched:**
- `prometheus/prometheus.yml`
- `Makefile` — minor CLI updates

## 15. Non-Goals

- Parallelism / multiprocessing — single-threaded is fine for demo + integration testing
- Generic arbitrary-label support — we know the exact label set
- Production deployment of the generator — this is a test/demo tool
- grafana2slo parser implementation — this spec covers only the data generation side
