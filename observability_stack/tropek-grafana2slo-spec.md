# Tropek & grafana2slo — Project Specification

> **Status:** Brainstorming / Early Implementation
> **Date:** 2026-03-20
> **Author:** Dominik
> **Language:** Python

---

## Table of Contents

1. [Background & Motivation](#1-background--motivation)
2. [Project Overview](#2-project-overview)
3. [Tropek — Quality Gate Engine](#3-tropek--quality-gate-engine)
4. [grafana2slo — SLO Extraction Tool](#4-grafana2slo--slo-extraction-tool)
5. [SLI / SLO Data Model](#5-sli--slo-data-model)
6. [PromQL Query Classification](#6-promql-query-classification)
7. [Extraction Pipeline](#7-extraction-pipeline)
8. [Validation — The Single-Value Contract](#8-validation--the-single-value-contract)
9. [Output Format](#9-output-format)
10. [Integration Test Environment](#10-integration-test-environment)
11. [Open Questions & Research Items](#11-open-questions--research-items)
12. [Phased Implementation Plan](#12-phased-implementation-plan)
13. [Non-Goals](#13-non-goals)

---

## 1. Background & Motivation

### The Keptn v1 Problem

Keptn v1 provided a quality gate mechanism called **Lighthouse**. Its role was to prevent deployment of faulty software by:

- Running a load test or monitoring a deployment window
- Collecting performance metrics automatically
- Comparing current results against a historical baseline (last 14–30 days)
- Issuing a PASS or FAIL decision to the CI/CD pipeline

Keptn v1 was decommissioned in 2023. **Keptn v2 exists but dropped the historical baseline comparison and the UI**, making it useless for automated quality gate decisions without significant custom work.

Nothing in the current open-source ecosystem fills this gap.

### The Use Case

The primary use case is **load test assessment in CI/CD**:

1. A load test runs against a target environment where a performance agent is installed
2. Prometheus collects metrics during the test window
3. After the test, a quality gate evaluates whether metrics are acceptable
4. The gate compares the current test's aggregated values against baseline values from the previous N days
5. CI/CD pipeline receives PASS or FAIL

This is distinct from production SLO monitoring. There are no burn rates, no alerting windows, no error budgets. Every SLI is a **single scalar** — one number per metric per test run.

### Why Build This

| Tool | Gap |
|---|---|
| Keptn v1 | Decommissioned |
| Keptn v2 | No historical baseline, no UI |
| Sloth / pyrra | Generate Prometheus rules, not quality gates |
| Grafana Cloud SLOs | Vendor lock-in, no bulk import |
| slo-generator (Google) | No Grafana ingestion, no baseline comparison |

---

## 2. Project Overview

Two components, one goal:

```
┌─────────────────────────────────────────────────────────────┐
│                        CI/CD Pipeline                        │
│                                                              │
│  Load test runs → Prometheus collects metrics                │
│                          │                                   │
│                     [tropek eval]                            │
│                          │                                   │
│              Compare against 30-day baseline                 │
│                          │                                   │
│                    PASS / FAIL                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    Onboarding (one-time)                     │
│                                                              │
│  Grafana dashboard JSON                                      │
│          │                                                   │
│    [grafana2slo]                                             │
│          │                                                   │
│   tropek SLO YAML  ←── ready to use, ~80% accuracy          │
└─────────────────────────────────────────────────────────────┘
```

**Tropek** is the quality gate engine — it stores test results, maintains baselines, evaluates SLOs, and exposes a UI and API.

**grafana2slo** is the onboarding accelerator — it converts existing Grafana dashboards into tropek SLO YAML automatically, eliminating the manual work of writing hundreds of SLO definitions.

---

## 3. Tropek — Quality Gate Engine

### Core Concept

Tropek is a Python-based rebuild of Keptn v1 Lighthouse. It evaluates whether a software version is acceptable by comparing aggregated metric values from the current test run against a historical baseline.

### Baseline Algorithm

Uses the same algorithm as Keptn v1: **mean ± N standard deviations** over a configurable lookback window (default: 30 days).

```
baseline_mean  = mean(metric_values, last_N_days)
baseline_stddev = stddev(metric_values, last_N_days)

pass_threshold = baseline_mean + (N * baseline_stddev)   # for metrics where lower is better
```

This is a pre-existing design. It is not being redesigned as part of this work.

### Keptn v1 vs Tropek Feature Comparison

| Capability | Keptn v1 | Keptn v2 | Tropek |
|---|---|---|---|
| SLI / SLO YAML definitions | ✅ | ✅ | ✅ |
| Prometheus evaluation | ✅ | ✅ | ✅ |
| Historical baseline comparison | ✅ | ❌ | ✅ |
| Quality gate pass / fail | ✅ | manual only | ✅ |
| UI / dashboard | ✅ | ❌ | 🔧 in progress |
| Meta tags / grouping | ❌ | ❌ | ✅ added |
| Actively maintained | ❌ decommissioned 2023 | ✅ | ✅ |

### What Was Added Beyond Keptn v1

- **Meta tags** — parameterise a single SLI query across multiple instances (hosts, services, environments) without duplicating the query definition
- **Grouping** — express SLO scope in YAML using label selectors that get injected into the SLI query at evaluation time

---

## 4. grafana2slo — SLO Extraction Tool

### Problem It Solves

New users of tropek need to define SLOs before the quality gate can work. Writing SLO YAML by hand for a large dashboard (50–400 panels) is impractical. Most teams already have Grafana dashboards observing the same metrics they want to gate on.

grafana2slo reads those dashboards and generates a first-pass SLO YAML file automatically.

### Design Philosophy

- **Input:** Grafana dashboard JSON (file or Grafana API)
- **Output:** tropek SLO YAML + extraction report
- **Target accuracy:** 80% — not perfect extraction, but transparent extraction with evidence
- **Validation:** every extracted query is executed against Prometheus; only queries that return a single scalar are marked OK
- **Non-destructive:** always emits something, even for failed extractions — with YAML comments explaining what went wrong

### 80% Rule

The tool targets 80% of real-world dashboard panels. Load test dashboards use straightforward PromQL — `sum`, `rate`, `histogram_quantile`, `avg`. Edge cases (nested subqueries, multi-level aggregations, `label_replace`) are flagged as `MANUAL_REQUIRED` rather than guessed at.

---

## 5. SLI / SLO Data Model

### SLI — Service Level Indicator

A single query that produces a **single scalar value** when executed against Prometheus. The value represents an aggregated measurement over the test window (e.g. P99 latency over the entire 30-minute load test).

```yaml
sli:
  query: 'histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket{service="frontend"}[30m])))'
```

### SLO — Service Level Objective

A named objective with a target value, linked to an SLI query, with optional meta tags for parameterisation.

```yaml
- name: p99-latency-frontend
  description: "P99 request latency for frontend service"
  metadata:
    service: frontend           # meta tag — injected into SLI query at eval time
  sli:
    query: 'histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket{service="{{ .service }}"}[{{ .window }}])))'
  objective:
    value: 0.500                # 500ms
    comparison: lte             # current value must be ≤ target
  window: 30m                   # test duration / evaluation window
```

### Meta Tags

Meta tags parameterise a single SLI query across multiple instances. Instead of N identical SLOs with different label values hardcoded, you have one SLO with a template and N metadata entries.

```yaml
# One SLI definition
sli:
  query: 'sum(rate(http_errors_total{service="{{ .service }}"}[{{ .window }}]))'

# Multiple SLOs sharing it
- name: errors-frontend
  metadata: { service: frontend }

- name: errors-api
  metadata: { service: api }

- name: errors-backend
  metadata: { service: backend }
```

---

## 6. PromQL Query Classification

Every panel query is classified into one of four types before transformation is attempted.

### Type C — Simple Scalar (no grouping, no variables)

```promql
sum(rate(http_requests_total[5m]))
avg(cpu_usage_percent)
histogram_quantile(0.99, sum by (le) (rate(duration_bucket[5m])))
```

Already returns a scalar or can be made scalar with window substitution only. No label expansion needed. Easiest case — pass through.

### Type A — Grafana Template Variable

```promql
sum(rate(http_requests_total{service="$service"}[5m]))
avg(cpu_usage_percent{host="$host"})
```

Contains `$variable` syntax. Variables that are not Grafana built-ins become meta tag keys. Substitution: `$service` → `{{ .service }}`. One SLO is emitted per discovered label value.

### Type B — Aggregation Grouping (no variable)

```promql
sum by (service) (rate(http_requests_total[5m]))
histogram_quantile(0.99, sum by (service, le) (rate(duration_bucket[5m])))
```

Returns a vector per label value — violates the single-value contract. Requires stripping the `by (label)` clause and injecting a label selector. Harder than Type A; attempted transformation followed by Prometheus validation.

### COMPLEX — MANUAL_REQUIRED

Signals that automatic transformation should not be attempted:

- Subquery syntax: `[30m:1m]`
- Multiple nested `by()` clauses at different aggregation levels
- `label_replace` or `label_join`
- Cross-metric arithmetic between separately grouped vectors

### Grafana Built-in Variables to Strip

These are Grafana internals, not Prometheus labels. They must be removed or substituted before query execution:

```
$__interval        $__rate_interval     $__range
$__from            $__to                $__dashboard
$__user            $__org               $timeFilter
$__timeTo          $__timeFrom
```

`$__interval` and `$__rate_interval` are replaced with the configured `default_window`. All others are removed.

### Known Valid SLI Patterns

The set of meaningful SLI query shapes is finite:

| Pattern | SLI Type |
|---|---|
| `sum(rate(errors[w])) / sum(rate(total[w]))` | Availability ratio |
| `histogram_quantile(0.99, sum by (le) (rate(bucket[w])))` | Latency p99 |
| `sum(rate(duration_sum[w])) / sum(rate(duration_count[w]))` | Latency average |
| `min(metric)` / `max(metric)` / `avg(metric)` | Gauge (resource utilisation) |
| `avg_over_time(metric[w])` | Time-averaged gauge |
| `max_over_time(metric[w])` | Peak gauge |
| `sum(rate(requests[w]))` | Throughput |

---

## 7. Extraction Pipeline

```
Input: dashboard JSON + Prometheus URL + config

For each panel:
  │
  ├── 1. Extract
  │       title, description, query/queries, thresholds, panel type
  │
  ├── 2. Classify variables
  │       strip Grafana built-ins
  │       replace $__interval → default_window
  │       remaining $vars → candidate meta tag keys
  │
  ├── 3. Classify query type
  │       Type A / B / C / COMPLEX
  │       COMPLEX → skip, emit MANUAL_REQUIRED immediately
  │
  ├── 4. Transform
  │       Type A: $var → {{ .var }} template substitution
  │       Type B: strip by(label), inject label selector
  │       Type C: window substitution only
  │
  ├── 5. Label discovery (Type A and B only)
  │       Execute: count by (label) (metric[lookback_window])
  │       Collect distinct label values
  │       If count ≤ expand_threshold: emit one SLO per value
  │       If count > expand_threshold: emit one templated SLO
  │
  ├── 6. Validate (Prometheus execution)
  │       Execute transformed query as instant query
  │       Check: exactly 1 result, 0 labels
  │       Assign: OK / WARN / FAILED
  │
  └── 7. Emit YAML block + update report
```

### Window Handling Priority

1. Explicit window already in query (`[30m]`) → extract and preserve
2. Grafana built-in time variable (`$__rate_interval`, `$interval`) → substitute with `default_window`
3. No window (gauge metric) → leave as-is

---

## 8. Validation — The Single-Value Contract

Every valid SLI query must return **exactly one result with zero labels** when executed as an instant query against Prometheus.

```python
result = prometheus.query(transformed_query, time=now())

if result.status != "success":    → FAILED  (reason: query_error)
if len(result.data) == 0:         → WARN    (reason: no_data)
if len(result.data) > 1:          → FAILED  (reason: multiple_series)
if result.data[0].labels != {}:   → FAILED  (reason: has_labels)
else:                             → OK
```

### Status Meanings

| Status | Meaning | Action |
|---|---|---|
| `OK` | Query returns exactly one scalar | Include in output as-is |
| `WARN` | Query returned no data | Include with warning — zero errors today is valid |
| `FAILED` | Query returned multiple series or errored | Include with TODO, flag in report |
| `MANUAL_REQUIRED` | Query too complex to transform | Include original query as comment only |

The `WARN / no_data` case is genuinely ambiguous in a load test context: a service with zero errors during the test is correct behaviour. The report calls these out explicitly for human review.

---

## 9. Output Format

### YAML File

Every panel produces at least one YAML block, regardless of extraction status. Failures include the original query as a comment so the user has starting material.

```yaml
# ── EXTRACTION STATUS: OK ─────────────────────────────────────────────────
- name: p99-latency-frontend
  description: "P99 request latency — frontend service"
  metadata:
    service: frontend
  sli:
    query: 'histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket{service="frontend"}[30m])))'
  objective:
    value: 0.500
    comparison: lte
  source:
    panel_title: "P99 Latency by Service"
    panel_id: 6
    original_query: 'histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket{service="$service"}[$__rate_interval])))'
    transformation: variable_substitution

# ── EXTRACTION STATUS: MANUAL_REQUIRED ────────────────────────────────────
# Reason: nested subquery syntax [30m:1m] — complexity too high
# Original: max_over_time(sum by (service) (rate(http_errors_total[5m]))[30m:1m])
- name: complex-panel-TODO
  sli:
    query: null
  source:
    panel_title: "Complex Subquery"
    panel_id: 17
```

### Extraction Report

```
Dashboard: "Production Load Test"
Processed: 18 panels → 24 SLOs (some panels expand to multiple)
────────────────────────────────────────────
✅ OK                  17  (71%)
⚠️  WARN (no data)      3  (12%)
❌ FAILED               3  (12%)
🔧 MANUAL REQUIRED      1   (4%)

FAILED:
  • "Errors Grouped by Host"     — returned 4 series after transformation
  • "Request Rate"               — query error: unknown metric http_req_totl
  • "DB Connections"             — has labels: {instance="..."} after transform

WARN — no data (verify manually):
  • "DB Errors"                  — zero errors in lookback window
  • "Timeout Rate"               — same
  • "Retry Count"                — same

MANUAL REQUIRED:
  • "Complex Subquery"           — nested subquery [30m:1m]

DENOMINATOR MISSING (availability SLOs needing total query):
  • "Error Rate by Service"
  • "5xx Rate"
```

### CLI Interface

```bash
grafana2slo \
  --dashboard ./dashboard.json \
  --prometheus http://localhost:9090 \
  --window 30m \
  --lookback 24h \
  --expand-threshold 20 \
  --output ./slos.yaml \
  --report ./report.md \
  --interactive
```

| Flag | Default | Description |
|---|---|---|
| `--dashboard` | required | Path to JSON file or `uid:abc123` for API fetch |
| `--grafana-url` | — | Grafana base URL (required if using uid) |
| `--prometheus` | required | Prometheus base URL for validation |
| `--window` | `30m` | Default SLI aggregation window |
| `--lookback` | `24h` | Lookback window for label discovery |
| `--expand-threshold` | `20` | Max label values before switching to template mode |
| `--output` | `slos.yaml` | Output YAML path |
| `--report` | stdout | Extraction report path |
| `--interactive` | false | Pause on WARN / ambiguous for human confirmation |

---

## 10. Integration Test Environment

A Docker Compose stack providing a pre-loaded Prometheus + Grafana + InfluxDB environment for testing grafana2slo against realistic data.

### Stack

```
influxdb    ← starts first (healthcheck gate)
generator   ← Python container, runs once and exits
               writes OpenMetrics → promtool TSDB backfill → prometheus volume
               writes same data to InfluxDB
prometheus  ← starts after generator exits, picks up pre-filled TSDB blocks
grafana     ← starts after prometheus, auto-provisions datasources + dashboard
```

### Service URLs

| Service | URL | Credentials |
|---|---|---|
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | — |
| InfluxDB | http://localhost:8086 | admin / adminpassword |

### Synthetic Scenarios

Three distinct data scenarios are generated, each covering a different test condition:

**Scenario 1 — Healthy (baseline)**
Everything is normal. Mild diurnal variation (±15% throughput over 24h). Represents 30-day baseline data that the quality gate compares against.

- Throughput: ~100 rps, error rate: ~0.1%, P99: ~80ms, CPU: ~40%

**Scenario 2 — Outage**
Sudden failure with configurable duration (default: 30 min). Ramps in over 2 minutes, followed by a 10-minute recovery.

- Throughput drops 90%, error rate spikes to ~80%, P99 spikes to ~10s, CPU spikes to ~90%
- Expected quality gate result: **FAIL**

**Scenario 3 — Degradation (bad deployment)**
Throughput stays the same — application still accepts all requests. Latency and error rate increase due to a regression in the deployed code.

- Throughput: unchanged, P99 grows 5× (80ms → 400ms), error rate grows 5× (0.1% → 0.5%), CPU +35%
- Expected quality gate result: **FAIL**
- This is the most important scenario — it tests that the gate catches subtle regressions, not just outages

### Metrics Generated

All metrics carry labels `service` ∈ {frontend, api, backend} and `host` ∈ {host1, host2}.

| Metric | Type |
|---|---|
| `http_requests_total` | counter |
| `http_errors_total` | counter |
| `http_request_duration_seconds_{bucket,sum,count}` | histogram |
| `cpu_usage_percent` | gauge |
| `memory_usage_bytes` | gauge |

### Dashboard Panel Coverage

The pre-provisioned Grafana dashboard contains 18 panels deliberately designed to test every query type the parser must handle:

| Type | Count | Purpose |
|---|---|---|
| Type C — simple scalar | 6 | Trivially parseable — should all be OK |
| Type A — template variable | 6 | Core use case — variable → meta tag |
| Type B — aggregation grouping | 3 | Requires label discovery + transformation |
| Multi-target edge case | 1 | Tests denominator detection |
| COMPLEX / MANUAL_REQUIRED | 2 | Must be rejected cleanly, not guessed |

### Dashboard Source

The dashboard is defined in `grafana/dashboard_config.yaml` (YAML) and rendered to Grafana JSON via a Jinja2 template. The JSON is never edited directly — always regenerate from the YAML config.

```bash
python grafana/generate_dashboard.py
# or
make dashboard
```

### InfluxDB Version Note

InfluxDB 2.7 is used deliberately, not by accident. InfluxDB 3 Core has a 72-hour maximum query window which is incompatible with the 7-day data window this environment generates. InfluxDB 2.7 is not EOL. The datasource is configured for **InfluxQL** (not Flux) using the v2 InfluxQL compatibility endpoint with basic auth where the password is the API token.

---

## 11. Open Questions & Research Items

Items that need investigation before implementation can proceed.

### Critical

- **PromQL parser for Python** — `py-promql-parser` on PyPI has minimal AST support. Is it sufficient for Type B transformation (stripping `by()` and injecting label selectors)? If not, is a thin Go subprocess wrapper feasible? This is the highest technical risk item.

- **Tropek YAML schema** — confirm the exact field names, whether templated metadata (`{{ .service }}`) is supported today, and the `comparison` operator options (`lte`, `gte`, `between`).

### Important

- **Denominator strategy for availability SLOs** — panels showing error rate rarely include the total query. Options: (a) always emit TODO placeholder, (b) heuristic matching `_errors_total` → `_requests_total`, (c) user-supplied denominator template. Decision needed before YAML emitter is built.

- **Multi-target panels** — when a panel has two queries, take the first only? Attempt to detect error/total pair? Emit both as separate SLOs? Define behaviour explicitly.

- **Panel type semantics** — does `stat` vs `gauge` vs `timeseries` affect SLI interpretation, or is it purely cosmetic for this tool?

### Nice to Have

- **Integration point** — standalone CLI first, then `tropek init --from-grafana` command? Or build inside tropek from day one?

- **Grafana API auth** — how should API tokens be passed for non-public Grafana instances?

- **InfluxQL panels** — the integration test environment currently uses Prometheus-only panels. Should InfluxQL-sourced panels be supported by grafana2slo, and if so, how does query translation work?

---

## 12. Phased Implementation Plan

### Phase 1 — Core (targets 80%)

- Grafana JSON file parsing (no API yet)
- Type A query handling — variable substitution → meta tag
- Type C query handling — pass-through + window substitution
- Built-in variable stripping
- Prometheus instant query validation (single-value contract)
- YAML emission with status annotations
- Extraction report (stdout)
- CLI with basic flags (`--dashboard`, `--prometheus`, `--window`, `--output`)

### Phase 2 — Coverage Expansion

- Grafana HTTP API ingestion (`/api/dashboards/uid/:uid`)
- Type B handling — `by()` clause → label selector injection
- Label discovery via Prometheus for meta tag expansion
- Denominator heuristics for common availability patterns
- Interactive confirmation mode (`--interactive`)
- `--report` flag writing markdown

### Phase 3 — Tropek Integration

- `tropek init --from-grafana` command
- Schema alignment with live tropek YAML format
- Integration tests using the Docker Compose test environment
- Round-trip test: generate SLOs → run evaluation → verify pass/fail against known scenarios

---

## 13. Non-Goals

These are explicitly out of scope and will not be addressed:

- **Production monitoring SLOs** — load test context only for v1; production is a future consideration
- **Alerting rule generation** — that is Sloth/pyrra territory; tropek is a point-in-time evaluator, not an alert system
- **Non-Prometheus backends in grafana2slo v1** — InfluxDB, Datadog, etc. may be added later
- **Perfect extraction** — 80% is the explicit success criterion; the report exists precisely because extraction will not be perfect
- **UI for grafana2slo** — CLI only
- **Real-time / continuous evaluation** — tropek evaluates on demand (triggered by CI/CD), not continuously
