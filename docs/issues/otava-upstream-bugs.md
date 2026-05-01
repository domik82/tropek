# Apache Otava — Upstream Bug Report

Two bugs in `otava/change_point_divisive/detector.py` `get_change_points()`, both
affecting windowed detection via `split()`.

Discovered during extraction of the E-Divisive algorithm into
[TROPEK](https://github.com/tropek) change point detection module.

Repository: https://github.com/apache/otava
File: `otava/change_point_divisive/detector.py`, lines 35–63

---

## Bug 1: Windowed slicing skipped for numpy arrays

### Description

`get_change_points(series, start, end)` only slices the series when it is **not**
a numpy array. If `series` is already an ndarray, the `start`/`end` parameters are
silently ignored — the detector runs on the full array instead of the requested window.

### Root cause

```python
# detector.py, lines 37-38
if not isinstance(series, np.ndarray):
    series = np.array(series[start : end], dtype=np.float64)
```

When `series` is a list, it gets sliced to `series[start:end]` and converted to ndarray.
When `series` is already an ndarray, the branch is skipped entirely — no slicing happens.

### Impact

`split()` in `analysis.py` calls `get_change_points(series, start, end)` in a sliding
window loop. If `series` is an ndarray (common when callers pre-convert or chain from
`compute_change_points`), every window call runs the detector on the **full series**
instead of the window. The detected change points get `start` added to their indices
(line 59–61), producing incorrect positions that may fall outside the window or the
series entirely.

In practice this means `split()` silently returns no change points or wrong change
points when the input is a numpy array, because:
1. The detector finds CPs at global positions (e.g., index 50 in a 100-point series)
2. The offset `start` is added (e.g., 50 + 30 = 80)
3. The resulting index 80 doesn't correspond to a real distributional shift in the window

### Reproduction

```python
import numpy as np
from otava.change_point_divisive.detector import ChangePointDetector
from otava.change_point_divisive.calculator import PairDistanceCalculator
from otava.analysis import TTestSignificanceTester

# Step change at position 50: mean jumps from 100 to 150
rng = np.random.default_rng(42)
series = np.concatenate([
    rng.normal(100, 5, size=50),
    rng.normal(150, 5, size=50),
])

tester = TTestSignificanceTester(max_pvalue=0.05)
detector = ChangePointDetector(significance_tester=tester, calculator=PairDistanceCalculator)

# Direct slice — works correctly
window = series[35:65]
cps_direct = detector.get_change_points(series=window)
print("Direct slice:", [(cp.index, round(cp.stats.pvalue, 6)) for cp in cps_direct])
# Expected: detects change point near index 15 (= position 50 - 35)

# Windowed call — BUG: start/end ignored because series is ndarray
cps_windowed = detector.get_change_points(series, start=35, end=65)
print("Windowed call:", [(cp.index, round(cp.stats.pvalue, 6)) for cp in cps_windowed])
# Expected: same as direct slice, offset by 35
# Actual: empty list or wrong indices — detector ran on full 100-point series
```

### Fix

Always slice when `start` or `end` is provided, regardless of type:

```python
def get_change_points(self, series, start=None, end=None):
    if start is not None or end is not None:
        series = series[start:end]
    if not isinstance(series, np.ndarray):
        series = np.array(series, dtype=np.float64)
    if not np.issubdtype(series.dtype, np.floating):
        series = series.astype(np.float64, copy=False)
    # ... rest unchanged
```

---

## Bug 2: Boundary change point crashes `compare()`

### Description

`get_change_points()` can return a change point with `index == len(subarray)`.
After the offset addition (`cp.index += start`), this becomes `index == end` — a
boundary position that produces an empty segment when `TTestSignificanceTester`
tries to split the series at that index, crashing with `ValueError` in `compare()`.

### Root cause

The E-Divisive Q-hat maximization in `PairDistanceCalculator.get_candidate_change_point()`
can select `index == len(subarray)` as the argmax position. This is a valid mathematical
result (the dissimilarity function peaks at the boundary) but not a valid change point —
there are zero data points on one side.

`get_change_points()` does not filter these boundary candidates before returning them.
When `split()` later calls `tester.change_point()` or `tester.compare()` with this
boundary index, one of the segments is empty:

```python
# analysis.py, TTestSignificanceTester.compare()
def compare(self, left, right):
    if len(left) == 0 or len(right) == 0:
        raise ValueError  # <-- crashes here
```

### Reproduction

```python
import numpy as np
from otava.analysis import split

# Clean step change — 15 points at 10.0, then 15 points at 50.0
series = np.array([10.0] * 15 + [50.0] * 15, dtype=np.float64)

# This can raise ValueError when the detector returns a boundary CP
try:
    result = split(series, window_len=30, max_pvalue=0.01)
    print("Change points:", [cp.index for cp in result])
except ValueError as e:
    print(f"Crash: {e}")
    # ValueError from compare() receiving an empty segment
```

Note: this bug is non-deterministic in the sense that it depends on the exact data
values and window alignment. The step series `[10]*15 + [50]*15` with `window_len=30`
reliably triggers it because the entire series fits in one window and the Q-hat maximum
lands at the boundary.

### Fix

Filter boundary change points before returning from `get_change_points()`:

```python
# After offset addition, before return:
effective_end = end if end is not None else (start or 0) + len(series)
change_points = [cp for cp in change_points if 0 < cp.index < effective_end]
```

And/or in `split()`, before passing CPs to `get_intervals()`:

```python
for cp in new_change_points:
    if cp.index <= 0 or cp.index >= len(series):
        continue
    if cp not in change_points:
        change_points.append(cp)
```

Both locations are recommended — `get_change_points()` as the primary fix (protects
all callers), `split()` as defense-in-depth.
