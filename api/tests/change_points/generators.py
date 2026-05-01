# Adapted from Cody Rioux's PyData 2015 Seattle tutorial on change detection.
# Original: https://github.com/codyrioux/pydata2015seattle
# Based on Netflix's real-time analytics change detection approach.

"""Distribution-based time series generators for testing change point detectors.

Each generator produces a sequence of floats from scipy distributions,
with configurable change points, drift, and variance shifts. Useful for
creating controlled test data where the ground truth is known.

Usage::

    from scipy.stats import norm
    gen = StepChangeGenerator(
        dist=norm, before={"loc": 100, "scale": 5},
        after={"loc": 120, "scale": 5}, changepoint=50,
    )
    series = gen.generate(100)
    # series[:50] ~ N(100, 5), series[50:] ~ N(120, 5)
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import numpy as np
from scipy.stats import rv_continuous


class StableGenerator:
    """Generates values from a single unchanging distribution.

    Useful as a control — running detectors against this should produce
    no change points (testing false positive rate).
    """

    def __init__(
        self,
        dist: rv_continuous,
        params: dict[str, float],
        seed: int | None = None,
    ) -> None:
        self._dist = dist
        self._params = params
        self._rng = np.random.default_rng(seed)

    def generate(self, count: int) -> list[float]:
        return [float(self._dist.rvs(**self._params, random_state=self._rng)) for _ in range(count)]


class StepChangeGenerator:
    """Generates values from one distribution, then abruptly switches to another.

    The changepoint index is where the switch happens: values[:changepoint]
    come from `before`, values[changepoint:] come from `after`.
    """

    def __init__(
        self,
        dist: rv_continuous,
        before: dict[str, float],
        after: dict[str, float],
        changepoint: int,
        seed: int | None = None,
    ) -> None:
        self._dist = dist
        self._before = before
        self._after = after
        self._changepoint = changepoint
        self._rng = np.random.default_rng(seed)

    def generate(self, count: int) -> list[float]:
        series: list[float] = []
        for i in range(count):
            params = self._before if i < self._changepoint else self._after
            series.append(float(self._dist.rvs(**params, random_state=self._rng)))
        return series


class DriftGenerator:
    """Generates values that gradually drift from one distribution to another.

    Before the changepoint: pure `before` distribution.
    During drift (changepoint to changepoint + steps): linear interpolation
    between `before` and `after` samples using beta in [0, 1].
    After drift completes: pure `after` distribution.
    """

    def __init__(
        self,
        dist: rv_continuous,
        before: dict[str, float],
        after: dict[str, float],
        changepoint: int,
        steps: int,
        seed: int | None = None,
    ) -> None:
        self._dist = dist
        self._before = before
        self._after = after
        self._changepoint = changepoint
        self._steps = steps
        self._gradient = np.linspace(0, 1, steps)
        self._rng = np.random.default_rng(seed)

    def generate(self, count: int) -> list[float]:
        series: list[float] = []
        for i in range(count):
            if i < self._changepoint:
                value = self._dist.rvs(**self._before, random_state=self._rng)
            elif i < self._changepoint + self._steps:
                beta = self._gradient[i - self._changepoint]
                before_sample = self._dist.rvs(**self._before, random_state=self._rng)
                after_sample = self._dist.rvs(**self._after, random_state=self._rng)
                value = (1.0 - beta) * before_sample + beta * after_sample
            else:
                value = self._dist.rvs(**self._after, random_state=self._rng)
            series.append(float(value))
        return series


class VarianceChangeGenerator:
    """Generates values where the mean stays the same but variance changes.

    Useful for testing detectors that catch instability — E-Divisive may miss
    this, but Levene's test or variance-aware detectors should catch it.
    """

    def __init__(
        self,
        dist: rv_continuous,
        loc: float,
        scale_before: float,
        scale_after: float,
        changepoint: int,
        seed: int | None = None,
    ) -> None:
        self._dist = dist
        self._loc = loc
        self._scale_before = scale_before
        self._scale_after = scale_after
        self._changepoint = changepoint
        self._rng = np.random.default_rng(seed)

    def generate(self, count: int) -> list[float]:
        series: list[float] = []
        for i in range(count):
            scale = self._scale_before if i < self._changepoint else self._scale_after
            series.append(float(self._dist.rvs(loc=self._loc, scale=scale, random_state=self._rng)))
        return series


class MultipleChangePointGenerator:
    """Generates values with multiple step changes at known positions.

    Each segment uses the same distribution family but different parameters.
    """

    def __init__(
        self,
        dist: rv_continuous,
        segments: Sequence[tuple[int, dict[str, float]]],
        seed: int | None = None,
    ) -> None:
        self._dist = dist
        self._segments = sorted(segments, key=lambda s: s[0])
        self._rng = np.random.default_rng(seed)

    def generate(self, count: int) -> list[float]:
        series: list[float] = []
        segment_idx = 0
        for i in range(count):
            while (
                segment_idx < len(self._segments) - 1
                and i >= self._segments[segment_idx + 1][0]
            ):
                segment_idx += 1
            params = self._segments[segment_idx][1]
            series.append(float(self._dist.rvs(**params, random_state=self._rng)))
        return series


def make_timestamps(
    count: int,
    start: datetime | None = None,
    interval: timedelta | None = None,
) -> list[datetime]:
    """Generate evenly-spaced timestamps for a series."""
    if start is None:
        start = datetime(2026, 1, 1, tzinfo=UTC)
    if interval is None:
        interval = timedelta(hours=1)
    return [start + interval * i for i in range(count)]
