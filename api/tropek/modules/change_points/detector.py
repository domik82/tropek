"""Pure change point detector — wraps the vendored E-Divisive engine.

No I/O. Takes a list of values + timestamps, returns detected change points
with direction, magnitude, and statistical significance.

Global defaults live here as module constants so the whole system has one
canonical source. Per-metric overrides in change_point_config replace
individual fields; absent rows inherit these defaults entirely.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from statistics import mean, stdev

import numpy as np
import structlog
from pydantic import BaseModel

from tropek.modules.change_points.engine import merge, split

logger = structlog.get_logger()

DEFAULT_ENABLED = True
DEFAULT_WINDOW_SIZE = 30
DEFAULT_MAX_PVALUE = 0.001
DEFAULT_MIN_MAGNITUDE = 0.0
DEFAULT_MIN_SAMPLE_SIZE = 10

MIN_EFFECTIVE_WINDOW = 4
MIN_STDEV_SAMPLES = 2
PVALUE_STRICT_THRESHOLD = 0.05
PVALUE_MODERATE_THRESHOLD = 0.5


class Direction(StrEnum):
    """Whether a change point represents a regression or improvement."""

    REGRESSION = 'regression'
    IMPROVEMENT = 'improvement'


class ChangePointResult(BaseModel):
    """A single detected change point with direction and magnitude."""

    position: int
    timestamp: datetime
    detector: str
    direction: Direction
    change_relative_pct: float
    change_absolute: float
    pvalue: float
    pre_segment_mean: float
    post_segment_mean: float
    post_segment_std: float


def detect_change_points(  # noqa: PLR0913
    *,
    values: Sequence[float],
    timestamps: Sequence[datetime],
    higher_is_better: bool = False,
    window_size: int = DEFAULT_WINDOW_SIZE,
    max_pvalue: float = DEFAULT_MAX_PVALUE,
    min_magnitude: float = DEFAULT_MIN_MAGNITUDE,
    min_sample_size: int = DEFAULT_MIN_SAMPLE_SIZE,
    pvalue_strict_threshold: float = PVALUE_STRICT_THRESHOLD,
    pvalue_moderate_threshold: float = PVALUE_MODERATE_THRESHOLD,
) -> list[ChangePointResult]:
    """Run E-Divisive change point detection on a single metric time series.

    Args:
        values: Metric values in chronological order.
        timestamps: Corresponding timestamps (same length as values).
        higher_is_better: If True, a decrease is a regression (throughput).
                          If False, an increase is a regression (latency).
        window_size: Sliding window length for the algorithm.
        max_pvalue: Significance threshold for the merge phase t-test.
        min_magnitude: Minimum relative change to keep a change point.
        min_sample_size: Skip detection if fewer values than this.
        pvalue_strict_threshold: First-pass relaxation boundary. When max_pvalue
            is below this, the split phase uses 10x relaxation to cast a wide net
            for weak candidates that the merge phase refines.
        pvalue_moderate_threshold: Second relaxation boundary. When max_pvalue is
            between strict and moderate, the split phase uses 2x relaxation.
            Above moderate, no relaxation is applied.

    Returns:
        List of detected change points, ordered by position.
    """
    if len(values) < min_sample_size:
        return []

    series = np.array(values, dtype=np.float64)
    effective_window = min(window_size, len(values))
    if effective_window < MIN_EFFECTIVE_WINDOW:
        return []

    first_pass_pvalue = (
        max_pvalue * 10 if max_pvalue < pvalue_strict_threshold
        else (max_pvalue * 2 if max_pvalue < pvalue_moderate_threshold else max_pvalue)
    )
    weak_change_points = split(series, effective_window, first_pass_pvalue)
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
        post_std = stdev(post_values) if len(post_values) >= MIN_STDEV_SAMPLES else 0.0
        absolute_change = post_mean - pre_mean
        relative_change = (absolute_change / pre_mean * 100) if pre_mean != 0 else 0.0

        if higher_is_better:
            direction = Direction.REGRESSION if post_mean < pre_mean else Direction.IMPROVEMENT
        else:
            direction = Direction.REGRESSION if post_mean > pre_mean else Direction.IMPROVEMENT

        results.append(
            ChangePointResult(
                position=position,
                timestamp=timestamps[position],
                detector='e_divisive',
                direction=direction,
                change_relative_pct=round(relative_change, 2),
                change_absolute=round(absolute_change, 4),
                pvalue=round(change_point.stats.pvalue, 6),
                pre_segment_mean=round(pre_mean, 4),
                post_segment_mean=round(post_mean, 4),
                post_segment_std=round(post_std, 4),
            )
        )

    return sorted(results, key=lambda r: r.position)
