# E-Divisive Algorithm — Optimization Opportunities

Analysis of computational bottlenecks in the vendored E-Divisive change point detection
engine (`api/tropek/modules/change_points/engine/`) and potential optimizations.

Based on the original algorithm from Matteson & James (2014) and the Hunter adaptation
by Fleming et al. (2023).

---

## Current Complexity Profile

The algorithm has two phases: **split** (sliding window detection) and **merge**
(iterative removal of weak change points).

### Split phase (`analysis.py::split`)

```
For each window position (n / step windows):
    Create PairDistanceCalculator          → O(w²) distance matrix
    For each recursive iteration:
        Compute Q-hat for each interval    → O(w²) per interval
        T-test significance                → O(w)
```

- Distance matrix: O(w²) memory and compute per window, where w = window_len
- Q-hat (`_get_Q_vals`): O(w²) per interval, building A/B/C from V/H cumulative sums
- Number of windows: O(n / step), where step = w/2
- **Total split phase: O(n · w)** — dominated by redundant distance matrix recomputation

### Merge phase (`analysis.py::merge`)

```
While change points remain:
    Find weakest by p-value              → O(k)
    Find weakest by magnitude            → O(k)
    Remove and recompute neighbors       → O(n) per recompute (rebuilds intervals + t-test)
```

- k = number of change points (typically small, < 10)
- **Total merge phase: O(k² · n)** — fast in practice since k is small

### Overall: O(n · w) for typical inputs

The split phase dominates. For a 1000-point series with w=30, that's ~33 windows
each computing a 30×30 distance matrix — roughly 30,000 pairwise distance computations
repeated 33 times despite 50% window overlap.

---

## Optimization 1: Reuse distance matrix across sliding windows

**Speedup: ~5–10× for split phase | Effort: Low | Risk: None (mathematically identical)**

### Problem

`split()` creates a new `PairDistanceCalculator` for each window position. Each
constructor call triggers `_calculate_pairwise_differences()` which builds the full
O(w²) distance matrix from scratch — even though consecutive windows share ~50% of
their data points.

### Approach

Compute the full-series distance matrix once, then extract submatrices per window
via numpy slicing (O(1) view, no copy):

```python
# Compute once for the full series — O(n²) total, paid once
full_distances = np.power(np.abs(series[:, None] - series[None, :]), power)

# Each window extracts a view — O(1)
window_distances = full_distances[start:end, start:end]
```

### Implementation sketch

Refactor `PairDistanceCalculator` to accept a precomputed distance matrix:

```python
class PairDistanceCalculator(Calculator):

    def __init__(
        self, series: NDArray, power: float = 1.0,
        precomputed_distances: NDArray | None = None,
    ) -> None:
        super().__init__(series)
        self.power = power
        if precomputed_distances is not None:
            self.distances = precomputed_distances
        # V and H are still computed lazily per interval
```

Then `split()` computes the full distance matrix once and passes slices:

```python
full_distances = np.power(np.abs(series[:, None] - series[None, :]), power)

while start < series_len:
    end = min(start + window_len, series_len)
    window_series = series[start:end]
    window_distances = full_distances[start:end, start:end]
    calc = PairDistanceCalculator(window_series, precomputed_distances=window_distances)
    # ...
```

### Trade-off

Requires O(n²) memory for the full distance matrix. For n=10,000 this is ~800 MB
(float64) — acceptable for typical performance test series (hundreds to low thousands
of data points). For very long series (n > 50,000), a chunked approach would be needed.

---

## Optimization 2: Early-exit Q-hat scan

**Speedup: Up to 3–5× for `_get_Q_vals` | Effort: Low | Risk: None (identical results)**

### Problem

`_get_Q_vals()` computes the entire Q = A - B - C matrix, then takes `argmax`. For
a w×w matrix this means computing all w² entries even though we only need the maximum.

### Approach

Compute A first (the dominant positive term), maintain a running maximum, and skip
(i, j) positions where A[i,j] is already below the current best Q. Since B and C
are non-negative, Q[i,j] = A[i,j] - B[i,j] - C[i,j] ≤ A[i,j]. If A[i,j] < current
best Q, that position can never be the argmax.

### Implementation sketch

```python
def _get_Q_vals(self, start: int, end: int) -> NDArray:
    # ... compute A as before ...

    # Early exit: find upper bound from A alone
    a_max = np.max(A)
    # Only compute B and C for positions where A could beat current best
    # In the vectorized form, this means masking the B/C computation

    q_max = 0.0
    best_i, best_j = 0, 0

    # Row-wise scan with pruning
    for i in range(A.shape[0]):
        row_a_max = np.max(A[i, :])
        if row_a_max < q_max:
            continue  # entire row pruned
        q_row = A[i, :] - B[i, :] - C[i, :]
        row_max_idx = np.argmax(q_row)
        if q_row[row_max_idx] > q_max:
            q_max = q_row[row_max_idx]
            best_i, best_j = i, row_max_idx

    return best_i, best_j, q_max
```

### Trade-off

Adds branching which reduces numpy vectorization benefit. Best gains come from series
with one dominant change point (common case) — the pruning eliminates most of the
matrix. Worst case (flat series, uniform Q) gains nothing.

Note: this changes the return type from a full matrix to just the argmax. Callers
that need the full Q matrix (tests, debugging) would need a separate code path.

---

## Optimization 3: Sorted-array trick for 1D absolute distances

**Speedup: O(n²) → O(n log n) per interval | Effort: Medium | Risk: None (exact)**

### Problem

The Q-hat computation requires pairwise distance sums of the form:

```
A = (2 / (κ - start)) · Σ |x_i - x_j|  for i < τ, j ≥ τ
B = ... · Σ |x_i - x_k|  for i, k < τ
C = ... · Σ |x_j - x_k|  for j, k ≥ τ
```

The current implementation precomputes all O(n²) pairwise distances, then uses
cumulative sums to compute A, B, C. For 1D data with power=1 (the default and most
common case), there's a well-known trick to compute these sums in O(n log n).

### Mathematical basis

For a sorted array z₁ ≤ z₂ ≤ ... ≤ zₙ:

```
Σᵢ<ⱼ |zᵢ - zⱼ| = Σⱼ (2j - n - 1) · zⱼ
```

This follows from the identity: for sorted values, |zᵢ - zⱼ| = zⱼ - zᵢ when i < j.
Each zⱼ appears in (j-1) terms as the larger value and (n-j) terms as the smaller,
giving a net coefficient of (2j - n - 1).

For cross-set sums Σ |xᵢ - yⱼ| where x ∈ left, y ∈ right:

1. Merge-sort the two sets, tracking which set each element belongs to
2. Use prefix sums on the sorted merged array to compute the cross-set sum
3. Total: O((n_left + n_right) · log(n_left + n_right))

### Applicability

Only works for `power=1` (the default). For other powers (0 < power < 2), the
identity doesn't hold and O(n²) pairwise computation is unavoidable. The calculator
already supports arbitrary power via `self.power`, so this would be a specialized
fast path for the common case.

### Trade-off

More complex implementation. The current vectorized numpy approach is elegant and
easy to verify against the brute-force reference. A sorted-array version would need
its own verification tests. Worth it only for series longer than ~500 points where
the O(n²) → O(n log n) difference is measurable.

---

## Optimization 4: Cache V/H cumulative sums across recursive iterations

**Speedup: ~2× for `get_change_points` | Effort: Medium | Risk: None (identical)**

### Problem

Inside `get_change_points()`, the recursive while-loop finds change points one at a
time. Each iteration calls `calc.get_next_candidate(intervals)`, which calls
`_get_Q_vals(start, end)` for each interval. `_get_Q_vals` lazily computes V and H
from the distance matrix on first call, then caches them.

However, V and H are cumulative sums over the **full series** distance matrix —
they don't change when intervals are refined. Only the (start, end) slicing into
V and H changes. The current code correctly caches V/H after the first call, but
the cache is per-calculator-instance. Since `split()` creates a new calculator per
window (Optimization 1 addresses this), V/H are recomputed for each window.

### Approach

If Optimization 1 is implemented (shared distance matrix), V and H should also be
computed once for the full series and shared. Per-interval Q-hat then becomes pure
index arithmetic on the shared V/H arrays — no redundant cumulative sums.

### Implementation sketch

```python
class PairDistanceCalculator(Calculator):

    def __init__(self, series, power=1.0, shared_state=None):
        super().__init__(series)
        if shared_state:
            self.distances = shared_state.distances
            self.V = shared_state.V
            self.H = shared_state.H
        # _get_Q_vals now just slices into pre-existing V/H
```

### Trade-off

Tightly couples to Optimization 1. Implement them together for maximum benefit.

---

## Optimization 5: Approximate Q-hat via random subsampling

**Speedup: O(n²) → O(n log n) | Effort: Low | Risk: Small (approximate)**

### Problem

Computing exact Q-hat requires all O(n²) pairwise distances. For long series this
dominates runtime.

### Mathematical basis

Matteson & James (2014, Section 3.2) note that the energy statistic E(X, Y) can be
consistently estimated using random subsamples. Instead of all n_left × n_right cross
pairs, sample m random pairs and scale:

```
Ê = (n_left · n_right / m) · Σₖ₌₁ᵐ |x_iₖ - y_jₖ|
```

where (iₖ, jₖ) are m randomly chosen pairs. The estimator is unbiased and converges
at rate O(1/√m). Setting m = O(n log n) gives high-probability accuracy guarantees.

### Implementation sketch

```python
def _get_Q_vals_approximate(self, start, end, n_samples=None):
    n = end - start
    if n_samples is None:
        n_samples = int(n * np.log(n))

    # Sample random index pairs instead of computing full matrix
    rng = np.random.default_rng(self._seed)
    indices_i = rng.integers(start, end, size=n_samples)
    indices_j = rng.integers(start, end, size=n_samples)

    # Compute distances only for sampled pairs
    sampled_distances = np.abs(self.series[indices_i] - self.series[indices_j])
    # ... estimate Q-hat from sampled distances
```

### Trade-off

Introduces approximation error. The argmax position may differ from the exact
computation, potentially missing or misplacing change points. Appropriate for
exploratory/fast-mode detection, not for final statistical assessment. Could be
used as a first pass to identify candidate regions, followed by exact computation
in those regions only.

---

## Optimization 6: Doubly-linked list for merge phase

**Speedup: O(k) → O(1) neighbor access | Effort: Low | Risk: None**

### Problem

`merge()` removes the weakest change point and recomputes stats for its neighbors.
Finding the neighbors requires `change_points.index(weakest)` — O(k) linear scan.
After removal, the neighbor indices shift.

### Approach

Use a doubly-linked list or maintain prev/next pointers so that after removing a
node, its neighbors are immediately accessible in O(1).

### Trade-off

k (number of change points) is typically < 10 in practice, so the absolute time
saved is negligible. This is a clean-code improvement more than a performance one.
Only worth implementing if merge becomes a bottleneck on series with many change
points (k > 50).

---

## Priority Matrix

| # | Optimization | Speedup | Effort | Risk | Depends on |
|---|---|---|---|---|---|
| 1 | Reuse distance matrix | 5–10× split | Low | None | — |
| 4 | Cache V/H sums | 2× recursive | Medium | None | #1 |
| 2 | Early-exit Q scan | Up to 3–5× | Low | None | — |
| 3 | Sorted-array 1D | O(n²)→O(n log n) | Medium | None | — |
| 5 | Subsampling | O(n²)→O(n log n) | Low | Approximate | — |
| 6 | Linked list merge | Negligible | Low | None | — |

**Recommended implementation order:** #1 → #2 → #4 → #3.

Optimizations #1 and #2 are independent, low-risk, and give the best return for
typical series lengths (100–1000 points). #4 builds on #1. #3 is the most impactful
for long series but requires the most work and careful testing. #5 is only needed
if exact computation remains too slow after #1–#4. #6 is cosmetic.

---

## Validation Strategy

Any optimization must prove two things: **(1) identical results** and **(2) faster
execution**. This section defines the test data, equivalence criteria, and benchmark
methodology needed to validate each optimization before merging.

### Principle: same inputs, same outputs, less time

Every optimization has a "reference" (current implementation) and a "candidate"
(optimized implementation). The validation pipeline:

```
generate test data → run reference → run candidate → compare outputs → compare time
```

Both implementations must coexist during validation. The recommended approach is to
add an `optimized=True` flag or a parallel class (e.g., `FastPairDistanceCalculator`)
rather than replacing the original in-place. The original is removed only after all
validation passes.

### Test data requirements

The generators in `tests/change_points/generators.py` produce all needed patterns.
Each test series should be generated with a **fixed seed** for determinism.

| Generator | Purpose | Parameters |
|---|---|---|
| `StableGenerator` | No change — tests false positive rate | `loc=100, scale=5, seed=1` |
| `StepChangeGenerator` | Single abrupt shift | `before={loc:100, scale:5}, after={loc:150, scale:5}, cp=50` |
| `StepChangeGenerator` | Small shift (sensitivity) | `before={loc:100, scale:5}, after={loc:108, scale:5}, cp=50` |
| `DriftGenerator` | Gradual shift | `before={loc:100, scale:3}, after={loc:130, scale:3}, cp=30, steps=40` |
| `VarianceChangeGenerator` | Variance-only change | `loc=100, scale_before=5, scale_after=15, cp=50` |
| `MultipleChangePointGenerator` | Two shifts | `segments=[(0, {loc:100}), (35, {loc:150}), (70, {loc:80})]` |

Each pattern should be generated at multiple lengths to test scaling:

| Length | Purpose |
|---|---|
| 100 | Minimum viable (current test suite) |
| 500 | Typical performance test history |
| 1,000 | Long-running metric |
| 5,000 | Stress test — where O(n²) vs O(n log n) diverges |
| 10,000 | Upper bound — only for optimizations #3 and #5 |

### Tier 1: Exact numerical equivalence

For optimizations #1, #2, #3, #4, and #6 — results must be **bit-identical**.

#### Q-hat matrix equivalence

The strongest test: compare the full Q-hat matrix between reference and optimized
calculators. This catches any numerical drift in intermediate computations.

```python
def test_optimized_qhat_matches_reference(series_length, seed):
    """Q-hat matrix from optimized calculator must match reference exactly."""
    gen = StepChangeGenerator(
        dist=norm, before={"loc": 100, "scale": 5},
        after={"loc": 150, "scale": 5}, changepoint=series_length // 2, seed=seed,
    )
    series = np.array(gen.generate(series_length))

    reference_calc = PairDistanceCalculator(series)
    reference_Q = reference_calc._get_Q_vals(0, len(series))

    optimized_calc = OptimizedPairDistanceCalculator(series)
    optimized_Q = optimized_calc._get_Q_vals(0, len(series))

    assert reference_Q.shape == optimized_Q.shape
    assert np.allclose(reference_Q, optimized_Q, atol=1e-12)
```

Run for every (pattern, length) combination. The `atol=1e-12` tolerance accounts
for floating-point reordering in vectorized operations — if the optimization changes
the summation order, the last few bits may differ.

#### Change point position equivalence

End-to-end test: same detected change points from `detect_change_points()`.

```python
def test_optimized_detection_matches_reference(series_length, seed):
    """Detected change points must be identical between implementations."""
    gen = StepChangeGenerator(
        dist=norm, before={"loc": 100, "scale": 5},
        after={"loc": 150, "scale": 5}, changepoint=series_length // 2, seed=seed,
    )
    series = gen.generate(series_length)
    timestamps = make_timestamps(series_length)

    reference_results = detect_change_points_reference(
        values=series, timestamps=timestamps, higher_is_better=False,
    )
    optimized_results = detect_change_points_optimized(
        values=series, timestamps=timestamps, higher_is_better=False,
    )

    assert len(reference_results) == len(optimized_results)
    for ref, opt in zip(reference_results, optimized_results):
        assert ref.position == opt.position
        assert ref.direction == opt.direction
        assert abs(ref.pvalue - opt.pvalue) < 1e-10
        assert abs(ref.change_relative_pct - opt.change_relative_pct) < 1e-6
```

#### Windowed detection equivalence

Specifically for optimization #1 (shared distance matrix): verify that each
window produces the same Q-hat when extracted from a shared matrix vs computed
independently.

```python
def test_shared_distance_matrix_per_window(series_length, window_len):
    """Each window's Q-hat from shared matrix must match standalone computation."""
    series = np.array(StableGenerator(
        dist=norm, params={"loc": 100, "scale": 5}, seed=1,
    ).generate(series_length))

    full_distances = np.power(np.abs(series[:, None] - series[None, :]), 1.0)
    step = window_len // 2

    start = 0
    while start < series_length:
        end = min(start + window_len, series_length)

        # Reference: fresh calculator
        ref_calc = PairDistanceCalculator(series[start:end])
        ref_Q = ref_calc._get_Q_vals(0, end - start)

        # Optimized: shared distance matrix, sliced
        opt_calc = PairDistanceCalculator(
            series[start:end],
            precomputed_distances=full_distances[start:end, start:end],
        )
        opt_Q = opt_calc._get_Q_vals(0, end - start)

        assert np.allclose(ref_Q, opt_Q, atol=1e-12), (
            f"Q-hat mismatch in window [{start}:{end}]"
        )
        start += step
```

#### Edge cases

These must pass for both reference and optimized:

```python
# Minimum-length series (2 points)
test_two_point_series()

# All identical values (Q-hat should be all zeros)
test_constant_series()

# Single outlier in otherwise flat series
test_single_spike()

# Series where change point is at position 1 or len-1 (boundary)
test_boundary_change_point()

# Very large step (mean jumps by 100× the std)
test_extreme_step_change()

# Very small step (mean shifts by 0.1× the std — should not be detected)
test_subthreshold_step_change()
```

### Tier 2: Statistical equivalence (optimization #5 only)

Subsampling produces approximate results. Exact bit-equality is not expected.
Instead, validate statistically:

```python
def test_approximate_detection_accuracy(n_trials=1000):
    """Approximate Q-hat must agree with exact on CP position in >99% of trials."""
    agreements = 0
    for seed in range(n_trials):
        gen = StepChangeGenerator(
            dist=norm, before={"loc": 100, "scale": 5},
            after={"loc": 150, "scale": 5}, changepoint=50, seed=seed,
        )
        series = gen.generate(100)
        timestamps = make_timestamps(100)

        exact = detect_change_points_exact(values=series, timestamps=timestamps)
        approx = detect_change_points_approximate(values=series, timestamps=timestamps)

        if len(exact) == len(approx):
            if all(abs(e.position - a.position) <= 1 for e, a in zip(exact, approx)):
                agreements += 1

    accuracy = agreements / n_trials
    assert accuracy > 0.99, f"Approximate detection accuracy {accuracy:.3f} < 0.99"


def test_approximate_no_false_positives(n_trials=500):
    """Approximate method must not detect CPs in stable series."""
    false_positives = 0
    for seed in range(n_trials):
        gen = StableGenerator(dist=norm, params={"loc": 100, "scale": 5}, seed=seed)
        series = gen.generate(100)
        timestamps = make_timestamps(100)

        results = detect_change_points_approximate(values=series, timestamps=timestamps)
        if len(results) > 0:
            false_positives += 1

    fp_rate = false_positives / n_trials
    assert fp_rate < 0.01, f"False positive rate {fp_rate:.3f} > 0.01"
```

### Tier 3: Performance benchmarks

Prove the optimization is actually faster. Use `time.perf_counter` (not
`pytest-benchmark`) to keep it simple and dependency-free.

```python
def benchmark_split_phase(series_lengths, n_repeats=5):
    """Compare wall-clock time of reference vs optimized split phase."""
    for length in series_lengths:
        gen = StepChangeGenerator(
            dist=norm, before={"loc": 100, "scale": 5},
            after={"loc": 150, "scale": 5},
            changepoint=length // 2, seed=42,
        )
        series = np.array(gen.generate(length))

        # Reference timing
        ref_times = []
        for _ in range(n_repeats):
            start_t = time.perf_counter()
            split_reference(series, window_len=30, max_pvalue=0.001)
            ref_times.append(time.perf_counter() - start_t)

        # Optimized timing
        opt_times = []
        for _ in range(n_repeats):
            start_t = time.perf_counter()
            split_optimized(series, window_len=30, max_pvalue=0.001)
            opt_times.append(time.perf_counter() - start_t)

        ref_median = np.median(ref_times)
        opt_median = np.median(opt_times)
        speedup = ref_median / opt_median

        print(f"n={length:>6d}  ref={ref_median:.4f}s  opt={opt_median:.4f}s  speedup={speedup:.1f}x")

# Expected output (example):
# n=   100  ref=0.0012s  opt=0.0008s  speedup=1.5x
# n=   500  ref=0.0310s  opt=0.0055s  speedup=5.6x
# n=  1000  ref=0.1240s  opt=0.0180s  speedup=6.9x
# n=  5000  ref=3.1000s  opt=0.2100s  speedup=14.8x
```

#### Memory benchmarks (optimization #1)

The shared distance matrix trades memory for speed. Verify the trade-off is
acceptable:

```python
def benchmark_memory(series_lengths):
    """Measure peak memory of reference vs optimized."""
    for length in series_lengths:
        series = np.array(StableGenerator(
            dist=norm, params={"loc": 100, "scale": 5}, seed=42,
        ).generate(length))

        tracemalloc.start()
        split_reference(series, window_len=30, max_pvalue=0.001)
        ref_peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()

        tracemalloc.start()
        split_optimized(series, window_len=30, max_pvalue=0.001)
        opt_peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()

        print(f"n={length:>6d}  ref={ref_peak/1e6:.1f}MB  opt={opt_peak/1e6:.1f}MB")

# Expected: optimization #1 uses more memory (full n×n matrix)
# n=   100  ref=0.2MB   opt=0.3MB    (negligible)
# n=  1000  ref=1.8MB   opt=8.2MB    (acceptable)
# n=  5000  ref=4.5MB   opt=200MB    (review threshold)
# n= 10000  ref=8.0MB   opt=800MB    (may need chunked approach)
```

### Validation checklist per optimization

Before merging any optimization, all applicable checks must pass:

| Check | #1 | #2 | #3 | #4 | #5 | #6 |
|---|---|---|---|---|---|---|
| Q-hat matrix equivalence | yes | yes | yes | yes | statistical | n/a |
| CP position equivalence | yes | yes | yes | yes | statistical | yes |
| Windowed detection equivalence | yes | n/a | n/a | yes | n/a | n/a |
| Edge cases (boundary, constant, spike) | yes | yes | yes | yes | yes | yes |
| No false positives on stable series | yes | yes | yes | yes | yes | yes |
| Wall-clock speedup demonstrated | yes | yes | yes | yes | yes | n/a |
| Memory usage within bounds | yes | n/a | n/a | yes | n/a | n/a |
| Existing test suite passes (35 tests) | yes | yes | yes | yes | yes | yes |
