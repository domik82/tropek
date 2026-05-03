# SLO Authoring Guide

This guide covers the SLO definition format, criteria syntax, scoring mechanics,
and common pitfalls. It is the primary reference for writing and debugging SLO definitions
in TROPEK.

## SLO format basics

TROPEK's evaluation engine is inspired by
[Keptn v1](https://keptn.sh)'s lighthouse-service and uses a similar criteria syntax,
but the SLO format is **TROPEK's own**. SLOs are created via the REST API
(`POST /slo-definitions`) as JSON, or provisioned via YAML manifests using the
`tropek` Python client (see `dev_setup/mock/` for examples).

SLI queries are **not embedded** in the SLO — they live in a separate SLI registry
and are referenced by `sli_name` and `sli_version`.

### API format (JSON)

```json
{
  "name": "http-availability-slo",
  "display_name": "HTTP Availability SLO",
  "sli_name": "http-service-sli",
  "sli_version": 1,
  "kind": "standard",
  "comparison": {
    "compare_with": "several_results",
    "number_of_comparison_results": 3,
    "include_result_with_score": "pass_or_warn",
    "aggregate_function": "avg",
    "scope_tags": ["os", "arch"]
  },
  "total_score_pass_threshold": 90.0,
  "total_score_warning_threshold": 75.0,
  "objectives": [
    {
      "sli": "response_time_p99",
      "display_name": "Response Time P99 (ms)",
      "pass_threshold": ["<600", "<=+10%"],
      "warning_threshold": ["<800"],
      "weight": 2,
      "key_sli": false
    },
    {
      "sli": "error_rate",
      "display_name": "Error Rate",
      "pass_threshold": ["=0"],
      "weight": 3,
      "key_sli": true
    }
  ]
}
```

### Manifest format (YAML via `tropek` client)

```yaml
api_version: tropek/v1
kind: SLO
metadata:
  name: http-availability-slo
  display_name: HTTP Availability SLO
  author: bootstrap
spec:
  sli_name: http-service-sli
  sli_version: 1
  kind: standard
  comparison:
    compare_with: several_results
    number_of_comparison_results: 3
    include_result_with_score: pass_or_warn
    aggregate_function: avg
  total_score:
    pass_threshold: 90.0
    warning_threshold: 75.0
  objectives:
    - sli: response_time_p99
      display_name: "Response Time P99 (ms)"
      pass_threshold: [">0", "<600", "<=+10%"]
      warning_threshold: [">0", "<800"]
      weight: 2
    - sli: error_rate
      display_name: "Error Rate"
      pass_threshold: ["=0"]
      weight: 3
      key_sli: true
```

Apply manifests with: `uv run --directory clients/python tropek apply -f <dir> --base-url http://localhost:8080`

### Top-level fields (API)

| Field | Required | Description |
|---|---|---|
| `name` | yes | Unique SLO name |
| `objectives` | yes | List of SLO objectives (at least one) |
| `sli_name` | no | Reference to an SLI definition in the registry |
| `sli_version` | no | Pinned SLI version (latest if omitted) |
| `total_score_pass_threshold` | no | Minimum weighted % to pass. Default: 90.0 |
| `total_score_warning_threshold` | no | Minimum weighted % to warn. Default: 75.0 |
| `comparison` | no | Baseline comparison strategy. See [Comparison config](#comparison-config) |
| `kind` | no | `standard` (default) or `template` (for SLO groups) |
| `variables` | no | Key-value dict for SLI query variable substitution |

## Criteria syntax

Each objective defines `pass_threshold` and optionally `warning_threshold` — flat lists
of criteria strings that compare a metric value against a fixed threshold or a relative
baseline.

### Supported patterns

| Pattern | Type | Meaning |
|---|---|---|
| `<600` | Fixed | value must be less than 600 |
| `<=600` | Fixed | value must be less than or equal to 600 |
| `=0` | Fixed | value must equal 0 |
| `>10` | Fixed | value must be greater than 10 |
| `>=10` | Fixed | value must be greater than or equal to 10 |
| `<=+10%` | Relative % | value must be at most 10% above baseline |
| `>=-5%` | Relative % | value must be at least 5% below baseline (i.e., `baseline * 0.95`) |
| `<=+50` | Relative abs | value must be at most baseline + 50 |
| `>=-20` | Relative abs | value must be at least baseline - 20 |

### Parsing rules

The criteria parser (`criteria.py`) accepts these patterns:

- **Operators:** `<`, `<=`, `=`, `>=`, `>`
- **Sign:** an explicit `+` or `-` before the number marks the criterion as relative
  (even without `%`). No sign + no `%` = fixed threshold.
- **Percentage suffix:** `%` computes the target as `baseline * (1 +/- pct/100)`.
  Without `%` but with a sign, the target is `baseline +/- value` (absolute delta).
- **Whitespace:** ignored. `"  <= + 10  %"` is equivalent to `"<=+10%"`.
- **Decimal values:** supported. `<=+10.5%` is valid.

### Evaluation logic within an objective

- **Within a criteria list: AND.** All criteria in a single list must pass.
  Example: `["<600", "<=+10%"]` -- the value must be both below 600 AND within
  10% of the baseline.

### Relative criteria with no baseline

Relative criteria with no comparison history **always pass**. The first evaluation
of a new asset has no baseline, so relative criteria impose no penalty. This prevents
false failures on initial runs.

## Pass vs warning ordering

The evaluation engine checks `pass_threshold` first, then falls back to
`warning_threshold`:

1. If the value satisfies `pass_threshold` -> **PASS** (warning is never checked)
2. If pass fails but `warning_threshold` is satisfied -> **WARNING**
3. If both fail -> **FAIL**

This means **pass is the stricter gate** — it defines the high-quality band.
Warning is more permissive — it catches values that aren't good enough to pass
but aren't bad enough to fail.

### Example: response time

```json
{
  "sli": "response_time_p95",
  "pass_threshold": ["<=+10%"],
  "warning_threshold": ["<=+25%"]
}
```

With a baseline of 100ms:
- 105ms: within +10% (110ms limit) -> **pass** (meets the strict gate)
- 118ms: exceeds +10% but within +25% (125ms limit) -> **warning** (degraded but acceptable)
- 130ms: exceeds +25% -> **fail**

### Example: error rate

```json
{
  "sli": "error_rate",
  "pass_threshold": ["=0"],
  "warning_threshold": ["<5"]
}
```

- 0 errors: satisfies `=0` -> **pass**
- 3 errors: fails `=0`, satisfies `<5` -> **warning**
- 7 errors: fails both -> **fail**

### The mistake: warning stricter than pass

If `warning_threshold` is stricter than `pass_threshold`, the warning band becomes
**unreachable** — any value satisfying warning also satisfies pass.

```json
// Wrong -- warning is unreachable:
{ "pass_threshold": ["<800"], "warning_threshold": ["<500"] }
```

Value 400: satisfies `<800` -> PASS (warning never checked).
Value 600: satisfies `<800` -> PASS (warning never checked).
Value 900: fails both -> FAIL.
The warning band is empty — everything is either PASS or FAIL.

```json
// Correct -- warning catches the degraded-but-acceptable range:
{ "pass_threshold": ["<500"], "warning_threshold": ["<800"] }
```

Value 400: satisfies `<500` -> PASS.
Value 600: fails `<500`, satisfies `<800` -> WARNING.
Value 900: fails both -> FAIL.

## Key SLI

Setting `key_sli: true` on an objective makes it a gate: if this objective
fails, the **entire evaluation fails** regardless of the total weighted score.

```json
{
  "sli": "error_rate",
  "pass_threshold": ["=0"],
  "key_sli": true,
  "weight": 3
}
```

Key SLI failure overrides the total score. Even if the weighted score is 95%
(above the pass threshold), a key SLI failure forces the result to FAIL.

Use `key_sli: true` for hard requirements that should never be compromised:
zero errors, availability above a threshold, or critical latency bounds.

## Weights

Each objective has a `weight` (default: 1) that determines its contribution
to the total score.

### Scoring per objective

| Outcome | Score contribution |
|---|---|
| PASS | `weight` (full credit) |
| WARNING | `0.5 * weight` (half credit) |
| FAIL | `0` |
| INFO (no pass criteria defined) | Does not contribute to total |

### Total score calculation

```
total_score_pct = 100 * sum(achieved_scores) / sum(weights_of_contributing_objectives)
```

The total score percentage is compared against the `total_score` thresholds:
- >= `pass` threshold -> overall PASS
- >= `warning` threshold -> overall WARNING
- below both -> overall FAIL

### Example

Three objectives with weights 2, 3, 1 (maximum possible = 6):
- Objective A (weight 2): PASS -> score 2
- Objective B (weight 3): WARNING -> score 1.5
- Objective C (weight 1): FAIL -> score 0

Total: `100 * 3.5 / 6 = 58.3%`. With default thresholds (pass=90%, warning=75%),
this is a FAIL.

## Comparison config

The `comparison` block controls how baseline values are selected and aggregated
for relative criteria.

```json
{
  "compare_with": "several_results",
  "number_of_comparison_results": 3,
  "include_result_with_score": "pass_or_warn",
  "aggregate_function": "avg",
  "scope_tags": ["os", "arch"]
}
```

### Fields

| Field | Values | Default | Description |
|---|---|---|---|
| `compare_with` | `single_result`, `several_results` | `single_result` | How many previous evaluations to use as baseline |
| `number_of_comparison_results` | integer | `3` | Number of previous results to fetch (only for `several_results`) |
| `include_result_with_score` | `pass`, `pass_or_warn`, `all` | `all` | Filter previous results by their outcome |
| `aggregate_function` | `avg`, `p50`, `p90`, `p95`, `p99` | `avg` | How to aggregate multiple baseline values into a single number |
| `scope_tags` | list of tag keys | `["os"]` | Scope baseline queries to previous evaluations with matching tag values |

### How it works

1. TROPEK fetches the N most recent previous evaluations for the same asset.
2. Results are filtered by `include_result_with_score` (e.g., only evaluations
   that passed or warned).
3. For each SLI, the historical metric values are aggregated using `aggregate_function`.
4. This aggregated value becomes the `baseline` for relative criteria evaluation.

### scope_tags

`scope_tags` is a TROPEK extension not present in Keptn. It scopes baseline queries
to previous evaluations that share the same tag values for the listed keys.

Example: with `scope_tags: [os, arch]`, an evaluation tagged `{os: linux, arch: arm64}`
only compares against previous evaluations also tagged `{os: linux, arch: arm64}`.
This prevents cross-environment baseline contamination.

## Variable substitution

SLI queries (defined in the SLI registry) can contain `$variable` tokens that are
replaced at evaluation time. Variables come from multiple sources, merged in priority
order.

### Built-in variables

| Variable | Source |
|---|---|
| `$asset_name` | Name of the asset being evaluated |
| `$evaluation_name` | Evaluation identifier from the trigger request |
| `$test_name` | Alias for `$evaluation_name` (backward compatibility) |
| `$start` | ISO timestamp -- evaluation period start |
| `$end` | ISO timestamp -- evaluation period end |

### Custom variables via metadata

Any key-value pair in the evaluation request's `metadata` field becomes a variable.
Metadata keys take the lowest priority -- built-in variables are not overridden.

An SLI query like:
```
histogram_quantile(0.99, rate(http_duration_bucket{instance="$vm_ip"}[5m]))
```

Triggered with `metadata: {"vm_ip": "10.0.1.15"}`, becomes:
```
histogram_quantile(0.99, rate(http_duration_bucket{instance="10.0.1.15"}[5m]))
```

### SLO-level variables

SLO definitions carry a `variables` dict that is substituted into SLI queries at
evaluation time. This allows the same SLI definition to be reused across SLOs with
different parameters.

### Unresolved variables

If a `$variable` has no corresponding value in the merged variable dict, the engine
raises `UnresolvedVariableError` with the list of available variables. This catches
typos and missing metadata early.

## Template SLOs

Template SLOs use `kind: template` and contain `$__gen_<key>` placeholders. They are
not evaluated directly -- instead, an SLO group expands a template into multiple
concrete SLOs using `gen_variables`.

### How it works

1. Define a template SLO with `kind: template` and `$__gen_<key>` placeholders
   in the name and/or variable values.
2. Create an SLO group that references the template and provides `gen_variables` --
   a dict of lists, one entry per generated SLO.
3. The generator substitutes `$__gen_<key>` placeholders with each row of values,
   producing N concrete SLO specs.

### Example

Template SLO named `"perf-$__gen_service"` with variables `{endpoint: "$__gen_endpoint"}`:

```json
{
  "gen_variables": {
    "service": ["checkout", "catalog", "cart"],
    "endpoint": ["/api/checkout", "/api/products", "/api/cart"]
  }
}
```

This generates three SLOs:
- `perf-checkout` with `endpoint=/api/checkout`
- `perf-catalog` with `endpoint=/api/products`
- `perf-cart` with `endpoint=/api/cart`

### Rules

- All `gen_variables` lists must be the same length (each index produces one SLO).
- `$__gen_<key>` placeholders are only substituted in the template name and variable
  values, not in objective definitions.
- If the template has no `$__gen_` placeholders, the generator warns that all
  generated SLOs will be identical copies.
- Generated SLOs are automatically tagged with `slo_group: <group_name>` and
  `generated: true`.

## Aggregated-mode SLIs

TROPEK supports two SLI definition modes: **raw** and **aggregated**.

### Raw mode (default)

Each indicator has its own query. This is the standard Keptn-compatible approach:

```json
{
  "name": "web-perf",
  "mode": "raw",
  "adapter_type": "prometheus",
  "indicators": {
    "response_time_p99": "histogram_quantile(0.99, rate(http_duration_bucket[5m]))",
    "error_rate": "rate(http_errors_total[5m])"
  }
}
```

### Aggregated mode

A single `query_template` returns a time series, and TROPEK computes statistical
aggregations (`methods`) over it. The SLO objectives reference the SLI as
`<sli_name>.<method>`.

```json
{
  "name": "response-time",
  "mode": "aggregated",
  "adapter_type": "prometheus",
  "query_template": "http_request_duration_seconds{service=\"$asset_name\"}",
  "interval": "30s",
  "methods": ["mean", "p95", "p99", "max"]
}
```

### Available aggregation methods

| Method | Description |
|---|---|
| `min` | Minimum value |
| `mean` | Arithmetic mean |
| `max` | Maximum value |
| `std` | Standard deviation |
| `sum` | Sum of all values |
| `median` | Median (50th percentile) |
| `p75` | 75th percentile |
| `p90` | 90th percentile |
| `p95` | 95th percentile |
| `p99` | 99th percentile |

### Referencing in SLO objectives

When an SLO links to an aggregated-mode SLI, each objective's `sli` field references
a specific method:

```json
{
  "objectives": [
    { "sli": "response_time.mean", "pass_threshold": ["<500"] },
    { "sli": "response_time.p99", "pass_threshold": ["<2000"] }
  ]
}
```

## Common mistakes

### 1. Warning stricter than pass

The most frequent mistake. Pass is the **stricter** gate (high-quality band).
Warning is more permissive (degraded but acceptable). If warning is stricter
than pass, the warning band is unreachable — any value satisfying warning
also satisfies pass.

```json
// Wrong -- warning is unreachable (stricter than pass)
{ "pass_threshold": ["<800"], "warning_threshold": ["<500"] }

// Correct -- pass is stricter, warning catches the degraded range
{ "pass_threshold": ["<500"], "warning_threshold": ["<800"] }
```

See [Pass vs warning ordering](#pass-vs-warning-ordering) for the full explanation.

### 2. Relative criteria with no baseline

Relative criteria (`<=+10%`, `>=-5%`) require comparison history. On the first
evaluation of an asset, there is no baseline, so relative criteria **always pass**.
This is by design -- no penalty for the first run.

If you need hard bounds from the very first evaluation, use a fixed threshold
alongside the relative one:

```json
{ "pass_threshold": ["<600", "<=+10%"] }
```

### 3. Mixing fixed and relative without understanding AND logic

Multiple criteria in a single list are ANDed. Both must pass:

```json
{ "pass_threshold": ["<600", "<=+10%"] }
```

This means: value must be less than 600 **AND** within 10% of baseline. The fixed
threshold provides an absolute ceiling while the relative threshold catches regressions.

### 4. Forgetting key_sli overrides total score

A key SLI failure forces the entire evaluation to FAIL, even if the total weighted
score is above the pass threshold. If an objective should not have veto power over
the whole evaluation, do not mark it as `key_sli: true`.

### 5. Warning threshold higher than pass in total_score

If `total_score_warning_threshold` is set higher than `total_score_pass_threshold`,
the warning band disappears -- every score above the warning threshold also exceeds
the pass threshold.

```json
// Wrong -- warning band is empty
{ "total_score_pass_threshold": 75.0, "total_score_warning_threshold": 90.0 }

// Correct
{ "total_score_pass_threshold": 90.0, "total_score_warning_threshold": 75.0 }
```

### 6. Objectives with no pass criteria

An objective without `pass_threshold` criteria gets status INFO and does **not contribute**
to the total score. The metric is fetched and recorded but has no effect on the
evaluation outcome. This is useful for informational metrics you want to track
without gating on them.
