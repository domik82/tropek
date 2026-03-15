# Quality Platform — Design Specification

**Date:** 2026-03-12
**Status:** Draft
**Scope:** Standalone quality gate and performance test evaluation platform extracted from Keptn

---

## 1. Background and Motivation

Keptn's quality gate (lighthouse-service + SLI/SLO evaluation) was a well-designed approach to automated performance evaluation but required ~12 Kubernetes microservices to operate. This project extracts that evaluation capability into a standalone platform that:

- Runs in Docker Compose — no Kubernetes required
- Supports VM-based performance testing, microservice load testing, HTTP testing, and any metric source that can produce scalar values
- Scales from a single engineer running local tests to a CI/CD pipeline evaluating across 400 metrics, multiple OS environments, and multi-VM test harnesses
- Retains Keptn's core SLI/SLO model (proven in production) while replacing the infrastructure coupling

The immediate use case: a software product tested across Windows 7/8/10/11, Windows Server, Ubuntu, CentOS in 32-bit and 64-bit variants, across multiple branches (7.4, 7.6, etc.), with test cases including compilation, file I/O, and network saturation — each producing ~400 Prometheus metrics per environment, with some non-Prometheus metrics (e.g. raw compilation duration) pushed directly.

---

## 2. Goals and Non-Goals

### Goals
- Evaluate SLI values against SLO criteria using Keptn's proven scoring algorithm
- Support pull-mode (Prometheus/InfluxDB), push-mode (inline metrics), and file-mode (CSV, JMeter, Gatling) metric ingestion
- Track which software version/commit was under test at evaluation time
- Support weighted multi-VM and multi-service group evaluations
- Store SLI values as time-series for trend analysis and Grafana dashboards
- Scope historical comparisons by asset metadata (same OS + arch = valid baseline)
- Provide a React UI with SLI breakdown, heatmap, trend charts with axis control, and result invalidation
- Work for HTTP load testing tools (k6, Locust, Gatling, JMeter) without modification to those tools

### Non-Goals (for now)
- Real-time streaming evaluation (evaluations are point-in-time batch operations)
- Running load tests (the platform evaluates results, it does not generate load)
- Replacing Prometheus itself (Prometheus remains the time-series store; this platform stores aggregated scalars)
- Cross-version comparison UI (Phase 3)
- Multi-tenant access control (single-team deployment assumed)

---

## 3. Architecture Overview

### 3.1 Services

```
Docker Compose
├── quality-gate-api    :8080   Python FastAPI — evaluation engine, all modules
├── adapter-prometheus  :8081   Python FastAPI — Prometheus query adapter
├── timescaledb         :5432   PostgreSQL + TimescaleDB extension
└── ui                  :3000   React SPA served by nginx
```

External (pre-existing, not managed by this platform):
- Prometheus (VM metrics, agent metrics)
- Any CI/CD system (triggers evaluations via REST API)
- Grafana (optional, connects directly to timescaledb as a PostgreSQL data source)

### 3.2 Internal Module Structure (quality-gate-api)

The API service is a single FastAPI application organised into three modules with clear internal boundaries. Modules communicate through shared database models, not HTTP. This avoids operational overhead of inter-service calls while preserving clean separation of concerns.

```
quality-gate-api/
├── main.py
├── modules/
│   ├── registry/         # Sub-project 2: Asset Registry
│   │   ├── router.py
│   │   ├── models.py
│   │   └── service.py
│   ├── catalog/          # Sub-project 3: Test Catalog
│   │   ├── router.py
│   │   ├── models.py
│   │   └── service.py
│   └── quality_gate/     # Sub-project 1: Quality Gate Engine
│       ├── router.py
│       ├── models.py
│       ├── service.py
│       └── engine/       # Pure evaluation logic, zero I/O
│           ├── evaluator.py
│           ├── criteria.py
│           ├── scoring.py
│           └── slo_parser.py
├── adapters/
│   └── client.py         # HTTP client for adapter services
└── db/
    ├── session.py
    └── migrations/
```

### 3.3 Adapter Architecture

Adapters are independent FastAPI microservices. Each implements a single contract:

```
POST /query
{
  "indicators": ["response_time_p99", "error_rate", "throughput"],
  "start": "2026-03-11T10:00:00Z",
  "end": "2026-03-11T10:30:00Z",
  "variables": {"vm_ip": "192.168.1.10", "branch": "7.6"},
  "sli_yaml": "spec_version: \"1.0\"\nindicators:\n  response_time_p99: \"histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{instance=\\\"$vm_ip\\\"}[5m]))\"\n  ..."
}

→ 200 OK
{
  "metrics": {
    "response_time_p99": 450.3,
    "error_rate": 0.02,
    "throughput": 1523.4
  },
  "errors": {
    "some_missing_metric": "no data in time range"
  }
}

GET /health → 200 OK {"status": "ok", "datasource": "prometheus"}
```

The `sli_yaml` field is mandatory for pull-mode requests. It contains the SLI indicator-to-query mapping (Keptn SLI spec 1.0 format). The main service extracts the `indicators:` block from the resolved SLO YAML (whether sourced from a named registry entry or passed inline) and forwards it as the `sli_yaml` value in the adapter request. The adapter is stateless — it never stores SLI definitions.

The `variables` map is used for template substitution in SLI queries. A query like `cpu_usage{instance="$vm_ip"}` becomes `cpu_usage{instance="192.168.1.10"}` before execution. Variables are sourced from asset metadata + evaluation request metadata at trigger time.

### 3.4 Metric Ingestion Modes

Three modes produce identical stored results:

| Mode | Trigger | Use case |
|---|---|---|
| **Pull** | `datasource.adapter` specified in request | Prometheus/InfluxDB — continuous VM monitoring |
| **Push** | `metrics` object provided in request body | k6, Locust, custom scripts — caller aggregates and posts |
| **File** | `results_file` uploaded (multipart) or `results_path` scanned | JMeter XML, Gatling simulation.log, CSV — CI artifact consumption |

In Phase 1, file type routing is hardcoded: the `results_format` field in the request selects a built-in parser (`"jmeter"` → JMeter XML parser, `"csv"` → generic CSV parser). No dynamic plugin registration is needed in Phase 1. Additional parsers are added as new Python modules in Phase 2+. File delivery options:
- **Upload**: `multipart/form-data` with `results_file` field alongside JSON metadata
- **Path scan**: `results_path` in the request body — a filesystem path accessible to the container (via Docker volume mount)

---

## 4. Domain Model

### 4.1 Asset (polymorphic)

An Asset is any entity under test — a VM, a microservice, a container, or an HTTP endpoint.

```
Asset
  id            UUID
  name          string        mandatory, unique, human-readable
  type          enum          vm | service | container | endpoint
  tags          JSONB         arbitrary key-value metadata
                              e.g. {os: "windows-11", arch: "x64", team: "platform"}

  # VM-specific (stored in tags or dedicated columns)
  ip            string        optional
  hostname      string        optional

  # Service-specific
  repository    string        optional — repo URL
  deployment_url string       optional

  created_at    timestamp
  updated_at    timestamp
```

### 4.2 AssetGroup

A named collection of assets with per-member weights. Used for multi-VM test harnesses where the same test runs on several machines and results are aggregated.

```
AssetGroup
  id            UUID
  name          string        e.g. "windows11-64b-group"
  description   string

AssetGroupMember
  group_id      UUID → AssetGroup
  asset_id      UUID → Asset
  weight        float         e.g. 0.5 (two VMs each contribute 50%)
```

Example: `windows11-64b-group` = [VM-01 @ 0.5, VM-02 @ 0.5]. A single CentOS 7 VM = [vm-centos7 @ 1.0].

### 4.3 VersionSnapshot

Captures the exact software state at the moment of evaluation trigger. Answers "what was deployed when this test ran?"

```
VersionSnapshot
  id              UUID
  asset_id        UUID → Asset
  captured_at     timestamp
  primary_version string      commit hash, semver tag, or "7.6-abc123"
  build_ref       string      CI build number, PR number, branch name
  components      JSONB       [{name: "agent-core", version: "2.1.0"}, ...]
```

For multi-service test harnesses, multiple VersionSnapshots are captured — one per asset involved in the evaluation.

### 4.4 SLODefinition (versioned)

A named, reusable SLO template with full version history. Every update creates a new immutable version row — previous versions are never modified or deleted. The latest version (highest integer `version` per `name`) is used automatically in evaluations.

```
SLODefinition
  id          UUID          primary key (unique per version row)
  name        TEXT          stable external identifier — never changes
                            e.g. "compilation-test-windows"
  version     INTEGER       auto-incremented per name (1, 2, 3, ...)
                            unique constraint on (name, version)
  slo_yaml    TEXT          full SLO YAML content (Keptn 1.0 spec compatible)
                            includes indicators block
  notes       TEXT          optional — describes what changed in this version
                            e.g. "Tightened compilation_duration threshold to +3%"
  author      TEXT          optional — who created this version
  meta        JSONB         expandable key-value metadata
                            e.g. {review_status: "approved", ticket: "PERF-421",
                                  tags: ["windows", "compilation"]}
  created_at  TIMESTAMPTZ   when this version was created (immutable)
```

Version auto-increment is enforced at the database level via a trigger or at the application layer using `SELECT MAX(version) + 1 ... FOR UPDATE` within a transaction to prevent races.

**Querying rules:**
- `GET /slos/{name}` — returns the highest version (latest)
- `GET /slos/{name}/versions` — returns full version history, newest first
- `GET /slos/{name}/versions/{v}` — returns a specific version
- `PUT /slos/{name}` — inserts a new version row (never overwrites)

Evaluations store both `slo_name` and `slo_version` (integer) alongside the resolved `slo_yaml` snapshot, so you can always trace back which exact SLO version was active when an evaluation ran.

Evaluations can reference a named SLO (`slo_name`) or provide one inline (`slo_yaml`). Inline SLOs take precedence and are not stored in the registry.

### 4.5 Evaluation

Result of evaluating one test case against one asset for one time window.

```
Evaluation
  id                UUID
  name              string          test identifier (e.g. "compilation-test")
  asset_id          UUID → Asset    nullable if asset not registered in Phase 1
  asset_snapshot    JSONB           denormalised snapshot of asset state captured at
                                    trigger time: union of Asset fields + the most recent
                                    VersionSnapshot for that asset (or just request-provided
                                    metadata if no registered asset exists in Phase 1).
                                    Shape: {name, tags, primary_version, build_ref, components}
  start             timestamptz
  end               timestamptz
  result            enum            pass | warning | fail | error
  score             float           0.0 – 100.0
  slo_yaml          text            resolved SLO used (after variable substitution)
  indicator_results JSONB           full per-SLI breakdown (see §4.7)
  metadata          JSONB           arbitrary caller-provided key-value pairs
  slo_name          TEXT            nullable — name of the registry SLO used
  slo_version       INTEGER         nullable — version number of the registry SLO used
                                    (both null if SLO was provided inline)
  ingestion_mode    enum            pull | push | file
  adapter_used      string          nullable — e.g. "prometheus"
  invalidated       boolean         default false
  invalidation_note text            reason for invalidation
  created_at        timestamptz
```

### 4.6 GroupEvaluation

Aggregated result across an AssetGroup. Computed from weighted individual Evaluation scores.

```
GroupEvaluation
  id              UUID
  name            string
  asset_group_id  UUID → AssetGroup    nullable (can be ad-hoc)
  evaluation_ids  UUID[]               individual evaluations included
  weights         JSONB                {eval_id: weight} at computation time
  weighted_score  float
  result          enum                 pass | warning | fail
  created_at      timestamptz
```

Weighted score: `sum(eval.score * weight) / sum(weight)`. Pass/warning/fail thresholds are taken from the `total_score` section of the first evaluation's stored `slo_yaml`.

**Constraint enforcement:** `POST /group-evaluations` validates that all submitted evaluation IDs share the same `total_score.pass` and `total_score.warning` values. If they differ, the API returns `422 Unprocessable Entity` with a message identifying the conflicting evaluations. "Same SLO" is defined as matching `total_score` thresholds — not structural equality of the full SLO YAML, which would be too strict for minor SLI query differences. When the constraint passes and thresholds are equivalent across all evaluations, the threshold values are taken from any evaluation — conventionally the one with the earliest `created_at`.

### 4.7 EvaluationAnnotation

A free-form contextual note attached to an evaluation after the fact. Annotations record environmental factors, manual interventions, or observations that explain metric changes without affecting the evaluation result. Multiple annotations can be attached to one evaluation.

**Use cases:**
- "New Windows Defender definitions deployed to this VM 2h before test"
- "Kernel upgraded from 5.15 to 6.1 on this host"
- "Allocated additional 4GB RAM to checkout-service pod at 09:45"
- "Network switch firmware updated in this rack — baseline latency shifted +2ms"

```
EvaluationAnnotation
  id              UUID
  evaluation_id   UUID → Evaluation
  content         TEXT          the note (required, no length limit)
  author          TEXT          optional — who added the note
  category        TEXT          optional — free label e.g. "environment",
                                "infrastructure", "deployment", "known-issue"
  meta            JSONB         expandable key-value metadata
                                e.g. {ticket: "OPS-8821", affects_baseline: true}
  created_at      TIMESTAMPTZ
```

Annotations are append-only. They can be deleted but not edited — if a correction is needed, delete and re-add. This preserves an audit trail. Annotations do not change `result`, `score`, or `invalidated` on the parent evaluation.

### 4.8 SLIValue (TimescaleDB hypertable)

One row per aggregated metric value per evaluation. Time column is `eval_start` to enable Grafana time-series queries.

```
SLIValue (hypertable, partitioned by eval_start)
  eval_id       UUID → Evaluation
  eval_start    timestamptz       (chunk key)
  metric_name   string            e.g. "response_time_p99"
  aggregation   string            p50 | p90 | p99 | avg | min | max | raw
  value         double precision
  asset_name    string            denormalised for Grafana query convenience
  test_name     string            denormalised
  os_tag        string            denormalised from asset tags
```

Denormalised columns (asset_name, test_name, os_tag) avoid joins in Grafana SQL queries, which typically cannot do joins cleanly.

---

## 5. Evaluation Engine

### 5.1 Algorithm (Python port of lighthouse-service)

The engine is a pure function: `evaluate(slo, metrics) → EvaluationResult`. Zero database calls, zero HTTP calls. Fully unit-testable in isolation.

**Per-SLI scoring:**
1. For each objective in the SLO:
   - If no pass criteria defined: skip (informational only, contributes no score)
   - Add `objective.weight` to `maximum_achievable_score`
   - If metric missing or retrieval failed: `score = 0`, `status = fail`
   - Evaluate pass criteria (AND within a criteria block, OR across blocks)
   - If pass: `score = objective.weight`, `status = pass`
   - Else evaluate warning criteria
   - If warning: `score = 0.5 * objective.weight`, `status = warning`
   - Else: `score = 0`, `status = fail`
   - **If `key_sli: true` and status is fail: mark `key_sli_failed = true`**

> **key_sli behaviour:** Any objective marked `key_sli: true` acts as a hard veto. If it fails, the entire evaluation is `fail` regardless of the total weighted score — even if every other SLI is green and the score would be 99%. This is the mechanism for mandatory criteria (e.g. zero compilation errors, zero test crashes). A single `key_sli` failure short-circuits the pass/warning threshold check entirely.

**Total score:**
```
if maximum_achievable_score == 0:           → pass (score=100.0, no criteria to evaluate)
else:
  achieved_pct = 100.0 * (sum(scores) / maximum_achievable_score)

  if key_sli_failed:                        → fail
  elif achieved_pct >= total_score.pass:    → pass
  elif achieved_pct >= total_score.warning: → warning
  else:                                     → fail
```

Edge case: if `maximum_achievable_score` is zero (no objectives have pass criteria), the evaluation returns `pass` with `score=100.0`. This matches Keptn's lighthouse-service behaviour and handles informational-only SLOs gracefully.

**Criteria types:**
- Fixed threshold: `<600`, `>=0`, `=0` — compared directly against metric value
- Relative: `<=+10%`, `>=-5%` — compared against aggregated value from previous evaluations

### 5.2 Historical Comparison and Baseline Scoping

For relative criteria, the engine fetches previous evaluations from the database. This is a Phase 1 feature — it is required for `<=+10%`-style criteria to work correctly.

**Phase 1 scoping:** Previous evaluations are filtered by:
1. `name` (test name) — same test identifier
2. `asset_snapshot->>'os'` tag — if the current evaluation's asset snapshot contains an `os` tag, only evaluations with the same `os` tag value are considered as baselines

In Phase 1, asset snapshots are populated from request `metadata` fields (see §5.4). If no `os` tag is present, scoping falls back to test name only.

**Phase 1+ scoping (via `scope_tags` extension, available from Phase 1):** The SLO may specify which asset snapshot tags to match:

```yaml
comparison:
  compare_with: "several_results"
  number_of_comparison_results: 3
  include_result_with_score: "pass_or_warn"
  aggregate_function: "avg"
  scope_tags: ["os", "arch"]   # which asset_snapshot tags must match for a valid baseline
```

If `scope_tags` is omitted, the Phase 1 default (`os` only) applies. This field is available from Phase 1 — it is not deferred to Phase 3.

### 5.3 Metric Aggregation (pull mode)

When the Prometheus adapter is used, SLI queries return raw time-series over the evaluation window. The adapter computes aggregations before returning:

- The SLO objective references an indicator name (e.g. `response_time_p99`)
- The SLI YAML maps that name to a PromQL query (e.g. `histogram_quantile(0.99, ...)`)
- The adapter evaluates the query and returns a single scalar
- Multiple aggregations of the same raw metric (avg, p99, min, max) require separate indicator entries in the SLI YAML

For push and file modes, the caller is responsible for computing aggregations. The posted `metrics` map must match indicator names in the SLO.

### 5.4 SLO Variable Substitution

Before evaluation, all `$variable_name` tokens in SLI queries are resolved in this order (later entries override):
1. Evaluation request `metadata` fields (available Phase 1)
2. Reserved variables derived from the request: `$asset_name` (from `asset_name` field), `$asset_ip` (from `metadata.ip` if present), `$test_name` (from `name` field)
3. Phase 2+: Asset tags from the registered Asset record in the database

In Phase 1 there is no Asset Registry, so all variable values must be explicitly passed in the evaluation request's `metadata` map or `asset_name` field. For example, to substitute `$vm_ip` in a PromQL query, the caller includes `"metadata": {"vm_ip": "192.168.1.10"}`.

Unresolved variables (tokens still starting with `$` after substitution) cause a `422` validation error before the adapter is called, with the list of unresolved variable names included in the error response.

---

## 6. REST API

### 6.1 Evaluations

```
POST   /evaluations                    Trigger a new evaluation
GET    /evaluations                    List evaluations (filter: name, asset, result, from, to)
GET    /evaluations/{id}               Get evaluation detail with full indicator results
PATCH  /evaluations/{id}               Invalidate or un-invalidate (body: {invalidated, note})
GET    /evaluations/{id}/compare       Compare with a specific previous evaluation

POST   /evaluations/file               Trigger evaluation with file upload (multipart)

POST   /evaluations/{id}/annotations   Add a contextual note to an evaluation
GET    /evaluations/{id}/annotations   List all annotations for an evaluation
DELETE /evaluations/{id}/annotations/{ann_id}   Remove an annotation

POST   /group-evaluations              Compute group evaluation from existing eval IDs
GET    /group-evaluations/{id}         Get group evaluation detail
```

**POST /evaluations — request body:**
```json
{
  "name": "compilation-test",
  "start": "2026-03-11T10:00:00Z",
  "end": "2026-03-11T10:30:00Z",

  "asset_name": "vm-win11-01",
  "assets": [
    {"name": "auth-service", "commit": "a1b2c3"},
    {"name": "checkout-service", "commit": "d4e5f6"}
  ],

  "slo_name": "compilation-test-slo",
  "slo_yaml": "spec_version: '1.0'\n...",

  "datasource": {
    "adapter": "prometheus",
    "url": "http://adapter-prometheus:8081"
  },

  "metrics": {
    "response_time_p99": 450.3,
    "error_rate": 0.02,
    "compilation_duration_s": 45.3
  },

  "results_path": "/data/jmeter-results/run-20260311.xml",
  "results_format": "jmeter",

  "metadata": {
    "branch": "7.6",
    "build": "ci-4521",
    "triggered_by": "github-actions"
  }
}
```

**Ingestion mode rules:** Exactly one of `datasource`, `metrics`, or `results_path`+`results_format` must be provided. Providing more than one or none returns `422`.

**Asset identification rules:**
- `asset_name` identifies the single primary asset being evaluated. It becomes the `asset_id` link if that name matches a registered Asset, and is always stored in `asset_snapshot.name`.
- `assets` is an optional supplementary list for multi-service test harnesses. It captures version metadata for all services involved in the test (e.g. 3 microservices tested together). These are stored in `asset_snapshot.components` alongside the primary asset — they do not create separate Evaluation records.
- Both can be provided simultaneously: `asset_name` is the primary asset, `assets` provides the version context of co-deployed services.
- Variable substitution (§5.4) uses only the primary asset's metadata. Multi-asset version data is stored for audit/history only in Phase 1.

**POST /evaluations — response:**
```json
{
  "id": "uuid",
  "result": "pass",
  "score": 92.39,
  "name": "compilation-test",
  "start": "...", "end": "...",
  "indicator_results": [
    {
      "metric": "response_time_p99",
      "display_name": "Response Time P99",
      "value": 450.3,
      "compared_value": 410.5,
      "status": "pass",
      "score": 2.0,
      "weight": 2,
      "key_sli": true,
      "pass_targets": [{"criteria": "<=+10%", "target_value": 451.55, "violated": false}],
      "warning_targets": [{"criteria": "<=800", "target_value": 800, "violated": false}]
    }
  ],
  "compared_evaluation_ids": ["uuid1", "uuid2"],
  "asset_snapshot": {"name": "vm-win11-01", "tags": {"os": "windows-11", "arch": "x64"}},
  "invalidated": false
}
```

### 6.2 Asset Registry

```
POST   /assets                         Register an asset
GET    /assets                         List assets (filter: type, tags)
GET    /assets/{id}                    Get asset detail
PATCH  /assets/{id}                    Update asset metadata/tags
DELETE /assets/{id}                    Remove asset

POST   /asset-groups                   Create group with members and weights
GET    /asset-groups                   List groups
GET    /asset-groups/{id}              Get group detail
PATCH  /asset-groups/{id}/members      Update member weights
```

### 6.3 SLO Registry

```
POST   /slos                           Create a new named SLO (version 1)
GET    /slos                           List all SLOs (latest version per name)
GET    /slos/{name}                    Get latest version of a named SLO
PUT    /slos/{name}                    Create new version (never overwrites)
DELETE /slos/{name}                    Soft-delete: mark all versions inactive
                                       (evaluations that used it are unaffected)

GET    /slos/{name}/versions           List all versions, newest first
GET    /slos/{name}/versions/{v}       Get a specific version by integer

POST   /slos/validate                  Validate SLO YAML without registering
```

`name` is the stable external identifier for all SLO API routes. The internal `id` (UUID) is never exposed. Version number is auto-assigned and returned in the response.

**PUT /slos/{name} request body:**
```json
{
  "slo_yaml": "spec_version: '1.0'\n...",
  "notes": "Tightened compilation_duration threshold from +5% to +3% after baseline stabilised",
  "author": "jane.smith",
  "meta": {
    "review_status": "approved",
    "ticket": "PERF-421",
    "tags": ["windows", "compilation"]
  }
}
```

**Response:**
```json
{
  "name": "compilation-test-windows",
  "version": 3,
  "author": "jane.smith",
  "notes": "Tightened compilation_duration threshold from +5% to +3%...",
  "meta": {"review_status": "approved", "ticket": "PERF-421"},
  "created_at": "2026-03-12T11:30:00Z"
}
```

**GET /slos/{name}/versions response:**
```json
{
  "name": "compilation-test-windows",
  "versions": [
    {"version": 3, "author": "jane.smith", "notes": "Tightened threshold...", "created_at": "2026-03-12T11:30:00Z"},
    {"version": 2, "author": "john.doe",   "notes": "Added memory_peak_mb indicator", "created_at": "2026-03-01T09:00:00Z"},
    {"version": 1, "author": "jane.smith", "notes": "Initial version", "created_at": "2026-02-15T14:00:00Z"}
  ]
}
```

### 6.4 Trend

```
GET    /trend
  ?test_name=compilation-test
  &metric=response_time_p99
  &asset_name=vm-win11-01
  &from=2026-03-01T00:00:00Z
  &to=2026-03-12T00:00:00Z
  &result_filter=pass,warning
```

Returns time-series data points as a JSON array of `{timestamp, value, eval_id, result}` objects — a custom format optimised for the React UI. **Phase 1 does not implement Grafana SimpleJSON compatibility.** Grafana users in Phase 1 connect directly to TimescaleDB as a PostgreSQL data source using SQL queries against the `sli_values` table. Full Grafana SimpleJSON endpoint compatibility is a Phase 3 feature.

---

## 7. React UI

### 7.1 Screens

**Evaluation List**
- Filterable by test name, asset, date range, result (pass/warn/fail/invalidated)
- Heatmap view: rows = test names, columns = time buckets, cells = pass/warn/fail colour
- Table view: sortable columns
- Multiple evaluations per day shown as numbered runs

**Evaluation Detail**
- Overall score + result badge
- SLO name + version used (links to `/slos/{name}/versions/{v}` diff view)
- SLI breakdown table: metric name, value, compared value, % change, pass/warn/fail per metric, weight, score contribution
- Criteria violations highlighted
- Key SLI failures called out prominently
- SLO YAML viewer (syntax-highlighted, with version history dropdown)
- Annotations panel: list of contextual notes with author, category, timestamp; Add annotation button
- Invalidate button → modal for reason entry
- Heatmap cell shows annotation indicator icon (⚑) if any annotations exist

**Metric Trend**
- Line chart for a single metric across evaluations over time
- Y-axis: fully configurable min/max (avoids the "one outlier blows the scale" problem)
- X-axis: evaluation number or timestamp
- Toggleable: show individual VM lines + group average
- Overlay pass/warning threshold lines from the SLO
- Filter by result (e.g. exclude invalidated, show only passing runs)

**Asset Registry**
- List, create, edit assets and groups
- View version history per asset

**SLO Manager**
- YAML editor with live validation
- List named SLOs — shows latest version number, author, notes, created date
- Version history view per SLO: table of all versions with diff link between any two
- Author, notes, and meta fields editable when creating a new version
- "Which evaluations used this version?" link from any version row

### 7.2 Technology
- React + TypeScript
- Recharts for charts (lightweight, composable, good axis control)
- TanStack Query for data fetching
- Tailwind CSS for styling
- nginx for static serving in Docker

---

## 8. Prometheus Adapter

The Prometheus adapter is a standalone FastAPI service. It:
1. Receives the `/query` request with indicators, time range, and variables
2. Loads the SLI YAML (passed in the request body or fetched by name)
3. Substitutes `$variable` tokens in PromQL queries
4. Executes queries against the configured Prometheus instance
5. Returns scalar values — aggregation functions (avg_over_time, quantile, etc.) are in the PromQL itself
6. Reports per-metric errors without failing the entire request

Configuration via environment variables:
- `PROMETHEUS_URL` — default Prometheus base URL (overridden per request if needed)
- `DEFAULT_STEP` — PromQL range step (default: `60s`)

---

## 9. Storage Schema (key tables)

```sql
-- Assets
CREATE TABLE assets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT UNIQUE NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('vm','service','container','endpoint')),
  tags JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Evaluations
CREATE TABLE evaluations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  asset_id UUID REFERENCES assets(id),
  asset_snapshot JSONB,
  start_time TIMESTAMPTZ NOT NULL,
  end_time TIMESTAMPTZ NOT NULL,
  result TEXT NOT NULL CHECK (result IN ('pass','warning','fail','error')),
  score DOUBLE PRECISION,
  slo_yaml TEXT NOT NULL,
  indicator_results JSONB NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}',
  ingestion_mode TEXT NOT NULL CHECK (ingestion_mode IN ('pull','push','file')),
  adapter_used TEXT,
  invalidated BOOLEAN NOT NULL DEFAULT FALSE,
  invalidation_note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_evaluations_name ON evaluations(name);
CREATE INDEX idx_evaluations_asset ON evaluations(asset_id);
CREATE INDEX idx_evaluations_result ON evaluations(result);
CREATE INDEX idx_evaluations_start ON evaluations(start_time DESC);

-- SLI Values (TimescaleDB hypertable)
CREATE TABLE sli_values (
  eval_id UUID NOT NULL REFERENCES evaluations(id),
  eval_start TIMESTAMPTZ NOT NULL,
  metric_name TEXT NOT NULL,
  aggregation TEXT NOT NULL,
  value DOUBLE PRECISION NOT NULL,
  asset_name TEXT,
  test_name TEXT,
  os_tag TEXT
);
SELECT create_hypertable('sli_values', 'eval_start');
CREATE INDEX idx_sli_values_lookup ON sli_values(test_name, metric_name, eval_start DESC);

-- SLO Definitions (versioned — rows are immutable after insert)
CREATE TABLE slo_definitions (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT        NOT NULL,
  version     INTEGER     NOT NULL,
  slo_yaml    TEXT        NOT NULL,
  notes       TEXT,
  author      TEXT,
  meta        JSONB       NOT NULL DEFAULT '{}',
  active      BOOLEAN     NOT NULL DEFAULT TRUE,   -- FALSE = soft-deleted name
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_slo_name_version UNIQUE (name, version)
);

CREATE INDEX idx_slo_definitions_name ON slo_definitions(name);
CREATE INDEX idx_slo_definitions_latest ON slo_definitions(name, version DESC);

-- Version auto-increment: enforced in application layer within serialisable transaction
-- SELECT COALESCE(MAX(version), 0) + 1 FROM slo_definitions WHERE name = $1 FOR UPDATE

-- Evaluation Annotations (append-only)
CREATE TABLE evaluation_annotations (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  evaluation_id   UUID        NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
  content         TEXT        NOT NULL,
  author          TEXT,
  category        TEXT,       -- e.g. 'environment', 'infrastructure', 'deployment'
  meta            JSONB       NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_annotations_evaluation ON evaluation_annotations(evaluation_id);
```

Add `slo_name` and `slo_version` columns to the evaluations table (additive, nullable):

```sql
ALTER TABLE evaluations
  ADD COLUMN slo_name    TEXT,
  ADD COLUMN slo_version INTEGER;

CREATE INDEX idx_evaluations_slo ON evaluations(slo_name, slo_version);
```

---

## 10. Implementation Phasing

### Phase 1 — Core Quality Gate (ship first)
- Evaluation engine: Python port of Keptn lighthouse scoring algorithm (including `scope_tags` baseline scoping)
- All three ingestion modes: pull, push, file (CSV + JMeter; hardcoded format dispatching)
- Prometheus adapter service
- TimescaleDB schema: `assets` (name + tags only), `evaluations`, `sli_values` hypertable, `slo_definitions`
- REST API: `/evaluations`, `/slos`, `/trend`
- Asset support: flat — name + tags stored in `asset_snapshot` JSONB from request metadata; `assets` table exists but has no typed fields or registry UI yet
- Variable substitution: from request `metadata` fields only (no DB asset lookup)
- Baseline scoping: by test name + `os` tag from `asset_snapshot` (or `scope_tags` if specified in SLO)
- React UI: evaluation list with heatmap, evaluation detail with SLI breakdown, basic trend chart, invalidation workflow, SLO manager
- Docker Compose with all four services
- SLO YAML format: 100% compatible with Keptn 1.0 spec

**Phase 1 database migrations:** Initial migration creates `assets`, `evaluations`, `sli_values`, `slo_definitions`. Phase 2 migration adds `asset_groups`, `asset_group_members`, `version_snapshots` as additive changes with no breaking schema alterations.

### Phase 2 — Asset Registry + Group Evaluations
- Full Asset Registry: typed assets (vm/service/container/endpoint), persistent registration with tags
- Variable substitution upgraded: DB asset lookup as primary source, request metadata as override
- VersionSnapshot: captured at trigger time, full component list, linked to evaluations
- Multi-asset evaluation: `assets[]` in request creates VersionSnapshots for all co-deployed services
- AssetGroup + GroupEvaluation: weighted rollup across VMs, `POST /group-evaluations`
- `/assets`, `/asset-groups` REST API
- Phase 2 migrations: add `asset_groups`, `asset_group_members`, `version_snapshots` tables
- UI: asset registry screens, group evaluation view, per-VM breakdown in trend chart

### Phase 3 — Test Catalog + Advanced UI
- TestCase entity: named test definitions with one-to-many SLO associations (join table, not a single default field — one test covers 400 metrics split across multiple SLO definitions by concern: timing, resources, errors, etc.)
- Cross-version comparison: select two evaluations, diff their SLI breakdowns side-by-side
- Advanced trend chart: Y-axis lock/zoom, overlay pass/warning threshold lines from SLO, exclude invalidated toggle
- Grafana SimpleJSON endpoint for `/trend` (enables Grafana panel consumption without direct DB access)
- InfluxDB adapter

---

## 11. SLO Format Compatibility

SLO YAML is 100% compatible with the Keptn 1.0 specification. Existing Keptn SLOs migrate without modification. The SLI YAML (indicator name → PromQL query mapping) is embedded within the SLO definition stored in the registry, or passed inline in the evaluation request. Unlike Keptn, there is no separate resource-service — SLI and SLO configuration travel together.

The only extension to the Keptn 1.0 SLO spec is the optional `comparison.scope_tags` field (available Phase 1):

```yaml
spec_version: '1.0'
comparison:
  compare_with: "several_results"
  number_of_comparison_results: 3
  include_result_with_score: "pass_or_warn"
  aggregate_function: "avg"
  scope_tags: ["os", "arch"]        # extension: scope comparison baseline
objectives:
  - sli: response_time_p99
    displayName: "Response Time P99"
    pass:
      - criteria: ["<=+10%", "<600"]
    warning:
      - criteria: ["<=800"]
    weight: 2
    key_sli: true
  - sli: compilation_duration_s
    displayName: "Compilation Duration"
    pass:
      - criteria: ["<=+5%"]
    weight: 1
total_score:
  pass: "90%"
  warning: "75%"
```

---

## 22. Reliability — Job Lifecycle, Retries, and Reruns

### 22.1 Job Status Tracking

Every evaluation job has an explicit `status` column on the `evaluations` table:

```
status  TEXT  NOT NULL  DEFAULT 'pending'
        CHECK (status IN ('pending','running','completed','failed','partial'))
```

| Status | Meaning |
|---|---|
| `pending` | Enqueued in arq, not yet picked up by a worker |
| `running` | Worker has claimed the job and is executing |
| `completed` | Evaluation finished, result written (pass/warn/fail/error) |
| `failed` | Job crashed or timed out, no result written |
| `partial` | Some SLI values written, job died mid-execution |

Workers set `status='running'` + `started_at=now()` before calling the adapter. On crash/timeout arq moves the job to the dead-letter queue; a watchdog query finds `status='running'` rows where `started_at < now() - timeout` and marks them `failed`, then re-enqueues.

### 22.2 Configurable Timeouts and Retry Logic

```yaml
# config.yaml additions
reliability:
  job_timeout_seconds: 120          # wall-clock limit per evaluation job
  adapter_timeout_seconds: 30       # per-indicator HTTP call to adapter
  adapter_retry_attempts: 3         # retry failed adapter calls before marking indicator error
  adapter_retry_backoff_seconds: 2  # exponential base: 2, 4, 8 seconds
  job_max_retries: 3                # arq retry count on job crash
  job_retry_delay_seconds: 10       # delay before re-enqueue after crash
  watchdog_interval_seconds: 60     # how often the watchdog checks for stuck jobs
  stuck_job_threshold_seconds: 180  # running > this → considered stuck → reschedule
```

Each indicator HTTP call to the adapter is independently retried with exponential backoff. If all retries fail, the indicator is recorded as `error` (value=null, success=false) and evaluation continues with the remaining indicators. The job does not fail on a single adapter error — the SLO engine handles missing metrics (score=0 for that objective).

### 22.3 Partial Execution and Job Stats

When a job crashes mid-execution (after some `sli_values` are written but before the final `evaluations` row is updated), the evaluation record shows `status='partial'`. The `job_stats` JSONB column records what was completed:

```json
{
  "indicators_attempted": 150,
  "indicators_completed": 87,
  "indicators_failed": 3,
  "indicators_pending": 60,
  "worker_id": "worker-2",
  "started_at": "2026-03-12T10:00:05Z",
  "crashed_at": "2026-03-12T10:01:42Z",
  "retry_count": 1,
  "error": "asyncio.TimeoutError: adapter call exceeded 30s"
}
```

Add to `evaluations` table:
```sql
ALTER TABLE evaluations
  ADD COLUMN status       TEXT NOT NULL DEFAULT 'pending'
             CHECK (status IN ('pending','running','completed','failed','partial')),
  ADD COLUMN started_at   TIMESTAMPTZ,
  ADD COLUMN job_stats    JSONB NOT NULL DEFAULT '{}';

CREATE INDEX idx_evaluations_status ON evaluations(status);
CREATE INDEX idx_evaluations_stuck  ON evaluations(status, started_at)
  WHERE status = 'running';
```

### 22.4 Rerun Modes

Two rerun modes are exposed on `POST /evaluations/{id}/rerun`:

**Soft rerun** — continues from where the job stopped. Re-fetches only indicators that were not yet successfully retrieved (those absent from `sli_values` for this `eval_id`). Preserves already-written SLI values. Recalculates score after completing the missing indicators.

Use case: job timed out after 200 of 400 indicators; re-run fetches the remaining 200 without re-querying the already-completed ones.

**Hard rerun** — deletes all `sli_values` rows for this `eval_id`, resets `status='pending'`, and re-enqueues a fresh full evaluation. Existing `indicator_results` JSONB is cleared.

Use case: Prometheus returned zeros/nulls due to a scrape gap or bug; the stored values are garbage and must be replaced entirely.

```
POST /evaluations/{id}/rerun
Body: {"mode": "soft" | "hard", "reason": "optional note"}
→ 202 Accepted {eval_id, status: "pending"}
```

Both modes append an `EvaluationAnnotation` automatically:
```json
{
  "category": "rerun",
  "content": "Hard rerun triggered: Prometheus scrape gap caused nil values",
  "meta": {"rerun_mode": "hard", "triggered_by": "jane.smith"}
}
```

## 12. Open Questions (deferred to implementation)

1. **File path scanning security** — path traversal prevention when `results_path` is caller-provided; recommend restricting to a configured allowed-paths prefix via env var
2. **Adapter discovery** — adapters are currently configured via environment variables in the API service; a dynamic registration endpoint could be added in Phase 2
3. **Authentication** — no auth in Phase 1 (internal network assumed); API key header support planned for Phase 2
4. **SLI YAML storage** — SLI queries (PromQL/SQL) currently live outside the SLO definition (Keptn stored them in resource-service); for Phase 1 they are embedded in the named SLO definition or passed inline

---

## 18. Queue System — Redis + arq

### 18.1 Decision

The internal asyncio queue described in §14 is replaced by **Redis + arq** (async Redis Queue). Redis is already in the stack for caching (§15). Using it as a job queue adds no new operational dependency and eliminates the primary risks of in-process queues:

| Risk | asyncio Queue | Redis + arq |
|---|---|---|
| Jobs lost on container restart | ✅ All lost | ✅ Persisted in Redis |
| Visibility into backlog | ❌ None | ✅ Redis keys + arq dashboard |
| Failed job handling | ❌ Silent drop | ✅ Retry + dead-letter queue |
| Horizontal scaling | ❌ Single process | ✅ Multiple worker processes |

The asyncio **semaphore** for adapter rate limiting (§14.4) remains unchanged — it is a concurrency limiter within a worker process, not a queue.

### 18.2 arq in Docker Compose

```yaml
# docker-compose.yml additions
services:
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}

  quality-gate-worker:
    build: ./quality-gate-api
    command: arq app.worker.WorkerSettings
    environment:
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/1
    depends_on: [redis, timescaledb]
    deploy:
      replicas: 2          # scale workers independently of the API
```

The API process enqueues jobs; worker processes consume them. Both share the same codebase — only the entry point differs (`uvicorn` for API, `arq` for workers).

### 18.3 Updated Config

```yaml
queue:
  backend: "redis"
  db_index: 1              # separate from cache (db_index: 0)
  max_retries: 3
  retry_delay_seconds: 5
  job_timeout_seconds: 120
  keep_result_seconds: 3600   # how long completed job results stay in Redis
```

---

## 19. Configuration — Secrets Separation

### 19.1 Two-File Approach

Runtime configuration is split into two concerns:

**`config.yaml`** — non-secret settings, safe to commit to Git:
```yaml
server:
  host: "0.0.0.0"
  port: 8080

database:
  host: "timescaledb"
  port: 5432
  name: "quality_gate"
  pool_size: 10
  max_overflow: 20

cache:
  backend: "redis"
  host: "redis"
  port: 6379
  db: 0
  ttl_seconds:
    trend: 60
    evaluation_list: 30
    evaluation_detail: 300
    slo_definition: 600

queue:
  backend: "redis"
  db_index: 1
  max_retries: 3
  retry_delay_seconds: 5
  job_timeout_seconds: 120

evaluation:
  workers: 20
  async_threshold_metrics: 10

adapters:
  prometheus:
    url: "http://adapter-prometheus:8081"
    timeout_seconds: 30
  max_concurrent_queries_per_adapter: 10

db_writer:
  workers: 5
  batch_size: 100

file_ingestion:
  allowed_path_prefix: "/data/results"
  max_file_size_mb: 50

logging:
  level: "INFO"
  format: "json"
```

**Secrets** — never in `config.yaml`, sourced at runtime via one of three mechanisms (checked in priority order):

```bash
# Option A: environment variables / Docker secrets / .env file (local dev)
QG_DB_USER=quality_gate
QG_DB_PASSWORD=changeme
QG_REDIS_PASSWORD=changeme
QG_SECRET_KEY=randomly-generated-signing-key

# Option B: Vault (production)
QG_VAULT_ADDR=https://vault.internal:8200
QG_VAULT_TOKEN=s.xxxxx               # or use AppRole / K8s auth
QG_VAULT_SECRET_PATH=secret/data/quality-gate
# Vault secret at that path contains: db_password, redis_password, secret_key
```

### 19.2 Loading Priority (Pydantic Settings)

Pydantic v2 `BaseSettings` handles this natively:

```
1. Vault (if QG_VAULT_ADDR is set)          ← highest priority
2. Environment variables (QG_* prefix)
3. .env file (development convenience)
4. config.yaml defaults                     ← lowest priority
```

A Vault loader is injected as a custom settings source. If `QG_VAULT_ADDR` is absent, Vault is skipped entirely — no error, no extra dependency at runtime for teams not using it.

### 19.3 Adapter Credentials

Each adapter can also have its own credentials (e.g. a Prometheus instance behind basic auth, a PostgreSQL adapter with its own DB user):

```bash
QG_ADAPTER_PROMETHEUS_USERNAME=prom_reader
QG_ADAPTER_PROMETHEUS_PASSWORD=secret

QG_ADAPTER_POSTGRES_DSN=postgresql://user:pass@host:5432/metrics_db
```

These are forwarded by the API to the adapter in the `/query` request headers (not in the body), and the adapter never logs them.

---

## 20. Phase 3 Test Catalog — Data Model (one-to-many)

This section documents the Phase 3 data model in advance so Phase 1 and 2 data decisions do not preclude it.

A test case like `compilation-windows7` has ~400 metrics. These are split across multiple SLO definitions by concern rather than crammed into one 400-objective YAML file (which would be unwieldy to author and maintain):

```
compilation-windows7
  ├── slo: compilation-timing-slo      (duration, phases, overhead)
  ├── slo: compilation-resources-slo   (CPU, memory, disk I/O)
  └── slo: compilation-errors-slo      (errors, warnings, crashes — all key_sli)
```

**Data model:**

```
test_cases
  name          TEXT  PRIMARY KEY     "compilation-windows7"
  description   TEXT
  meta          JSONB
  created_at    TIMESTAMPTZ

test_case_slos  (join table — one test, many SLOs)
  test_case_name  TEXT → test_cases.name
  slo_name        TEXT → slo_definitions.name
  position        INTEGER    display/execution order
  required        BOOLEAN    if true, this SLO must be evaluated (vs. optional/informational)
  PRIMARY KEY (test_case_name, slo_name)
```

When a test case is used in `POST /evaluations`, the caller can omit `slo_name` — the API evaluates against **all** SLOs registered for that test case and returns one result per SLO. The overall test result is the worst result across all SLO evaluations (one `fail` anywhere = test fails).

This model is additive in Phase 3: Phase 1 and 2 evaluations continue to work with explicit `slo_name` in the request. The test catalog is an optional convenience layer, not a required dependency.

---

## 21. Change Point Detection — Planned Expansion (Post Phase 3)

### 21.1 Purpose

Standard SLO evaluation compares a metric value against a fixed threshold or a relative change from a baseline. This catches known patterns ("response time must be under 600ms") but can miss **gradual drift** — a metric that slowly degrades over many test runs, never triggering any single threshold, but representing a clear regime change in the underlying system.

Change point detection addresses this: it analyses the historical time series of a metric value across evaluations and determines whether the current value represents a statistically significant break from the prior distribution.

**Result:** `0` = no change detected (evaluation unaffected), `1` = change point detected → SLI fails.

### 21.2 Algorithm — Apache OTAVA

The planned implementation uses **[Apache OTAVA](https://github.com/apache/otava)** (Online Time series Anomaly and Variability Analysis), a purpose-built change point detection library for performance test result analysis.

OTAVA uses the E-Divisive algorithm with permutation testing. Key properties:
- Non-parametric (no assumption about metric distribution)
- Works well with the small, irregular sample sizes typical of performance test history
- Returns a significance level (p-value), allowing configurable sensitivity
- Designed specifically for performance testing scenarios — not a generic anomaly detector

### 21.3 SLO YAML Extension (reserved field, Phase 1+)

The `change_point_detection` field is reserved in the SLO schema from Phase 1 but **ignored by the evaluation engine** until the feature is implemented. This means SLO YAMLs authored with this field today will work without modification when the feature ships.

```yaml
objectives:
  - sli: response_time_p99
    displayName: "Response Time P99"
    pass:
      - criteria: ["<=+10%", "<600"]
    weight: 2
    key_sli: false
    change_point_detection:           # optional — ignored until post-Phase 3
      enabled: true
      algorithm: "otava"              # extensible for future algorithms
      sensitivity: 0.05              # p-value threshold (lower = less sensitive)
      min_history: 10                # minimum number of prior evaluations required
                                     # before detection is attempted
      fail_on_detection: true        # if change detected, treat SLI as failed
                                     # (regardless of threshold criteria result)
```

### 21.4 Evaluation Behaviour When Enabled

```
For each objective with change_point_detection.enabled = true:

1. Query sli_values for last N evaluations (same test + scope_tags)
   where N >= change_point_detection.min_history
   If insufficient history → skip detection (do not fail)

2. Pass values to OTAVA algorithm
   → p_value = otava.detect(historical_values + [current_value])

3. If p_value <= sensitivity:
   → change_point_detected = true
   → if fail_on_detection: mark SLI as failed (overrides threshold result)

4. Store detection result in indicator_results:
   {
     "change_point_detected": true,
     "change_point_p_value": 0.023,
     "change_point_algorithm": "otava"
   }
```

### 21.5 Data Model Readiness

The `sli_values` hypertable (§4.8) already stores the time-series data needed by OTAVA. No schema changes are required to support this feature. The `indicator_results` JSONB column on `evaluations` is schema-free, so the additional detection fields are stored without migration.

The only implementation work when this feature is built:
- Add OTAVA as a Python dependency
- Implement the detection step in the evaluation engine as an optional post-processing pass
- Update the UI to surface change point flags in the SLI breakdown table and trend chart

---

## 13. System Configuration (YAML-based)

All runtime configuration is defined in a `config.yaml` file mounted into the `quality-gate-api` container. Environment variable overrides are supported for secrets. The config file is the source of truth for all tuneable parameters.

```yaml
server:
  host: "0.0.0.0"
  port: 8080
  workers: 4                        # Uvicorn/Gunicorn worker processes

database:
  url: "postgresql+asyncpg://user:pass@timescaledb:5432/quality_gate"
  pool_size: 10
  max_overflow: 20

cache:
  backend: "redis"                  # "redis" | "memory" (in-process, for single-worker dev)
  url: "redis://redis:6379/0"
  ttl_seconds:
    trend: 60                       # /trend endpoint results
    evaluation_list: 30             # /evaluations list queries
    evaluation_detail: 300          # individual evaluation (immutable once complete)
    slo_definition: 600             # SLO YAML (rarely changes)

evaluation:
  workers: 20                       # concurrent evaluation jobs in the asyncio pool
  job_queue_size: 500               # max pending jobs before 503 is returned
  job_timeout_seconds: 120          # max time to wait for adapter + engine + write
  async_threshold_metrics: 10       # if indicator count exceeds this, always use async mode
                                    # (returns 202 Accepted; caller polls for result)

adapters:
  prometheus:
    url: "http://adapter-prometheus:8081"
    timeout_seconds: 30
  # Future adapters registered here:
  # influxdb:
  #   url: "http://adapter-influxdb:8082"

  max_concurrent_queries_per_adapter: 10   # semaphore limit per adapter instance
                                            # protects small Prometheus instances from overload

db_writer:
  workers: 5                        # parallel DB write workers
  write_queue_size: 2000            # max pending write jobs
  batch_size: 100                   # sli_values rows inserted per batch statement
                                    # (TimescaleDB performs best with batched inserts)

file_ingestion:
  allowed_path_prefix: "/data/results"   # security: restrict results_path to this prefix
  max_file_size_mb: 50

logging:
  level: "INFO"                     # DEBUG | INFO | WARNING | ERROR
  format: "json"                    # "json" | "text"
```

Configuration is loaded at startup. A `GET /config` endpoint (admin-only in Phase 2) returns the active configuration with secrets redacted.

---

## 14. Concurrency and Queue Architecture

### 14.1 Problem

A single evaluation against 400 metrics on 60 VMs could trigger 24,000 Prometheus queries. Without rate limiting this would overwhelm a small Prometheus instance. Similarly, writing 24,000 `sli_values` rows synchronously in a web request would cause timeouts. The queue architecture solves both.

### 14.2 Two-Queue Design

```mermaid
flowchart LR
    subgraph API["API Layer (FastAPI)"]
        R[Router\nPOST /evaluations]
        V[Validate &\nResolve SLO]
    end

    subgraph EQ["Evaluation Queue (asyncio.Queue)"]
        EJ[Eval Job\npool: config.evaluation.workers]
        EW1[Worker 1]
        EW2[Worker 2]
        EWN[Worker N]
    end

    subgraph AL["Adapter Layer"]
        SEM["Semaphore\nmax_concurrent_queries_per_adapter"]
        PA[adapter-prometheus\nor adapter-postgres]
    end

    subgraph ENG["Evaluation Engine"]
        PURE["evaluate(slo, metrics)\npure function"]
    end

    subgraph WQ["Write Queue (asyncio.Queue)"]
        WJ[Write Job\npool: config.db_writer.workers]
        WW1[Writer 1]
        WW2[Writer 2]
    end

    subgraph STORE["Storage"]
        DB[(TimescaleDB)]
        RC[(Redis Cache\ninvalidated on write)]
    end

    R --> V
    V -->|"enqueue → 202 Accepted"| EJ
    EJ --> EW1 & EW2 & EWN
    EW1 & EW2 & EWN -->|rate-limited| SEM
    SEM --> PA
    PA -->|metric values| ENG
    ENG -->|result| WJ
    WJ --> WW1 & WW2
    WW1 & WW2 -->|batch INSERT| DB
    DB -->|invalidate keys| RC
```

### 14.3 Sync vs Async Response Mode

The API supports two response modes, selected automatically based on `async_threshold_metrics`:

| Condition | Mode | HTTP response |
|---|---|---|
| Indicators ≤ threshold (push/file, or small pull) | **Synchronous** | `200 OK` with full result |
| Indicators > threshold, or explicitly `async: true` | **Asynchronous** | `202 Accepted` `{eval_id, status_url}` |

Callers poll `GET /evaluations/{id}` — the `result` field is `null` and `status` is `"pending"` until complete.

### 14.4 Adapter Rate Limiting

Each adapter type has a shared semaphore sized by `max_concurrent_queries_per_adapter`. Multiple evaluation workers share the same semaphore, ensuring that even with 20 concurrent evaluations, only 10 Prometheus queries run simultaneously. This is per-adapter-type — a future InfluxDB adapter has its own independent semaphore.

### 14.5 DB Write Batching

`sli_values` rows are buffered in the write queue and flushed in batches (`config.db_writer.batch_size`). This converts 400 individual INSERTs into 4 batch statements, which is dramatically more efficient for TimescaleDB's chunk-based storage. Evaluations metadata is always written before `sli_values` to maintain referential integrity.

---

## 15. Caching Layer

### 15.1 What Gets Cached

| Endpoint | Cache key | TTL | Invalidated by |
|---|---|---|---|
| `GET /trend` | `trend:{test_name}:{metric}:{asset}:{from}:{to}:{filter}` | 60s | Any new evaluation for test_name |
| `GET /evaluations` (list) | `evals:list:{filter_hash}` | 30s | Any new evaluation |
| `GET /evaluations/{id}` | `eval:{id}` | 300s | PATCH (invalidation) on that ID |
| `GET /slos/{name}` | `slo:{name}` | 600s | PUT/DELETE on that SLO |

Evaluation detail is effectively immutable after completion (only `invalidated` flag changes), so long TTLs are safe.

### 15.2 Why Redis

- Survives API container restarts (unlike in-process cache)
- Shared across multiple API workers/processes
- `config.cache.backend: "memory"` is available for single-developer local runs without Redis

### 15.3 Large Result Sets

Loading 400 metrics × 60 VMs from the trend endpoint could return up to 24,000 data points per time range. The cache TTL of 60s ensures the expensive TimescaleDB aggregation query runs at most once per minute regardless of how many UI tabs are open. The `/trend` endpoint also supports a `metrics[]` array parameter so the UI fetches one metric at a time per chart panel — amortising the load across lazy chart renders rather than one blocking request.

---

## 16. Flow Diagrams

### 16.1 SLO/SLI Creation Flow

SLI queries (PromQL, SQL, etc.) are embedded inside the SLO YAML under an `indicators` block — there is no separate SLI file as in Keptn.

```mermaid
flowchart TD
    A["Author writes combined SLO+SLI YAML\n(indicators block + objectives block)"] --> B{How will it be used?}

    B -->|"Reused across many evaluations\n(named registry)"| C["POST /slos\nbody: {name, description, slo_yaml}"]
    B -->|"One-off or version-controlled\nin test repo"| D["Include slo_yaml inline\nin POST /evaluations"]
    B -->|"Validate before committing"| E["POST /slos/validate\nbody: {slo_yaml}"]

    C --> F["Internal validation\n- Keptn 1.0 schema check\n- indicators block present?\n- $variables resolvable?"]
    E --> F

    F --> G{Valid?}
    G -->|No| H["422: validation errors\nwith field-level detail"]
    G -->|Yes| I["Stored in slo_definitions\nname is external key"]

    I --> J["Reference by name in\nPOST /evaluations\n{slo_name: 'my-slo'}"]
    D --> K["Validated at evaluation\ntrigger time\n(same rules)"]

    J --> L["At evaluation time:\nextract indicators block\n→ forward as sli_yaml\nto adapter"]
    K --> L
```

### 16.2 Evaluation Trigger — Pull Mode (Prometheus Adapter)

```mermaid
sequenceDiagram
    participant CI as CI/CD Pipeline
    participant API as quality-gate-api
    participant EQ as Eval Job Queue
    participant W as Eval Worker
    participant SEM as Semaphore (max 10)
    participant ADAPT as adapter-prometheus
    participant PROM as Prometheus
    participant WQ as Write Queue
    participant DB as TimescaleDB
    participant CACHE as Redis

    CI->>API: POST /evaluations\n{name, asset_name, start, end,\nslo_name: "compile-slo",\ndatasource: {adapter: "prometheus"},\nmetadata: {vm_ip: "10.0.0.5", os: "windows-11"}}

    API->>API: Resolve SLO YAML from registry
    API->>API: Substitute $variables\n($vm_ip → "10.0.0.5")
    API->>API: Extract indicators block
    API->>API: Validate all $vars resolved
    API->>EQ: Enqueue eval job
    API->>CI: 202 Accepted\n{eval_id, status: "pending",\nstatus_url: "/evaluations/{id}"}

    EQ->>W: Dispatch to available worker

    loop For each indicator (rate-limited by semaphore)
        W->>SEM: Acquire (blocks if 10 already running)
        SEM->>ADAPT: POST /query\n{indicators, start, end,\nvariables, sli_yaml}
        ADAPT->>PROM: GET /api/v1/query\n(PromQL with substituted vars)
        PROM->>ADAPT: Scalar result
        ADAPT->>SEM: Release
        SEM->>W: metric value
    end

    W->>W: evaluate(slo, metrics)\npure scoring function
    W->>WQ: Enqueue write job\n{evaluation record + sli_values rows}

    WQ->>DB: INSERT evaluations (single row)
    WQ->>DB: INSERT sli_values (batch)\neval_id, metric_name, value, asset_name, test_name, os_tag

    DB->>CACHE: Invalidate\ncache keys for test_name

    CI->>API: GET /evaluations/{id}
    API->>CACHE: GET eval:{id}
    CACHE->>API: miss (first fetch)
    API->>DB: SELECT evaluation + indicator_results
    DB->>API: Full record
    API->>CACHE: SET eval:{id} TTL=300s
    API->>CI: 200 OK — full evaluation result
```

### 16.3 Evaluation Trigger — Pull Mode (PostgreSQL Adapter)

The PostgreSQL adapter enables querying metrics stored in any PostgreSQL-compatible database (TimescaleDB, application DB, data warehouse). SLI queries are SQL instead of PromQL. The `$start` and `$end` reserved variables are automatically injected alongside custom metadata variables.

```mermaid
sequenceDiagram
    participant CI as CI/CD Pipeline
    participant API as quality-gate-api
    participant W as Eval Worker
    participant ADAPT as adapter-postgres
    participant PGDB as PostgreSQL / TimescaleDB

    Note over CI,API: SLO registered with SQL-based indicators block:\nindicators:\n  compilation_p99: |\n    SELECT percentile_cont(0.99) WITHIN GROUP\n    (ORDER BY duration_ms)\n    FROM compilation_runs\n    WHERE vm_ip = '$vm_ip'\n    AND started_at BETWEEN '$start' AND '$end'

    CI->>API: POST /evaluations\n{name: "compile-test",\nasset_name: "vm-win11-01",\nstart, end,\nslo_name: "compile-slo",\ndatasource: {adapter: "postgres",\n  url: "http://adapter-postgres:8083"},\nmetadata: {vm_ip: "10.0.0.5"}}

    API->>API: Resolve SLO, substitute variables\n$vm_ip → "10.0.0.5"\n$start → ISO timestamp\n$end → ISO timestamp
    API->>W: Enqueue job

    W->>ADAPT: POST /query\n{indicators: ["compilation_p99"],\nvariables: {vm_ip, start, end},\nsli_yaml: "...SQL queries..."}

    ADAPT->>ADAPT: Substitute variables in SQL
    ADAPT->>PGDB: Execute parameterised SQL query
    Note over ADAPT,PGDB: Parameterised queries prevent SQL injection.\nVariables are bound as query parameters\nnot interpolated as strings.
    PGDB->>ADAPT: Single scalar result row
    ADAPT->>W: {metrics: {compilation_p99: 4250.3}}

    W->>W: evaluate(slo, metrics)
    W->>DB: Write evaluation result
```

### 16.4 Evaluation Trigger — Push Mode (k6 / Locust / CSV)

```mermaid
sequenceDiagram
    participant TOOL as Load Test Tool (k6, Locust)
    participant CI as CI/CD Script
    participant API as quality-gate-api
    participant W as Eval Worker
    participant DB as TimescaleDB

    TOOL->>TOOL: Run load test\n(30 minutes)
    TOOL->>TOOL: Compute aggregations\n(p99, avg, error_rate, throughput)

    CI->>API: POST /evaluations\n{name: "checkout-api-load-test",\nasset_name: "checkout-service",\nstart, end,\nslo_name: "http-api-slo",\nmetrics: {\n  response_time_p99: 450.3,\n  error_rate: 0.019,\n  throughput: 1523.4\n},\nmetadata: {commit: "d4e5f6", branch: "main"}}

    Note over API: No adapter call needed.\nMetrics already in request body.

    API->>W: Enqueue eval job (sync if ≤ threshold)
    W->>W: evaluate(slo, metrics)\nidentical engine, no I/O
    W->>DB: Write result
    API->>CI: 200 OK — full evaluation result\n(synchronous, fast path)
```

### 16.5 UI Cache and Lazy Load Flow

```mermaid
sequenceDiagram
    participant USER as User (browser)
    participant UI as React SPA
    participant API as quality-gate-api
    participant CACHE as Redis
    participant DB as TimescaleDB

    USER->>UI: Open evaluation list
    UI->>API: GET /evaluations?name=compile-test&limit=20
    API->>CACHE: GET evals:list:{hash}
    CACHE->>API: miss
    API->>DB: SELECT evaluations WHERE name=...
    DB->>API: 20 evaluation summaries
    API->>CACHE: SET TTL=30s
    API->>UI: Evaluation list (scores, results, timestamps)
    UI->>USER: Render heatmap — no metric detail yet

    USER->>UI: Click one evaluation row
    UI->>API: GET /evaluations/{id}
    API->>CACHE: GET eval:{id}
    CACHE->>API: hit (if recently loaded)
    API->>UI: Full detail with 400 indicator_results

    USER->>UI: Open Metric Trend tab for "response_time_p99"
    UI->>API: GET /trend?test_name=compile-test\n&metric=response_time_p99\n&asset_name=vm-win11-01

    Note over UI: Metrics loaded ONE AT A TIME per chart panel.\nUI does NOT request all 400 metrics at once.

    API->>CACHE: GET trend:{key}
    CACHE->>API: miss
    API->>DB: SELECT sli_values WHERE\ntest_name=... AND metric_name=...\n(TimescaleDB time-series query, fast)
    DB->>API: Time-series data points
    API->>CACHE: SET TTL=60s
    API->>UI: [{timestamp, value, result, eval_id}, ...]
    UI->>USER: Render line chart with axis controls
```

---

## 17. Sample Payloads

### 17.1 Create a Named SLO (Prometheus / PromQL)

`POST /slos`

```json
{
  "name": "compilation-test-windows",
  "description": "Compilation test SLO for Windows environments. Compares against last 3 passing results for same OS/arch.",
  "slo_yaml": "spec_version: '1.0'\ncomparison:\n  compare_with: several_results\n  number_of_comparison_results: 3\n  include_result_with_score: pass_or_warn\n  aggregate_function: avg\n  scope_tags:\n    - os\n    - arch\nindicators:\n  compilation_duration_s: 'avg_over_time(compilation_duration_seconds{instance=\"$vm_ip\"}[5m])'\n  cpu_usage_avg: 'avg_over_time(process_cpu_seconds_total{instance=\"$vm_ip\"}[$duration])'\n  memory_peak_mb: 'max_over_time(process_resident_memory_bytes{instance=\"$vm_ip\"}[$duration]) / 1048576'\nobjectives:\n  - sli: compilation_duration_s\n    displayName: Compilation Duration (seconds)\n    pass:\n      - criteria:\n          - <=+5%\n    warning:\n      - criteria:\n          - <=+15%\n    weight: 3\n    key_sli: true\n  - sli: cpu_usage_avg\n    displayName: CPU Usage (avg)\n    pass:\n      - criteria:\n          - <=+10%\n          - <90\n    weight: 2\n  - sli: memory_peak_mb\n    displayName: Peak Memory (MB)\n    pass:\n      - criteria:\n          - <2048\n    weight: 1\ntotal_score:\n  pass: '90%'\n  warning: '75%'\n"
}
```

### 17.2 Create a Named SLO (PostgreSQL / SQL queries)

`POST /slos`

```json
{
  "name": "compilation-test-db",
  "description": "Same test but sourcing from internal results DB instead of Prometheus.",
  "slo_yaml": "spec_version: '1.0'\ncomparison:\n  compare_with: several_results\n  number_of_comparison_results: 3\n  include_result_with_score: pass_or_warn\n  aggregate_function: avg\n  scope_tags:\n    - os\nindicators:\n  compilation_duration_p99: |\n    SELECT percentile_cont(0.99) WITHIN GROUP (ORDER BY duration_ms)\n    FROM compilation_runs\n    WHERE vm_ip = '$vm_ip'\n    AND started_at BETWEEN '$start' AND '$end'\n  error_count: |\n    SELECT COUNT(*)\n    FROM compilation_errors\n    WHERE vm_ip = '$vm_ip'\n    AND occurred_at BETWEEN '$start' AND '$end'\nobjectives:\n  - sli: compilation_duration_p99\n    displayName: Compilation Duration P99 (ms)\n    pass:\n      - criteria:\n          - <=+5%\n    weight: 2\n    key_sli: true\n  - sli: error_count\n    displayName: Compilation Errors\n    pass:\n      - criteria:\n          - =0\n    weight: 3\n    key_sli: true\ntotal_score:\n  pass: '100%'\n  warning: '75%'\n"
}
```

### 17.3 Trigger Evaluation — Pull Mode (Prometheus)

`POST /evaluations`

```json
{
  "name": "compilation-test",
  "start": "2026-03-12T10:00:00Z",
  "end": "2026-03-12T10:45:00Z",
  "asset_name": "vm-win11-01",
  "slo_name": "compilation-test-windows",
  "datasource": {
    "adapter": "prometheus",
    "url": "http://adapter-prometheus:8081"
  },
  "metadata": {
    "vm_ip": "10.0.1.15",
    "os": "windows-11",
    "arch": "x64",
    "branch": "7.6",
    "build": "ci-7821",
    "duration": "45m"
  }
}
```

`→ 202 Accepted`

```json
{
  "eval_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "pending",
  "status_url": "/evaluations/f47ac10b-58cc-4372-a567-0e02b2c3d479"
}
```

### 17.4 Trigger Evaluation — Pull Mode (PostgreSQL Adapter)

`POST /evaluations`

```json
{
  "name": "compilation-test",
  "start": "2026-03-12T10:00:00Z",
  "end": "2026-03-12T10:45:00Z",
  "asset_name": "vm-win11-01",
  "slo_name": "compilation-test-db",
  "datasource": {
    "adapter": "postgres",
    "url": "http://adapter-postgres:8083"
  },
  "metadata": {
    "vm_ip": "10.0.1.15",
    "os": "windows-11",
    "arch": "x64",
    "branch": "7.6"
  }
}
```

### 17.5 Trigger Evaluation — Push Mode (k6 / Load Test Tool)

`POST /evaluations`

```json
{
  "name": "checkout-api-load-test",
  "start": "2026-03-12T14:00:00Z",
  "end": "2026-03-12T14:30:00Z",
  "asset_name": "checkout-service",
  "assets": [
    {"name": "checkout-service", "commit": "d4e5f6", "branch": "main"},
    {"name": "payment-service",  "commit": "a1b2c3", "branch": "main"},
    {"name": "auth-service",     "commit": "g7h8i9", "branch": "main"}
  ],
  "slo_name": "http-api-slo",
  "metrics": {
    "response_time_p50": 120.5,
    "response_time_p95": 380.2,
    "response_time_p99": 450.3,
    "error_rate": 0.019,
    "throughput_rps": 1523.4
  },
  "metadata": {
    "triggered_by": "github-actions",
    "pr": "1842",
    "test_tool": "k6",
    "vus": 50
  }
}
```

`→ 200 OK` (synchronous — push mode with 5 metrics is below async threshold)

### 17.6 Trigger Evaluation — File Mode (CSV)

`POST /evaluations/file` (multipart/form-data)

```
meta (application/json):
{
  "name": "network-saturation-test",
  "start": "2026-03-12T09:00:00Z",
  "end": "2026-03-12T09:20:00Z",
  "asset_name": "vm-ubuntu22-01",
  "slo_name": "network-test-slo",
  "results_format": "csv",
  "metadata": {
    "os": "ubuntu-22.04",
    "arch": "x64",
    "branch": "7.6"
  }
}

results_file (text/csv):
metric_name,value,aggregation
throughput_mbps,945.3,avg
packet_loss_pct,0.02,max
latency_p99_ms,12.4,p99
retransmit_rate,0.001,avg
```

Expected CSV format: `metric_name`, `value`, `aggregation` columns. The `metric_name` values must match indicator names in the referenced SLO.

### 17.7 Trigger Evaluation — File Mode (JMeter XML)

`POST /evaluations/file` (multipart/form-data)

```
meta (application/json):
{
  "name": "http-endurance-test",
  "start": "2026-03-12T08:00:00Z",
  "end": "2026-03-12T09:00:00Z",
  "asset_name": "vm-win-server-2019",
  "slo_name": "http-endurance-slo",
  "results_format": "jmeter",
  "metadata": {
    "os": "windows-server-2019",
    "arch": "x64"
  }
}

results_file: [JMeter .jtl XML file content]
```

The JMeter adapter extracts standard metrics from the `.jtl` file:
- `response_time_avg`, `response_time_p90`, `response_time_p95`, `response_time_p99`
- `error_rate` (errors / total samples)
- `throughput_rps`
- `bytes_per_second`

These extracted names must match indicator names in the SLO `objectives`.

### 17.8 Evaluation Result (Full Response)

`GET /evaluations/{id}` → `200 OK`

```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "name": "compilation-test",
  "status": "completed",
  "result": "pass",
  "score": 94.44,
  "start": "2026-03-12T10:00:00Z",
  "end": "2026-03-12T10:45:00Z",
  "slo_name": "compilation-test-windows",
  "slo_version": 2,
  "ingestion_mode": "pull",
  "adapter_used": "prometheus",
  "invalidated": false,
  "invalidation_note": null,
  "annotations": [
    {
      "id": "9a3b1c2d-...",
      "content": "Windows Defender signature update applied 90 min before test",
      "author": "ops-team",
      "category": "environment",
      "meta": {"defender_version": "1.383.1234.0"},
      "created_at": "2026-03-12T11:45:00Z"
    }
  ],
  "asset_snapshot": {
    "name": "vm-win11-01",
    "tags": {"os": "windows-11", "arch": "x64"},
    "primary_version": "7.6",
    "build_ref": "ci-7821",
    "components": []
  },
  "metadata": {
    "branch": "7.6",
    "build": "ci-7821",
    "triggered_by": "github-actions"
  },
  "compared_evaluation_ids": [
    "a1b2c3d4-...",
    "e5f6g7h8-...",
    "i9j0k1l2-..."
  ],
  "indicator_results": [
    {
      "metric": "compilation_duration_s",
      "display_name": "Compilation Duration (seconds)",
      "value": 42.1,
      "compared_value": 41.5,
      "change_absolute": 0.6,
      "change_relative_pct": 1.44,
      "aggregation": "avg",
      "status": "pass",
      "score": 3.0,
      "weight": 3,
      "key_sli": true,
      "pass_targets": [
        {"criteria": "<=+5%", "target_value": 43.575, "violated": false}
      ],
      "warning_targets": [
        {"criteria": "<=+15%", "target_value": 47.725, "violated": false}
      ]
    },
    {
      "metric": "cpu_usage_avg",
      "display_name": "CPU Usage (avg)",
      "value": 78.3,
      "compared_value": 71.2,
      "change_absolute": 7.1,
      "change_relative_pct": 9.97,
      "aggregation": "avg",
      "status": "warning",
      "score": 1.0,
      "weight": 2,
      "key_sli": false,
      "pass_targets": [
        {"criteria": "<=+10%", "target_value": 78.32, "violated": true},
        {"criteria": "<90",    "target_value": 90,    "violated": false}
      ],
      "warning_targets": null
    },
    {
      "metric": "memory_peak_mb",
      "display_name": "Peak Memory (MB)",
      "value": 1024.0,
      "compared_value": null,
      "aggregation": "max",
      "status": "pass",
      "score": 1.0,
      "weight": 1,
      "key_sli": false,
      "pass_targets": [
        {"criteria": "<2048", "target_value": 2048, "violated": false}
      ],
      "warning_targets": null
    }
  ],
  "created_at": "2026-03-12T10:46:03Z"
}
```

### 17.9 Create a New SLO Version

`PUT /slos/compilation-test-windows`

```json
{
  "slo_yaml": "spec_version: '1.0'\ncomparison:\n  ...\nobjectives:\n  - sli: compilation_duration_s\n    pass:\n      - criteria: [<=+3%]\n    ...",
  "notes": "Tightened compilation_duration threshold from +5% to +3% — baselines have stabilised after 6 weeks of data",
  "author": "jane.smith",
  "meta": {
    "review_status": "approved",
    "ticket": "PERF-421",
    "reviewed_by": "john.doe",
    "tags": ["windows", "compilation", "threshold-change"]
  }
}
```

`→ 201 Created`

```json
{
  "name": "compilation-test-windows",
  "version": 3,
  "author": "jane.smith",
  "notes": "Tightened compilation_duration threshold from +5% to +3%...",
  "meta": {"review_status": "approved", "ticket": "PERF-421"},
  "created_at": "2026-03-12T11:30:00Z"
}
```

Future evaluations referencing `slo_name: "compilation-test-windows"` will automatically use version 3. Evaluations that ran under version 1 or 2 are unaffected — their stored `slo_yaml`, `slo_version`, and results are immutable.

### 17.10 Add an Annotation to an Evaluation

`POST /evaluations/f47ac10b-58cc-4372-a567-0e02b2c3d479/annotations`

```json
{
  "content": "Windows Defender signature update (version 1.383.1234.0) was applied to this VM approximately 90 minutes before the test window. CPU spikes during definition update may explain the elevated cpu_usage_avg result.",
  "author": "ops-team",
  "category": "environment",
  "meta": {
    "defender_version": "1.383.1234.0",
    "update_time": "2026-03-12T08:30:00Z",
    "affects_baseline": false
  }
}
```

`→ 201 Created`

```json
{
  "id": "9a3b1c2d-...",
  "evaluation_id": "f47ac10b-...",
  "content": "Windows Defender signature update...",
  "author": "ops-team",
  "category": "environment",
  "meta": {"defender_version": "1.383.1234.0", "update_time": "...", "affects_baseline": false},
  "created_at": "2026-03-12T11:45:00Z"
}
```

The evaluation result (`pass`, score `94.44`) is unchanged. The annotation is visible in the evaluation detail view and in the UI as a contextual flag on the heatmap cell.

### 17.11 Invalidate an Evaluation

`PATCH /evaluations/f47ac10b-58cc-4372-a567-0e02b2c3d479`

```json
{
  "invalidated": true,
  "invalidation_note": "VM had a disk I/O spike due to antivirus scan during test window. Results are not representative."
}
```

`→ 200 OK` — updated evaluation with `invalidated: true`. Cache key `eval:{id}` and all affected trend/list keys are purged immediately.
