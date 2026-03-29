"""Statistical computation for aggregated-mode query results.

Uses numpy for efficient array operations. NaN values are filtered
before computation. Empty arrays after filtering produce None for all methods.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from app.core.methods import AggregationMethod

_PERCENTILE_MAP: dict[AggregationMethod, float] = {
    AggregationMethod.MEDIAN: 50.0,
    AggregationMethod.P75: 75.0,
    AggregationMethod.P90: 90.0,
    AggregationMethod.P95: 95.0,
    AggregationMethod.P99: 99.0,
}

_SIMPLE_DISPATCH: dict[AggregationMethod, object] = {
    AggregationMethod.MIN: lambda a: float(np.min(a)),
    AggregationMethod.MAX: lambda a: float(np.max(a)),
    AggregationMethod.MEAN: lambda a: float(np.mean(a)),
    AggregationMethod.SUM: lambda a: float(np.sum(a)),
    AggregationMethod.STD: lambda a: float(np.std(a, ddof=0)),
}


def compute_statistics(
    values: list[float],
    methods: list[AggregationMethod],
) -> dict[AggregationMethod, float | None]:
    """Compute requested statistics on a 1-D array of floats.

    NaN values are dropped before computation. If the array is empty after
    filtering, all methods return None.

    Args:
        values: Raw float values (may contain NaN).
        methods: List of AggregationMethod members to compute.

    Returns:
        Dict mapping each requested method to its computed value or None.
    """
    arr = np.array(values, dtype=np.float64)
    clean: NDArray[np.float64] = arr[~np.isnan(arr)]

    if clean.size == 0:
        return dict.fromkeys(methods, None)

    result: dict[AggregationMethod, float | None] = {}
    for method in methods:
        if method in _SIMPLE_DISPATCH:
            result[method] = _SIMPLE_DISPATCH[method](clean)
        elif method in _PERCENTILE_MAP:
            result[method] = float(np.percentile(clean, _PERCENTILE_MAP[method]))

    return result
