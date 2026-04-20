"""Pure change point detector — wraps Apache Otava's E-Divisive algorithm.

No I/O. Takes a list of values + timestamps, returns detected change points
with direction, magnitude, and statistical significance.

Global defaults live here as module constants so the whole system has one
canonical source. Per-metric overrides in change_point_config replace
individual fields; absent rows inherit these defaults entirely.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from statistics import mean

import numpy as np
import structlog
from pydantic import BaseModel

from otava.analysis import TTestSignificanceTester, merge
from otava.change_point_divisive.calculator import PairDistanceCalculator
from otava.change_point_divisive.detector import ChangePointDetector

logger = structlog.get_logger()

DEFAULT_ENABLED = True
DEFAULT_WINDOW_SIZE = 30
DEFAULT_MAX_PVALUE = 0.001
DEFAULT_MIN_MAGNITUDE = 0.0
DEFAULT_MIN_SAMPLE_SIZE = 10


class ChangePointResult(BaseModel):
    """A single detected change point with direction and magnitude."""

    position: int
    timestamp: datetime
    direction: str
    change_relative_pct: float
    change_absolute: float
    t_statistic: float
    pre_segment_mean: float
    post_segment_mean: float


def _split_with_boundary_fix(
    series: np.ndarray,
    window_len: int,
    max_pvalue: float,
) -> list:
    """Windowed E-Divisive split — filters out boundary CPs that cause ValueError in Otava."""
    step = int(window_len / 2)
    start = 0
    change_points: list = []
    tester = TTestSignificanceTester(max_pvalue)
    series_len = len(series)

    while start < series_len:
        end = min(start + window_len, series_len)
        algo = ChangePointDetector(significance_tester=tester, calculator=PairDistanceCalculator)
        new_change_points = algo.get_change_points(series, start, end)
        last_new_index = new_change_points[-1].index if new_change_points else 0
        start = max(last_new_index, start + step)
        for detected_point in new_change_points:
            # Filter boundary CPs that would produce empty segments
            if detected_point.index <= 0 or detected_point.index >= series_len:
                continue
            if detected_point not in change_points:
                change_points.append(detected_point)

    change_points.sort(key=lambda cp: cp.index)
    if not change_points:
        return []

    intervals = tester.get_intervals(change_points)
    return [tester.change_point(cp.to_candidate(), series, intervals) for cp in change_points]


def detect_change_points(
    *,
    values: Sequence[float],
    timestamps: Sequence[datetime],
    higher_is_better: bool = False,
    window_size: int = DEFAULT_WINDOW_SIZE,
    max_pvalue: float = DEFAULT_MAX_PVALUE,
    min_magnitude: float = DEFAULT_MIN_MAGNITUDE,
    min_sample_size: int = DEFAULT_MIN_SAMPLE_SIZE,
) -> list[ChangePointResult]:
    """Run E-Divisive change point detection on a single metric time series.

    Args:
        values: Metric values in chronological order.
        timestamps: Corresponding timestamps (same length as values).
        higher_is_better: If True, a decrease is a regression (throughput).
                          If False, an increase is a regression (latency).
        window_size: Sliding window length for the algorithm.
        max_pvalue: Significance threshold for the t-test.
        min_magnitude: Minimum relative change to keep a change point.
        min_sample_size: Skip detection if fewer values than this.

    Returns:
        List of detected change points, ordered by position.
    """
    if len(values) < min_sample_size:
        return []

    series = np.array(values, dtype=np.float64)
    effective_window = min(window_size, len(values))
    if effective_window < 4:
        return []

    # Two-phase algorithm (same as Otava's compute_change_points):
    # 1. Split with relaxed pvalue to find candidate ("weak") change points
    # 2. Merge to filter down to statistically significant ones
    first_pass_pvalue = (
        max_pvalue * 10 if max_pvalue < 0.05
        else (max_pvalue * 2 if max_pvalue < 0.5 else max_pvalue)
    )
    weak_change_points = _split_with_boundary_fix(series, effective_window, first_pass_pvalue)
    detected = merge(weak_change_points, series, max_pvalue, min_magnitude)

    results: list[ChangePointResult] = []
    for change_point in detected:
        position = change_point.index
        if position <= 0 or position >= len(values):
            continue

        pre_values = list(values[:position])
        post_values = list(values[position:])
        pre_mean = mean(pre_values)
        post_mean = mean(post_values)
        absolute_change = post_mean - pre_mean
        relative_change = (absolute_change / pre_mean * 100) if pre_mean != 0 else 0.0

        if higher_is_better:
            direction = 'regression' if post_mean < pre_mean else 'improvement'
        else:
            direction = 'regression' if post_mean > pre_mean else 'improvement'

        results.append(
            ChangePointResult(
                position=position,
                timestamp=timestamps[position],
                direction=direction,
                change_relative_pct=round(relative_change, 2),
                change_absolute=round(absolute_change, 4),
                t_statistic=round(change_point.stats.pvalue, 6),
                pre_segment_mean=round(pre_mean, 4),
                post_segment_mean=round(post_mean, 4),
            )
        )

    return sorted(results, key=lambda r: r.position)
