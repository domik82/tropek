# Adapted from Cody Rioux's PyData 2015 Seattle tutorial on change detection.
# Original: https://github.com/codyrioux/pydata2015seattle
# Based on Netflix's real-time analytics change detection approach.

"""Time series generators for testing.

Two complementary approaches:

**Distribution-based** (scipy) — precise control over statistical properties.
Useful for testing detector accuracy against known ground truth::

    from scipy.stats import norm
    gen = StepChangeGenerator(
        dist=norm, before={"loc": 100, "scale": 5},
        after={"loc": 120, "scale": 5}, changepoint=50,
    )
    series = gen.generate(100)

**Phase-based** (YAML-compatible) — same schema as mock adapter scenarios.
Useful for generating realistic metric shapes (stable/ramp/spike) from
scenario definitions::

    series, timestamps = generate_from_phases(
        baseline=5.0,
        phases=[
            {"duration_hours": 20, "pattern": "stable", "jitter_pct": 10},
            {"duration_hours": 4, "pattern": "ramp", "target": 22.0, "jitter_pct": 5},
            {"duration_hours": 48, "pattern": "stable", "jitter_pct": 8},
        ],
        interval_minutes=5,
        seed=42,
    )

Phase definitions use the same format as ``adapters/mock/scenarios/*.yaml``
so YAML files can be loaded directly::

    import yaml
    with open("scenarios/office-apps.yaml") as f:
        scenario = yaml.safe_load(f)
    metric_def = scenario["metrics"]["process_cpu_pct"]
    series, timestamps = generate_from_phases(**metric_def, seed=42)
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
from scipy.stats import rv_continuous

# ---------------------------------------------------------------------------
# Phase-based generation (YAML-compatible with mock adapter scenarios)
# ---------------------------------------------------------------------------


def generate_from_phases(
    baseline: float,
    phases: list[dict[str, Any]],
    *,
    interval_minutes: int = 5,
    start: datetime | None = None,
    seed: int | str | None = None,
) -> tuple[list[float], list[datetime]]:
    """Generate a time series from phase definitions.

    Uses the same schema as ``adapters/mock/scenarios/*.yaml`` metric
    definitions, so YAML files can drive test data generation directly.

    Returns (values, timestamps) where both lists have the same length.
    """
    if start is None:
        start = datetime(2026, 1, 1, tzinfo=UTC)

    rng = random.Random(seed)  # noqa: S311
    interval = timedelta(minutes=interval_minutes)
    values: list[float] = []
    timestamps: list[datetime] = []
    current_baseline = baseline
    current_time = start

    for phase in phases:
        duration = timedelta(hours=phase['duration_hours'])
        phase_end = current_time + duration
        jitter_pct = phase['jitter_pct'] / 100.0
        pattern = phase['pattern']
        target = phase.get('target', current_baseline)
        phase_start_time = current_time

        while current_time < phase_end:
            if pattern == 'stable':
                value = current_baseline * (1.0 + rng.uniform(-jitter_pct, jitter_pct))
            elif pattern == 'ramp':
                progress = (current_time - phase_start_time) / duration
                value = current_baseline + (target - current_baseline) * progress
                value *= 1.0 + rng.uniform(-jitter_pct, jitter_pct)
            elif pattern == 'spike':
                mid = phase_start_time + duration / 2
                if current_time < mid:
                    progress = (current_time - phase_start_time) / (duration / 2)
                    value = current_baseline + (target - current_baseline) * progress
                else:
                    progress = (current_time - mid) / (duration / 2)
                    value = target + (current_baseline - target) * progress
                value *= 1.0 + rng.uniform(-jitter_pct, jitter_pct)
            else:
                value = current_baseline

            values.append(value)
            timestamps.append(current_time)
            current_time += interval

        if pattern == 'ramp':
            current_baseline = target

    return values, timestamps


# ---------------------------------------------------------------------------
# Distribution-based generation (scipy)
# ---------------------------------------------------------------------------


class StableGenerator:
    """Generates values from a single unchanging distribution."""

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
    """Generates values from one distribution, then abruptly switches to another."""

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
    """Generates values that gradually drift from one distribution to another."""

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
    """Generates values where the mean stays the same but variance changes."""

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
    """Generates values with multiple step changes at known positions."""

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
            while segment_idx < len(self._segments) - 1 and i >= self._segments[segment_idx + 1][0]:
                segment_idx += 1
            params = self._segments[segment_idx][1]
            series.append(float(self._dist.rvs(**params, random_state=self._rng)))
        return series


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------


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
