# TROPEK Domain Model Redesign

**Date:** 2026-03-14
**Status:** Draft — Section 1 (Domain Model) approved. Sections 2+ pending.
**Supersedes:** Sections 3, 4, 9 of `2026-03-12-quality-platform-design.md`

---

## 1. Background

The original Phase 1 design made two simplifications that are being reversed:

1. **SLI embedded in SLO YAML** — the `indicators:` block was merged into the SLO
   definition for deployment simplicity. Keptn's original design kept them separate,
   and this project restores that separation to enable reuse of SLI queries across
   multiple SLOs and different datasources.

2. **No permanent asset-to-SLO binding** — callers had to specify `slo_name` in
   every evaluation request. The new model allows assets and asset groups to have
   named bindings that the system resolves automatically at trigger time.

Additional changes driven by review of the existing chunk 3 implementation:
- Naming confusion between `start_time`/`end_time` (evaluation window) and
  `started_at` (job lifecycle) → renamed to `period_start`/`period_end`
- Status strings scattered as literals → extracted to `EvaluationStatus` constants
- `EvaluationRepository.get()` too generic → renamed to `get_by_id()`
- Baseline comparison used `scope_tags` in SLO YAML → removed; scoping is now
  handled naturally by relational links (`asset_id` + `slo_name` + `sli_name`)
- Annotations were append-only with delete-to-correct semantics → changed to
  editable in place (PATCH, `updated_at` tracking)

---

## 2. Design Principles

- **snake_case everywhere** — all YAML keys, JSON API fields, DB columns, Python
  identifiers. No camelCase exceptions. (`display_name` not `displayName`,
  `api_version` not `apiVersion`, `sli_name` not `sliRef`)
- **`display_name` always optional** — when omitted, UI falls back to `name`
- **Labels are a free dict** — no mandatory label keys defined by spec; users
  add whatever key-value pairs they need
- **Asset not Service** — `Asset` covers VMs, servers, containers, sensors,
  battery monitors. "Service" implies microservices only and is too narrow.
- **Naming inspired by OpenSLO v2alpha** — structural conventions (`api_version`,
  `kind`, `metadata`) borrowed from OpenSLO; evaluation semantics (comparison,
  pass/warning/fail, key_sli, weight, total_score) kept from Keptn 1.0 because
  OpenSLO has no equivalent concepts

---

## 3. Entity Reference

### 3.1 DataSource

A named pointer to a running adapter service instance. Names are unique across
the entire deployment. The DataSource entity tells TROPEK **where to send queries**;
the adapter service manages its own connection credentials internally via env vars.
TROPEK never stores or transmits connection credentials.

```
data_sources
  id            UUID          primary key
  name          TEXT          unique across the deployment
                              e.g. "prometheus-dc-a", "postgres-metrics-db1"
  display_name  TEXT          optional
  adapter_type  TEXT          "prometheus" | "postgres" | "influxdb"
  adapter_url   TEXT          adapter service endpoint
                              e.g. "http://adapter-prometheus-dc-a:8081"
  labels        JSONB         free key-value metadata
                              e.g. {"dc": "dc-a", "env": "production"}
  created_at    TIMESTAMPTZ
  updated_at    TIMESTAMPTZ
```

**Credential model:** Each adapter container is deployed with exactly one set of
credentials via env vars (Docker Compose / Docker secrets). Two databases with
different credentials = two adapter containers, two DataSource entries. This keeps
credentials out of the DB, out of HTTP requests, and scoped to the adapter process.

```yaml
# docker-compose.yml — adapter owns its credentials
adapter-postgres-db1:
  build: ./adapters/postgres
  environment:
    POSTGRES_DSN: "postgresql://user1:pass1@db1:5432/metrics"

adapter-postgres-db2:
  build: ./adapters/postgres
  environment:
    POSTGRES_DSN: "postgresql://user2:pass2@db2:5432/metrics"
```

```
DataSource "postgres-metrics-db1"  →  adapter_url: http://adapter-postgres-db1:8082
DataSource "postgres-metrics-db2"  →  adapter_url: http://adapter-postgres-db2:8083
```

**Access key (wishlist — not Phase 1):** When TROPEK calls `/query` on an adapter,
it may include `X-Adapter-Key: <token>` for the adapter to validate. The adapter
contract reserves this header. For Phase 1, internal Docker network trust is assumed.

---

### 3.2 SLI Definition

A named, versioned set of indicator queries for a specific adapter type.
Rows are immutable after insert (same versioning pattern as SLO).

```
sli_definitions
  id              UUID          primary key (unique per version row)
  name            TEXT          stable identifier  e.g. "linux-compilation-sli"
  display_name    TEXT          optional
  version         INTEGER       auto-incremented per name
  indicators      JSONB         {"indicator_name": "query_string", ...}
                                query strings are adapter-specific
                                (PromQL for prometheus, SQL for postgres)
  notes           TEXT          optional — what changed in this version
  author          TEXT          optional
  meta            JSONB         expandable metadata
  active          BOOLEAN       false = soft-deleted
  created_at      TIMESTAMPTZ
  UNIQUE (name, version)
```

**Indicator query format** (by adapter type):
```yaml
# prometheus adapter
indicators:
  response_time_p95: "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{instance=\"$vm_ip\"}[5m]))"
  cpu_usage_avg:     "avg_over_time(process_cpu_seconds_total{instance=\"$vm_ip\"}[$duration])"
  compilation_errors: "compilation_errors_total{instance=\"$vm_ip\"}"

# postgres adapter
indicators:
  compilation_p99: |
    SELECT percentile_cont(0.99) WITHIN GROUP (ORDER BY duration_ms)
    FROM compilation_runs
    WHERE vm_ip = '$vm_ip'
    AND started_at BETWEEN '$period_start' AND '$period_end'
```

Variable substitution (`$vm_ip`, `$duration`, `$period_start`, `$period_end`)
is resolved from evaluation request metadata at trigger time.

---

### 3.3 SLO Definition

A named, versioned set of objectives and scoring rules. **No `indicators:` block.**
SLI queries live entirely in the SLI definition. SLO objectives reference indicator
names; the actual queries are resolved at evaluation time via the SLI entity.

```
slo_definitions
  id              UUID          primary key (unique per version row)
  name            TEXT          stable identifier  e.g. "linux-compilation-slo"
  display_name    TEXT          optional
  version         INTEGER       auto-incremented per name
  slo_yaml        TEXT          objectives + comparison + total_score only
  notes           TEXT          optional
  author          TEXT          optional
  meta            JSONB         expandable metadata
  active          BOOLEAN       false = soft-deleted
  created_at      TIMESTAMPTZ
  UNIQUE (name, version)
```

---

### 3.4 Asset

Any named entity under test — VM, server, container, endpoint, sensor, or any
other measurable thing. Not restricted to software services.

```
assets
  id              UUID
  name            TEXT          unique, stable identifier  e.g. "vm-linux-01"
  display_name    TEXT          optional
  type            TEXT          "vm" | "server" | "container" | "endpoint" | "sensor"
  labels          JSONB         free key-value metadata
                                e.g. {"os": "linux", "arch": "x64", "dc": "dc-a"}
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ
```

---

### 3.5 Asset Groups

Named containers of assets. Supports group-of-groups for multi-tier structures
(e.g. "linux_boxes" inside "software_xyz").

```
asset_groups
  id              UUID
  name            TEXT          e.g. "linux_boxes", "software_xyz"
  display_name    TEXT          optional
  description     TEXT          optional
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ

asset_group_members             (assets inside a group)
  group_id        UUID → asset_groups
  asset_id        UUID → assets
  weight          FLOAT         default 1.0 — used for weighted group scoring

asset_group_links               (groups inside a group)
  parent_group_id UUID → asset_groups
  child_group_id  UUID → asset_groups
  weight          FLOAT         default 1.0
```

---

### 3.6 Binding Tables

Permanent named bindings that link an asset or group to a specific SLO + SLI +
DataSource triple. These are what the evaluation trigger resolves at runtime —
callers no longer need to specify which SLO/SLI to use.

```
asset_slo_links
  id                UUID
  link_name         TEXT        e.g. "vm-linux-01-compilation-check"
  asset_id          UUID → assets
  slo_name          TEXT        resolves to latest version at trigger time
  sli_name          TEXT        resolves to latest version at trigger time
  data_source_name  TEXT        → data_sources.name
  created_at        TIMESTAMPTZ

asset_group_slo_links
  id                UUID
  link_name         TEXT        e.g. "linux-boxes-compilation-check"
  group_id          UUID → asset_groups
  slo_name          TEXT
  sli_name          TEXT
  data_source_name  TEXT        → data_sources.name
  created_at        TIMESTAMPTZ
```

**`data_source_name` is at the binding level, not the SLI level.** This allows
the same SLI (same PromQL queries) to be used with different datasources across
different assets — e.g. `linux-compilation-sli` bound to `prometheus-dc-a` for
VMs in DC-A and `prometheus-dc-b` for VMs in DC-B. No SLI duplication required.

---

### 3.7 Evaluation (updated columns)

```
evaluations
  ...existing columns...

  -- renamed (were start_time / end_time — confused with job lifecycle started_at)
  period_start      TIMESTAMPTZ   the performance test window start
  period_end        TIMESTAMPTZ   the performance test window end

  -- new: SLI provenance alongside existing slo_name / slo_version
  sli_name          TEXT          nullable (null for push/file mode)
  sli_version       INTEGER       nullable — snapshot of version at trigger time
  data_source_name  TEXT          nullable — which datasource was used

  -- job lifecycle (unchanged)
  status            TEXT          see EvaluationStatus constants
  started_at        TIMESTAMPTZ   when the worker claimed this job
  ...
```

`EvaluationStatus` constants extracted to `api/app/modules/quality_gate/engine/constants.py`:
```python
class EvaluationStatus:
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    PARTIAL   = "partial"
```

`EvaluationRepository.get()` renamed to `get_by_id()`.

---

### 3.8 Evaluation Batch (new)

Groups all evaluations created by a single trigger call. When triggering an asset
group with multiple bindings, one batch is created containing all resulting
evaluation IDs.

```
evaluation_batches
  id              UUID
  status          TEXT          "pending" | "running" | "completed" | "partial" | "failed"
  trigger_params  JSONB         snapshot of what was requested
                                {group_name, binding_filter, period_start, period_end}
  evaluation_ids  UUID[]        all evaluations spawned by this trigger
  created_at      TIMESTAMPTZ
```

Trigger response (when group has 2 bindings × 2 VMs = 4 evaluations):
```json
{
  "batch_id": "uuid",
  "status": "pending",
  "evaluation_ids": ["uuid1", "uuid2", "uuid3", "uuid4"]
}
```

---

### 3.9 Evaluation Annotation (updated)

Annotations are now **editable in place** via PATCH. The append-only + delete-to-
correct model from the original spec is replaced with standard CRUD. An audit trail
is maintained via `created_at` + `updated_at` + `author`.

```
evaluation_annotations
  id              UUID
  evaluation_id   UUID → evaluations (CASCADE DELETE)
  content         TEXT          required — the note text, JIRA links, etc.
  author          TEXT          optional
  category        TEXT          optional free label e.g. "investigation", "environment"
  meta            JSONB         e.g. {"jira": "PERF-421", "jira_url": "https://..."}
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ   set on every PATCH
```

---

### 3.10 SLI Values (unchanged)

```
sli_values  (TimescaleDB hypertable, partitioned by eval_start)
  eval_id       UUID → evaluations
  eval_start    TIMESTAMPTZ   chunk key (= evaluation period_start)
  metric_name   TEXT
  aggregation   TEXT          "avg" | "p99" | "max" | "min" | "raw"
  value         DOUBLE PRECISION
  asset_name    TEXT          denormalised — avoids joins in Grafana SQL
  test_name     TEXT          denormalised
  os_tag        TEXT          denormalised
```

Denormalised columns are intentional. Grafana with PostgreSQL data source supports
JOINs, but denormalisation avoids join overhead on every panel refresh across
potentially millions of hypertable rows. Values are computed once at write time.

---

## 4. YAML Format

All YAML keys are snake_case. `display_name` is always optional.

### 4.1 DataSource YAML

```yaml
api_version: tropek/v1
kind: DataSource
metadata:
  name: prometheus-dc-a              # unique across the deployment
  display_name: "Prometheus DC-A"   # optional
  labels:
    dc: dc-a
    env: production
spec:
  adapter_type: prometheus
  adapter_url: "http://adapter-prometheus-dc-a:8081"
  # no connection_details — the adapter manages its own connection via env vars
```

The `name` in the DataSource YAML is the stable identifier used in SLI binding
tables (`data_source_name`). Renaming a DataSource requires updating all bindings
that reference it.

### 4.2 SLI YAML

```yaml
api_version: tropek/v1
kind: SLI
metadata:
  name: linux-compilation-sli
  display_name: "Linux Compilation Indicators"   # optional
  labels:
    os: linux
    test_type: compilation
spec:
  indicators:
    compilation_duration_s: "avg_over_time(compilation_duration_seconds{instance=\"$vm_ip\"}[5m])"
    cpu_usage_avg:           "avg_over_time(process_cpu_seconds_total{instance=\"$vm_ip\"}[$duration])"
    memory_peak_mb:          "max_over_time(process_resident_memory_bytes{instance=\"$vm_ip\"}[$duration]) / 1048576"
    compilation_errors:      "compilation_errors_total{instance=\"$vm_ip\"}"
```

### 4.3 SLO YAML

No `indicators:` block. Objectives reference indicator names defined in the
linked SLI entity via `sli_name` in each objective.

```yaml
api_version: tropek/v1
kind: SLO
metadata:
  name: linux-compilation-slo
  display_name: "Linux Compilation Quality Gate"   # optional
  labels:
    os: linux
    test_type: compilation
spec:
  comparison:
    compare_with: several_results
    number_of_comparison_results: 3
    include_result_with_score: pass_or_warn
    aggregate_function: avg
    # no scope_tags — baseline scoped naturally by asset_id + slo_name + sli_name
  objectives:
    - sli_name: compilation_errors
      display_name: "Compilation Errors"   # optional
      pass:
        - criteria: ["=0"]
      weight: 3
      key_sli: true
    - sli_name: compilation_duration_s
      display_name: "Compilation Duration"
      pass:
        - criteria: ["<=+5%"]
      warning:
        - criteria: ["<=+15%"]
      weight: 2
      key_sli: false
    - sli_name: cpu_usage_avg
      display_name: "CPU Usage"
      pass:
        - criteria: ["<=+10%", "<90"]
      weight: 1
    - sli_name: memory_peak_mb
      display_name: "Peak Memory (MB)"
      pass:
        - criteria: ["<2048"]
      weight: 1
  total_score:
    pass: "90%"
    warning: "75%"
```

**Scoring reminder:** `weight` values are arbitrary integers. The engine normalises
automatically: `score = (sum of achieved weights / sum of all weights) × 100`.
A `weight: 3` objective is three times as impactful as `weight: 1` — users do not
need to make weights sum to 100.

---

## 5. Baseline Comparison Model

The `scope_tags` field from the original design is **removed**. Baseline scoping
is handled entirely by relational links stored on the evaluation record.

When evaluating a relative criterion (`<=+10%`), the engine fetches previous
evaluations using:

```sql
SELECT sli_values.*
FROM sli_values
JOIN evaluations ON sli_values.eval_id = evaluations.id
WHERE evaluations.asset_id    = :current_asset_id     -- same asset (implicitly same OS/arch/etc)
  AND evaluations.slo_name    = :current_slo_name     -- same SLO
  AND evaluations.sli_name    = :current_sli_name     -- same SLI
  AND evaluations.status      = 'completed'
  AND evaluations.invalidated = false
  AND evaluations.result      IN (...)                -- based on include_result_with_score
ORDER BY evaluations.period_start DESC
LIMIT :number_of_comparison_results
```

A Linux VM (`asset_id = vm-linux-01`) can never accidentally pull in Windows VM
results because they have different `asset_id` values. No tag-level filtering
needed — the relational structure provides the correct scope.

---

## 6. Evaluation Trigger Flow (overview — detail in Section 2 TBD)

**Trigger for an asset group:**
```
POST /evaluations
{
  "group_name": "linux_boxes",
  "binding_name": null,              // null = run ALL bindings on the group
  "period_start": "2026-03-14T10:00:00Z",
  "period_end":   "2026-03-14T10:45:00Z",
  "metadata": {"branch": "7.6", "build": "ci-4521"}
}
```

With `binding_name` specified: runs only that one binding.
Without `binding_name`: runs all bindings registered on the group (and recursively
on any child groups).

Response: `202 Accepted` with `batch_id` + list of `evaluation_ids`.

---

## 7. Changes from Existing Implementation (Chunk 3)

| Location | Change |
|---|---|
| `api/app/db/models.py` | Rename `start_time`→`period_start`, `end_time`→`period_end` on `Evaluation` |
| `api/app/db/models.py` | Add `sli_name`, `sli_version`, `data_source_name` to `Evaluation` |
| `api/app/db/models.py` | Add `updated_at` to `EvaluationAnnotation` |
| `api/app/db/models.py` | Add new models: `DataSource`, `SLIDefinition`, `AssetGroup`, `AssetGroupMember`, `AssetGroupLink`, `AssetSLOLink`, `AssetGroupSLOLink`, `EvaluationBatch` |
| `api/app/modules/quality_gate/engine/constants.py` | Add `EvaluationStatus` class with string constants |
| `api/app/modules/quality_gate/repository.py` | Rename `get()` → `get_by_id()` |
| `api/app/modules/quality_gate/repository.py` | Replace all status string literals with `EvaluationStatus.*` constants |
| `api/app/modules/quality_gate/repository.py` | Baseline query: remove `scope_tags` logic, filter by `asset_id + slo_name + sli_name` |
| `api/app/modules/quality_gate/repository.py` | Status filter in baseline query: make `include_result_with_score` the only filter; remove hardcoded `status='completed'` assumption (heatmap needs all statuses) |
| `api/alembic/versions/` | New migration: add all new tables + rename columns + add indexes |
| `api/app/modules/slo_registry/` | Split into `slo_registry/` (SLO) and `sli_registry/` (SLI) modules |
| Adapter contract | No change to `/query` shape — adapter manages its own connection via env vars |

---

## 8. What Does NOT Change

- Evaluation engine pure function `evaluate(slo, metrics) → EvaluationResult` — no I/O, no changes
- SLO criteria syntax (`<=+10%`, `<600`, `=0`, `<=+50`) — unchanged
- `key_sli` veto behaviour — unchanged
- `sli_values` hypertable schema — unchanged
- Adapter `/query` + `/health` contract shape — extended, not replaced
- Redis + arq queue architecture — unchanged
- Config / secrets separation — unchanged
