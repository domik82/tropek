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

"""Permutation-based significance tester for the E-Divisive algorithm.

Uses random permutations to estimate the p-value of a candidate change point.
This is the original method from Matteson & James (2014). For faster detection
on normally-distributed data, see TTestSignificanceTester in analysis.py.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from pydantic import ConfigDict

from tropek.modules.change_points.engine.base import (
    BaseStats,
    Calculator,
    CandidateChangePoint,
    ChangePoint,
    SignificanceTester,
)


class PermutationStats(BaseStats):
    """Statistics from a permutation significance test."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    permuted_qhats: NDArray
    extreme_qhat_perm: int
    n_perm: int


class PermutationsSignificanceTester(SignificanceTester):

    def __init__(
        self,
        max_pvalue: float,
        permutations: int,
        calculator: type[Calculator],
        seed: int | None,
    ) -> None:
        super().__init__(max_pvalue)
        self.permutations = permutations
        self.calculator = calculator
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def change_point(
        self,
        candidate: CandidateChangePoint,
        series: NDArray,
        intervals: list[slice],
    ) -> ChangePoint:
        """Perform permutation test within candidate cluster."""
        qhats = np.empty(self.permutations)
        for i in range(self.permutations):
            rand_series = series.copy()
            for interval in intervals:
                segment = rand_series[interval]
                self.rng.shuffle(segment)
            rand_calc = self.calculator(rand_series)
            rand_candidate = rand_calc.get_next_candidate(intervals)
            qhats[i] = rand_candidate.qhat

        extreme_qhat_perm = int(np.sum(qhats >= candidate.qhat))
        pvalue = extreme_qhat_perm / (self.permutations + 1)
        stats = PermutationStats(
            pvalue=pvalue,
            permuted_qhats=qhats,
            extreme_qhat_perm=extreme_qhat_perm,
            n_perm=self.permutations,
        )
        return ChangePoint.from_candidate(candidate, stats)
