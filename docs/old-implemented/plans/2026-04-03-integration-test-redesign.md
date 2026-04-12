# Integration Test Redesign & Scale Seed Data — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trim hollow bootstrap assets, add binding-test assets covering all 4 assignment paths, add a scale-test asset with 24 SLOs × 8 SLIs and 90 days of walking-diagonal data, and create integration tests for binding resolution through the HTTP layer.

**Architecture:** Bootstrap manifests define assets, SLIs, SLOs, groups, and assignments declaratively. The mock adapter generates CSV time-series from scenario YAML files. `scripts/bootstrap.py` applies manifests via the Python client, then `scripts/seed_evaluations.py` triggers evaluations window-by-window. Integration tests use httpx AsyncClient against the FastAPI app with a test DB session.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, pytest + pytest-asyncio, YAML manifests, CSV mock data generator.

**Spec:** `docs/superpowers/specs/2026-04-03-integration-test-redesign.md`

---

## File Structure

### Bootstrap manifests (modify)
- `bootstrap_mock/manifests/assets.yaml` — remove 9 hollow assets, add 5 new ones
- `bootstrap_mock/manifests/asset-groups.yaml` — remove stg/infra groups, trim members, add new groups
- `bootstrap_mock/manifests/sli-definitions.yaml` — add `binding-test-sli` and `lab-process-sli`
- `bootstrap_mock/manifests/slo-definitions.yaml` — add 4 binding-test SLOs + 3 lab template SLOs
- `bootstrap_mock/manifests/slo-groups.yaml` — add 5 new SLO groups
- `bootstrap_mock/manifests/slo-assignments.yaml` — remove stg assignment, add binding-test assignments
- `bootstrap_mock/manifests/slo-group-assignments.yaml` — add 5 template assignments

### Mock adapter (new)
- `adapters/mock/scenarios/lab-process.yaml` — 90-day walking diagonal scenario

### Seed script (modify)
- `scripts/seed_evaluations.py` — update asset list, add 90-day lab-monitor seeding

### Integration tests (new)
- `api/tests/db/test_binding_resolution.py` — 7 binding resolution test scenarios

---

## Task 1: Trim hollow assets from bootstrap manifests

**Files:**
- Modify: `bootstrap_mock/manifests/assets.yaml`
- Modify: `bootstrap_mock/manifests/asset-groups.yaml`
- Modify: `bootstrap_mock/manifests/slo-assignments.yaml`
- Modify: `scripts/seed_evaluations.py`

- [ ] **Step 1: Remove hollow assets from assets.yaml**

Remove these asset blocks from `bootstrap_mock/manifests/assets.yaml`:
- `catalog-db` (lines 65-79)
- `session-cache` (lines 80-94)
- `payment-gateway` (lines 96-107)
- `metrics-collector` (lines 108-122)
- `log-aggregator` (lines 124-137)
- `bastion-host` (lines 139-153)
- `build-runner` (lines 155-168)
- `vm-prod-web-03` (lines 202-216)
- `vm-prod-web-04` (lines 217-232)
- `vm-prod-web-05` (lines 233-248)
- `vm-stg-web-01` through `vm-stg-web-05` (lines 249-328)
- `laptop-user-03` (lines 360-373)
- `laptop-user-04` (lines 374-388)
- `laptop-user-05` (lines 389-403)

After trimming, 8 assets remain: checkout-api, product-catalog, user-service, orders-db, vm-prod-web-01, vm-prod-web-02, laptop-user-01, laptop-user-02.

- [ ] **Step 2: Update asset-groups.yaml**

Replace the entire file content with:

```yaml
# Groups with members and subgroups.
# Order matters: child groups must appear before parent groups that reference them.

api_version: tropek/v1
kind: AssetGroup
metadata:
  name: core-services
  display_name: Core Services
spec:
  members:
    - asset_name: checkout-api
      weight: 1.0
    - asset_name: product-catalog
      weight: 1.0
    - asset_name: user-service
      weight: 1.0
---
api_version: tropek/v1
kind: AssetGroup
metadata:
  name: data-tier
spec:
  members:
    - asset_name: orders-db
      weight: 1.0
---
api_version: tropek/v1
kind: AssetGroup
metadata:
  name: vm-prod-web
  display_name: Production Web VMs
spec:
  members:
    - asset_name: vm-prod-web-01
      weight: 1.0
    - asset_name: vm-prod-web-02
      weight: 1.0
---
api_version: tropek/v1
kind: AssetGroup
metadata:
  name: office-laptops
  display_name: Office Laptops
spec:
  members:
    - asset_name: laptop-user-01
      weight: 1.0
    - asset_name: laptop-user-02
      weight: 1.0
---
api_version: tropek/v1
kind: AssetGroup
metadata:
  name: ecommerce-prod
  display_name: E-Commerce Production
spec:
  subgroups:
    - group_name: core-services
      weight: 1.0
    - group_name: data-tier
      weight: 1.0
```

Removed groups: `infra-production`, `infra-staging`, `infra-monitoring`, `vm-stg-web`, `infrastructure`.

- [ ] **Step 3: Remove stale SLO assignment**

In `bootstrap_mock/manifests/slo-assignments.yaml`, remove the `vm-stg-web-health-assignment` block (lines 83-92):

```yaml
---
api_version: tropek/v1
kind: SLOAssignment
metadata:
  name: vm-stg-web-health-assignment
spec:
  target_type: asset_group
  target_name: vm-stg-web
  slo_name: vm-health-slo
  data_source_name: prometheus-local
```

- [ ] **Step 4: Update seed_evaluations.py asset list**

In `scripts/seed_evaluations.py`, replace the ASSETS list (lines 22-40) with:

```python
ASSETS = [
    # E-Commerce
    'checkout-api',
    'product-catalog',
    'user-service',
    'orders-db',
    # VM Infrastructure
    'vm-prod-web-01',
    'vm-prod-web-02',
    # Office Laptops
    'laptop-user-01',
    'laptop-user-02',
]
```

- [ ] **Step 5: Verify bootstrap still applies**

Run: `uv run --directory clients/python python ../../scripts/bootstrap.py "http://localhost:8080"` (if dev env is running) or just verify the YAML parses:

```bash
uv run python -c "import yaml; [yaml.safe_load_all(open(f'bootstrap_mock/manifests/{f}')) for f in ['assets.yaml','asset-groups.yaml','slo-assignments.yaml']]"
```

Expected: No YAML parse errors.

- [ ] **Step 6: Commit**

```bash
git add bootstrap_mock/manifests/assets.yaml bootstrap_mock/manifests/asset-groups.yaml bootstrap_mock/manifests/slo-assignments.yaml scripts/seed_evaluations.py
git commit -m "chore: trim 14 hollow bootstrap assets and stale groups"
```

---

## Task 2: Add binding-test SLI, SLOs, groups, and assignments

**Files:**
- Modify: `bootstrap_mock/manifests/assets.yaml`
- Modify: `bootstrap_mock/manifests/asset-groups.yaml`
- Modify: `bootstrap_mock/manifests/sli-definitions.yaml`
- Modify: `bootstrap_mock/manifests/slo-definitions.yaml`
- Modify: `bootstrap_mock/manifests/slo-groups.yaml`
- Modify: `bootstrap_mock/manifests/slo-assignments.yaml`
- Modify: `bootstrap_mock/manifests/slo-group-assignments.yaml`

- [ ] **Step 1: Add binding-test assets to assets.yaml**

Append to the end of `bootstrap_mock/manifests/assets.yaml`:

```yaml
---
# ---- Binding Test Assets ----
# Each tests a specific SLO assignment path.

api_version: tropek/v1
kind: Asset
metadata:
  name: direct-slo
  display_name: "Binding Test: Direct SLO"
  tags:
    purpose: binding-test
  variables:
    job: direct-slo
    namespace: binding-test
spec:
  type_name: service
---
api_version: tropek/v1
kind: Asset
metadata:
  name: group-slo
  display_name: "Binding Test: Group SLO"
  tags:
    purpose: binding-test
  variables:
    job: group-slo
    namespace: binding-test
spec:
  type_name: service
---
api_version: tropek/v1
kind: Asset
metadata:
  name: group-template
  display_name: "Binding Test: Group Template"
  tags:
    purpose: binding-test
  variables:
    job: group-template
    namespace: binding-test
spec:
  type_name: service
---
api_version: tropek/v1
kind: Asset
metadata:
  name: direct-template
  display_name: "Binding Test: Direct Template"
  tags:
    purpose: binding-test
  variables:
    job: direct-template
    namespace: binding-test
spec:
  type_name: service
```

- [ ] **Step 2: Add binding-test groups to asset-groups.yaml**

Append to the end of `bootstrap_mock/manifests/asset-groups.yaml`:

```yaml
---
# ---- Binding Test Groups ----

api_version: tropek/v1
kind: AssetGroup
metadata:
  name: binding-test-group
  display_name: Binding Test Group
spec:
  members:
    - asset_name: group-slo
      weight: 1.0
---
api_version: tropek/v1
kind: AssetGroup
metadata:
  name: template-test-group
  display_name: Template Test Group
spec:
  members:
    - asset_name: group-template
      weight: 1.0
```

- [ ] **Step 3: Add binding-test-sli to sli-definitions.yaml**

Append to the end of `bootstrap_mock/manifests/sli-definitions.yaml`:

```yaml
---
# ---- Binding Test SLI ----

api_version: tropek/v1
kind: SLI
metadata:
  name: binding-test-sli
  display_name: Binding Test Indicators
  author: bootstrap
  notes: Minimal SLI for binding resolution tests.
spec:
  adapter_type: prometheus
  indicators:
    response_time_ms: 'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{job="$job",namespace="$namespace"}[5m]))'
    error_count: 'increase(http_requests_total{job="$job",namespace="$namespace",status=~"5.."}[5m])'
```

- [ ] **Step 4: Add binding-test SLOs to slo-definitions.yaml**

Append to the end of `bootstrap_mock/manifests/slo-definitions.yaml`:

```yaml
---
# ---- Binding Test SLOs ----
# One standard SLO per direct binding path, two templates for group paths.

api_version: tropek/v1
kind: SLO
metadata:
  name: direct-health-slo
  display_name: "Direct Health SLO"
  author: bootstrap
  notes: Tests direct asset-to-SLO assignment path.
spec:
  sli_name: binding-test-sli
  sli_version: 1
  kind: standard
  total_score:
    pass_threshold: 90.0
    warning_threshold: 75.0
  objectives:
    - sli: response_time_ms
      display_name: "Response Time (ms)"
      pass_threshold: ["<500"]
      weight: 1
    - sli: error_count
      display_name: "Error Count"
      pass_threshold: ["<10"]
      weight: 1
---
api_version: tropek/v1
kind: SLO
metadata:
  name: group-health-slo
  display_name: "Group Health SLO"
  author: bootstrap
  notes: Tests group-inherited SLO assignment path.
spec:
  sli_name: binding-test-sli
  sli_version: 1
  kind: standard
  total_score:
    pass_threshold: 90.0
    warning_threshold: 75.0
  objectives:
    - sli: response_time_ms
      display_name: "Response Time (ms)"
      pass_threshold: ["<500"]
      weight: 1
    - sli: error_count
      display_name: "Error Count"
      pass_threshold: ["<10"]
      weight: 1
---
api_version: tropek/v1
kind: SLO
metadata:
  name: "tmpl-health/$__gen_process_name"
  display_name: "Template Health — $__gen_process_name"
  author: bootstrap
  notes: Tests template SLO via group assignment path.
spec:
  sli_name: binding-test-sli
  sli_version: 1
  kind: template
  variables:
    process_name: "$__gen_process_name"
  total_score:
    pass_threshold: 90.0
    warning_threshold: 75.0
  objectives:
    - sli: response_time_ms
      display_name: "Response Time (ms)"
      pass_threshold: ["<500"]
      weight: 1
    - sli: error_count
      display_name: "Error Count"
      pass_threshold: ["<10"]
      weight: 1
---
api_version: tropek/v1
kind: SLO
metadata:
  name: "dtmpl-health/$__gen_process_name"
  display_name: "Direct Template Health — $__gen_process_name"
  author: bootstrap
  notes: Tests template SLO via direct asset assignment path.
spec:
  sli_name: binding-test-sli
  sli_version: 1
  kind: template
  variables:
    process_name: "$__gen_process_name"
  total_score:
    pass_threshold: 90.0
    warning_threshold: 75.0
  objectives:
    - sli: response_time_ms
      display_name: "Response Time (ms)"
      pass_threshold: ["<500"]
      weight: 1
    - sli: error_count
      display_name: "Error Count"
      pass_threshold: ["<10"]
      weight: 1
```

- [ ] **Step 5: Add binding-test SLO groups to slo-groups.yaml**

Append to the end of `bootstrap_mock/manifests/slo-groups.yaml`:

```yaml
---
# ---- Binding Test SLO Groups ----

api_version: tropek/v1
kind: SLOGroup
metadata:
  name: tmpl-health-group
spec:
  display_name: Template Health Group
  template_slo_name: "tmpl-health/$__gen_process_name"
  template_slo_version: 1
  gen_variables:
    process_name: ["alpha", "beta"]
  tags:
    purpose: binding-test
---
api_version: tropek/v1
kind: SLOGroup
metadata:
  name: dtmpl-health-group
spec:
  display_name: Direct Template Health Group
  template_slo_name: "dtmpl-health/$__gen_process_name"
  template_slo_version: 1
  gen_variables:
    process_name: ["gamma", "delta"]
  tags:
    purpose: binding-test
```

- [ ] **Step 6: Add binding-test SLO assignments to slo-assignments.yaml**

Append to the end of `bootstrap_mock/manifests/slo-assignments.yaml`:

```yaml
---
# ---- Binding Test Assignments ----

api_version: tropek/v1
kind: SLOAssignment
metadata:
  name: direct-slo-health-assignment
spec:
  target_type: asset
  target_name: direct-slo
  slo_name: direct-health-slo
  data_source_name: prometheus-local
---
api_version: tropek/v1
kind: SLOAssignment
metadata:
  name: binding-test-group-health-assignment
spec:
  target_type: asset_group
  target_name: binding-test-group
  slo_name: group-health-slo
  data_source_name: prometheus-local
```

- [ ] **Step 7: Add binding-test SLO group assignments**

Append to the end of `bootstrap_mock/manifests/slo-group-assignments.yaml`:

```yaml
---
# ---- Binding Test SLO Group Assignments ----

api_version: tropek/v1
kind: SLOGroupAssignment
metadata:
  name: template-test-group-tmpl-assignment
spec:
  target_type: asset_group
  target_name: template-test-group
  slo_group_name: tmpl-health-group
  data_source_name: prometheus-local
---
api_version: tropek/v1
kind: SLOGroupAssignment
metadata:
  name: direct-template-dtmpl-assignment
spec:
  target_type: asset
  target_name: direct-template
  slo_group_name: dtmpl-health-group
  data_source_name: prometheus-local
```

- [ ] **Step 8: Verify YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
for f in sorted(Path('bootstrap_mock/manifests').glob('*.yaml')):
    list(yaml.safe_load_all(f.read_text()))
    print(f'OK: {f.name}')
"
```

Expected: All files print OK, no parse errors.

- [ ] **Step 9: Commit**

```bash
git add bootstrap_mock/manifests/
git commit -m "feat: add binding-test assets, SLIs, SLOs, groups, and assignments"
```

---

## Task 3: Add scale-test asset, SLI, SLOs, and groups

**Files:**
- Modify: `bootstrap_mock/manifests/assets.yaml`
- Modify: `bootstrap_mock/manifests/asset-groups.yaml`
- Modify: `bootstrap_mock/manifests/sli-definitions.yaml`
- Modify: `bootstrap_mock/manifests/slo-definitions.yaml`
- Modify: `bootstrap_mock/manifests/slo-groups.yaml`
- Modify: `bootstrap_mock/manifests/slo-group-assignments.yaml`

- [ ] **Step 1: Add lab-monitor-01 asset**

Append to the end of `bootstrap_mock/manifests/assets.yaml`:

```yaml
---
# ---- Scale Test Asset ----
# Reproduces beta tester's template explosion: 24 SLOs x 8 SLIs.

api_version: tropek/v1
kind: Asset
metadata:
  name: lab-monitor-01
  display_name: "Lab Monitor 01"
  tags:
    purpose: scale-test
    env: lab
  variables:
    job: lab-monitor
    namespace: lab
spec:
  type_name: service
```

- [ ] **Step 2: Add lab-monitors group**

Append to the end of `bootstrap_mock/manifests/asset-groups.yaml`:

```yaml
---
# ---- Scale Test Group ----

api_version: tropek/v1
kind: AssetGroup
metadata:
  name: lab-monitors
  display_name: Lab Monitors
spec:
  members:
    - asset_name: lab-monitor-01
      weight: 1.0
```

- [ ] **Step 3: Add lab-process-sli**

Append to the end of `bootstrap_mock/manifests/sli-definitions.yaml`:

```yaml
---
# ---- Scale Test SLI ----

api_version: tropek/v1
kind: SLI
metadata:
  name: lab-process-sli
  display_name: Lab Process Indicators
  author: bootstrap
  notes: 8-indicator SLI for scale testing template explosion scenarios.
spec:
  adapter_type: prometheus
  indicators:
    cpu_pct: 'rate(process_cpu_seconds_total{job="$job",process="$process_name"}[5m]) * 100'
    memory_mb: 'process_resident_memory_bytes{job="$job",process="$process_name"} / 1048576'
    handles: 'process_open_fds{job="$job",process="$process_name"}'
    io_bytes_sec: 'rate(process_io_bytes_total{job="$job",process="$process_name"}[5m])'
    threads: 'process_threads{job="$job",process="$process_name"}'
    gc_pause_ms: 'process_gc_pause_seconds_total{job="$job",process="$process_name"} * 1000'
    heap_mb: 'process_heap_bytes{job="$job",process="$process_name"} / 1048576'
    open_files: 'process_open_fds{job="$job",process="$process_name"}'
```

- [ ] **Step 4: Add 3 lab template SLOs**

Append to the end of `bootstrap_mock/manifests/slo-definitions.yaml`:

```yaml
---
# ---- Scale Test SLO Templates ----
# 3 templates x 8 processes = 24 generated SLOs, each with 8 indicators.

api_version: tropek/v1
kind: SLO
metadata:
  name: "lab-health/$__gen_process_name"
  display_name: "Lab Health — $__gen_process_name"
  author: bootstrap
  notes: Health thresholds for lab process monitoring (scale test).
spec:
  sli_name: lab-process-sli
  sli_version: 1
  kind: template
  variables:
    process_name: "$__gen_process_name"
  total_score:
    pass_threshold: 90.0
    warning_threshold: 75.0
  objectives:
    - sli: cpu_pct
      display_name: "CPU %"
      pass_threshold: ["<60"]
      warning_threshold: ["<80"]
      weight: 2
      key_sli: true
    - sli: memory_mb
      display_name: "Memory (MB)"
      pass_threshold: ["<512"]
      warning_threshold: ["<768"]
      weight: 2
    - sli: handles
      display_name: "Handles"
      pass_threshold: ["<500"]
      warning_threshold: ["<750"]
      weight: 1
    - sli: io_bytes_sec
      display_name: "I/O (bytes/s)"
      pass_threshold: ["<1000000"]
      warning_threshold: ["<1500000"]
      weight: 1
    - sli: threads
      display_name: "Threads"
      pass_threshold: ["<200"]
      warning_threshold: ["<300"]
      weight: 1
    - sli: gc_pause_ms
      display_name: "GC Pause (ms)"
      pass_threshold: ["<50"]
      warning_threshold: ["<75"]
      weight: 1
    - sli: heap_mb
      display_name: "Heap (MB)"
      pass_threshold: ["<256"]
      warning_threshold: ["<384"]
      weight: 1
    - sli: open_files
      display_name: "Open Files"
      pass_threshold: ["<100"]
      warning_threshold: ["<150"]
      weight: 1
---
api_version: tropek/v1
kind: SLO
metadata:
  name: "lab-perf/$__gen_process_name"
  display_name: "Lab Perf — $__gen_process_name"
  author: bootstrap
  notes: Performance thresholds for lab process monitoring (scale test).
spec:
  sli_name: lab-process-sli
  sli_version: 1
  kind: template
  variables:
    process_name: "$__gen_process_name"
  total_score:
    pass_threshold: 90.0
    warning_threshold: 75.0
  objectives:
    - sli: cpu_pct
      display_name: "CPU %"
      pass_threshold: ["<50"]
      warning_threshold: ["<70"]
      weight: 2
      key_sli: true
    - sli: memory_mb
      display_name: "Memory (MB)"
      pass_threshold: ["<400"]
      warning_threshold: ["<600"]
      weight: 2
    - sli: handles
      display_name: "Handles"
      pass_threshold: ["<400"]
      warning_threshold: ["<600"]
      weight: 1
    - sli: io_bytes_sec
      display_name: "I/O (bytes/s)"
      pass_threshold: ["<800000"]
      warning_threshold: ["<1200000"]
      weight: 1
    - sli: threads
      display_name: "Threads"
      pass_threshold: ["<150"]
      warning_threshold: ["<250"]
      weight: 1
    - sli: gc_pause_ms
      display_name: "GC Pause (ms)"
      pass_threshold: ["<40"]
      warning_threshold: ["<60"]
      weight: 1
    - sli: heap_mb
      display_name: "Heap (MB)"
      pass_threshold: ["<200"]
      warning_threshold: ["<320"]
      weight: 1
    - sli: open_files
      display_name: "Open Files"
      pass_threshold: ["<80"]
      warning_threshold: ["<120"]
      weight: 1
---
api_version: tropek/v1
kind: SLO
metadata:
  name: "lab-resource/$__gen_process_name"
  display_name: "Lab Resource — $__gen_process_name"
  author: bootstrap
  notes: Resource utilization thresholds for lab process monitoring (scale test).
spec:
  sli_name: lab-process-sli
  sli_version: 1
  kind: template
  variables:
    process_name: "$__gen_process_name"
  total_score:
    pass_threshold: 90.0
    warning_threshold: 75.0
  objectives:
    - sli: cpu_pct
      display_name: "CPU %"
      pass_threshold: ["<70"]
      warning_threshold: ["<85"]
      weight: 2
      key_sli: true
    - sli: memory_mb
      display_name: "Memory (MB)"
      pass_threshold: ["<600"]
      warning_threshold: ["<850"]
      weight: 2
    - sli: handles
      display_name: "Handles"
      pass_threshold: ["<600"]
      warning_threshold: ["<900"]
      weight: 1
    - sli: io_bytes_sec
      display_name: "I/O (bytes/s)"
      pass_threshold: ["<1200000"]
      warning_threshold: ["<1800000"]
      weight: 1
    - sli: threads
      display_name: "Threads"
      pass_threshold: ["<250"]
      warning_threshold: ["<350"]
      weight: 1
    - sli: gc_pause_ms
      display_name: "GC Pause (ms)"
      pass_threshold: ["<60"]
      warning_threshold: ["<90"]
      weight: 1
    - sli: heap_mb
      display_name: "Heap (MB)"
      pass_threshold: ["<300"]
      warning_threshold: ["<450"]
      weight: 1
    - sli: open_files
      display_name: "Open Files"
      pass_threshold: ["<120"]
      warning_threshold: ["<180"]
      weight: 1
```

- [ ] **Step 5: Add 3 lab SLO groups**

Append to the end of `bootstrap_mock/manifests/slo-groups.yaml`:

```yaml
---
# ---- Scale Test SLO Groups ----
# 3 groups x 8 processes = 24 generated SLOs.

api_version: tropek/v1
kind: SLOGroup
metadata:
  name: lab-health-group
spec:
  display_name: Lab Health Monitoring
  template_slo_name: "lab-health/$__gen_process_name"
  template_slo_version: 1
  gen_variables:
    process_name: ["nginx", "postgres", "redis", "kafka", "etcd", "vault", "consul", "grafana"]
  tags:
    purpose: scale-test
---
api_version: tropek/v1
kind: SLOGroup
metadata:
  name: lab-perf-group
spec:
  display_name: Lab Performance Monitoring
  template_slo_name: "lab-perf/$__gen_process_name"
  template_slo_version: 1
  gen_variables:
    process_name: ["nginx", "postgres", "redis", "kafka", "etcd", "vault", "consul", "grafana"]
  tags:
    purpose: scale-test
---
api_version: tropek/v1
kind: SLOGroup
metadata:
  name: lab-resource-group
spec:
  display_name: Lab Resource Monitoring
  template_slo_name: "lab-resource/$__gen_process_name"
  template_slo_version: 1
  gen_variables:
    process_name: ["nginx", "postgres", "redis", "kafka", "etcd", "vault", "consul", "grafana"]
  tags:
    purpose: scale-test
```

- [ ] **Step 6: Add lab SLO group assignments**

Append to the end of `bootstrap_mock/manifests/slo-group-assignments.yaml`:

```yaml
---
# ---- Scale Test SLO Group Assignments ----
# All 3 groups assigned directly to lab-monitor-01.

api_version: tropek/v1
kind: SLOGroupAssignment
metadata:
  name: lab-monitor-health-assignment
spec:
  target_type: asset
  target_name: lab-monitor-01
  slo_group_name: lab-health-group
  data_source_name: prometheus-local
---
api_version: tropek/v1
kind: SLOGroupAssignment
metadata:
  name: lab-monitor-perf-assignment
spec:
  target_type: asset
  target_name: lab-monitor-01
  slo_group_name: lab-perf-group
  data_source_name: prometheus-local
---
api_version: tropek/v1
kind: SLOGroupAssignment
metadata:
  name: lab-monitor-resource-assignment
spec:
  target_type: asset
  target_name: lab-monitor-01
  slo_group_name: lab-resource-group
  data_source_name: prometheus-local
```

- [ ] **Step 7: Verify YAML parses**

```bash
uv run python -c "
import yaml
from pathlib import Path
for f in sorted(Path('bootstrap_mock/manifests').glob('*.yaml')):
    list(yaml.safe_load_all(f.read_text()))
    print(f'OK: {f.name}')
"
```

Expected: All files print OK.

- [ ] **Step 8: Commit**

```bash
git add bootstrap_mock/manifests/
git commit -m "feat: add scale-test asset with 24 SLOs x 8 SLIs for UI stress testing"
```

---

## Task 4: Create 90-day walking diagonal mock scenario

**Files:**
- Create: `adapters/mock/scenarios/lab-process.yaml`

- [ ] **Step 1: Create the lab-process scenario YAML**

The mock generator uses phases to shape metric values over time. For the 90-day walking diagonal
pattern, we need 90 days = 2160 hours of data. The generator creates one data point per
`interval_minutes` (5 min default), but evaluations sample a window within that range.

The walking diagonal requires per-day control over which SLI fails/warns. The existing generator
only supports `stable`, `ramp`, and `spike` patterns — it cannot express "SLI X fails on day 6
but not day 7." We need to extend the generator or build the diagonal into the phase structure.

**Approach:** Build 90 days as 90 consecutive phases of 24 hours each. Each phase is `stable` at
either the pass value, fail value, or warn value depending on the diagonal formula. This is verbose
(90 phases × 8 metrics = 720 phase entries) but works with the existing generator without changes.

Instead, create a simpler approach: a new Python script that generates the lab-process CSV directly
using the diagonal formula, bypassing the scenario YAML entirely.

Create `adapters/mock/scenarios/lab-process.yaml` as a stub that the generator skips (or that
produces baseline data), and create `scripts/generate_lab_data.py` for the diagonal pattern.

Create file `scripts/generate_lab_data.py`:

```python
"""Generate 90-day walking diagonal CSV data for the lab-monitor scale test.

Each day produces one evaluation window (30 min). For 8 SLI metrics across
24 SLOs (3 templates x 8 processes), the fail/warn pattern walks diagonally
across SLI rows so every heatmap column has a unique fingerprint.

Pattern per 11-day cycle:
  Days 0-4: all pass
  Day 5: one SLI fails (walks to next SLI each cycle)
  Days 6-9: all pass
  Day 10: one SLI warns (offset +4 from fail SLI)

Output: adapters/mock/data/prometheus-local/lab-metrics.csv
Usage: uv run python scripts/generate_lab_data.py
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 8 metrics matching lab-process-sli indicators
METRICS = [
    ('cpu_pct', 30.0, 95.0, 70.0),        # (name, pass_val, fail_val, warn_val)
    ('memory_mb', 200.0, 900.0, 700.0),
    ('handles', 150.0, 900.0, 700.0),
    ('io_bytes_sec', 300000.0, 1800000.0, 1400000.0),
    ('threads', 80.0, 350.0, 280.0),
    ('gc_pause_ms', 20.0, 90.0, 70.0),
    ('heap_mb', 100.0, 450.0, 360.0),
    ('open_files', 40.0, 180.0, 140.0),
]

NUM_DAYS = 90
CYCLE_LEN = 11
FAIL_DAY = 5
WARN_DAY = 10
NUM_SLIS = len(METRICS)

# Start date: 90 days before 2026-03-15 (existing data start)
# so the lab data covers 2025-12-16 to 2026-03-15
START = datetime(2025, 12, 16, tzinfo=timezone.utc)
WINDOW_MINUTES = 30
INTERVAL_MINUTES = 5


def compute_value(day: int, sli_idx: int) -> tuple[str, float]:
    """Return (metric_name, value) for a given day and SLI index."""
    name, pass_val, fail_val, warn_val = METRICS[sli_idx]
    cycle_day = day % CYCLE_LEN
    fail_sli = (day // CYCLE_LEN) % NUM_SLIS
    warn_sli = ((day // CYCLE_LEN) + 4) % NUM_SLIS

    if cycle_day == FAIL_DAY and sli_idx == fail_sli:
        return name, fail_val
    if cycle_day == WARN_DAY and sli_idx == warn_sli:
        return name, warn_val
    return name, pass_val


def main() -> None:
    """Generate lab-metrics.csv with 90 days of walking diagonal data."""
    output_dir = Path('adapters/mock/data/prometheus-local')
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / 'lab-metrics.csv'

    rows: list[dict[str, str]] = []

    for day in range(NUM_DAYS):
        window_start = START + timedelta(days=day, hours=12)  # noon each day
        t = window_start

        while t < window_start + timedelta(minutes=WINDOW_MINUTES):
            for sli_idx in range(NUM_SLIS):
                metric_name, value = compute_value(day, sli_idx)
                rows.append({
                    'timestamp': t.isoformat(),
                    'metric_name': metric_name,
                    'value': f'{value:.6f}',
                })
            t += timedelta(minutes=INTERVAL_MINUTES)

    rows.sort(key=lambda r: (r['timestamp'], r['metric_name']))

    with csv_path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['timestamp', 'metric_name', 'value'])
        writer.writeheader()
        writer.writerows(rows)

    print(f'generated {csv_path} ({len(rows)} rows, {NUM_DAYS} days)')


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Run the generator and verify output**

```bash
uv run python scripts/generate_lab_data.py
```

Expected output: `generated adapters/mock/data/prometheus-local/lab-metrics.csv (NNNN rows, 90 days)`

Verify the CSV has the expected structure:

```bash
head -5 adapters/mock/data/prometheus-local/lab-metrics.csv
```

Expected: CSV with `timestamp,metric_name,value` header and data rows.

- [ ] **Step 3: Update dev-start.sh to run the lab data generator**

In `scripts/dev-start.sh`, find the line that runs the mock adapter generator (line 65-66):

```bash
uv run --directory adapters/mock python generate.py
```

Add the lab data generator call right after it. Find the exact line and add after:

```bash
uv run python scripts/generate_lab_data.py
```

- [ ] **Step 4: Update seed_evaluations.py to seed lab-monitor-01**

In `scripts/seed_evaluations.py`, add `lab-monitor-01` to the ASSETS list and update `get_eval_runs`
to handle its 90-day schedule.

Add to the ASSETS list:

```python
    # Scale Test
    'lab-monitor-01',
```

The existing 10-window WINDOWS list covers 48 hours. For 90 days we need a different approach.
Add a dedicated function and separate seeding loop. After the existing `main()` logic, add
lab-specific seeding.

Replace the `get_eval_runs` function to also handle lab assets:

```python
def get_eval_runs(asset_name: str) -> list[tuple[str, list[int]]]:
    """Return (evaluation_name, window_indices) pairs for this asset."""
    if asset_name == 'lab-monitor-01':
        return []  # handled separately in _seed_lab_monitor
    if 'laptop' in asset_name:
        return [('load-test', list(range(10)))]
    if 'vm-' in asset_name:
        return [
            ('user-experience', list(range(10))),
            ('optimization-testing', [0, 3, 6, 9]),
        ]
    # E-commerce + binding test assets
    return [
        ('load-test', list(range(10))),
        ('prod-validation', [0, 2, 4, 6, 8]),
    ]
```

Add the lab seeding function before `main()`:

```python
LAB_START = datetime.fromisoformat('2025-12-16T12:00:00+00:00')
LAB_DAYS = 90
LAB_WINDOW_MINUTES = 30


def _seed_lab_monitor(client: TropekClient) -> list[str]:
    """Seed 90 daily evaluations for lab-monitor-01."""
    all_ids: list[str] = []
    for day in range(LAB_DAYS):
        start = LAB_START + timedelta(days=day)
        end = start + timedelta(minutes=LAB_WINDOW_MINUTES)
        start_str = start.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_str = end.strftime('%Y-%m-%dT%H:%M:%SZ')

        print(f'  lab-monitor day {day + 1}/{LAB_DAYS} ({start_str})', end='\r', flush=True)
        result = client.evaluations.evaluate('lab-monitor-01', 'daily-lab', start_str, end_str)
        slo_ids = result['slo_evaluation_ids']
        _wait_for_ids(client, slo_ids, f'lab day {day + 1}')
        all_ids.extend(slo_ids)

    print()
    return all_ids
```

Add the `datetime` and `timedelta` imports at the top of the file:

```python
from datetime import datetime, timedelta
```

In `main()`, after the existing seeding loop and before the final summary, add:

```python
    # Seed lab-monitor-01 with 90 daily evaluations
    print('Seeding lab-monitor-01 (90 days)...')
    lab_ids = _seed_lab_monitor(client)
    all_slo_eval_ids.extend(lab_ids)
```

- [ ] **Step 5: Add binding-test assets to seed_evaluations.py ASSETS list**

Add the 4 binding-test assets to the ASSETS list so they get the standard 10-window treatment:

```python
ASSETS = [
    # E-Commerce
    'checkout-api',
    'product-catalog',
    'user-service',
    'orders-db',
    # VM Infrastructure
    'vm-prod-web-01',
    'vm-prod-web-02',
    # Office Laptops
    'laptop-user-01',
    'laptop-user-02',
    # Binding Tests
    'direct-slo',
    'group-slo',
    'group-template',
    'direct-template',
    # Scale Test (seeded separately)
    # 'lab-monitor-01',  — handled by _seed_lab_monitor
]
```

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_lab_data.py scripts/seed_evaluations.py scripts/dev-start.sh
git commit -m "feat: add 90-day walking diagonal mock data and lab-monitor seeding"
```

---

## Task 5: Write binding resolution integration tests

**Files:**
- Create: `api/tests/db/test_binding_resolution.py`

- [ ] **Step 1: Create test file with imports and fixtures**

Create `api/tests/db/test_binding_resolution.py`:

```python
"""Integration tests for SLO binding resolution across all 4 assignment paths.

Tests go through the HTTP layer to verify end-to-end binding discovery.
Each test creates isolated entities with a shared prefix for readability.

Requires TEST_DATABASE_URL and a running TimescaleDB instance.
Run: ./scripts/api-test.sh --tail 20 tests/db/test_binding_resolution.py -v -m integration
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from app.db.session import get_session
from app.main import app
from app.queue import get_arq_pool
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture()
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """Yield an httpx AsyncClient bound to the FastAPI app with test DB session."""

    async def _override_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    mock_pool = AsyncMock()
    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_arq_pool] = lambda: mock_pool
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def prefix() -> str:
    """Short random prefix for test entity names to avoid cross-test collisions."""
    return uuid.uuid4().hex[:6]


async def _create_base_entities(
    client: AsyncClient, prefix: str,
) -> tuple[str, str, str]:
    """Create asset type, datasource, and SLI shared across binding tests.

    Returns (type_name, ds_name, sli_name).
    """
    type_name = f'{prefix}-svc'
    resp = await client.post('/asset-types', json={'name': type_name})
    assert resp.status_code == 201

    ds_name = f'{prefix}-ds'
    resp = await client.post(
        '/datasources',
        json={'name': ds_name, 'adapter_type': 'mock', 'adapter_url': 'http://mock:8082'},
    )
    assert resp.status_code == 201

    sli_name = f'{prefix}-sli'
    resp = await client.post(
        '/sli-definitions',
        json={
            'name': sli_name,
            'adapter_type': 'mock',
            'indicators': {'metric_a': 'mock_query_a'},
        },
    )
    assert resp.status_code == 201

    return type_name, ds_name, sli_name


async def _create_slo(
    client: AsyncClient, slo_name: str, sli_name: str, kind: str = 'standard',
    variables: dict | None = None,
) -> str:
    """Create an SLO definition and return its ID."""
    body: dict = {
        'name': slo_name,
        'sli_name': sli_name,
        'sli_version': 1,
        'total_score_pass_threshold': 90.0,
        'total_score_warning_threshold': 75.0,
        'objectives': [{'sli': 'metric_a', 'pass_threshold': ['<100']}],
    }
    if kind != 'standard':
        body['kind'] = kind
    if variables:
        body['variables'] = variables
    resp = await client.post('/slo-definitions', json=body)
    assert resp.status_code == 201
    return resp.json()['id']


async def _create_asset(client: AsyncClient, name: str, type_name: str) -> None:
    """Create an asset."""
    resp = await client.post('/assets', json={'name': name, 'type_name': type_name})
    assert resp.status_code == 201


async def _create_group_with_member(
    client: AsyncClient, group_name: str, asset_name: str,
) -> None:
    """Create an asset group and add one member."""
    resp = await client.post('/asset-groups', json={'name': group_name})
    assert resp.status_code == 201
    resp = await client.post(
        f'/asset-groups/{group_name}/members',
        json={'asset_name': asset_name, 'weight': 1.0},
    )
    assert resp.status_code == 201


async def _evaluate(client: AsyncClient, asset_name: str) -> tuple[int, dict]:
    """Trigger evaluation and return (status_code, response_body)."""
    resp = await client.post(
        '/evaluate',
        json={
            'asset_name': asset_name,
            'eval_name': 'binding-test',
            'period_start': '2026-01-15T00:00:00Z',
            'period_end': '2026-01-15T23:59:59Z',
        },
    )
    return resp.status_code, resp.json()
```

- [ ] **Step 2: Add test_evaluate_direct_slo_assignment**

Append to `api/tests/db/test_binding_resolution.py`:

```python
# ---------------------------------------------------------------------------
# Test: Direct asset → SLO assignment
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_evaluate_direct_slo_assignment(
    async_client: AsyncClient, prefix: str,
) -> None:
    """Asset with direct SLO assignment — evaluation discovers the SLO."""
    type_name, ds_name, sli_name = await _create_base_entities(async_client, prefix)

    asset_name = f'{prefix}-direct-slo'
    await _create_asset(async_client, asset_name, type_name)

    slo_name = f'{prefix}-direct-health'
    slo_id = await _create_slo(async_client, slo_name, sli_name)

    resp = await async_client.post(
        f'/assets/{asset_name}/slo-assignments',
        json={'slo_definition_id': slo_id, 'data_source_name': ds_name},
    )
    assert resp.status_code == 201

    status, body = await _evaluate(async_client, asset_name)

    assert status == 201
    assert len(body['slo_evaluation_ids']) == 1
```

- [ ] **Step 3: Run test to verify it passes**

```bash
./scripts/api-test.sh --tail 20 tests/db/test_binding_resolution.py::test_evaluate_direct_slo_assignment -v -m integration
```

Expected: 1 passed.

- [ ] **Step 4: Add test_evaluate_group_slo_assignment**

Append to the test file:

```python
# ---------------------------------------------------------------------------
# Test: Group → SLO assignment (asset inherits from group)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_evaluate_group_slo_assignment(
    async_client: AsyncClient, prefix: str,
) -> None:
    """Asset in group — SLO assigned to group is discovered for the asset."""
    type_name, ds_name, sli_name = await _create_base_entities(async_client, prefix)

    asset_name = f'{prefix}-group-slo'
    await _create_asset(async_client, asset_name, type_name)

    group_name = f'{prefix}-grp'
    await _create_group_with_member(async_client, group_name, asset_name)

    slo_name = f'{prefix}-group-health'
    slo_id = await _create_slo(async_client, slo_name, sli_name)

    resp = await async_client.post(
        f'/asset-groups/{group_name}/slo-assignments',
        json={'slo_definition_id': slo_id, 'data_source_name': ds_name},
    )
    assert resp.status_code == 201

    status, body = await _evaluate(async_client, asset_name)

    assert status == 201
    assert len(body['slo_evaluation_ids']) == 1
```

- [ ] **Step 5: Add test_evaluate_group_template_assignment**

Append to the test file:

```python
# ---------------------------------------------------------------------------
# Test: Group → SLO group (template) assignment
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_evaluate_group_template_assignment(
    async_client: AsyncClient, prefix: str,
) -> None:
    """SLO group assigned to asset group — template-generated SLOs discovered."""
    type_name, ds_name, sli_name = await _create_base_entities(async_client, prefix)

    asset_name = f'{prefix}-group-tmpl'
    await _create_asset(async_client, asset_name, type_name)

    group_name = f'{prefix}-tmpl-grp'
    await _create_group_with_member(async_client, group_name, asset_name)

    # Create template SLO + SLO group that generates 2 SLOs
    tpl_slo_name = f'{prefix}-tpl/$__gen_proc'
    await _create_slo(
        async_client, tpl_slo_name, sli_name,
        kind='template', variables={'proc': '$__gen_proc'},
    )

    resp = await async_client.post(
        '/slo-groups',
        json={
            'name': f'{prefix}-sg',
            'template_slo_name': tpl_slo_name,
            'template_slo_version': 1,
            'gen_variables': {'proc': ['alpha', 'beta']},
        },
    )
    assert resp.status_code == 201

    resp = await async_client.post(
        f'/asset-groups/{group_name}/slo-group-assignments',
        json={'slo_group_name': f'{prefix}-sg', 'data_source_name': ds_name},
    )
    assert resp.status_code == 201

    status, body = await _evaluate(async_client, asset_name)

    assert status == 201
    assert len(body['slo_evaluation_ids']) == 2
```

- [ ] **Step 6: Add test_evaluate_direct_template_assignment**

Append to the test file:

```python
# ---------------------------------------------------------------------------
# Test: Direct asset → SLO group (template) assignment
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_evaluate_direct_template_assignment(
    async_client: AsyncClient, prefix: str,
) -> None:
    """SLO group assigned directly to asset — template-generated SLOs discovered."""
    type_name, ds_name, sli_name = await _create_base_entities(async_client, prefix)

    asset_name = f'{prefix}-direct-tmpl'
    await _create_asset(async_client, asset_name, type_name)

    tpl_slo_name = f'{prefix}-dtpl/$__gen_proc'
    await _create_slo(
        async_client, tpl_slo_name, sli_name,
        kind='template', variables={'proc': '$__gen_proc'},
    )

    resp = await async_client.post(
        '/slo-groups',
        json={
            'name': f'{prefix}-dsg',
            'template_slo_name': tpl_slo_name,
            'template_slo_version': 1,
            'gen_variables': {'proc': ['gamma', 'delta']},
        },
    )
    assert resp.status_code == 201

    resp = await async_client.post(
        f'/assets/{asset_name}/slo-group-assignments',
        json={'slo_group_name': f'{prefix}-dsg', 'data_source_name': ds_name},
    )
    assert resp.status_code == 201

    status, body = await _evaluate(async_client, asset_name)

    assert status == 201
    assert len(body['slo_evaluation_ids']) == 2
```

- [ ] **Step 7: Add test_direct_assignment_overrides_group**

Append to the test file:

```python
# ---------------------------------------------------------------------------
# Test: Precedence — direct asset assignment wins over group assignment
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_direct_assignment_overrides_group(
    async_client: AsyncClient, prefix: str,
) -> None:
    """Same SLO name assigned both directly and via group — direct wins."""
    type_name, ds_name, sli_name = await _create_base_entities(async_client, prefix)

    # Create a second datasource to distinguish which assignment wins
    ds2_name = f'{prefix}-ds2'
    resp = await async_client.post(
        '/datasources',
        json={'name': ds2_name, 'adapter_type': 'mock', 'adapter_url': 'http://mock:8082'},
    )
    assert resp.status_code == 201

    asset_name = f'{prefix}-precedence'
    await _create_asset(async_client, asset_name, type_name)

    group_name = f'{prefix}-prec-grp'
    await _create_group_with_member(async_client, group_name, asset_name)

    slo_name = f'{prefix}-prec-slo'
    slo_id = await _create_slo(async_client, slo_name, sli_name)

    # Assign to group with ds1
    resp = await async_client.post(
        f'/asset-groups/{group_name}/slo-assignments',
        json={'slo_definition_id': slo_id, 'data_source_name': ds_name},
    )
    assert resp.status_code == 201

    # Assign directly to asset with ds2 — should win
    resp = await async_client.post(
        f'/assets/{asset_name}/slo-assignments',
        json={'slo_definition_id': slo_id, 'data_source_name': ds2_name},
    )
    assert resp.status_code == 201

    status, body = await _evaluate(async_client, asset_name)

    assert status == 201
    # Only 1 SLO evaluation (deduplicated by name, direct wins)
    assert len(body['slo_evaluation_ids']) == 1
```

- [ ] **Step 8: Add test_direct_assignment_overrides_template**

Append to the test file:

```python
# ---------------------------------------------------------------------------
# Test: Precedence — direct assignment wins over template-generated
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_direct_assignment_overrides_template(
    async_client: AsyncClient, prefix: str,
) -> None:
    """Direct SLO assignment overrides template-generated SLO with same name."""
    type_name, ds_name, sli_name = await _create_base_entities(async_client, prefix)

    ds2_name = f'{prefix}-ds-ot'
    resp = await async_client.post(
        '/datasources',
        json={'name': ds2_name, 'adapter_type': 'mock', 'adapter_url': 'http://mock:8082'},
    )
    assert resp.status_code == 201

    asset_name = f'{prefix}-tmpl-override'
    await _create_asset(async_client, asset_name, type_name)

    # Create template that generates SLO named "<prefix>-ot/alpha"
    tpl_slo_name = f'{prefix}-ot/$__gen_proc'
    await _create_slo(
        async_client, tpl_slo_name, sli_name,
        kind='template', variables={'proc': '$__gen_proc'},
    )

    resp = await async_client.post(
        '/slo-groups',
        json={
            'name': f'{prefix}-ot-sg',
            'template_slo_name': tpl_slo_name,
            'template_slo_version': 1,
            'gen_variables': {'proc': ['alpha']},
        },
    )
    assert resp.status_code == 201

    # Assign template group to asset
    resp = await async_client.post(
        f'/assets/{asset_name}/slo-group-assignments',
        json={'slo_group_name': f'{prefix}-ot-sg', 'data_source_name': ds_name},
    )
    assert resp.status_code == 201

    # Create a direct SLO with the SAME name the template generates
    generated_name = f'{prefix}-ot/alpha'
    direct_slo_id = await _create_slo(async_client, generated_name, sli_name)

    resp = await async_client.post(
        f'/assets/{asset_name}/slo-assignments',
        json={'slo_definition_id': direct_slo_id, 'data_source_name': ds2_name},
    )
    assert resp.status_code == 201

    status, body = await _evaluate(async_client, asset_name)

    assert status == 201
    # Only 1 evaluation — direct overrides template for same name
    assert len(body['slo_evaluation_ids']) == 1
```

- [ ] **Step 9: Add test_mixed_binding_types_all_discovered**

Append to the test file:

```python
# ---------------------------------------------------------------------------
# Test: Mixed — all 4 binding types with different SLO names
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_mixed_binding_types_all_discovered(
    async_client: AsyncClient, prefix: str,
) -> None:
    """Asset with direct SLO + group SLO + template SLOs — all discovered."""
    type_name, ds_name, sli_name = await _create_base_entities(async_client, prefix)

    asset_name = f'{prefix}-mixed'
    await _create_asset(async_client, asset_name, type_name)

    group_name = f'{prefix}-mix-grp'
    await _create_group_with_member(async_client, group_name, asset_name)

    # 1) Direct SLO assignment
    direct_slo_name = f'{prefix}-mix-direct'
    direct_slo_id = await _create_slo(async_client, direct_slo_name, sli_name)
    resp = await async_client.post(
        f'/assets/{asset_name}/slo-assignments',
        json={'slo_definition_id': direct_slo_id, 'data_source_name': ds_name},
    )
    assert resp.status_code == 201

    # 2) Group SLO assignment (different name)
    group_slo_name = f'{prefix}-mix-group'
    group_slo_id = await _create_slo(async_client, group_slo_name, sli_name)
    resp = await async_client.post(
        f'/asset-groups/{group_name}/slo-assignments',
        json={'slo_definition_id': group_slo_id, 'data_source_name': ds_name},
    )
    assert resp.status_code == 201

    # 3) Template via group — generates 2 SLOs
    tpl_name = f'{prefix}-mix-tpl/$__gen_proc'
    await _create_slo(
        async_client, tpl_name, sli_name,
        kind='template', variables={'proc': '$__gen_proc'},
    )
    resp = await async_client.post(
        '/slo-groups',
        json={
            'name': f'{prefix}-mix-sg',
            'template_slo_name': tpl_name,
            'template_slo_version': 1,
            'gen_variables': {'proc': ['one', 'two']},
        },
    )
    assert resp.status_code == 201
    resp = await async_client.post(
        f'/asset-groups/{group_name}/slo-group-assignments',
        json={'slo_group_name': f'{prefix}-mix-sg', 'data_source_name': ds_name},
    )
    assert resp.status_code == 201

    status, body = await _evaluate(async_client, asset_name)

    assert status == 201
    # 1 direct + 1 group + 2 template = 4 SLO evaluations
    assert len(body['slo_evaluation_ids']) == 4
```

- [ ] **Step 10: Run all binding resolution tests**

```bash
./scripts/api-test.sh --tail 30 tests/db/test_binding_resolution.py -v -m integration
```

Expected: 7 passed.

- [ ] **Step 11: Run full integration test suite to check for regressions**

```bash
./scripts/api-test.sh --tail 10 -m integration -v
```

Expected: All tests pass (existing + new).

- [ ] **Step 12: Commit**

```bash
git add api/tests/db/test_binding_resolution.py
git commit -m "test: add integration tests for all 4 SLO binding resolution paths"
```

---

## Task 6: Final verification

- [ ] **Step 1: Run all API unit tests**

```bash
./scripts/api-test.sh --tail 5
```

Expected: All pass (unit tests don't touch manifests).

- [ ] **Step 2: Run all integration tests**

```bash
./scripts/api-test.sh --tail 10 -m integration -v
```

Expected: All pass including the 7 new binding tests.

- [ ] **Step 3: Verify YAML manifests parse cleanly**

```bash
uv run python -c "
import yaml
from pathlib import Path
total = 0
for f in sorted(Path('bootstrap_mock/manifests').glob('*.yaml')):
    docs = list(yaml.safe_load_all(f.read_text()))
    total += len(docs)
    print(f'OK: {f.name} ({len(docs)} docs)')
print(f'Total: {total} manifest documents')
"
```

Expected: All files OK, ~40+ manifest documents total.

- [ ] **Step 4: Verify lab data generator runs**

```bash
uv run python scripts/generate_lab_data.py
```

Expected: CSV generated with ~4320 rows (90 days × 6 windows/day × 8 metrics).

- [ ] **Step 5: Commit any final adjustments**

If any fixes were needed, commit them:

```bash
git add -A
git commit -m "fix: address issues found during final verification"
```
