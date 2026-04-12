# Raw Data Pipeline — Micrometer-Accurate Multi-Backend Generation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the generator pipeline so all three backends (Prometheus, InfluxDB, TimescaleDB) derive their data from a single source of truth — raw per-second samples with individual latency values. Prometheus adapter mimics real Micrometer/PrometheusMeterRegistry behavior (cumulative counters + histogram buckets). TimescaleDB stores raw latencies and computes exact percentiles at query time. InfluxDB stores per-second rates with pre-computed percentiles. Values differ between backends by the *expected* amount (~5-10% from Prometheus bucket interpolation), not by 10x.

**Architecture change:**
```
BEFORE:  Scenario → Profile(throughput, p50, p99) → Shaper → Adapter
                     ↑ each shaper independently fabricates its representation

AFTER:   Scenario → RawSample(request_count, latencies[], cpu, memory)
                     ↓ single source of truth
              ┌──────┼──────────────┐
              ▼      ▼              ▼
         Prometheus  InfluxDB   TimescaleDB
         (Micrometer (exact      (raw latencies,
          accumulation, rates,    percentile_cont
          histogram   pre-computed at query time)
          buckets)    percentiles)
```

**Tech Stack:** Python 3.13, pandas, numpy, pyarrow (for Parquet), uv package manager.

**Base paths:**
- `$BASE` = `observability_stack/integration-test`
- `$GEN` = `$BASE/generator`
- `$SRC` = `$GEN/src/slo_generator`
- `$TESTS` = `$GEN/tests`

**Run tests with:** `uv run --directory $GEN pytest tests/ -v`

**Important context:**
- This is a standalone Python package inside the tropek repo, NOT part of the main tropek API
- Uses `uv` as package manager — always `uv run --directory $GEN` for Python execution
- No `cd && command` chaining — use `uv run --directory` and `git -C` per CLAUDE.md
- All imports at the top of files (project rule)
- The generator lives in a worktree at `.worktrees/generator-refactor` on branch `feat/generator-refactor`
- Reference implementation: `docs/micrometer/micrometer_prometheus_sim.py` — the `MicrometerApp` class shows exactly how cumulative counters and histogram buckets should work

---

## Design Decisions (agreed with user)

### D1: TimescaleDB stores raw latency values
TimescaleDB's recommended pattern is "store raw events, compute percentiles at query time" using `percentile_cont(0.99) WITHIN GROUP (ORDER BY value)`. No pre-computed p99 stored — this is how real TimescaleDB deployments work. Each request becomes a row in a `request_latencies` table.

For a 4-hour timeline: 4h × 3600s × 6 combos × ~30 req/s = **2.6M latency rows**. TimescaleDB handles this trivially. For a 1-week timeline at 1s: ~108M rows — still fine for TimescaleDB, generation takes longer.

### D2: InfluxDB stores raw latency values (same as TimescaleDB)
InfluxDB also stores individual latency points and computes percentiles at query time using `percentile("latency_ms", 99)` in InfluxQL. This mirrors how TimescaleDB works — both compute exact percentiles from raw data, both should produce identical results. Only Prometheus approximates (due to histogram bucket interpolation).

For InfluxDB, latencies go into an `http_request_latency` measurement with fields `latency_ms` and tags `service`, `host`. Throughput/error/CPU/memory remain as separate measurements with per-second values.

| Backend | Latency storage | Query-time percentile function |
|---|---|---|
| Prometheus | histogram buckets (cumulative) | `histogram_quantile(0.99, rate(bucket[5m]))` — approximate |
| InfluxDB | individual latency points | `percentile("latency_ms", 99)` — exact |
| TimescaleDB | individual latency rows | `percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms)` — exact |

### D3: Prometheus mimics real Micrometer
The Prometheus shaper uses `MicrometerApp`-style accumulation from `micrometer_prometheus_sim.py`:
- Cumulative counter for `http_requests_total`
- Each individual latency is placed into histogram buckets (cumulative `le` semantics)
- `_sum` and `_count` track cumulative totals
- Scrape interval is configurable (default 15s)
- Bucket boundaries default to Micrometer's standard set (configurable globally)

### D4: Jitter on all metrics
Every sample gets configurable jitter:
- `jitter: 0` = deterministic (for tests, reproducibility)
- `jitter: 0.05` = ±5% random variation on each value
- Applied to: throughput, latency base, CPU, memory
- Jitter seed is deterministic (RNG seeded per service+host+timestamp)

### D5: Error model
Two-layer error model:
- **Base error rate**: ~1% random failures (independent probability per request)
- **Outage error rate**: 40-90% during outage events
- Errors are requests that fail — they count toward `http_errors_total` but do NOT generate latency samples (failed requests don't complete with a measured latency, they timeout or get rejected)

### D6: Histogram buckets — Micrometer defaults, global config
```python
MICROMETER_BUCKETS_MS = [
    1, 2, 3, 5, 7, 10, 15, 20, 25, 30, 40, 50,
    60, 70, 80, 90, 100, 150, 200, 250, 300, 400, 500,
    750, 1000, 1500, 2000, 5000
]
```
Converted to seconds for Prometheus. Configurable in generator config YAML. In real Micrometer, `publishPercentileHistogram()` uses these globally — per-timer customization exists but we don't need it.

### D7: Raw data format — Parquet
Parquet with snappy compression. Supports list columns (for latencies), compact (~20x smaller than CSV), and pandas reads it natively. `pyarrow` dependency.

Estimated sizes (4-hour timeline, 6 service×host combos):
- Raw samples: ~86K rows × ~2KB each (with latency list) ≈ **~170MB uncompressed, ~20MB Parquet**
- Individual latencies (for TimescaleDB): ~2.6M rows × ~50 bytes ≈ **~130MB uncompressed, ~15MB Parquet**

### D8: Pipeline parallelism
```
Phase 1: Generate raw data (parallel per service×host — 6 threads)
Phase 2: Transform for adapters (parallel per backend — 3 threads)
Phase 3: Write to adapters (parallel per backend — 3 threads)
Phases 2+3 merge: each backend thread transforms + writes in a streaming fashion
```

### D9: Two timeline tiers
- **Short (4h)**: Committed as Parquet raw data + adapter output files. Docker loads pre-generated data. Fast CI.
- **Long (7d/30d/60d)**: Generated on-the-fly, streamed 1h at a time. For full demo/testing.

---

## File Map

### New Files

| File | Purpose |
|---|---|
| `$SRC/raw.py` | `RawSample` dataclass, `RawChunk` (list of samples), latency distribution generator, jitter system |
| `$SRC/micrometer.py` | `MicrometerApp` class — cumulative counter + histogram bucket accumulation (ported from `micrometer_prometheus_sim.py`) |
| `$SRC/generator_config.py` | `GeneratorConfig` dataclass — bucket boundaries, scrape interval, jitter, error rates |
| `$BASE/generator_config.yaml` | Default generator configuration (buckets, scrape interval, jitter) |
| `$TESTS/test_raw_pipeline.py` | End-to-end pipeline test: 5 min of data → all 3 shapers → verify cross-backend consistency |
| `$TESTS/test_micrometer.py` | Unit tests for MicrometerApp accumulation (matches micrometer_prometheus_sim.py behavior) |
| `$TESTS/test_jitter.py` | Jitter system tests: deterministic with seed, distribution bounds |

### Modified Files

| File | Change |
|---|---|
| `$SRC/constants.py` | Replace `PROFILE_COLUMNS` with `RAW_COLUMNS`, add `MICROMETER_BUCKETS_SECONDS`, replace `DURATION_BUCKETS` |
| `$SRC/scenarios/base.py` | `_build_profiles()` → `_build_raw_samples()`, return `RawChunk` instead of profile DataFrame |
| `$SRC/scenarios/healthy.py` | Generate `request_count` + latency distribution instead of p50/p99 floats |
| `$SRC/scenarios/outage.py` | Generate raw samples with high error rate + latency spike |
| `$SRC/scenarios/degradation.py` | Generate raw samples with gradually worsening latency distribution |
| `$SRC/scenarios/memory_leak.py` | Generate raw samples with growing memory + latency |
| `$SRC/scenarios/traffic_spike.py` | Generate raw samples with burst request counts |
| `$SRC/scenarios/step_change.py` | Generate raw samples with shifted baseline |
| `$SRC/scenarios/polska.py` | Generate raw samples using polska contour |
| `$SRC/shapers/prometheus.py` | **Rewrite**: consume `RawChunk`, use `MicrometerApp` accumulation, emit OpenMetrics-ready DataFrame |
| `$SRC/shapers/influxdb.py` | Consume `RawChunk`, compute exact per-second percentiles from latency lists |
| `$SRC/shapers/timescaledb.py` | **Rewrite**: emit individual latency rows for `request_latencies` table + gauge/counter rows for `metrics` table |
| `$SRC/adapters/timescaledb.py` | Add `request_latencies` table DDL, handle two table types |
| `$SRC/pipeline.py` | Add parallel backend execution (ThreadPoolExecutor), stream raw chunks |
| `$SRC/composer.py` | Generate `RawChunk` instead of profile DataFrames |
| `$SRC/cli.py` | Add `--generator-config` CLI arg |
| `$GEN/pyproject.toml` | Add `pyarrow` dependency |
| `$BASE/grafana/dashboard_config.yaml` | Rewrite TimescaleDB SQL queries to use `percentile_cont()` on `request_latencies` table |
| `$BASE/grafana/templates/dashboard.json.j2` | No change expected (queries come from config) |
| `$BASE/docker-compose.yml` | Add init SQL for `request_latencies` table |
| `$TESTS/conftest.py` | Update fixtures for new raw data model |
| `$TESTS/test_scenarios.py` | Update for raw sample output |
| `$TESTS/test_shapers.py` | Update for raw chunk input |
| `$TESTS/test_adapters.py` | Update for new shaped data format |
| `$TESTS/test_pipeline.py` | Update for new pipeline |
| `$TESTS/test_composer.py` | Update for raw chunk output |

### Potentially New Files (pre-generation)

| File | Purpose |
|---|---|
| `$BASE/pregenerated/raw_4h.parquet` | Pre-generated 4-hour raw data (committed) |
| `$BASE/pregenerated/prometheus_4h.om` | Pre-generated OpenMetrics file (committed) |
| `$BASE/pregenerated/influxdb_4h.lp` | Pre-generated InfluxDB line protocol (committed) |
| `$BASE/pregenerated/timescaledb_metrics_4h.csv` | Pre-generated TimescaleDB metrics CSV (committed) |
| `$BASE/pregenerated/timescaledb_latencies_4h.csv` | Pre-generated TimescaleDB latencies CSV (committed) |
| `$BASE/scripts/pregenerate.sh` | Script to regenerate pre-generated files |

---

## Task Breakdown

### Phase 1: Raw Data Model + Jitter System

#### Task 1: RawSample dataclass and latency generator (`$SRC/raw.py`)
- [ ] Create `RawSample` dataclass:
  ```python
  @dataclass
  class RawSample:
      timestamp: datetime
      service: str
      host: str
      request_count: int          # successful requests this second
      error_count: int            # failed requests this second
      latencies_ms: list[float]   # len == request_count, individual latencies
      cpu_percent: float          # gauge, 0-100
      memory_bytes: float         # gauge
  ```
- [ ] Create `RawChunk = list[RawSample]` type alias
- [ ] Create `generate_latencies(count, base_ms, sigma, rng) -> list[float]` using lognormal distribution
  - `base_ms` = median latency (scenario-controlled)
  - `sigma` = distribution width (scenario-controlled, default 0.4)
  - Uses `rng.lognormal(mean=log(base_ms), sigma=sigma, size=count)`
- [ ] Create `apply_jitter(value, jitter_pct, rng) -> float` helper
  - Returns `value * (1 + rng.uniform(-jitter_pct, jitter_pct))`
  - `jitter_pct=0` returns value unchanged (deterministic)
- [ ] Create `generate_errors(request_count, base_error_rate, rng) -> int` helper
  - Returns `rng.binomial(request_count, base_error_rate)`
  - During outage scenarios, `base_error_rate` is elevated (0.4-0.9)

**Tests (in `$TESTS/test_raw_pipeline.py` or `$TESTS/test_jitter.py`):**
- [ ] `test_generate_latencies_count` — output length matches request_count
- [ ] `test_generate_latencies_deterministic` — same seed → same output
- [ ] `test_generate_latencies_distribution` — p50 ≈ base_ms (within 20%)
- [ ] `test_apply_jitter_zero` — jitter=0 returns exact value
- [ ] `test_apply_jitter_bounds` — output within [value*(1-pct), value*(1+pct)]
- [ ] `test_generate_errors_zero_rate` — error_rate=0 → 0 errors
- [ ] `test_generate_errors_high_rate` — error_rate=0.9 → ~90% errors

#### Task 2: Generator config (`$SRC/generator_config.py` + `$BASE/generator_config.yaml`)
- [ ] Create `GeneratorConfig` dataclass:
  ```python
  @dataclass
  class GeneratorConfig:
      histogram_buckets_ms: list[float]  # default: MICROMETER_BUCKETS_MS
      scrape_interval_s: int             # default: 15
      jitter_pct: float                  # default: 0.0 (deterministic)
      base_error_rate: float             # default: 0.01
      latency_sigma: float              # default: 0.4
      seed: int                          # default: 42
  ```
- [ ] `GeneratorConfig.from_yaml(path)` class method
- [ ] `GeneratorConfig.default()` class method
- [ ] Create `$BASE/generator_config.yaml`:
  ```yaml
  generator:
    scrape_interval: 15s
    jitter: 0.05           # ±5% for production-like data
    base_error_rate: 0.01  # 1% random failures
    latency_sigma: 0.4     # lognormal spread
    seed: 42
    histogram_buckets_ms:  # Micrometer defaults
      - 1
      - 2
      - 3
      # ... (full list)
  ```

**Tests:** Covered by existing config loading patterns, minimal new tests needed.

#### Task 3: Update constants.py
- [ ] Replace `PROFILE_COLUMNS` with `RAW_SAMPLE_FIELDS` (for documentation, not enforcement — RawSample is a dataclass)
- [ ] Replace `DURATION_BUCKETS` with `MICROMETER_BUCKETS_SECONDS` (converted from ms):
  ```python
  MICROMETER_BUCKETS_MS = [1, 2, 3, 5, 7, 10, 15, 20, 25, 30, 40, 50,
                           60, 70, 80, 90, 100, 150, 200, 250, 300, 400, 500,
                           750, 1000, 1500, 2000, 5000]
  MICROMETER_BUCKETS_SECONDS = [b / 1000 for b in MICROMETER_BUCKETS_MS]
  ```
- [ ] Keep `SERVICES`, `HOSTS`, `SERVICE_FACTORS`, `HOST_FACTORS`, `HEALTHY_DEFAULTS`
- [ ] Update `HEALTHY_DEFAULTS` to use `base_latency_ms` instead of `p50_latency`/`p99_latency`:
  ```python
  HEALTHY_DEFAULTS = {
      "throughput_rps": 100.0,
      "base_latency_ms": 20.0,    # median latency in ms
      "cpu_percent": 40.0,
      "memory_bytes": 512 * 1024 * 1024,
  }
  ```

---

### Phase 2: Scenario Refactor

#### Task 4: Refactor BaseScenario to produce RawChunk
- [ ] Change `_build_profiles()` → `_build_raw_samples()` returning `list[RawSample]`
- [ ] `_build_chunk()` now returns `list[RawSample]` instead of DataFrame
- [ ] `generate()` yields `list[RawSample]` chunks instead of DataFrames
- [ ] `generate_window()` returns `list[RawSample]`
- [ ] Add `config: GeneratorConfig` parameter to `__init__` (for jitter, error rate, latency sigma)
- [ ] Each second in the timestamp range produces one `RawSample` per service×host

**Key change:** Scenarios no longer produce DataFrames. They produce lists of `RawSample` objects. The shaper is responsible for converting to DataFrames.

#### Task 5: Refactor HealthyScenario
- [ ] `_build_raw_samples()` generates per-second raw samples:
  - `request_count = int(throughput_rps * jitter)` — jittered, rounded to int
  - `latencies_ms = generate_latencies(request_count, base_latency_ms, sigma, rng)`
  - `error_count = generate_errors(request_count, base_error_rate, rng)`
  - `cpu_percent = base_cpu * diurnal * jitter`
  - `memory_bytes = base_memory * jitter`
- [ ] Diurnal variation applied to `throughput_rps` and `base_latency_ms`
- [ ] Service/host scaling factors applied as before

#### Task 6: Refactor remaining scenarios (outage, degradation, memory_leak, traffic_spike, step_change, polska)
- [ ] Each scenario's `_build_raw_samples()` produces `RawSample` objects
- [ ] Outage: `error_count` uses elevated error rate (0.4-0.9), latency spikes
- [ ] Degradation: `base_latency_ms` gradually increases
- [ ] Memory leak: `memory_bytes` grows, latency increases with memory pressure
- [ ] Traffic spike: `request_count` bursts up
- [ ] Step change: permanent baseline shift
- [ ] Polska: throughput follows contour shape

#### Task 7: Refactor TimelineComposer
- [ ] `generate()` yields `list[RawSample]` chunks instead of DataFrames
- [ ] `_splice_events()` operates on `list[RawSample]` — filter by timestamp, concatenate, sort
- [ ] Accept `GeneratorConfig` and pass to scenarios
- [ ] Config comes from `generator_config.yaml` or CLI override

---

### Phase 3: MicrometerApp + Prometheus Shaper Rewrite

#### Task 8: Port MicrometerApp (`$SRC/micrometer.py`)
- [ ] Port `MicrometerApp` class from `docs/micrometer/micrometer_prometheus_sim.py`
- [ ] Key methods:
  - `record_second(sample: RawSample)` — accumulates counters and histogram buckets from individual latencies
  - `scrape(timestamp) -> ScrapeSnapshot` — reads current cumulative state (no mutation)
- [ ] Configurable bucket boundaries (from `GeneratorConfig`)
- [ ] Bucket accumulation uses `bisect_left` — each latency increments all buckets where `le >= latency` (cumulative semantics)
- [ ] Separate accumulator per (service, host)

**Tests (`$TESTS/test_micrometer.py`):**
- [ ] `test_counter_accumulation` — feed 3 seconds of data, verify counter = total requests
- [ ] `test_histogram_buckets_cumulative` — verify bucket[i] <= bucket[i+1] (monotonic)
- [ ] `test_histogram_inf_bucket` — `+Inf` bucket == total count
- [ ] `test_sum_accumulation` — `_sum` = sum of all latencies
- [ ] `test_scrape_is_readonly` — calling scrape twice at same state gives identical results
- [ ] `test_bucket_placement` — known latency (e.g., 15ms) lands in correct bucket (le=20ms but not le=10ms)

#### Task 9: Rewrite PrometheusShaper
- [ ] Input: `list[RawSample]` (raw chunk)
- [ ] Maintains one `MicrometerApp` instance per (service, host)
- [ ] For each second of raw data: `app.record_second(sample)`
- [ ] At scrape intervals: `app.scrape(timestamp)` → emit OpenMetrics-ready DataFrame rows
  - `http_requests_total` (cumulative counter)
  - `http_errors_total` (cumulative counter)
  - `http_request_duration_seconds_bucket{le="..."}` (cumulative histogram)
  - `http_request_duration_seconds_sum` (cumulative)
  - `http_request_duration_seconds_count` (cumulative)
  - `cpu_usage_percent` (gauge — last value in scrape interval)
  - `memory_usage_bytes` (gauge — last value in scrape interval)
- [ ] Output DataFrame has same columns as current Prometheus adapter expects: `timestamp, metric, value, service, host, instance, job, le, status_code`
- [ ] Delete `_lognormal_bucket_fractions()` — no longer needed (real bucket counting replaces it)

**Tests (in `$TESTS/test_shapers.py`):**
- [ ] `test_prometheus_shaper_cumulative_counters` — counters only increase
- [ ] `test_prometheus_shaper_histogram_from_raw` — histogram buckets match MicrometerApp behavior
- [ ] `test_prometheus_shaper_scrape_interval` — output only at scrape boundaries

---

### Phase 4: InfluxDB + TimescaleDB Shaper Rewrites

#### Task 10: Rewrite InfluxDBShaper
- [ ] Input: `list[RawSample]` (raw chunk)
- [ ] Emit TWO types of rows (similar to TimescaleDB approach):
  1. **Counter/gauge measurements** (per-second, one point per sample):
     - `http_requests_total`: value = `request_count`
     - `http_errors_total`: value = `error_count`
     - `cpu_usage_percent`: gauge
     - `memory_usage_bytes`: gauge
  2. **Individual latency points** → `http_request_latency` measurement:
     - One point per latency value: tags=`service,host`, field=`latency_ms`
     - ~30 points per RawSample (one per successful request)
     - Grafana queries use `percentile("latency_ms", 99)` at query time
- [ ] No `numpy.percentile()` computation — InfluxDB computes percentiles from raw data
- [ ] If `latencies_ms` is empty (all requests errored), no latency points emitted
- [ ] Update InfluxDB adapter to handle the new `http_request_latency` measurement

**Tests:** Update existing `test_shapers.py` tests for new input format.

#### Task 10b: Update InfluxDB adapter for latency measurement
- [ ] `write_chunk()` handles `http_request_latency` measurement (potentially high cardinality — batch writes)
- [ ] Line protocol format: `http_request_latency,service=frontend,host=host1 latency_ms=23.45 1234567890000000000`

#### Task 11: Rewrite TimescaleDBShaper
- [ ] Input: `list[RawSample]` (raw chunk)
- [ ] Emit TWO types of DataFrames (adapter must handle both):
  1. **Gauge/counter rows** → `metrics` table (same schema as before):
     - `http_requests_total` (per-second count)
     - `http_errors_total` (per-second count)
     - `cpu_usage_percent` (gauge)
     - `memory_usage_bytes` (gauge)
  2. **Individual latency rows** → `request_latencies` table:
     - One row per latency value: `(timestamp, service, host, latency_ms)`
     - ~30 rows per RawSample (one per successful request)
- [ ] Use a `table` column in the output DataFrame to distinguish target table
- [ ] Percentiles are NOT pre-computed — TimescaleDB computes them at query time

**Tests:** New tests for two-table output format.

#### Task 12: Update TimescaleDB adapter
- [ ] Add `request_latencies` table DDL:
  ```sql
  CREATE TABLE IF NOT EXISTS request_latencies (
      timestamp TIMESTAMPTZ NOT NULL,
      service TEXT NOT NULL,
      host TEXT NOT NULL,
      latency_ms DOUBLE PRECISION NOT NULL
  );
  SELECT create_hypertable('request_latencies', 'timestamp', if_not_exists => TRUE);
  ```
- [ ] `write_chunk()` routes rows to correct table based on `table` column
- [ ] COPY protocol for both tables

---

### Phase 5: Pipeline + Parallelism

#### Task 13: Refactor pipeline.py for parallel execution
- [ ] Raw data generation: `ThreadPoolExecutor` with workers per service×host
  - Actually, raw generation is per-chunk (1 hour), and each chunk contains all service×host combos
  - Parallelism is better at the **backend level**: fan out each raw chunk to 3 backend threads
- [ ] New pipeline flow:
  ```python
  def run_pipeline(scenario, backends, config, ...):
      # Build shaper+adapter pairs (sequential)
      pairs = build_pairs(backends, ...)

      # Stream chunks through all backends in parallel
      with ThreadPoolExecutor(max_workers=len(pairs)) as pool:
          for raw_chunk in scenario.generate():
              futures = []
              for backend, shaper, adapter in pairs:
                  futures.append(pool.submit(process_chunk, shaper, adapter, raw_chunk))
              for f in futures:
                  f.result()  # propagate exceptions

      # Finalize all adapters
      for backend, shaper, adapter in pairs:
          adapter.close()
  ```
- [ ] Shapers receive `list[RawSample]` instead of DataFrames
- [ ] Each shaper is responsible for converting raw samples to its output format

**Tests:** Update `test_pipeline.py` for new flow.

#### Task 14: Update CLI and composer
- [ ] Add `--generator-config` option to CLI
- [ ] `TimelineComposer` accepts `GeneratorConfig`
- [ ] Pass config through to scenarios and shapers
- [ ] `run_pipeline()` accepts `GeneratorConfig`

---

### Phase 6: Grafana Dashboard Queries

#### Task 15: Rewrite TimescaleDB + InfluxDB dashboard queries
- [ ] Latency panels query `request_latencies` table with `percentile_cont()`:
  ```sql
  -- P99 Latency by Service
  SELECT time_bucket('5 minutes', timestamp) AS time,
         service,
         percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms) / 1000.0 AS p99_latency
  FROM request_latencies
  WHERE service = '$service'
    AND timestamp BETWEEN $__timeFrom() AND $__timeTo()
  GROUP BY 1, 2
  ORDER BY 1
  ```
- [ ] Throughput/error panels continue using `metrics` table (same queries as current, fixed aggregation already done)
- [ ] Average Latency stat panel:
  ```sql
  SELECT avg(latency_ms) / 1000.0 AS avg_latency
  FROM request_latencies
  WHERE timestamp BETWEEN $__timeFrom() AND $__timeTo()
  ```
- [ ] P50 panels:
  ```sql
  SELECT time_bucket('5 minutes', timestamp) AS time,
         service,
         host,
         percentile_cont(0.50) WITHIN GROUP (ORDER BY latency_ms) / 1000.0 AS p50_latency
  FROM request_latencies
  WHERE timestamp BETWEEN $__timeFrom() AND $__timeTo()
  GROUP BY 1, 2, 3
  ORDER BY 1, 2, 3
  ```
- [ ] Rewrite InfluxDB latency queries to use `http_request_latency` measurement:
  ```influxql
  -- P99 Latency by Service
  SELECT percentile("latency_ms", 99) / 1000.0 AS "p99_latency"
  FROM "http_request_latency"
  WHERE "service" = '$service' AND $timeFilter
  GROUP BY time(5m), "service" fill(null)

  -- P50 Latency by Service and Host
  SELECT percentile("latency_ms", 50) / 1000.0 AS "p50_latency"
  FROM "http_request_latency"
  WHERE $timeFilter
  GROUP BY time(5m), "service", "host" fill(null)

  -- Average Latency (stat panel)
  SELECT mean("latency_ms") / 1000.0 AS "avg_latency"
  FROM "http_request_latency"
  WHERE $timeFilter
  ```
- [ ] Throughput/error/CPU/memory InfluxDB queries unchanged (still use existing measurements)

#### Task 16: Update docker-compose for request_latencies table
- [ ] Add init SQL script for TimescaleDB that creates both tables
- [ ] Or rely on adapter's DDL (current approach) — adapter creates tables on first write

---

### Phase 7: Pre-generation + Caching

#### Task 17: Add Parquet save/load to pipeline
- [ ] Add `pyarrow` to `$GEN/pyproject.toml` dependencies
- [ ] `save_raw_parquet(chunks: list[list[RawSample]], path: Path)` — serialize raw data
  - Schema: timestamp (datetime64), service (string), host (string), request_count (int32), error_count (int32), latencies_ms (list<float64>), cpu_percent (float64), memory_bytes (float64)
- [ ] `load_raw_parquet(path: Path) -> Iterator[list[RawSample]]` — deserialize in chunks
- [ ] CLI: `--save-raw path.parquet` and `--load-raw path.parquet` options
  - `--save-raw`: generate + save + optionally continue to adapters
  - `--load-raw`: skip generation, load from Parquet, feed to adapters

#### Task 18: Create pre-generation script and short timeline
- [ ] Create `$BASE/timelines/quick-test-4h.yaml` — 4-hour timeline for pre-generation
- [ ] Create `$BASE/scripts/pregenerate.sh`:
  ```bash
  uv run --directory $GEN slo-generate timeline timelines/quick-test-4h.yaml \
    --backends prometheus,influxdb,timescaledb,csv \
    --save-raw pregenerated/raw_4h.parquet \
    --output pregenerated/
  ```
- [ ] Commit pre-generated files to repo
- [ ] Update `docker-compose.yml` to use pre-generated files when available (env var toggle)

---

### Phase 8: End-to-End Validation Tests

#### Task 19: Cross-backend consistency test (`$TESTS/test_raw_pipeline.py`)
- [ ] Generate 5 minutes of healthy data at 1s resolution with `jitter=0` (deterministic)
- [ ] Feed through all 3 shapers
- [ ] **Prometheus verification:**
  - Run `MicrometerApp` + `PrometheusServer` from `micrometer_prometheus_sim.py` on same raw data
  - Verify shaper output matches simulation output (counter values, bucket counts)
  - Compute `histogram_quantile(0.99)` from shaper output
  - Verify it's within ~10% of exact p99 from raw data
- [ ] **InfluxDB verification:**
  - Individual latency point count == total request_count from raw data
  - `percentile(latency_ms, 99)` on stored points == exact p99 from raw data (both exact, must match)
- [ ] **TimescaleDB verification:**
  - Individual latency rows count == total request_count from raw data
  - `percentile_cont(0.99)` on latency rows == exact p99 from raw data
- [ ] **Cross-backend comparison:**
  - Prometheus p99 ≈ InfluxDB p99 (within ~10% due to bucket interpolation)
  - InfluxDB p99 == TimescaleDB p99 (both exact, must match)
  - Throughput rate: all 3 backends show same total request count over the 5-min window

#### Task 20: Jitter behavior test
- [ ] `jitter=0`: two runs produce identical output
- [ ] `jitter=0.05`: values differ from jitter=0 but stay within ±5% bounds
- [ ] Different seeds produce different jitter patterns

---

## Execution Order

**Batch 1 (foundation, sequential):** Tasks 1, 2, 3
**Batch 2 (scenario refactor, parallel after batch 1):** Tasks 4, 5, 6, 7
**Batch 3 (shaper rewrites, parallel after batch 2):** Tasks 8+9 (Prometheus), 10+10b (InfluxDB), 11+12 (TimescaleDB)
**Batch 4 (pipeline + integration, sequential after batch 3):** Tasks 13, 14
**Batch 5 (dashboards + infra, parallel after batch 3):** Tasks 15, 16
**Batch 6 (pre-generation, after batch 4):** Tasks 17, 18
**Batch 7 (validation, after all):** Tasks 19, 20

---

## Risk Notes

1. **Memory usage for long timelines:** 108M latency values for 1-week timeline ≈ 2GB in memory. Streaming 1h chunks limits peak to ~15M values (~120MB). Acceptable.

2. **TimescaleDB insert performance:** 2.6M rows via COPY for 4h timeline should take <10s. 108M rows for 1-week takes ~5 min. Acceptable for generation (happens once).

3. **Parquet with list columns:** `pyarrow` handles `list<float64>` natively. Verify pandas read/write roundtrip preserves list column type.

4. **Prometheus adapter compatibility:** The OpenMetrics adapter (`$SRC/adapters/prometheus.py`) expects a specific DataFrame schema with `metric, value, service, host, instance, job, le, status_code` columns. The rewritten Prometheus shaper must output this exact schema. The adapter itself should not need changes.

5. **Backward compatibility of `generate()` API:** The composer and pipeline both call `scenario.generate()`. Changing the return type from `Iterator[DataFrame]` to `Iterator[list[RawSample]]` breaks all callers simultaneously. This is intentional — everything changes together in this refactor. No backward compatibility shim needed.

6. **InfluxDB individual latency points:** Storing one point per request in InfluxDB creates high write volume (~2.6M points for 4h). InfluxDB handles this fine — it's designed for high-cardinality time series. Line protocol batching (1000+ points per write) keeps HTTP overhead low. For 1-week timelines (~108M points), writes may take a few minutes.

7. **InfluxDB measurement schema change:** The new `http_request_latency` measurement replaces the old `http_request_duration_seconds_p50` and `_p99` measurements. InfluxDB adapter must be updated to write individual latency points instead of pre-computed percentiles. The InfluxDB dashboard queries change from reading stored p99 values to computing `percentile("latency_ms", 99)` at query time.
