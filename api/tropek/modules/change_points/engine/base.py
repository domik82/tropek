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

"""Base types for the E-Divisive change point detection algorithm.

Provides the core data models (candidate change points, statistical results)
and abstract interfaces (significance testers, calculators) that the
detector, analysis, and calculator modules build on.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import SupportsFloat

from numpy.typing import NDArray
from pydantic import BaseModel


class CandidateChangePoint(BaseModel):
    """Candidate for a change point — maximizes Q-hat on [start:end+1] slice."""

    index: int
    qhat: float


class BaseStats(BaseModel):
    """Abstract statistics for a change point. Subclassed by each significance test."""

    pvalue: float


class ChangePoint:
    """Change point with index, Q-hat value, and significance test statistics.

    Not a Pydantic model — this is a mutable working data structure used
    internally by the algorithm (index is adjusted in-place after windowed
    detection). Stats are accessed polymorphically via BaseStats subclasses.
    """

    __slots__ = ('index', 'qhat', 'stats')

    def __init__(self, index: int, qhat: float, stats: BaseStats) -> None:
        self.index = index
        self.qhat = qhat
        self.stats = stats

    def __eq__(self, other: object) -> bool:
        return isinstance(other, self.__class__) and self.index == other.index

    def __hash__(self) -> int:
        return hash(self.index)

    @classmethod
    def from_candidate(
        cls,
        candidate: CandidateChangePoint,
        stats: BaseStats,
    ) -> ChangePoint:
        """Construct from a candidate and computed significance statistics."""
        return cls(index=candidate.index, qhat=candidate.qhat, stats=stats)

    def to_candidate(self) -> CandidateChangePoint:
        """Downgrade to a candidate — used to recompute stats for weak change points."""
        return CandidateChangePoint(index=self.index, qhat=self.qhat)


class SignificanceTester:
    """Abstract significance tester — determines if a candidate CP is statistically significant."""

    def __init__(self, max_pvalue: float) -> None:
        self.max_pvalue = max_pvalue

    def get_intervals(self, change_points: list[ChangePoint]) -> list[slice]:
        """Return slices of the series defined by sorted change points."""
        assert all(change_points[i].index <= change_points[i + 1].index for i in range(len(change_points) - 1)), (
            'change points must be sorted by index'
        )
        intervals = [
            slice(
                0 if i == 0 else change_points[i - 1].index,
                None if i == len(change_points) else change_points[i].index,
            )
            for i in range(len(change_points) + 1)
        ]
        return [interval for interval in intervals if interval.start != interval.stop]

    def is_significant(self, point: ChangePoint) -> bool:
        """Compare change point p-value to the significance threshold."""
        return point.stats.pvalue <= self.max_pvalue

    def change_point(
        self,
        candidate: CandidateChangePoint,
        series: NDArray,
        intervals: list[slice],
    ) -> ChangePoint:
        """Compute stats for a candidate and wrap it into a ChangePoint."""
        ...


class Calculator:
    """Abstract calculator — provides the interface for finding best CP candidates."""

    def __init__(self, series: NDArray) -> None:
        self.series = series

    def get_next_candidate(self, intervals: list[slice]) -> CandidateChangePoint | None:
        """Find the next best change point candidate across all intervals."""
        candidates = [
            self.get_candidate_change_point(interval=interval)
            for interval in intervals
            if len(self.series[interval]) > 1
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda point: point.qhat)

    def get_candidate_change_point(self, interval: slice) -> CandidateChangePoint:
        """Given a slice, return the best candidate change point within it."""
        ...


def fill_missing(data: Sequence[SupportsFloat]) -> None:
    """Forward-fill None values, then back-fill any remaining leading Nones."""
    prev = None
    for i in range(len(data)):
        if data[i] is None and prev is not None:
            data[i] = prev
        prev = data[i]

    prev = None
    for i in reversed(range(len(data))):
        if data[i] is None and prev is not None:
            data[i] = prev
        prev = data[i]
