# Integration Test Redesign & Scale Seed Data

**Date:** 2026-04-03
**Status:** Approved

## Problem

Integration tests and dev seed data route almost everything through group-level SLO assignments.
Direct asset-to-SLO bindings are barely tested, which allowed the `trigger_batch` bug
(ignoring `slo_bindings` table) to ship undetected. Test entity names use random UUIDs,
making failures opaque. Additionally, the seed data doesn't reproduce the beta tester's
template explosion scenario (20+ SLOs x 8 SLIs per asset), which causes UI performance
and usability issues that need to be addressed in follow-up work.

## Goals

1. **Trim** hollow bootstrap assets (9 assets with zero evaluations)
2. **Add binding-test assets** covering all 4 binding paths with descriptive names
3. **Add scale-test asset** reproducing the beta tester's template explosion (24 SLOs x 8 SLIs, 90 days)
4. **New integration test file** testing binding resolution end-to-end through HTTP layer

## Non-goals

- UI fixes for heatmap performance or SLO tree grouping (separate work, this provides the data)
- Unifying the 4 binding tables (separate design in `trigger-batch-ignores-slo-bindings.md`)
- Changing the mock adapter's core architecture

---

## Section 1: Asset Inventory After Trim

### Kept (trimmed from 25 to 8)

| Asset | Group | Binding Type | Purpose |
|---|---|---|---|
| checkout-api | core-services | direct + group | E-commerce, existing |
| product-catalog | core-services | group | E-commerce, existing |
| user-service | core-services | group | E-commerce, existing |
| orders-db | data-tier | direct | E-commerce, existing |
| vm-prod-web-01 | vm-prod-web | group | VM monitoring, existing |
| vm-prod-web-02 | vm-prod-web | group | VM monitoring, existing |
| laptop-user-01 | office-laptops | group | Office process monitoring, existing |
| laptop-user-02 | office-laptops | group | Office process monitoring, existing |

### New: Binding test assets (4)

| Asset | Group | Binding Type | Purpose |
|---|---|---|---|
| direct-slo | -- | direct asset -> SLO | Tests direct assignment only |
| group-slo | binding-test-group | group -> SLO | Tests group-inherited SLO |
| group-template | template-test-group | group -> SLO group (template) | Tests template-generated SLOs |
| direct-template | -- | direct asset -> SLO group (template) | Tests direct template assignment |

### New: Scale test asset (1)

| Asset | Group | Binding Type | Purpose |
|---|---|---|---|
| lab-monitor-01 | lab-monitors | direct template x 3 | 3 templates, 24 SLOs x 8 SLIs, 90 days |

### Removed (9 assets)

vm-prod-web-03, vm-prod-web-04, vm-prod-web-05, vm-stg-web-01..05, bastion-host,
build-runner, payment-gateway, metrics-collector, log-aggregator, session-cache.

Associated asset groups to remove or update:
- `vm-stg-web` -- remove entirely
- `vm-prod-web` -- update members to 01-02 only
- `office-laptops` -- update members to 01-02 only
- `infra-production`, `infra-staging`, `infra-monitoring` -- remove if all members are gone

---

## Section 2: Binding Test SLI/SLO Design

Minimal dedicated entities for testing each binding path.

### SLI definition

```yaml
name: binding-test-sli
indicators:
  - response_time_ms
  - error_count
adapter_type: prometheus
```

### SLO definitions

| SLO Name | SLI | Criteria | Assigned To | Via |
|---|---|---|---|---|
| direct-health-slo | binding-test-sli | response_time < 500, error_count < 10 | direct-slo asset | direct asset assignment |
| group-health-slo | binding-test-sli | response_time < 500, error_count < 10 | binding-test-group | group SLO assignment |
| tmpl-health/$process | binding-test-sli | response_time < 500, error_count < 10 | template-test-group | SLO group assignment to group |
| dtmpl-health/$process | binding-test-sli | response_time < 500, error_count < 10 | direct-template asset | SLO group assignment to asset |

### Template SLO groups

| SLO Group | Template Pattern | Generates For | Result |
|---|---|---|---|
| tmpl-health-group | tmpl-health/$process | processes: [alpha, beta] | 2 SLOs |
| dtmpl-health-group | dtmpl-health/$process | processes: [gamma, delta] | 2 SLOs |

### Evaluation data

10 windows (same cadence as existing bootstrap), stable mock data. Enough to verify
evaluations run through each binding path, not to stress test.

---

## Section 3: Scale Test SLI/SLO Design

Reproduces the beta tester's template explosion pattern.

### SLI definition

```yaml
name: lab-process-sli
indicators (8):
  - cpu_pct
  - memory_mb
  - handles
  - io_bytes_sec
  - threads
  - gc_pause_ms
  - heap_mb
  - open_files
adapter_type: prometheus
```

### Three templates, 8 processes each

| SLO Group | Template Pattern | Processes | SLOs Generated |
|---|---|---|---|
| lab-health-group | lab-health/$proc | nginx, postgres, redis, kafka, etcd, vault, consul, grafana | 8 |
| lab-perf-group | lab-perf/$proc | same 8 | 8 |
| lab-resource-group | lab-resource/$proc | same 8 | 8 |

**Total: 24 SLOs x 8 SLIs = 192 indicator cells per evaluation column.**

All 3 groups assigned directly to `lab-monitor-01` asset.

### SLI thresholds

```
cpu_pct:       pass < 60,  warn < 80,  fail >= 80
memory_mb:     pass < 512, warn < 768, fail >= 768
handles:       pass < 500, warn < 750, fail >= 750
io_bytes_sec:  pass < 1e6, warn < 1.5e6, fail >= 1.5e6
threads:       pass < 200, warn < 300, fail >= 300
gc_pause_ms:   pass < 50,  warn < 75,  fail >= 75
heap_mb:       pass < 256, warn < 384, fail >= 384
open_files:    pass < 100, warn < 150, fail >= 150
```

---

## Section 4: 90-Day Walking Diagonal Data Pattern

One evaluation per day for 90 days. The fail/warn pattern walks diagonally across SLI rows
so every heatmap column has a unique fingerprint, preventing UI caching from hiding
performance issues.

### Pattern formula

```
Cycle length: 11 days (5 pass, 1 fail, 4 pass, 1 warn)

For each day d (0..89), for each SLI s (0..7):
  cycle_day = d % 11
  fail_sli  = (d // 11) % 8
  warn_sli  = ((d // 11) + 4) % 8   # offset by 4, never overlaps fail

  if cycle_day == 5 and s == fail_sli:
      value = fail_value
  elif cycle_day == 10 and s == warn_sli:
      value = warn_value
  else:
      value = stable_value
```

### Visual example (first 22 days, 8 SLIs)

```
         D1  D2  D3  D4  D5  D6  D7  D8  D9  D10 D11 D12 ... D17 ... D22
SLI-0:   ok  ok  ok  ok  ok  FAIL ok  ok  ok  ok  WARN ok      ok      ok
SLI-1:   ok  ok  ok  ok  ok  ok  ok  ok  ok  ok  ok   ok  ... FAIL ... ok
SLI-2:   ok  ok  ok  ok  ok  ok  ok  ok  ok  ok  ok   ok      ok      WARN
SLI-3:   ok  ok  ok  ok  ok  ok  ok  ok  ok  ok  ok   ok      ok      ok
SLI-4:   ok  ok  ok  ok  ok  ok  ok  ok  ok  ok  ok   ok  ... ok  ... ok
         (warn_sli offset +4 from fail_sli, so warn lands on SLI-4 in cycle 0)
...
```

### Data volume

90 days x 24 SLOs x 8 SLIs = 17,280 metric data points. Trivial to generate.

Each of the 8 processes gets identical metric shapes. The walking pattern applies per-SLO
(not per-process), so `lab-health/nginx` might fail on day 6 while `lab-perf/nginx` fails
on day 17.

### Mock scenario file

New file: `adapters/mock/scenarios/lab-process.yaml`

The CSV generator in `dev-start.sh` produces 90 daily windows with metric values
computed from the diagonal formula above.

---

## Section 5: Integration Tests

New file: `api/tests/db/test_binding_resolution.py`

Deterministic fixture names matching the binding-test assets. All tests go through the
HTTP layer (POST /evaluations, GET /assets/{name}/slo-assignments, etc.).

### Test scenarios

#### Direct assignment path
```
test_evaluate_direct_slo_assignment
  Setup: asset "direct-slo" + direct SLO assignment
  Assert: trigger returns evaluation, result references correct SLO
```

#### Group-inherited path
```
test_evaluate_group_slo_assignment
  Setup: asset "group-slo" in "binding-test-group", SLO assigned to group
  Assert: asset inherits SLO from group, trigger evaluates it
```

#### Template via group path
```
test_evaluate_group_template_assignment
  Setup: asset "group-template" in "template-test-group",
         SLO group assigned to group, generates 2 SLOs
  Assert: both template-generated SLOs discovered and evaluated
```

#### Template via direct asset path
```
test_evaluate_direct_template_assignment
  Setup: asset "direct-template", SLO group assigned directly to asset
  Assert: template-generated SLOs discovered and evaluated
```

#### Precedence: direct overrides group
```
test_direct_assignment_overrides_group
  Setup: asset in group, same SLO assigned both directly and via group
         (different datasources to distinguish)
  Assert: evaluation uses the direct assignment's datasource
```

#### Precedence: direct overrides template
```
test_direct_assignment_overrides_template
  Setup: asset with direct SLO assignment + template generating same SLO name
  Assert: evaluation uses the direct assignment, not the template-generated one
```

#### Mixed: all binding types discovered
```
test_mixed_binding_types_all_discovered
  Setup: asset with 1 direct SLO + 1 group SLO + 2 template SLOs (all different names)
  Assert: all 4 SLOs discovered and evaluated
```

### Fixture design

Each test creates its own isolated entities using deterministic names with a shared
test-run prefix to avoid collisions across parallel test runs:

```python
@pytest.fixture
async def direct_slo_scenario(client, prefix):
    """Asset with a single direct SLO assignment."""
    asset_name = f"{prefix}-direct-slo"
    slo_name = f"{prefix}-direct-health-slo"
    # ... create asset type, asset, datasource, SLI, SLO, assignment
    return asset_name, [slo_name]
```

The `prefix` fixture generates a short random hex string (8 chars) once per
test session. Names stay readable (`a3f8-direct-slo`) while avoiding
collisions if tests run in parallel. The scenario part of the name
(`direct-slo`, `group-template`) is always deterministic and descriptive.

---

## Section 6: Files Changed

### Bootstrap manifests (modify)
- `bootstrap_mock/manifests/assets.yaml` -- remove 9 hollow assets, add 5 new ones
- `bootstrap_mock/manifests/asset-groups.yaml` -- remove stg/infra groups, add new groups
- `bootstrap_mock/manifests/sli-definitions.yaml` -- add binding-test-sli, lab-process-sli
- `bootstrap_mock/manifests/slo-definitions.yaml` -- add 4 binding-test SLOs, 3 lab templates
- `bootstrap_mock/manifests/slo-groups.yaml` -- add 5 new SLO groups
- `bootstrap_mock/manifests/slo-assignments.yaml` -- update for trimmed + new assets
- `bootstrap_mock/manifests/slo-group-assignments.yaml` -- add template assignments

### Mock adapter (new)
- `adapters/mock/scenarios/lab-process.yaml` -- 90-day walking diagonal scenario

### Seed script (modify)
- `scripts/dev-start.sh` -- update asset/group references, add 90-day evaluation windows

### Integration tests (new)
- `api/tests/db/test_binding_resolution.py` -- 7 test scenarios

### Integration tests (modify)
- `api/tests/db/conftest.py` -- add `prefix` fixture if not present
