# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

# Derived from Apache Otava — see NOTICE in this directory.

"""T-test significance tester and the two-phase split/merge algorithm.

The split phase uses a sliding window to find candidate ("weak") change points
with a relaxed p-value threshold. The merge phase filters these down to
statistically significant change points using the actual threshold.

Algorithm: "Hunter: Using Change Point Detection to Hunt for Performance
Regressions" by Fleming et al. (https://doi.org/10.1145/3578244.3583719).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import SupportsFloat, cast

import numpy as np
from pydantic import BaseModel
from scipy.stats import ttest_ind_from_stats

from tropek.modules.change_points.engine.base import (
    CandidateChangePoint,
    ChangePoint,
    SignificanceTester,
)
from tropek.modules.change_points.engine.calculator import PairDistanceCalculator
from tropek.modules.change_points.engine.detector import ChangePointDetector


class TTestStats(BaseModel):
    """Statistics from a two-sided Student's t-test between two segments."""

    mean_1: float
    mean_2: float
    std_1: float
    std_2: float
    pvalue: float

    def forward_rel_change(self, value_if_nan: float = 0.0) -> float:
        """Relative change from left to right."""
        if self.mean_1 == 0:
            return value_if_nan
        return self.mean_2 / self.mean_1 - 1.0

    def backward_rel_change(self, value_if_nan: float = 0.0) -> float:
        """Relative change from right to left."""
        if self.mean_2 == 0:
            return value_if_nan
        return self.mean_1 / self.mean_2 - 1.0

    def forward_change_percent(self) -> float:
        """Forward relative change as a percentage."""
        return self.forward_rel_change() * 100.0

    def backward_change_percent(self) -> float:
        """Backward relative change as a percentage."""
        return self.backward_rel_change() * 100.0

    def change_magnitude(self) -> float:
        """Maximum of absolutes of forward and backward relative change."""
        return max(abs(self.forward_rel_change()), abs(self.backward_rel_change()))


class TTestSignificanceTester(SignificanceTester):
    """Uses two-sided Student's t-test to decide if a candidate change point is significant.

    Works well even with small sample sizes (<10).
    """

    def compare(
        self,
        left: Sequence[SupportsFloat],
        right: Sequence[SupportsFloat],
    ) -> TTestStats:
        """Compute t-test statistics between two segments."""
        if len(left) == 0 or len(right) == 0:
            raise ValueError

        mean_left = float(np.mean(left))
        mean_right = float(np.mean(right))
        std_left = float(np.std(left)) if len(left) >= 2 else 0.0
        std_right = float(np.std(right)) if len(right) >= 2 else 0.0

        if len(left) + len(right) > 2:
            (_, pvalue) = ttest_ind_from_stats(
                mean_left, std_left, len(left),
                mean_right, std_right, len(right),
                alternative='two-sided',
            )
        else:
            pvalue = 1.0

        return TTestStats(
            mean_1=mean_left, mean_2=mean_right,
            std_1=std_left, std_2=std_right, pvalue=float(pvalue),
        )

    def change_point(
        self,
        candidate: CandidateChangePoint,
        series: Sequence[SupportsFloat],
        intervals: list[slice],
    ) -> ChangePoint:
        """Compute t-test statistics for a candidate change point.

        Works in both phases:
        1. Split: candidate index is inside an interval — split it.
        2. Merge: candidate index matches the boundary of two intervals.
        """
        for i, interval in enumerate(intervals):
            if interval.stop == candidate.index:
                left_interval = interval
                right_interval = intervals[i + 1]
                break
            if (
                (interval.start is None or interval.start < candidate.index)
                and (interval.stop is None or candidate.index < interval.stop)
            ):
                left_interval = slice(interval.start, candidate.index)
                right_interval = slice(candidate.index, interval.stop)
                break
        else:
            raise ValueError(
                f'candidate change point at index={candidate.index} '
                f'does not correspond to any interval in {intervals}'
            )
        left = series[left_interval]
        right = series[right_interval]
        stats = self.compare(left, right)
        return ChangePoint.from_candidate(candidate, stats)


def _ttest_stats(change_point: ChangePoint) -> TTestStats:
    return cast('TTestStats', change_point.stats)


def merge(
    change_points: list[ChangePoint],
    series: Sequence[SupportsFloat],
    max_pvalue: float,
    min_magnitude: float,
) -> list[ChangePoint]:
    """Merge phase — iteratively remove the weakest change point until all are significant."""
    tester = TTestSignificanceTester(max_pvalue)

    while change_points:
        weakest = max(change_points, key=lambda c: c.stats.pvalue)
        if weakest.stats.pvalue < max_pvalue:
            weakest = min(
                change_points, key=lambda c: _ttest_stats(c).change_magnitude(),
            )
            if _ttest_stats(weakest).change_magnitude() > min_magnitude:
                return change_points

        weakest_index = change_points.index(weakest)
        del change_points[weakest_index]

        intervals = tester.get_intervals(change_points)
        _recompute_neighbor(change_points, weakest_index, tester, series, intervals)
        _recompute_neighbor(change_points, weakest_index + 1, tester, series, intervals)

    return change_points


def _recompute_neighbor(
    change_points: list[ChangePoint],
    index: int,
    tester: TTestSignificanceTester,
    series: Sequence[SupportsFloat],
    intervals: list[slice],
) -> None:
    """Recompute statistics for a neighbor after removing the weakest change point."""
    if index < 0 or index >= len(change_points):
        return
    candidate = change_points[index]
    change_points[index] = tester.change_point(candidate.to_candidate(), series, intervals)


def split(
    series: Sequence[SupportsFloat],
    window_len: int = 30,
    max_pvalue: float = 0.001,
) -> list[ChangePoint]:
    """Split phase — sliding window E-Divisive detection.

    Finds candidate ("weak") change points using a relaxed p-value threshold,
    then computes t-test statistics for each.
    """
    assert window_len >= 2, 'window length must be at least 2'
    start = 0
    step = int(window_len / 2)
    change_points: list[ChangePoint] = []
    series_len = len(series)

    tester = TTestSignificanceTester(max_pvalue)
    while start < series_len:
        end = min(start + window_len, series_len)
        algo = ChangePointDetector(significance_tester=tester, calculator=PairDistanceCalculator)
        new_change_points = algo.get_change_points(series, start, end)
        last_new_index = new_change_points[-1].index if new_change_points else 0
        start = max(last_new_index, start + step)

        for cp in new_change_points:
            # Fix: filter boundary CPs that would produce empty segments.
            # Upstream Otava bug — see NOTICE in this directory.
            if cp.index <= 0 or cp.index >= series_len:
                continue
            if cp not in change_points:
                change_points.append(cp)

    change_points.sort(key=lambda cp: cp.index)
    if not change_points:
        return []

    intervals = tester.get_intervals(change_points)
    return [tester.change_point(cp.to_candidate(), series, intervals) for cp in change_points]
