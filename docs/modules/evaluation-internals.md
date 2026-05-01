# Evaluation Engine Internals

The evaluation engine is a pure-function scoring library with zero I/O. It lives in
`api/tropek/modules/quality_gate/evaluation_engine/` and is ported from Keptn's Go
`lighthouse-service`. Every function receives its inputs as arguments and returns
structured results -- no database, network, or filesystem access.

For the full trigger-to-finalization lifecycle (worker phases, DB transactions,
finalization, sweeper), see
[../architecture/evaluation-lifecycle.md](../architecture/evaluation-lifecycle.md).


## Module Map

```
evaluation_engine/
  evaluator.py       -- evaluate() entry point
  scoring.py         -- score_objective(), calculate_total_score()
  criteria.py        -- parse_criteria_string(), evaluate_criteria(), aggregate_values()
  slo_parser.py      -- build_slo() constructor
  slo_models.py      -- SLO, SLOObjective, SLOComparison, SLOTotalScore (Pydantic)
  result_models.py   -- EvaluationResult, IndicatorResult, ObjectiveResult, etc. (Pydantic)
  variables.py       -- substitute_variables(), build_variables()
  constants.py       -- StrEnum constants (CriteriaType, IndicatorStatus, EvaluationOutcome, ...)
```


## Entry Point: `evaluate()`

**File:** `evaluator.py`

```python
def evaluate(
    slo: SLO,
    metrics: dict[str, float | None],
    baselines: dict[str, float | None],
    compared_evaluation_ids: list[str] | None = None,
) -> EvaluationResult:
```

For each `SLOObjective` in the SLO:

1. Look up the metric value and baseline by `objective.sli` key (missing key becomes `None`).
2. Call `score_objective()` to determine status and score.
3. Build pass and warning `CriteriaTarget` lists via `_build_targets()` (parses each
   criteria string, computes the target value, and checks violation).
4. Construct an `IndicatorResult` with the value, baseline, status, score, targets, and
   change deltas.

After all objectives, call `calculate_total_score()` and return an `EvaluationResult`
with the score rounded to 2 decimal places.

### Change deltas

When both `value` and `baseline` are present:

- `change_absolute = value - baseline`
- `change_relative_pct = ((value / baseline) - 1) * 100` (only when `baseline != 0`)


## Criteria Syntax

**File:** `criteria.py`, function `parse_criteria_string()`

A criteria string has the form:

```
<operator>[sign]<value>[%]
```

| Component | Options | Notes |
|-----------|---------|-------|
| operator | `<`, `<=`, `=`, `>=`, `>` | Longest-match in regex prevents `<` matching before `<=` |
| sign | `+`, `-`, absent | Presence of a sign marks the criterion as RELATIVE |
| value | integer or decimal | e.g. `600`, `10.5` |
| `%` suffix | present or absent | Marks relative-percentage mode |

### Type determination

- No sign, no `%` (e.g. `<600`) -- **FIXED**: compare value directly against the threshold.
- `%` present (e.g. `<=+10%`) -- **RELATIVE**: compare against `baseline +/- (baseline * pct / 100)`.
- Sign present without `%` (e.g. `<=+50`) -- **RELATIVE absolute**: same formula, matching
  Keptn Go behaviour. The `%` suffix controls display semantics but both forms use the same
  percentage-based computation internally.

### Examples

| Criteria | Type | Meaning |
|----------|------|---------|
| `<600` | Fixed | value must be less than 600 |
| `<=600` | Fixed | value must be at most 600 |
| `=0` | Fixed | value must equal 0 |
| `>=10` | Fixed | value must be at least 10 |
| `<=+10%` | Relative | value must be at most baseline * 1.10 |
| `>=-5%` | Relative | value must be at least baseline * 0.95 |
| `<=+50` | Relative | value must be at most baseline + (baseline * 50 / 100) |

### Whitespace

All whitespace is stripped before parsing (`''.join(raw.split())`), so
`"  <=+10   %"` is equivalent to `"<=+10%"`.

### `ParsedCriteria` model

The parsed result is a Pydantic model with fields: `raw`, `operator`, `type`
(`CriteriaType.FIXED` or `CriteriaType.RELATIVE`), `threshold`, `relative_pct`,
and `relative_direction` (`+` or `-`).

The method `compute_target_value(baseline)` resolves the concrete comparison value:

- **FIXED**: returns `threshold` (ignores baseline).
- **RELATIVE with baseline**: returns `baseline + (baseline * pct / 100)` or
  `baseline - (baseline * pct / 100)`.
- **RELATIVE without baseline**: returns `0.0`.


## Scoring Algorithm

**File:** `scoring.py`

### Per-objective: `score_objective()`

Evaluates a single `SLOObjective` against a metric value and optional baseline.
Returns an `ObjectiveResult` with status, score, and flags.

Status is determined in strict priority order (waterfall):

| Priority | Condition | Status | Score | Notes |
|----------|-----------|--------|-------|-------|
| 1 | `pass_threshold` is empty | `INFO` | 0 | Does not contribute to total |
| 2 | Value is `None` | `ERROR` | 0 | `key_sli_failed` set if `key_sli=True` |
| 3 | All `pass_threshold` criteria pass | `PASS` | `weight` | Full weight |
| 4 | `warning_threshold` exists and all pass | `WARNING` | `0.5 * weight` | Half weight |
| 5 | Otherwise | `FAIL` | 0 | `key_sli_failed` set if `key_sli=True` |

**AND logic within each block**: multiple criteria in `pass_threshold` or `warning_threshold`
are combined with AND -- all must pass. OR logic was deliberately removed from the Keptn port.

**Warning scoring**: a warning objective receives exactly half its weight. There is no
graduated scale between pass and fail.

### Total score: `calculate_total_score()`

Aggregates all `ObjectiveResult`s into a `TotalScore`:

1. `maximum = sum(weight)` for all objectives where `contributes_to_score` is True
   (excludes INFO objectives).
2. If `maximum == 0` (all objectives are informational): return PASS at 100%.
3. `achieved = sum(score)` for all results.
4. `pct = 100.0 * achieved / maximum`
5. **Key SLI veto**: if any objective has `key_sli_failed=True`, the result is forced
   to FAIL regardless of the score percentage.
6. `pct >= pass_threshold` (default 90.0) -- PASS.
7. `pct >= warning_threshold` (default 75.0) -- WARNING.
8. Otherwise -- FAIL.

The score is still computed and reported even when the key SLI veto fires. This allows
the UI to show "scored 85% but failed because error_rate was a key SLI".

### Worked example

Given three objectives with weights 2, 3, 1:

| Objective | Weight | Status | Score |
|-----------|--------|--------|-------|
| response_time | 2 | PASS | 2.0 |
| error_rate (key_sli) | 3 | WARNING | 1.5 |
| throughput | 1 | FAIL | 0.0 |

- `maximum = 2 + 3 + 1 = 6`
- `achieved = 2.0 + 1.5 + 0.0 = 3.5`
- `pct = 100 * 3.5 / 6 = 58.33`
- No key SLI veto (error_rate is WARNING, not FAIL)
- 58.33 < 75.0 -- result is **FAIL**


## Variable Substitution

**File:** `variables.py`

SLI query templates can contain `$variable` tokens that are replaced at evaluation time.

### `substitute_variables(template, variables)`

Regex-based replacement. Pattern matches `$` followed by a Python identifier
(`[a-zA-Z_][a-zA-Z0-9_]*`). A bare `$` not followed by an identifier (e.g. `$5`)
is left as-is.

Raises `UnresolvedVariableError` if a matched `$variable` has no corresponding key
in the variables dict.

### `build_variables(metadata, asset_name, evaluation_name, start, end)`

Merges variable sources into a single dict. Metadata is copied first, then reserved
variables are added via `setdefault()` (so metadata wins if there is a conflict):

| Reserved variable | Source |
|-------------------|--------|
| `$asset_name` | `asset_name` parameter |
| `$evaluation_name` | `evaluation_name` parameter |
| `$test_name` | Alias for `evaluation_name` (backward compat) |
| `$start` | ISO timestamp for period start |
| `$end` | ISO timestamp for period end |

**Priority**: metadata keys take precedence over reserved variables because `dict(metadata)`
is copied first and `setdefault()` does not overwrite existing keys.

Note: the full variable merge in the worker pipeline (which layers asset tags, SLO variables,
and evaluation overrides on top) happens in `evaluation_helpers.py`, outside the engine.
The engine's `build_variables()` handles only the metadata + reserved layer.


## Baseline Aggregation

**File:** `criteria.py`, function `aggregate_values()`

Aggregates a list of baseline values from previous evaluations into a single scalar.
Called by the worker pipeline, not by `evaluate()` itself.

| Function | Algorithm |
|----------|-----------|
| `avg` | Arithmetic mean |
| `p50` | 50th percentile (floor-index) |
| `p90` | 90th percentile (floor-index) |
| `p95` | 95th percentile (floor-index) |
| `p99` | 99th percentile (floor-index) |

The percentile implementation uses floor-index: `idx = int(len * pct / 100)`, clamped to
`len - 1`. This matches Go's Keptn `calculatePercentile` but does **not** interpolate.
For small datasets, this gives coarse results (e.g. p90 of 10 values returns the maximum).

Raises `ValueError` on an empty list.


## SLO Construction

**File:** `slo_parser.py`, function `build_slo()`

```python
def build_slo(
    objectives: list[dict[str, Any]],
    total_score_pass_threshold: float = 90.0,
    total_score_warning_threshold: float = 75.0,
    comparison: dict[str, Any] | None = None,
) -> SLO:
```

Constructs a validated `SLO` from raw dicts. Each objective dict is validated through
`SLOObjective.model_validate()`, and the comparison config through
`SLOComparison.model_validate()`. Wraps Pydantic `ValidationError` in `SLOParseError`.
Rejects an empty objectives list.


## Domain Models

### Input models (`slo_models.py`)

| Model | Key fields | Defaults |
|-------|------------|----------|
| `SLOObjective` | `sli`, `display_name`, `pass_threshold`, `warning_threshold`, `weight`, `key_sli` | weight=1, key_sli=False |
| `SLOComparison` | `compare_with`, `number_of_comparison_results`, `include_result_with_score`, `aggregate_function`, `scope_tags` | compare_with=SINGLE_RESULT, aggregate_function=AVG |
| `SLOTotalScore` | `pass_threshold`, `warning_threshold` | 90.0, 75.0 |
| `SLO` | `objectives`, `comparison`, `total_score` | -- |

Note: `SLOComparison` is carried on the SLO model but the engine's `evaluate()` function
does not read it. The caller uses it to decide how to query baselines before calling the
engine.

### Output models (`result_models.py`)

| Model | Key fields |
|-------|------------|
| `ObjectiveResult` | `objective` (SLOObjective), `status` (IndicatorStatus), `score`, `contributes_to_score`, `key_sli_failed` |
| `TotalScore` | `result` (EvaluationOutcome), `score` (0-100) |
| `CriteriaTarget` | `criteria` (raw string), `target_value`, `violated` (bool) |
| `IndicatorResult` | `metric`, `display_name`, `value`, `compared_value`, `status` (str), `score`, `weight`, `key_sli`, `pass_targets`, `warning_targets`, `change_absolute`, `change_relative_pct` |
| `EvaluationResult` | `result` (EvaluationOutcome), `score`, `indicator_results`, `compared_evaluation_ids` |

### Constants (`constants.py`)

| Enum | Values |
|------|--------|
| `CriteriaType` | `fixed`, `relative` |
| `IndicatorStatus` | `pass`, `warning`, `fail`, `info`, `error` |
| `EvaluationOutcome` | `pass`, `warning`, `fail` |
| `CompareWith` | `single_result`, `several_results` |
| `IncludeResultWithScore` | `all`, `pass_or_warn`, `pass` |
| `AggregateFunction` | `avg`, `p50`, `p90`, `p95`, `p99` |
| `EvaluationStatus` | `pending`, `running`, `completed`, `failed`, `partial` |

`RESULT_RANK` is a severity ordering dict: `{'pass': 0, 'warning': 1, 'fail': 2,
'error': 3, 'invalidated': 4}`. Used outside the engine (finalization, presentation)
for worst-case comparisons. The `invalidated` key has no corresponding enum member --
it exists only for the persistence layer where results can be manually invalidated.


## Error Handling

All engine exceptions inherit from `ValueError`:

| Exception | Raised by | Trigger |
|-----------|-----------|---------|
| `SLOParseError` | `build_slo()` | Empty objectives, invalid structure |
| `UnresolvedVariableError` | `substitute_variables()` | `$variable` with no matching key |
| `ValueError` | `aggregate_values()` | Empty values list or unknown function |
| `ValueError` | `parse_criteria_string()` | Unparseable criteria string |


## Edge Cases and Known Limitations

**Relative criteria with no baseline always pass.** On the first evaluation (no history),
relative criteria like `<=+10%` are automatically satisfied. This avoids penalizing the
first run.

**Relative criteria with negative baselines.** With `<=+10%` and baseline=-100, the target
becomes -110. A value of -90 (less negative, objectively "better") fails because -90 > -110.
This matches Go behaviour and is documented by tests but has no special handling.

**Pass/warning ordering is not validated.** The engine does not check that pass criteria
are stricter than warning criteria. If warning is stricter than pass (e.g. pass: `<=+20%`,
warning: `<=+5%`), the warning band becomes unreachable -- anything satisfying warning
also satisfies pass. Correct usage: pass is the strict gate, warning catches
degraded-but-acceptable values.

**`IndicatorResult.status` is typed as `str`**, not `IndicatorStatus`, even though it is
populated from `IndicatorStatus.value`. Consumers must compare against raw strings.

**Score rounding** happens only at the final output boundary in `evaluate()` (2 decimal
places). `calculate_total_score()` itself does not round.

**Stateless and thread-safe.** No module-level state, no singletons, no caching. Every
call to `evaluate()` is independent and safe for concurrent use.
