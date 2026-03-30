# Aggregated-Mode E2E Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add end-to-end test coverage for aggregated-mode SLI evaluations through the full TROPEK stack (manifest → API → worker → mock adapter → results).

**Architecture:** Extend the existing mock bootstrap manifests with an aggregated-mode SLI definition, a matching SLO, and an SLO link. Fix the manifest reconciler to pass aggregated-mode fields. Add an e2e test that triggers an aggregated-mode evaluation and verifies the `{sli}.{method}` result keys and metadata. Also update the Python client model to include the new fields.

**Tech Stack:** Python 3.13, Pydantic, httpx, YAML manifests, mock adapter (FastAPI)

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `clients/python/tropek_client/models.py` | Modify | Add `mode`, `query_template`, `interval`, `methods` to `SLIDefinition` |
| `clients/python/tropek_client/manifest.py` | Modify | Pass aggregated-mode fields in `_create`, `_update`, `_has_diff` for SLI kind |
| `bootstrap_mock/manifests/sli-definitions.yaml` | Modify | Add `agg-latency-sli` aggregated-mode SLI definition |
| `bootstrap_mock/manifests/slo-definitions.yaml` | Modify | Add `agg-latency-slo` SLO with `{sli}.{method}` objectives |
| `bootstrap_mock/manifests/slo-links.yaml` | Modify | Add SLO link binding `checkout-api` to the new aggregated SLO |
| `scripts/e2e_tests.py` | Modify | Add `test_aggregated_evaluation` test function |

---

### Task 1: Add aggregated-mode fields to Python client SLIDefinition model

The `SLIDefinition` Pydantic model in the Python client currently lacks `mode`, `query_template`, `interval`, and `methods` fields. The API already returns these fields (added in Phase 1a), but the client model silently drops them. We need to add them so that `_has_diff` in the manifest reconciler can compare them.

**Files:**
- Modify: `clients/python/tropek_client/models.py:93-107`

- [ ] **Step 1: Add the four new fields to `SLIDefinition`**

In `clients/python/tropek_client/models.py`, add four fields to the `SLIDefinition` class after the `indicators` field:

```python
class SLIDefinition(BaseModel):
    """SLI definition."""

    id: uuid.UUID
    name: str
    display_name: str | None
    version: int
    indicators: dict[str, str]
    mode: str = 'raw'
    query_template: str | None = None
    interval: str | None = None
    methods: list[str] | None = None
    notes: str | None
    author: str | None
    tags: dict[str, Any]
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

All four fields have defaults so existing raw-mode SLI definitions (which don't include these fields in older API responses) continue to work.

- [ ] **Step 2: Commit**

```bash
git add clients/python/tropek_client/models.py
git commit -m "feat(client): add aggregated-mode fields to SLIDefinition model"
```

---

### Task 2: Update manifest reconciler to handle aggregated-mode SLI fields

The manifest `_create` and `_update` functions for `SLI` kind only pass `indicators` and metadata fields. For aggregated-mode SLIs, we also need to pass `mode`, `query_template`, `interval`, and `methods`. The `_has_diff` function also needs to compare these fields.

**Files:**
- Modify: `clients/python/tropek_client/manifest.py:339-341` (`_has_diff` SLI case)
- Modify: `clients/python/tropek_client/manifest.py:444-452` (`_create` SLI case)
- Modify: `clients/python/tropek_client/manifest.py:515-524` (`_update` SLI case)

- [ ] **Step 1: Update `_has_diff` for SLI kind**

In `clients/python/tropek_client/manifest.py`, find the `_has_diff` function's SLI case (around line 339):

```python
        case "SLI":
            return doc.spec.get("indicators") != getattr(existing, "indicators", {})
```

Replace it with:

```python
        case "SLI":
            return (
                doc.spec.get("indicators", {}) != getattr(existing, "indicators", {})
                or doc.spec.get("mode", "raw") != getattr(existing, "mode", "raw")
                or doc.spec.get("query_template") != getattr(existing, "query_template", None)
                or doc.spec.get("interval") != getattr(existing, "interval", None)
                or doc.spec.get("methods") != getattr(existing, "methods", None)
            )
```

- [ ] **Step 2: Update `_create` for SLI kind**

In the same file, find the `_create` function's SLI case (around line 444):

```python
        case "SLI":
            client.sli_definitions.create(
                name,
                indicators=doc.spec["indicators"],
                adapter_type=doc.spec.get("adapter_type", "prometheus"),
                display_name=doc.metadata.get("display_name"),
                notes=doc.metadata.get("notes"),
                author=doc.metadata.get("author"),
            )
```

Replace it with:

```python
        case "SLI":
            client.sli_definitions.create(
                name,
                indicators=doc.spec.get("indicators", {}),
                adapter_type=doc.spec.get("adapter_type", "prometheus"),
                display_name=doc.metadata.get("display_name"),
                notes=doc.metadata.get("notes"),
                author=doc.metadata.get("author"),
                mode=doc.spec.get("mode", "raw"),
                query_template=doc.spec.get("query_template"),
                interval=doc.spec.get("interval"),
                methods=doc.spec.get("methods"),
            )
```

Note: `indicators` changed from `doc.spec["indicators"]` (KeyError on aggregated mode) to `doc.spec.get("indicators", {})`.

- [ ] **Step 3: Update `_update` for SLI kind**

In the same file, find the `_update` function's SLI case (around line 515):

```python
        case "SLI":
            # Creates new version
            client.sli_definitions.create(
                name,
                indicators=doc.spec["indicators"],
                adapter_type=doc.spec.get("adapter_type", "prometheus"),
                display_name=doc.metadata.get("display_name"),
                notes=doc.metadata.get("notes"),
                author=doc.metadata.get("author"),
            )
```

Replace it with:

```python
        case "SLI":
            # Creates new version
            client.sli_definitions.create(
                name,
                indicators=doc.spec.get("indicators", {}),
                adapter_type=doc.spec.get("adapter_type", "prometheus"),
                display_name=doc.metadata.get("display_name"),
                notes=doc.metadata.get("notes"),
                author=doc.metadata.get("author"),
                mode=doc.spec.get("mode", "raw"),
                query_template=doc.spec.get("query_template"),
                interval=doc.spec.get("interval"),
                methods=doc.spec.get("methods"),
            )
```

- [ ] **Step 4: Commit**

```bash
git add clients/python/tropek_client/manifest.py
git commit -m "feat(manifest): pass aggregated-mode fields for SLI create/update/diff"
```

---

### Task 3: Add aggregated-mode SLI definition to mock bootstrap manifests

Add a new aggregated-mode SLI definition to the mock bootstrap. This SLI uses `mode: aggregated` with a `query_template`, `interval`, and `methods` list. The mock adapter already handles aggregated mode (implemented in Phase 1a) — it generates random values for each `{sli}.{method}` key.

**Files:**
- Modify: `bootstrap_mock/manifests/sli-definitions.yaml` (append new document)

- [ ] **Step 1: Append the aggregated SLI definition**

Add the following YAML document at the end of `bootstrap_mock/manifests/sli-definitions.yaml`:

```yaml
---
api_version: tropek/v1
kind: SLI
metadata:
  name: agg-latency-sli
  display_name: Aggregated Latency Indicators
  author: bootstrap
  notes: Aggregated-mode SLI for latency statistics using query_range + statistical methods.
spec:
  adapter_type: prometheus
  mode: aggregated
  query_template: 'http_request_duration_seconds{job="$job",namespace="$namespace"}'
  interval: '1m'
  methods: ['mean', 'p95', 'p99', 'max']
```

Note: no `indicators` block — aggregated mode generates metric keys as `{sli_name}.{method}`.

- [ ] **Step 2: Commit**

```bash
git add bootstrap_mock/manifests/sli-definitions.yaml
git commit -m "feat(bootstrap): add aggregated-mode SLI definition agg-latency-sli"
```

---

### Task 4: Add aggregated-mode SLO definition to mock bootstrap manifests

Add a new SLO that references `agg-latency-sli`. The objectives use the `{sli_name}.{method}` naming convention that the aggregated adapter produces. For example, with methods `['mean', 'p95', 'p99', 'max']`, the adapter returns keys like `agg-latency-sli.mean`, `agg-latency-sli.p95`, etc.

**Files:**
- Modify: `bootstrap_mock/manifests/slo-definitions.yaml` (append new document)

- [ ] **Step 1: Append the aggregated SLO definition**

Add the following YAML document at the end of `bootstrap_mock/manifests/slo-definitions.yaml`:

```yaml
---
api_version: tropek/v1
kind: SLO
metadata:
  name: agg-latency-slo
  display_name: Aggregated Latency SLO
  author: bootstrap
  notes: Quality gate for aggregated latency statistics (mean, p95, p99, max).
spec:
  sli_name: agg-latency-sli
  sli_version: 1
  kind: standard
  total_score:
    pass_pct: 90.0
    warning_pct: 75.0
  objectives:
    - sli: agg-latency-sli.mean
      display_name: "Mean Latency"
      pass_threshold: ["<500"]
      warning_threshold: ["<800"]
      weight: 2
    - sli: agg-latency-sli.p95
      display_name: "P95 Latency"
      pass_threshold: ["<1000"]
      warning_threshold: ["<1500"]
      weight: 2
    - sli: agg-latency-sli.p99
      display_name: "P99 Latency"
      pass_threshold: ["<2000"]
      warning_threshold: ["<3000"]
      weight: 1
    - sli: agg-latency-sli.max
      display_name: "Max Latency"
      pass_threshold: ["<5000"]
      warning_threshold: ["<8000"]
      weight: 1
```

The mock adapter returns random values (base × multiplier), so thresholds are intentionally generous to ensure the evaluation passes.

- [ ] **Step 2: Commit**

```bash
git add bootstrap_mock/manifests/slo-definitions.yaml
git commit -m "feat(bootstrap): add aggregated-mode SLO definition agg-latency-slo"
```

---

### Task 5: Add SLO link binding checkout-api to the aggregated SLO

Bind an existing asset (`checkout-api`) to the new aggregated SLO + SLI + datasource so we can trigger an evaluation against it.

**Files:**
- Modify: `bootstrap_mock/manifests/slo-links.yaml` (append new document)

- [ ] **Step 1: Append the aggregated SLO link**

Add the following YAML document at the end of `bootstrap_mock/manifests/slo-links.yaml`:

```yaml
---
api_version: tropek/v1
kind: AssetSLOLink
metadata:
  name: checkout-api-agg-latency
spec:
  asset_name: checkout-api
  slo_name: agg-latency-slo
  sli_name: agg-latency-sli
  data_source_name: prometheus-local
```

This uses the same datasource (`prometheus-local`, which points to `http://127.0.0.1:9082` — the mock adapter) as the existing links.

- [ ] **Step 2: Commit**

```bash
git add bootstrap_mock/manifests/slo-links.yaml
git commit -m "feat(bootstrap): bind checkout-api to agg-latency-slo"
```

---

### Task 6: Add aggregated-mode e2e test

Add a test that triggers an aggregated-mode evaluation against `checkout-api` using `agg-latency-slo`, polls until completion, and verifies:
1. The evaluation completes successfully
2. The indicator results contain `{sli}.{method}` keys (e.g., `agg-latency-sli.mean`)
3. The `job_stats` includes `sli_metadata` with sample counts

**Files:**
- Modify: `scripts/e2e_tests.py` (add new test function + register in `main()`)

- [ ] **Step 1: Add the test function**

In `scripts/e2e_tests.py`, add the following function before the `main()` function (around line 354):

```python
def test_aggregated_evaluation(client: TropekClient) -> None:
    """Trigger an aggregated-mode evaluation and verify method-keyed results."""
    step('Step 22: Aggregated-mode evaluation')
    result = client.evaluations.trigger(
        'checkout-api',
        'agg-test',
        'agg-latency-slo',
        '2026-03-15T08:00:00Z',
        '2026-03-15T08:30:00Z',
    )
    eval_id = result['id']
    print(f'triggered aggregated eval: {eval_id}')

    ev = poll_eval(client, eval_id)
    print(f'status={ev.status} result={ev.result} score={ev.score}')
    assert ev.status == 'completed', f'expected completed, got {ev.status}'

    # Verify indicator results contain {sli}.{method} keys
    indicators = client.evaluations.get_indicators(eval_id)
    metric_names = [i.metric for i in indicators]
    print(f'indicator metrics: {metric_names}')
    for method in ['mean', 'p95', 'p99', 'max']:
        expected = f'agg-latency-sli.{method}'
        assert expected in metric_names, f'missing indicator {expected}, got {metric_names}'

    # Verify sli_metadata in job_stats
    job_stats = ev.job_stats or {}
    sli_metadata = job_stats.get('sli_metadata', {})
    print(f'sli_metadata keys: {list(sli_metadata.keys())}')
    if sli_metadata:
        for key, meta in sli_metadata.items():
            assert 'mode' in meta, f'metadata for {key} missing mode field'
            assert meta['mode'] == 'aggregated', f'expected aggregated mode for {key}'
            print(f'  {key}: {meta.get("actual_samples")} samples, {meta.get("missing_pct")}% missing')

    print('PASS: aggregated-mode evaluation')
```

- [ ] **Step 2: Register the test in `main()`**

In the `main()` function, add `test_aggregated_evaluation(client)` after `test_label_autocomplete(client)` and before `test_asset_type_delete_with_assets(client)`:

```python
def main() -> None:
    """Entry point — parse API URL from argv and run all tests."""
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <api_url>", file=sys.stderr)
        sys.exit(1)

    client = TropekClient(sys.argv[1])

    test_single_evaluation(client)
    test_pin_baseline(client)
    test_batch_evaluation(client)
    test_regression_eval(client)
    test_override_status(client)
    test_override_to_pass(client)
    test_reeval_from_pinned_baseline(client)
    test_reeval_from_date(client)
    test_reeval_dry_run(client)
    test_comparison_rules(client)
    test_annotations(client)
    test_asset_type_rename(client)
    test_asset_delete(client)
    test_label_autocomplete(client)
    test_aggregated_evaluation(client)
    test_asset_type_delete_with_assets(client)

    print("\n=== All integration tests passed ===")
```

- [ ] **Step 3: Check if `get_indicators` exists on the evaluations client**

The test calls `client.evaluations.get_indicators(eval_id)`. Check if this method exists in `clients/python/tropek_client/client.py`. If it doesn't exist, check the API for an endpoint that returns indicator results for an evaluation (likely `GET /evaluations/{id}/indicators`).

If the method does **not** exist, you need to add it. Look at the `_Evaluations` class in `clients/python/tropek_client/client.py` and the `IndicatorResult` model (or similar) in `models.py`. The endpoint is `GET /evaluations/{eval_id}/indicators`.

If `get_indicators` doesn't exist and there's no suitable method, simplify the test to only check `ev.status == 'completed'` and `ev.result` is one of `('pass', 'warning', 'fail')`, and skip the indicator-level assertions. Update the test code accordingly:

```python
def test_aggregated_evaluation(client: TropekClient) -> None:
    """Trigger an aggregated-mode evaluation and verify it completes."""
    step('Step 22: Aggregated-mode evaluation')
    result = client.evaluations.trigger(
        'checkout-api',
        'agg-test',
        'agg-latency-slo',
        '2026-03-15T08:00:00Z',
        '2026-03-15T08:30:00Z',
    )
    eval_id = result['id']
    print(f'triggered aggregated eval: {eval_id}')

    ev = poll_eval(client, eval_id)
    print(f'status={ev.status} result={ev.result} score={ev.score}')
    assert ev.status == 'completed', f'expected completed, got {ev.status}'
    assert ev.result in ('pass', 'warning', 'fail'), f'unexpected result: {ev.result}'

    # Verify sli_metadata in job_stats
    job_stats = ev.job_stats or {}
    sli_metadata = job_stats.get('sli_metadata', {})
    print(f'sli_metadata keys: {list(sli_metadata.keys())}')
    if sli_metadata:
        for key, meta in sli_metadata.items():
            assert 'mode' in meta, f'metadata for {key} missing mode field'
            assert meta['mode'] == 'aggregated', f'expected aggregated mode for {key}'
            print(f'  {key}: {meta.get("actual_samples")} samples, {meta.get("missing_pct")}% missing')

    print('PASS: aggregated-mode evaluation')
```

Use whichever version of the test matches what the client supports. The key assertions are:
1. Evaluation completes (not stuck/failed)
2. Result is a valid verdict
3. `sli_metadata` is present and shows `mode: aggregated`

- [ ] **Step 4: Commit**

```bash
git add scripts/e2e_tests.py
git commit -m "feat(e2e): add aggregated-mode evaluation test"
```

---

### Task 7: Verify the full flow with `dev-start.sh`

This is a manual verification task. No code changes needed.

- [ ] **Step 1: Run the dev environment**

```bash
./scripts/dev-start.sh
```

Watch for:
1. Bootstrap manifests apply successfully (should show `agg-latency-sli` and `agg-latency-slo` created)
2. e2e tests pass including `Step 22: Aggregated-mode evaluation`
3. The aggregated evaluation completes with a valid result and score

If the aggregated evaluation fails with an error like `"evaluation has no sli_name"` or `"sli not found"`, check:
- Did the SLI definition get created? `curl http://localhost:9080/sli-definitions/agg-latency-sli`
- Did the SLO definition get created? `curl http://localhost:9080/slo-definitions/agg-latency-slo`
- Does the SLO link exist? Check the asset's SLO links

- [ ] **Step 2: Verify in UI**

Open `http://localhost:5173` and navigate to `checkout-api`. You should see:
- The standard `http-availability-slo` evaluations (existing)
- The new `agg-latency-slo` evaluation with 4 indicator rows: `agg-latency-sli.mean`, `.p95`, `.p99`, `.max`

---

## Notes

- The mock adapter's `_handle_aggregated()` generates random base values with method-specific multipliers (e.g., max = 2.5× base, mean = 1.0× base). With `random.uniform(1.0, 100.0)` as base, max values range from 2.5 to 250.0. The SLO thresholds (`<5000`, `<8000`) are deliberately generous to ensure pass.
- The `method_criteria` column (added in Phase 1a schema) requires a DB migration. Run `./scripts/db-regen-migrations.sh` when the test DB is available before testing.
- The Prometheus bootstrap manifests (`bootstrap_prometheus/`) are NOT modified — those only run when the observability stack is available. Aggregated-mode e2e testing uses the mock adapter which is always available.
