# SLI Collection Service — Specification

## 1. Purpose

This document specifies the design of a metrics-backend-agnostic SLI (Service Level Indicator)
collection service. The service supports two distinct query modes that produce SLI values consumed
by an SLO (Service Level Objective) evaluation layer.

The two modes differ in **where aggregation responsibility sits** — in the service or in the user's
query expression — and consequently in how many SLOs a single configured metric can produce.

The specification covers two backend implementations: **Prometheus** (Section 3–7) and
**InfluxDB** (Section 8), including a cross-backend comparison (Section 9).

---

## 2. Core Concepts

### 2.1 SLI

A single numeric measurement of system behaviour over a defined time window. Examples:

- Mean CPU usage over a 24 h test run: `4.3 %`
- p99 resident memory over a 4 h soak: `312 MB`
- Total disk write bytes per second (max observed): `48 MB/s`

### 2.2 SLO

A threshold applied to one SLI with a pass/fail result. Each SLO is tied to exactly **one** SLI
value. Examples:

| SLI | Threshold | Result |
|-----|-----------|--------|
| `cpu.mean` | `< 10 %` | pass |
| `cpu.p99` | `< 25 %` | fail |
| `memory.max` | `< 512 MB` | pass |

### 2.3 Aggregation Window vs. Evaluation Window

| Term | Meaning |
|------|---------|
| **Aggregation interval** | Resolution of the time-series used for computing stats (`1m`, `5m`). Controls the `rate()` window and `query_range` step in Prometheus; `aggregateWindow` period in InfluxDB. |
| **Evaluation window** | The total time span over which the SLI is computed (e.g. `24h`, `4h`). |

---

## 3. Prometheus — Mode 1: Simple Query (Service-Side Aggregation)

### 3.1 Overview

The user provides a PromQL expression template and selects which aggregation methods the service
should compute. The service fetches a raw time-series via `query_range`, applies the chosen
statistics in-process, and emits **one SLI value per aggregation method**. Each SLI value is an
independent SLO candidate.

```
User config            Service pipeline               SLI output
─────────────          ─────────────────              ───────────
query template    ──►  fetch time-series         ──►  cpu.mean  = 4.3 %
eval window       ──►  flatten all series        ──►  cpu.p99   = 18.7 %
agg interval      ──►  compute selected stats    ──►  cpu.max   = 31.2 %
methods: [mean,        ────────────────────────       cpu.std   = 3.1 %
         p99,                                         (4 SLOs possible)
         max, std]
```

### 3.2 Input Contract

```yaml
# Example simple-mode SLI definition
sli:
 name: agent_cpu
 mode: simple

 query: 'sum(rate(app_process_cpu_time_seconds_total{instance=~"$instance", name=~"$process"}[$interval]))'

 instance: "10.0.0.1:9090"
 process: "agent.*"

 eval_window: "24h"          # total time range to evaluate
 agg_interval: "1m"          # rate() window AND query_range step — must match
 chunk_size: "4h"            # optional: split eval_window into parallel fetches

 methods:                    # user selects which stats to produce as SLIs
   - mean
   - p99
   - max
   - std
```

#### Constraints

- `agg_interval` must equal the `rate()` window in the query. Mismatched values produce correlated
 samples (overlapping windows) or gaps, both of which distort percentile calculations.
- `chunk_size` must be a multiple of `agg_interval`.
- `eval_window` must be ≥ `agg_interval`.

### 3.3 Query Template Placeholders

| Placeholder | Resolved to |
|-------------|-------------|
| `$instance` | `instance` field from config |
| `$process` | `process` field from config (regex) |
| `$group` | `group` field from config (regex) |
| `$interval` | `agg_interval` value |

The user is responsible for writing valid PromQL. The service substitutes placeholders only.

### 3.4 Fetch Pipeline

```
eval_window
│
├─ split into N chunks of chunk_size
│
├─ parallel fetch (ThreadPoolExecutor, configurable concurrency)
│   ├─ chunk 0: query_range(query, t0,   t0+4h, step=agg_interval)
│   ├─ chunk 1: query_range(query, t0+4h, t0+8h, step=agg_interval)
│   └─ ...
│
├─ concat DataFrames on time axis
│   └─ result: DataFrame[DatetimeIndex, series_columns...]
│
├─ flatten: df.dropna().values.flatten() → 1-D array
│
└─ compute stats → dict[method, float]
```

Chunk failures are isolated: a failed chunk is logged and excluded from aggregation. The remaining
chunks still produce valid SLI values with a reduced sample count recorded in metadata.

### 3.5 Available Aggregation Methods

| Method | Formula | Notes |
|--------|---------|-------|
| `min` | `array.min()` | Lowest observed value |
| `mean` | `array.mean()` | Arithmetic mean |
| `max` | `array.max()` | Peak observed value |
| `std` | `array.std(ddof=0)` | Population standard deviation |
| `sum` | `array.sum()` | Useful for counters expressed as rates |
| `median` | `percentile(50)` | Robust central tendency, ignores outliers |
| `p75` | `percentile(75)` | |
| `p90` | `percentile(90)` | |
| `p95` | `percentile(95)` | |
| `p99` | `percentile(99)` | Tail latency / resource spike detection |

All methods operate on the same fetched dataset. Adding or removing methods has zero impact on
Prometheus load.

### 3.6 SLO Mapping

Each method produces one named SLI that maps to one SLO:

```yaml
slos:
 - sli: agent_cpu.mean
   threshold: 10
   unit: percent
   comparator: lt

 - sli: agent_cpu.p99
   threshold: 25
   unit: percent
   comparator: lt

 - sli: agent_cpu.max
   threshold: 40
   unit: percent
   comparator: lt
```

### 3.7 SLO Model

Simple mode produces **window-aggregate SLOs**: the SLI is a single statistic computed over the
entire evaluation window. This answers: *"Over this test run, was the p99 CPU below threshold?"*

It does **not** answer: *"What percentage of individual minutes had CPU below threshold?"*
(that is a time-fraction SLO — see Raw mode).

### 3.8 Tradeoffs

| | Pro | Con |
|--|-----|-----|
| **Prometheus load** | One `query_range` fetch regardless of method count | Transfers full time-series (1,440 rows for 24 h @ 1 m) |
| **Flexibility** | Add methods without changing PromQL or re-querying | All methods share the same aggregation interval |
| **Accuracy** | High — computes over all raw samples | Percentiles are of the *rate* at each step, not of raw counter increments |
| **Data gaps** | NaN samples are dropped before stats — gaps reduce sample count, not silently inflate values | Sample count in output must be checked; a run with 40 % gaps is not comparable to a full run |
| **Debuggability** | PromQL query is simple; easy to replay in Grafana | Stats are opaque unless raw data is also exported |
| **SLO granularity** | One metric → N SLOs | All SLOs share the same eval window and agg interval |

---

## 4. Prometheus — Mode 2: Raw Query (User-Defined PromQL)

### 4.1 Overview

The user provides a complete PromQL expression that **already encodes the aggregation**. The service
executes it as an instant query at the end of the evaluation window and treats the returned scalar
as the SLI value. One query produces exactly one SLI and therefore one SLO.

```
User config              Service pipeline           SLI output
─────────────            ─────────────────          ───────────
full PromQL query   ──►  instant query at t_end ──►  cpu.p99 = 18.7 %
eval_window              (subquery range from           (1 SLO)
                         t_end - eval_window
                         to t_end)
```

### 4.2 Input Contract

```yaml
sli:
 name: agent_cpu_p99
 mode: raw

 query: >
   quantile_over_time(0.99,
     sum(rate(app_process_cpu_time_seconds_total{
       instance=~"10.0.0.1:9090",
       name=~"agent.*"
     }[1m]))[24h:1m]
   )

 # eval_window is informational only — it is encoded inside the query's subquery range.
 # The service executes the query as an instant query at t_end.
 eval_window: "24h"
```

#### Constraints

- The query must return a **scalar or single-element vector**. Multi-series results (without full
 label collapse) are rejected — the service cannot decide which series represents the SLI.
- The subquery range inside the PromQL (`[24h:1m]`) must be consistent with `eval_window`. The
 service does not validate this — it is the user's responsibility.
- `eval_window` in the config is used only for metadata and scheduling; it does not affect query
 execution.

### 4.3 Supported Query Patterns

#### Pattern A — Subquery aggregate (most common)

```promql
# Mean over 24h
avg_over_time(
 sum(rate(app_process_cpu_time_seconds_total{instance=~"10.0.0.1:9090"}[1m]))[24h:1m]
)

# p99 over 24h
quantile_over_time(0.99,
 sum(rate(app_process_cpu_time_seconds_total{instance=~"10.0.0.1:9090"}[1m]))[24h:1m]
)

# Max over 24h
max_over_time(
 sum(rate(app_process_cpu_time_seconds_total{instance=~"10.0.0.1:9090"}[1m]))[24h:1m]
)
```

The inner `[1m]` is the rate smoothing window. The outer `[24h:1m]` is the subquery range and
resolution. Both should match the intended aggregation interval.

#### Pattern B — Direct window rate (mean-only, no distribution)

```promql
# Single global average — cheaper but cannot produce p99
sum(rate(app_process_cpu_time_seconds_total{instance=~"10.0.0.1:9090"}[24h]))
```

Equivalent to `avg_over_time(...[24h:1m])` for well-behaved counters. Cannot produce percentiles.
Use only when a single global average is sufficient.

#### Pattern C — Time-fraction SLO (percent of windows meeting threshold)

```promql
# What fraction of 1-minute windows had CPU rate below 0.10 (10%)?
(
 count_over_time(
   (sum(rate(app_process_cpu_time_seconds_total{instance=~"10.0.0.1:9090"}[1m])) < 0.10)[24h:1m]
 ) or vector(0)
) / (24 * 60)
```

This is the only pattern that produces a **compliance ratio** (0–1). It enables SLOs of the form
*"CPU was below threshold for 99.5 % of the evaluation window"*. Not achievable in simple mode.

#### Pattern D — Ratio / error-rate SLO

```promql
# Ratio of failed operations to total (request-based SLO)
sum(rate(app_errors_total{instance=~"10.0.0.1:9090"}[24h]))
/
sum(rate(app_requests_total{instance=~"10.0.0.1:9090"}[24h]))
```

### 4.4 Fetch Pipeline

```
t_end = now() (or configured end time)
│
└─ instant query: GET /api/v1/query?query=<full_promql>&time=t_end
  │
  └─ parse scalar result → SLI value
```

No chunking, no DataFrame, no pandas. Single HTTP call.

### 4.5 SLO Mapping

One query → one SLI → one SLO:

```yaml
slos:
 - sli: agent_cpu_p99
   threshold: 25
   unit: percent
   comparator: lt
```

To have mean + p99 + max as separate SLOs, the user must define three separate `raw` SLI configs,
each with a different query. Each triggers an independent Prometheus instant query.

### 4.6 SLO Models Supported

| Pattern | SLO model | Question answered |
|---------|-----------|-------------------|
| A (subquery aggregate) | Window-aggregate | Was the p99 over the window below threshold? |
| B (direct rate) | Window-aggregate | Was the mean over the window below threshold? |
| C (time-fraction) | Time-fraction / error budget | What % of windows met the threshold? |
| D (ratio) | Request-based | What fraction of operations were errors? |

### 4.7 Tradeoffs

| | Pro | Con |
|--|-----|-----|
| **Prometheus load** | Single instant query, minimal data transfer — Prometheus computes everything | Subqueries `[24h:1m]` force Prometheus to evaluate inner expression 1,440 times server-side; higher RAM on Prometheus |
| **Flexibility** | Any PromQL pattern supported; time-fraction and ratio SLOs only available here | Each aggregation method requires a separate query and SLO config |
| **Accuracy** | Computation is identical to what Grafana/alerting rules would use | Subquery resolution must be chosen carefully; coarse resolution loses distribution detail |
| **Data gaps** | Behaviour depends on PromQL expression — user must handle explicitly | Gaps can silently affect result if not handled (e.g. `absent()` not guarded) |
| **Debuggability** | Query is self-contained and reproducible in Prometheus UI | Complex subqueries are hard to read and maintain |
| **SLO granularity** | Full control over what the single value represents | N stats = N queries = N round-trips to Prometheus |
| **Timeout risk** | `[24h:1m]` subqueries can hit Prometheus default 2 m query timeout on large metric sets | Mitigated by setting `--query.timeout=5m` server-side |

---

## 5. Prometheus — Side-by-Side Comparison

| Dimension | Simple Mode | Raw Mode |
|-----------|-------------|----------|
| **Who writes the aggregation** | Service | User (in PromQL) |
| **SLIs per metric config** | 1 per selected method (up to ~10) | Always 1 |
| **SLOs per metric config** | N (one per method) | 1 |
| **Prometheus round-trips** | 1 fetch (chunked, parallel) | 1 per SLI |
| **Data transferred** | Full time-series (1,440 rows × series count) | Single scalar |
| **Prometheus RAM** | Low (chunked queries) | Higher (subquery materialises full range) |
| **Percentiles (p99)** | Yes — computed in-process from raw samples | Yes — via `quantile_over_time` subquery |
| **Time-fraction SLO** | No | Yes — Pattern C |
| **Request-based SLO** | No | Yes — Pattern D |
| **Counter reset handling** | Prometheus handles in `rate()` before transfer | Prometheus handles in `rate()` inside subquery |
| **Data gap behaviour** | NaN dropped; sample count reduced | Depends on PromQL expression |
| **Config complexity** | Low — simple YAML, no PromQL knowledge for stats | High — user must understand subquery syntax |
| **Reusability** | One query config → many SLOs | Copy-paste per aggregation method |
| **Debuggability** | PromQL simple; stats opaque in output | PromQL complex; single value transparent |

---

## 6. Prometheus — Implementation Considerations

### 6.1 Aggregation Interval Alignment (Both Modes)

The `rate()` window and `query_range` step (simple mode) or subquery resolution (raw mode) must be
equal to avoid producing correlated samples that distort percentiles:

```
agg_interval = 1m
rate(metric[1m])        ← smoothing window = 1m
query_range step = 1m   ← sample every 1m      ← simple mode
subquery [24h:1m]       ← resolve every 1m      ← raw mode
```

If `rate[5m]` is used with `step=1m`, each sample overlaps with the previous by 4 minutes. The
resulting distribution has far fewer independent observations than it appears, inflating p99
confidence.

### 6.2 Chunk Size Selection (Simple Mode)

Recommended starting values:

| Eval window | Chunk size | Parallel fetches |
|-------------|------------|-----------------|
| 1 h | none (single fetch) | 1 |
| 4 h | 1 h | 4 |
| 8 h | 2 h | 4 |
| 24 h | 4 h | 6 |
| 48 h | 8 h | 6 |

Chunk size should be tuned to Prometheus query timeout. Default Prometheus timeout is 2 minutes;
each chunk should comfortably resolve within that budget.

### 6.3 Prometheus Timeout (Raw Mode)

Long subqueries must be protected server-side. Recommended configuration:

```
--query.timeout=5m
--query.max-concurrency=20
```

The service should also enforce a client-side timeout per query, defaulting to 4 minutes for raw
mode to allow Prometheus to produce a timeout error before the client gives up.

### 6.4 Multi-Series Results (Raw Mode)

If the PromQL returns a vector with multiple series (e.g. `sum by (name) (...)` without full
collapse), the service must reject the result with a descriptive error rather than silently picking
the first series. The user must add label aggregation to reduce to a scalar.

### 6.5 Sample Count Metadata (Simple Mode)

Every SLI output should carry metadata:

```json
{
 "sli": "agent_cpu.p99",
 "value": 18.7,
 "unit": "percent",
 "eval_window": "24h",
 "agg_interval": "1m",
 "expected_samples": 1440,
 "actual_samples": 1387,
 "missing_pct": 3.7,
 "chunks_failed": 0
}
```

An SLI with `missing_pct > 20` should be flagged as low-confidence and excluded from SLO pass/fail
by default (configurable threshold).

### 6.6 SLO Evaluation Model

Both modes produce point-in-time SLI values. The SLO layer compares each value against its
threshold at evaluation time:

```
slo_result = comparator(sli_value, threshold)
# e.g. 18.7 < 25 → pass
```

For time-fraction SLOs (raw mode Pattern C), the SLI value is already a ratio (0–1) and the
threshold is the acceptable compliance floor (e.g. `0.995` for 99.5 % compliance).

---

## 7. Prometheus — Decision Guide

**Use Simple Mode when:**

- You want multiple SLOs from a single metric (mean + p99 + max in one config)
- The PromQL query is straightforward (`rate()`, `sum by ()`)
- You want to add or change aggregation methods without touching PromQL
- You are new to the system and want guardrails
- You need comparable SLIs across different test runs with controlled resolution

**Use Raw Mode when:**

- You need a time-fraction SLO ("X% of minutes below threshold")
- You need a request-based / ratio SLO (error rate, success rate)
- You want Prometheus to own the full computation and minimise data transfer
- You have an existing PromQL expression (e.g. from Grafana) you want to use directly
- You need full control over how gaps, resets, and label aggregation are handled
- You are defining SLOs that must exactly match alerting rules already in Prometheus

**Use both for the same metric when:**

A simple mode config gives you mean + p99 + max as window-aggregate SLOs, while a raw mode config
with Pattern C gives you the compliance ratio SLO for the same metric. These are complementary and
answer different questions about the same underlying data.

---

## 8. InfluxDB Backend

### 8.1 Overview

InfluxDB supports the same two query modes (simple and raw) but differs from Prometheus in its
data model, query language, and how aggregation is expressed. The core statistical problems
(interval alignment, data gaps, percentile sample count) transfer directly; the mechanics do not.

This section covers InfluxDB 2.x with the **Flux** query language, which is the most capable
version for SLI collection. Version differences are noted in Section 8.7.

### 8.2 Data Model Differences

| Concept | Prometheus | InfluxDB |
|---------|-----------|---------|
| Storage unit | Time-series (metric name + label set) | Measurement + field + tag set |
| Typical value type | Cumulative counter or gauge (float64) | Usually gauge or pre-computed rate (any numeric) |
| Rate derivation | Required — `rate()` derives per-second rate from counter | Usually not needed — collectors send rates or gauges directly |
| Counter resets | Handled automatically by `rate()` | Not handled — if storing raw counters, application must detect resets manually |
| Scrape model | Pull (Prometheus scrapes targets) | Push (clients write to InfluxDB) |
| Gap cause | Scrape target unreachable | Client stopped sending data |

The most important practical difference: **InfluxDB setups typically store pre-computed rates or
gauge values** (e.g. `cpu_usage_percent = 4.3`). There is no `rate()` equivalent needed for the
common case, which eliminates the aggregation interval alignment problem for gauge metrics.

### 8.3 Mode 1 — Simple Query (Service-Side Aggregation)

#### Input Contract

```yaml
sli:
 name: agent_cpu
 mode: simple
 backend: influxdb

 bucket: "metrics"
 measurement: "app_process"
 field: "cpu_usage_percent"
 filters:
   host: "10.0.0.1"
   process: "agent"

 eval_window: "24h"
 agg_interval: "1m"       # aggregateWindow period
 chunk_size: "4h"         # optional parallel fetch split

 methods:
   - mean
   - p99
   - max
   - std
```

#### Fetch Pipeline

```flux
from(bucket: "metrics")
 |> range(start: -24h, stop: now())
 |> filter(fn: (r) =>
      r._measurement == "app_process" and
      r._field == "cpu_usage_percent" and
      r.host == "10.0.0.1" and
      r.process == "agent"
    )
 |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
// → returns time-series at 1m resolution
// → service receives as DataFrame, computes all stats in-process (same as Prometheus simple mode)
```

`createEmpty: false` drops windows with no data points, equivalent to NaN-drop in the Prometheus
pipeline. `createEmpty: true` would fill missing windows with nulls, inflating sample count.

#### Aggregation Interval Alignment

For **gauge metrics** (pre-computed rates, percentages) there is no `rate()` window to align.
The only alignment concern is that `aggregateWindow(every: Xm)` sets the resolution, and this
should match the expected SLI granularity.

For **cumulative counters** stored in InfluxDB (uncommon but possible):

```flux
|> derivative(unit: 1s, nonNegative: true)   // equivalent to rate(), no reset handling
|> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
```

`nonNegative: true` discards negative derivatives (counter resets) but does not adjust the
surrounding window as Prometheus `rate()` does. This is a known accuracy gap.

### 8.4 Mode 2 — Raw Query (User-Defined Flux)

#### Input Contract

```yaml
sli:
 name: agent_cpu_p99
 mode: raw
 backend: influxdb

 query: |
   from(bucket: "metrics")
     |> range(start: -24h, stop: now())
     |> filter(fn: (r) =>
          r._measurement == "app_process" and
          r._field == "cpu_usage_percent" and
          r.host == "10.0.0.1"
        )
     |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
     |> quantile(q: 0.99)

 eval_window: "24h"    # informational only — encoded in the query's range()
```

#### Supported Query Patterns

**Pattern A — Window aggregate with percentile (most common)**

```flux
from(bucket: "metrics")
 |> range(start: -24h)
 |> filter(fn: (r) => r._measurement == "app_process" and r._field == "cpu_usage_percent")
 |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
 |> quantile(q: 0.99)    // p99 of all 1m means → single scalar
```

```flux
// Mean
 |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
 |> mean()

// Max
 |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
 |> max()
```

**Pattern B — Direct window aggregate (mean-only, no distribution)**

```flux
from(bucket: "metrics")
 |> range(start: -24h)
 |> filter(...)
 |> mean()    // single mean over all raw points in the window — no intermediate resolution
```

Cheaper than Pattern A; equivalent to Prometheus `rate(metric[24h])` for the mean case. Cannot
produce percentiles.

**Pattern C — Time-fraction SLO**

```flux
total = 24.0 * 60.0   // expected 1-minute windows

from(bucket: "metrics")
 |> range(start: -24h)
 |> filter(...)
 |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
 |> map(fn: (r) => ({r with _value: if r._value < 10.0 then 1.0 else 0.0}))
 |> sum()
 |> map(fn: (r) => ({r with _value: r._value / total}))
// → compliance ratio 0–1
```

This is **more readable than the Prometheus equivalent** (Pattern C in Section 4.3), which requires
`count_over_time` with a threshold inside a subquery.

**Pattern D — Ratio SLO**

```flux
errors = from(bucket: "metrics")
 |> range(start: -24h)
 |> filter(fn: (r) => r._measurement == "app_requests" and r._field == "errors_total")
 |> sum()

total = from(bucket: "metrics")
 |> range(start: -24h)
 |> filter(fn: (r) => r._measurement == "app_requests" and r._field == "requests_total")
 |> sum()

join(tables: {errors: errors, total: total}, on: ["host"])
 |> map(fn: (r) => ({r with _value: r._value_errors / r._value_total}))
```

### 8.5 InfluxDB-Specific Implementation Considerations

#### Gap Semantics Differ From Prometheus

In Prometheus, a gap means the scrape target was unreachable. In InfluxDB, a gap means the client
stopped writing. The **cause** of the gap is not encoded in the data itself. For SLI confidence
metadata, the `missing_pct` field (Section 6.5) still applies but cannot distinguish between
"process crashed" and "network partition" without additional metadata.

#### `createEmpty` and Sample Count

`aggregateWindow(createEmpty: false)` is the correct default for SLI collection. Using
`createEmpty: true` fills missing windows with nulls. If nulls propagate into `quantile()` or
`mean()`, results are incorrect. Always use `createEmpty: false` and track actual vs. expected
sample counts in metadata.

#### Multi-Series Results (Raw Mode)

Flux pipelines that return multiple rows (one per tag combination) must be rejected by the service
for the same reason as Prometheus multi-series results. The query must end with a terminal
aggregation (`mean()`, `quantile()`, `sum()`, `max()`) that produces a single row. The service
should validate that the response contains exactly one row.

#### Cardinality

High-cardinality tag values (e.g. `trace_id`, `request_id`, `user_id`) cause series explosion in
InfluxDB just as in Prometheus. The series key in InfluxDB is `measurement + tag set`; every unique
combination creates a new series. SLI queries should filter to low-cardinality dimensions (host,
process name, service name) only.

### 8.6 InfluxDB Tradeoffs vs. Prometheus

| Problem | Prometheus | InfluxDB |
|---------|-----------|---------|
| **Counter rate derivation** | `rate()` — automatic reset handling | `derivative(nonNegative: true)` — resets discarded, not adjusted |
| **Aggregation interval alignment** | `rate[Xm]` must equal `step=Xm` (two knobs) | `aggregateWindow(every: Xm)` is one knob; gauge metrics have no alignment issue |
| **Subquery / multi-step aggregation** | Terse `[24h:1m]` syntax, easy to misconfigure | Explicit Flux pipeline — verbose but readable |
| **p99 in raw mode** | `quantile_over_time(0.99, ...[24h:1m])` | `aggregateWindow(...) \|> quantile(q: 0.99)` — cleaner |
| **Time-fraction SLO** | Complex `count_over_time` with inner threshold | Readable `map` + `sum` pipeline |
| **Data gaps** | NaN in pandas; `avg_over_time` skips | `createEmpty: false` drops missing windows |
| **Chunking for parallelism** | Needed for long `query_range` calls | Less necessary — TSM storage engine handles long ranges efficiently |
| **Query language stability** | PromQL stable since 2016 | Flux is deprecated in InfluxDB 3.x |
| **Version fragmentation** | None | Significant — 1.x / 2.x / 3.x are all different |
| **Counter reset accuracy** | High — `rate()` adjusts surrounding window | Low — `derivative(nonNegative: true)` only drops the reset point |
| **Gap cause observability** | Pull model: gap = target unreachable | Push model: gap = client stopped sending — root cause unknown from data alone |

### 8.7 InfluxDB Version Risk

| Version | Query language | Status | SLI suitability |
|---------|---------------|--------|-----------------|
| 1.x | InfluxQL (SQL-like) | Widely deployed | No native `PERCENTILE()` in continuous queries; p99 requires application-side computation only |
| 2.x | Flux | Active; deprecated in 3.x | Full support for both modes including percentiles |
| 3.x | SQL / InfluxQL v3 / Flight SQL | New; Apache Arrow underneath | Flux queries will not work; patterns must be rewritten |

**Recommendation:** If targeting InfluxDB, build the backend abstraction so the query language is
swappable per version. Do not couple SLI config directly to Flux syntax if there is any likelihood
of a 3.x migration.

---

## 9. Cross-Backend Comparison

| Dimension | Prometheus | InfluxDB 2.x (Flux) |
|-----------|-----------|---------------------|
| **Simple mode fetch** | `query_range` → DataFrame → pandas stats | Flux pipeline → `aggregateWindow` → DataFrame → pandas stats |
| **Raw mode fetch** | Instant query with PromQL subquery | Flux pipeline terminating in `quantile()` / `mean()` |
| **p99 raw mode** | `quantile_over_time(0.99, ...[24h:1m])` | `aggregateWindow(...) \|> quantile(q: 0.99)` |
| **Time-fraction SLO** | `count_over_time((expr < threshold)[24h:1m])` | `map(fn: ...) \|> sum() \|> map(fn: .../total)` |
| **Counter reset handling** | Automatic and accurate in `rate()` | `nonNegative: true` — drops reset, does not adjust window |
| **Interval alignment risk** | High — two separate knobs (`rate[]` and `step`) | Low for gauges; present for counters via `derivative` |
| **Data transfer (simple mode)** | Full time-series | Full time-series |
| **Data transfer (raw mode)** | Single scalar | Single scalar (if query terminates correctly) |
| **Backend RAM pressure** | Subqueries materialise full range on Prometheus | Long `range()` with `aggregateWindow` is efficient in TSM |
| **Chunking needed** | Yes for long eval windows | Less commonly needed |
| **Language readability** | Terse; subquery syntax is non-obvious | Verbose but stepwise pipeline is easier to audit |
| **Language stability** | High | Low — Flux deprecated in 3.x |
| **Cardinality risk** | Label combination explosion | Tag combination explosion — same root cause |

---

## 10. Universal Implementation Considerations

The following apply regardless of backend.

### 10.1 Sample Count Confidence

Every SLI output must include:

```json
{
 "sli": "agent_cpu.p99",
 "value": 18.7,
 "unit": "percent",
 "backend": "prometheus",
 "eval_window": "24h",
 "agg_interval": "1m",
 "expected_samples": 1440,
 "actual_samples": 1387,
 "missing_pct": 3.7,
 "chunks_failed": 0
}
```

An SLI with `missing_pct > 20` should be flagged as low-confidence and excluded from SLO pass/fail
by default (configurable threshold). A run with significant gaps is not comparable to a full run
and should not be used to set baselines.

### 10.2 SLO Evaluation Model

Both modes and both backends produce point-in-time SLI values. The SLO layer compares each value
against its threshold:

```
slo_result = comparator(sli_value, threshold)
# e.g. 18.7 < 25 → pass
```

For time-fraction SLOs, the SLI value is a ratio (0–1) and the threshold is the compliance floor
(e.g. `0.995` for 99.5 % compliance).

### 10.3 Aggregation Interval Alignment Summary

| Backend | Simple mode | Raw mode |
|---------|------------|---------|
| Prometheus (counter) | `rate[Xm]` window must equal `step=Xm` in `query_range` | Inner `rate[Xm]` must equal subquery resolution `[eval:Xm]` |
| Prometheus (gauge) | `step=Xm` only | Subquery resolution `[eval:Xm]` only |
| InfluxDB (gauge) | `aggregateWindow(every: Xm)` only | `aggregateWindow(every: Xm)` before terminal aggregation |
| InfluxDB (counter) | `derivative` unit + `aggregateWindow(every: Xm)` | Same, inside query pipeline |

Misalignment always produces one of: overlapping windows (correlated samples, inflated p99
confidence), gaps (reduced effective sample count), or silent double-smoothing.

### 10.4 Backend Abstraction Recommendation

If both Prometheus and InfluxDB backends are required, the service layer should expose a
backend-agnostic interface:

```
fetch_simple(query_config) → DataFrame
fetch_raw(query_config)    → float
```

Each backend implements this interface. SLI configs are backend-specific (different query
languages), but the aggregation logic (Section 3.5), SLO evaluation (Section 10.2), and metadata
(Section 10.1) are shared across backends.
