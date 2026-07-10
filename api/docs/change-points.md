# Change-Point Detection -- Contributor Guide

Deep dive for developers maintaining or extending TROPEK's change-point detection system,
derived from Apache Otava's E-Divisive implementation.

## Module Layout

```
api/tropek/modules/change_points/
    __init__.py
    detector.py              # Pure function wrapper: detect_change_points()
    worker_step.py           # Phase 4 orchestration: gather history, detect, persist
    repository.py            # ChangePointRepository: CRUD, dedup, config resolution
    router.py                # REST endpoints: list, triage, config CRUD
    schemas.py               # Pydantic: ChangePointRead, TriageRequest, config schemas
    engine/
        __init__.py          # Public re-exports for the E-Divisive engine
        base.py              # Core types: CandidateChangePoint, ChangePoint, SignificanceTester, Calculator
        calculator.py        # PairDistanceCalculator: vectorised Q-hat via pairwise distances
        detector.py          # ChangePointDetector: recursive E-Divisive bisection loop
        analysis.py          # TTestSignificanceTester + split/merge two-phase algorithm
        significance_test.py # PermutationsSignificanceTester (alternative to t-test)
        NOTICE               # Apache Otava attribution

api/tests/change_points/
    generators.py                  # Synthetic time series generators (5 classes)
    test_generators.py             # Generator validation + detector behavior
    test_detector.py               # Unit tests for detect_change_points()
    test_detection_scenarios.py    # End-to-end scenarios with real detector + fake repos
    test_worker_step.py            # Worker orchestration tests (mocked detector)
    test_presenter_enrichment.py   # Heatmap marker resolution tests
    engine/
        test_analysis.py           # fill_missing, split+merge, TTestSignificanceTester
        test_calculator.py         # Brute-force Q-hat matrix verification
        test_detector.py           # ChangePointDetector with both testers
    db/
        conftest.py                # Shared DB fixtures
        test_repository.py         # Integration: dedup, config CRUD, resolve_from_objective
```

## Engine Internals

### Algorithm: E-Divisive

The engine implements the E-Divisive algorithm from Matteson & James, adapted via Apache
Otava (Hunter project). It finds distributional change points in a univariate time series
using a nonparametric energy-statistic approach.

**PairDistanceCalculator** (`calculator.py`) computes the Q-hat statistic that measures how
"different" the distributions are on each side of a candidate split point.

- Constructor takes the series and a `power` parameter (0 < power < 2, default 1.0).
- Lazily computes `|x_i - x_j|^power` for all pairs, then builds cumulative-sum vectors
  `V` (column sums) and `H` (row sums of upper triangle) for O(1) range queries.
- `_get_Q_vals(start, end)` returns a matrix where `Q[i,j]` is the Q-hat value for a split
  at `tau=i+1+start` with `kappa=j+2+start`, using the A-B-C decomposition.
- `get_candidate_change_point(interval)` returns the argmax over the Q-hat matrix as a
  `CandidateChangePoint(index, qhat)`.

**ChangePointDetector** (`engine/detector.py`) runs the recursive bisection loop:

1. Slices the series, creates a `PairDistanceCalculator` instance.
2. Loop: computes intervals from known CPs, finds the next candidate (highest Q-hat across
   all intervals), tests significance. If significant, adds to the CP list and re-sorts.
   If not, terminates.
3. Adjusts indices by the `start` offset and filters boundary CPs where `index >= effective_end`
   (Otava bug fix).

**Significance testing** determines whether a candidate CP is real or noise. Two testers exist:

- **TTestSignificanceTester** (`analysis.py`) -- the production default. Runs a two-sided
  Student's t-test (`scipy.stats.ttest_ind_from_stats`) on the segments before and after the
  candidate. Returns `pvalue=1.0` when total sample size is <= 2.
- **PermutationsSignificanceTester** (`significance_test.py`) -- shuffles the series within
  each interval N times, computes max Q-hat per permutation, derives p-value as the fraction
  of permuted Q-hats exceeding the candidate's Q-hat. Not used in production.

**Split/merge two-phase algorithm** (`analysis.py`) improves detection quality:

- **Split phase**: slides a window of `window_len` (default 30) across the series with 50%
  overlap. Runs full E-Divisive recursion on each window with a relaxed p-value. Deduplicates
  candidates by index, then recomputes t-test stats using full-series intervals.
- **Merge phase**: iteratively removes the weakest CP (highest p-value; if all pass, lowest
  magnitude) and recomputes neighbor stats until all CPs meet both the strict p-value threshold
  and minimum magnitude.

**Sensitivity controls**: `max_pvalue` sets the significance threshold (lower = stricter).
`min_sample_size` gates the minimum number of data points before detection runs.
`min_magnitude` filters out statistically significant but practically irrelevant shifts.

### Key Types

**`CandidateChangePoint`** -- `index: int`, `qhat: float`. Pre-significance-test candidate.

**`ChangePoint`** (engine) -- `index: int`, `qhat: float`, `stats: BaseStats`. Mutable working
object with `__slots__`; equality/hash based on `index` only. Factory: `from_candidate()`.

**`TTestStats`** extends `BaseStats` -- `mean_1`, `mean_2`, `std_1`, `std_2`, `pvalue`.
Methods: `forward_rel_change()`, `backward_rel_change()`, `change_magnitude()` (max of
absolute forward/backward).

**`ChangePointResult`** -- output of the detector wrapper. Fields: `position`, `timestamp`,
`detector` ("e_divisive"), `direction` (REGRESSION/IMPROVEMENT), `change_relative_pct`
(nullable), `change_absolute`, `pvalue`, `pre_segment_mean`, `post_segment_mean`,
`post_segment_std`, `transition` (nullable). `change_relative_pct` is computed from the
adjacent segment means (`pre_segment_mean`, `post_segment_mean`) around the change point --
not the full series before/after. When `pre_segment_mean` is exactly 0, the percentage is
undefined (division by zero); `change_relative_pct` is set to `None` and `transition` is set
to `APPEARED`. When `post_segment_mean` is exactly 0, `transition` is `VANISHED` instead.
`min_magnitude` gates on these same adjacent segment means via `change_magnitude()`, not a
full-series comparison.

**`Direction`** (StrEnum) -- `REGRESSION`, `IMPROVEMENT`. Determined by `higher_is_better`
combined with the sign of the change.

**`Transition`** (StrEnum) -- `APPEARED`, `VANISHED`. Set only when a segment mean is exactly
zero and `change_relative_pct` cannot be computed; `None` otherwise.

## Detector Layer

`detect_change_points()` in `detector.py` (module-level, not engine) wraps the engine as a
pure function:

1. Returns empty if `len(values) < min_sample_size` or `effective_window < 4`.
2. Applies **p-value relaxation** for the split phase: 10x relaxation if `max_pvalue < 0.05`,
   2x if `< 0.5`, else no relaxation. This gives the split phase more candidates for the
   merge phase to refine.
3. Calls `split()` then `merge()`.
4. Enriches each detected CP with pre/post segment means, stds, absolute and relative change,
   and direction based on `higher_is_better`.
5. Returns `list[ChangePointResult]` sorted by position.

Module constants: `DEFAULT_WINDOW_SIZE=30`, `DEFAULT_MAX_PVALUE=0.001`,
`DEFAULT_MIN_MAGNITUDE=0.0`, `DEFAULT_MIN_SAMPLE_SIZE=10`, `MIN_EFFECTIVE_WINDOW=4`.

## Worker Step

The change-point phase runs as **Phase 4** of the evaluation job, fault-isolated so detection
failure never blocks evaluation completion. It is split into three decoupled steps, each in its
own short DB session (orchestrated by `_run_change_point_phase()` in `queue.py`): a **read** that
loads baseline history once per SLO, a **compute** that runs detection holding no DB connection,
and a **write** that persists results. This keeps the phase from pinning one connection
idle-in-transaction across the CPU-bound detection, and collapses the per-objective history
loads into a single query per SLO.

**Read** (`load_change_point_inputs()`):

1. **Resolve comparison_name** from `snapshot.compare_to` via `resolve_comparison_name()`.
   If `comparison_name != evaluation_name` (cross-series comparison), return `None` -- CPs
   across different series are not statistically meaningful.
2. **Load system defaults** from `ConfigurationRepository.get_change_point_defaults()` (reads
   `change_point.*` entries from the `configuration` table).
3. **Resolve enabled objectives**: for each SLO objective with a matching indicator row,
   `ChangePointRepository.resolve_from_objective()` merges the per-objective override with system
   defaults (algorithm tuning params `pvalue_strict_threshold`/`pvalue_moderate_threshold` always
   come from system defaults); objectives with `enabled=False` are dropped. Returns `None` if
   none are enabled.
4. **Fetch baseline history once** via `BaselineRepository.get_evaluation_baselines()` with
   `limit = max(window_size)` across the enabled objectives, scoped by `evaluation_name` -- one
   query per SLO instead of one per objective.

**Compute** (`detect_change_points_for_objectives()`) -- pure, holds no DB session:

For each enabled objective, `extract_metric_series()` slices the shared history to that
objective's `window_size` (the most-recent N, ordered ascending) and pulls the metric's values;
skip if insufficient history (`< min_sample_size`); run `detect_change_points()`. Each objective
is wrapped in `try/except` catching `(OSError, ValueError, TypeError, RuntimeError, LookupError)`
so one metric's failure never aborts the others.

**Write** (`persist_detected_change_points()`): runs `_persist_change_points()` for each detected
batch in the write session.

**Persistence pipeline** (`_persist_change_points()`):

For each candidate CP:
1. Compute nearby timestamps (+-1 ordinal position in the series).
2. **Dedup check**: `has_nearby_change_point()` -- direction-agnostic. If a CP exists at a
   nearby timestamp, skip (first detection wins).
3. **Regime check**: `get_latest_change_point()` -- if the previous CP has the same direction
   AND `|current_mean - previous_mean| < 2 * previous_std`, suppress as "same regime."
4. Otherwise insert via `insert_change_point()`.
5. Track batch timestamps to avoid within-batch collisions.

## Repository

### ChangePointRepository

| Method | Purpose | Key Details |
|--------|---------|-------------|
| `has_nearby_change_point(asset_id, slo_name, metric_name, period_start, nearby_timestamps, evaluation_name?)` | Dedup check | Matches asset/slo/metric + period_start IN nearby_timestamps. Optional JOIN through indicator_results -> evaluations to filter by eval_name. Returns `bool`. |
| `get_latest_change_point(asset_id, slo_name, metric_name, evaluation_name?)` | Regime suppression lookup | Same identity filter, ORDER BY period_start DESC LIMIT 1. Returns `ChangePoint | None`. |
| `insert_change_point(ChangePointInsertParams)` | Insert new CP | session.add + flush. Returns `ChangePoint`. |
| `list_change_points(ChangePointListParams)` | Filtered list | Supports status, direction, asset_id, slo_name, metric_name, from_ts, to_ts filters. ORDER BY created_at DESC with limit (default 50) + offset. |
| `get_by_id(change_point_id)` | Single CP lookup | Returns `ChangePoint | None`. |
| `triage(change_point_id, status, triage_note?, linked_ticket?, triage_author?)` | Update triage fields | Sets status, note, ticket, author, triage_at=now(). Returns updated `ChangePoint | None`. |
| `bulk_triage(ids, status, triage_note?, triage_author?)` | Batch triage | UPDATE WHERE id IN (ids). Returns rowcount. |
| `get_change_points_for_evaluations(asset_id, slo_name?, period_starts)` | Heatmap batch query | JOINs evaluations, filters status != 'hidden'. Returns `dict[(metric_name, period_start, eval_name), ChangePoint]`. |
| `get_change_points_for_range(asset_id, slo_name, metric_name, from_ts, to_ts?)` | Trend batch query | Same dict pattern for time-range queries. |
| `resolve_from_objective(objective, system_defaults)` | Config resolution (static) | Reads `objective.change_point_config` relationship. Per-objective values override system defaults. Algorithm tuning params always from system defaults. Returns `ResolvedConfig`. |
| `upsert_config_for_objective(slo_objective_id, ...)` | Config upsert | SELECT existing, update or INSERT. Returns `ChangePointConfig`. |
| `delete_config_for_objective(slo_objective_id)` | Config delete | Returns `bool`. |
| `get_config_for_objective(slo_objective_id)` | Config read | Returns `ChangePointConfig | None`. |

## Router & Schemas

### Change Points Endpoints

| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | `/change-points` | query: status, direction, asset_id, slo_name, metric, from_ts, to_ts, limit, offset | `list[ChangePointRead]` | Global scope |
| GET | `/change-points/{change_point_id}` | -- | `ChangePointRead` | 404 if missing |
| PATCH | `/change-points/{change_point_id}` | `TriageRequest` | `ChangePointRead` | 404 if missing |
| PATCH | `/change-points/bulk-triage` | `BulkTriageRequest` | `{"updated": int}` | Global scope |
| GET | `/change-points/config/{objective_id}` | -- | `ChangePointConfigRead` | Falls back to system defaults |
| PUT | `/change-points/config/{objective_id}` | `ChangePointConfigInput` | `ChangePointConfigRead` | Upserts, fills absent fields from defaults |
| DELETE | `/change-points/config/{objective_id}` | -- | 204 | 404 if no override exists |

### Configuration Endpoints

| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | `/configuration` | query: prefix? | `list[ConfigurationRead]` |
| GET | `/configuration/{name:path}` | -- | `ConfigurationRead` |
| PUT | `/configuration/{name:path}` | `ConfigurationUpdate` | `ConfigurationRead` |

### Key Schemas

- **ChangePointMarker** -- lightweight `{direction, change_relative_pct, transition}` used on
  heatmap cells, indicator results, and trend points across all three response surfaces.
  `change_relative_pct` is nullable (null when `transition` is set).
- **ChangePointRead** -- full detail with identity, stats, triage fields, timestamps.
- **TriageRequest** (StrictInput) -- `status`, optional `triage_note`, `linked_ticket`, `triage_author`.
- **BulkTriageRequest** (StrictInput) -- `ids: list[UUID]`, `status`, optional note/author.
- **ChangePointConfigInput** (StrictInput) -- all fields optional, uses `StrictBool`, `IntNotBool`,
  `FloatNotBool` for strict type coercion.
- **ChangePointConfigRead** -- fully resolved config for an objective.

## DB Models

### `change_points` table

Stores detected distributional shifts with denormalized identity for fast queries.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| indicator_result_id | UUID FK | -> indicator_results, ON DELETE SET NULL, nullable |
| evaluation_run_id | UUID FK | -> evaluations, ON DELETE SET NULL, nullable |
| asset_id | UUID | NOT NULL, denormalized |
| slo_name, metric_name | Text | NOT NULL, denormalized |
| period_start | DateTime(tz) | NOT NULL |
| detector | Text | default 'e_divisive' |
| direction | Text | 'regression' or 'improvement' |
| change_relative_pct | Float | nullable -- null when `transition` is set (segment mean of 0) |
| change_absolute, pvalue | Float | NOT NULL |
| pre_segment_mean, post_segment_mean, post_segment_std | Float | NOT NULL |
| transition | Text | nullable -- 'appeared' or 'vanished'; set when a segment mean is exactly 0 and `change_relative_pct` is null |
| status | Text | default 'unprocessed' |
| triage_author, triage_note, linked_ticket | Text | nullable |
| triage_at, created_at, updated_at | DateTime(tz) | |

**Indexes**: `idx_change_points_identity` on (asset_id, slo_name, metric_name, period_start)
for dedup; `idx_change_points_run` on (evaluation_run_id, metric_name, period_start) for
heatmap queries; `idx_change_points_unprocessed` partial index on status='unprocessed' for
triage queue; `idx_change_points_indicator` on indicator_result_id; `idx_change_points_created`
on created_at.

### `change_point_config` table

Sparse override table -- rows exist only when an objective deviates from system defaults.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| slo_objective_id | UUID FK | -> slo_objectives, CASCADE, UNIQUE |
| enabled, higher_is_better | Boolean | |
| window_size, min_sample_size | Integer | |
| max_pvalue, min_magnitude | Float | |
| created_at, updated_at | DateTime(tz) | |

The `SLOObjective` model has a `change_point_config` relationship (`uselist=False`,
`lazy='joined'`) to avoid N+1 queries.

## Integration Seams

**Evaluation executor** -- `EvaluationSnapshot` carries `compare_to: dict[str, str] | None`.
`resolve_comparison_name()` derives the target series name for both baseline queries (Phase 2)
and CP detection (Phase 4).

**Worker queue** -- Phase 4 of `run_evaluation_job()` is `_run_change_point_phase()`, which
orchestrates the read / compute / write steps across two short sessions (compute holds none)
with blanket exception handling. The read session re-loads indicator rows via
`IndicatorRepository.get_for_evaluation()`.

**Presenter** -- `build_column_fragment()` accepts an optional `change_point_lookup` dict and
populates `HeatmapCellGrouped.change_point` with a `ChangePointMarker`. The helper
`_resolve_change_point_marker()` performs the lookup by (metric_name, period_start, eval_name).

**Heatmap cache** -- cached fragments do NOT contain CP data. The router enriches responses
post-assembly via `_enrich_heatmap_with_change_points()`, which batch-loads CPs from the DB.
This is intentional: CPs can be triaged/hidden after a fragment is cached.

**Trend endpoints** -- both trend routes query `ChangePointRepository.get_change_points_for_range()`
and pass the lookup into `TrendRepository.get_trend_by_domain()`, which attaches a `change_point`
dict to each trend point.

**SLO registry** -- `SLORepository.create()` calls `_attach_change_point_config()` per objective
using three-tier priority: explicit input > copy-forward from previous SLO version > no row
(system defaults apply at detection time).

**Trigger service** -- passes `compare_to` from the evaluation request through to
`EvaluationRunRepository.create()`, which stores it as JSONB.

**Baseline repository** -- all baseline query methods accept an optional `evaluation_name`
parameter to scope history to a single evaluation series.

## Test Organisation

**Engine unit tests** (`tests/change_points/engine/`, 3 files) -- pure algorithm verification:
fill_missing, split+merge on known step changes, Q-hat matrix correctness (brute-force vs
vectorised), ChangePointDetector with both permutation and t-test testers, boundary CP
regression test.

**Detector wrapper tests** (`test_detector.py`) -- flat series produces no CPs, step
regression/improvement detected with correct direction, too-few-samples returns empty.

**Detection scenarios** (`test_detection_scenarios.py`) -- end-to-end with real detector + fake
repos: step regression/improvement, spike-and-recovery, same-regime suppression, eval-name scoping.

**Worker step tests** (`test_worker_step.py`) -- mocked detector: config resolution,
disabled/missing metric skip, dedup, `_same_regime()` (7 cases), regime consolidation.

**Presenter enrichment** (`test_presenter_enrichment.py`) -- ChangePointMarker serialization,
resolver returns None on no lookup/no match/wrong eval name, returns marker on match.

**Generators** (`generators.py`, `test_generators.py`) -- 5 synthetic series classes:
StableGenerator, StepChangeGenerator, DriftGenerator, MultipleChangePointGenerator, plus
make_timestamps. Tests validate detector behavior against each pattern.

**Integration tests** (`db/test_repository.py`) -- real database: dedup (nearby, distant,
hidden status, different direction), config CRUD, resolve_from_objective with/without override,
insert/read round-trip for a null `change_relative_pct` with a `transition` value.

## Known Issues & Limitations

**Variance-only changes not detected.** E-Divisive detects mean shifts but not pure variance
changes. A test explicitly documents that moderate variance increase (scale 5 to 15) produces
no CPs. A dedicated variance detector (e.g. Levene's test) would be needed.

**Slow drift may evade detection.** Gradual drifts (e.g. 100 to 110 over 50 steps with noise)
may not trigger detection. Test expects <= 1 result.

**Dedup is direction-agnostic.** A regression at position X blocks an improvement at the same
position. This is intentional (first detection wins) but means spike-and-recovery patterns
require the +-1 position tolerance to work correctly.

**Hidden CPs still block dedup.** Triaged/hidden CPs prevent re-detection at the same position.
This avoids re-insertion after triaging but means hiding a CP does not allow re-detection.

**No recency filter.** CPs deep in history (e.g. position 5 in a 20-element series) are saved.
Dedup prevents duplicates on subsequent evaluations.

**Cross-series detection silently skipped.** When `compare_to` points to a different series,
detection is skipped entirely without user notification.

**Naming collision.** Two files named `detector.py`: `modules/change_points/detector.py` (pure
function wrapper) and `modules/change_points/engine/detector.py` (recursive loop). Different
purposes, potential import confusion.

**Untested paths.** No integration tests for `list_change_points()` filter combinations,
`triage()`/`bulk_triage()` repository methods, `get_change_points_for_evaluations()`/
`get_change_points_for_range()` batch queries, or router HTTP-level endpoints.

**Permutation tester unused.** `PermutationsSignificanceTester` is tested but not used in
production; t-test is the default path.
