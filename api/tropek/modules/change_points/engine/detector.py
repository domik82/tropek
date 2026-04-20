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

"""E-Divisive recursive change point detector.

Recursively splits a series by finding candidates that maximise the Q-hat
dissimilarity function, then testing each candidate for statistical significance.
Stops when no significant candidate remains.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import SupportsFloat

import numpy as np

from tropek.modules.change_points.engine.base import (
    Calculator,
    ChangePoint,
    SignificanceTester,
)


class ChangePointDetector:

    def __init__(
        self,
        significance_tester: SignificanceTester,
        calculator: type[Calculator],
    ) -> None:
        self.tester = significance_tester
        self.calculator = calculator

    def get_change_points(
        self,
        series: Sequence[SupportsFloat],
        start: int | None = None,
        end: int | None = None,
    ) -> list[ChangePoint]:
        """Find change points in series[start:end]."""
        if not isinstance(series, np.ndarray):
            series = np.array(series[start:end], dtype=np.float64)
        if not np.issubdtype(series.dtype, np.floating):
            series = series.astype(np.float64, copy=False)

        calc = self.calculator(series)
        change_points: list[ChangePoint] = []

        while True:
            intervals = self.tester.get_intervals(change_points)
            candidate = calc.get_next_candidate(intervals)
            if candidate is None:
                break
            change_point = self.tester.change_point(candidate, series, intervals)
            if self.tester.is_significant(change_point):
                change_points.append(change_point)
                change_points.sort(key=lambda point: point.index)
            else:
                break

        if start is not None:
            for change_point in change_points:
                change_point.index += start

        # Fix: upstream Otava can return CPs at the series boundary (index == end),
        # producing empty segments that crash TTestSignificanceTester.compare().
        effective_end = end if end is not None else (start or 0) + len(series)
        change_points = [
            cp for cp in change_points if cp.index < effective_end
        ]

        return change_points
