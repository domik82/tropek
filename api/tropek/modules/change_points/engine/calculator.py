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

"""Pair distance calculator for the E-Divisive algorithm.

Computes the Q-hat dissimilarity function using vectorised numpy operations
on precomputed pairwise distance matrices. The Q-hat maximum identifies the
best candidate change point within a given interval.

Mathematical notation (V, H, Q, A, B, C) follows the paper:
"A Nonparametric Approach for Multiple Change Point Analysis of Multivariate Data"
by Matteson and James (https://doi.org/10.48550/arXiv.1306.4933).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from tropek.modules.change_points.engine.base import Calculator, CandidateChangePoint


class PairDistanceCalculator(Calculator):
    """Q-hat dissimilarity calculator using pairwise distances."""

    def __init__(self, series: NDArray, power: float = 1.0) -> None:
        super().__init__(series)
        assert 0 < power < 2, f'power={power} is not in (0, 2)'
        self.power = power
        self.V: NDArray | None = None
        self.H: NDArray | None = None
        self.distances: NDArray | None = None

    def _calculate_pairwise_differences(self) -> None:
        """Precompute V (vertical) and H (horizontal) cumulative sums of the distance matrix.

        V[τ] = Σ distances[0:τ, τ]   — column partial sums
        H[τ, κ] = Σ distances[τ, τ:κ] — row partial sums

        These are used by _get_Q_vals to compute the Q-hat function efficiently.
        """
        self.distances = np.power(
            np.abs(self.series[:, None] - self.series[None, :]), self.power,
        )
        triu = np.triu(self.distances, k=1)[:-1, 1:]
        self.V = triu.sum(axis=0)
        self.H = triu.cumsum(axis=1)

    def _get_Q_vals(self, start: int, end: int) -> NDArray:
        """Compute the Q-hat matrix for series[start:end].

        Returns a matrix Q where Q[i, j] = QQ(series[start:τ], series[τ:κ])
        with τ = i + 1 + start and κ = j + 2 + start.

        Q = A - B - C, where A, B, C are computed from the precomputed V and H
        cumulative sums using vectorised numpy operations.
        """
        if self.V is None or self.H is None:
            self._calculate_pairwise_differences()

        V = self.V[start : end - 1] - self.distances[0 : start, start + 1 : end].sum(axis=0)
        H = self.H[start : end - 1, start : end - 1]

        taus = np.arange(start + 1, end)[:, None]
        kappas = np.arange(start + 2, end + 1)[None, :]

        A = np.zeros((end - 1 - start, end - 1 - start))
        A_coefs = 2 / (kappas - start)
        A[1:, :] = np.cumsum(V)[:-1, None]
        A = A_coefs * np.triu(np.cumsum(H, axis=0) - A, k=0)

        B = np.zeros((end - 1 - start, end - 1 - start))
        B_num = 2 * (kappas - taus)
        B_den = (kappas - start) * (taus - start - 1)
        B_mask = np.triu(np.ones_like(B_den, dtype=bool), k=0)
        B_out = np.zeros_like(B_den, dtype=float)
        B_coefs = np.divide(B_num, B_den, out=B_out, where=B_mask & (B_den != 0))
        B[1:, 1:] = B_coefs[1:, 1:] * np.cumsum(V)[:-1, None]

        C = np.zeros((end - 1 - start, end - 1 - start))
        C_num = 2 * (taus - start)
        C_den = (kappas - start) * (kappas - taus - 1)
        C_mask = np.triu(np.ones_like(C_den, dtype=bool), k=1)
        C_out = np.zeros_like(C_den, dtype=float)
        C_coefs = np.divide(C_num, C_den, out=C_out, where=C_mask & (C_den != 0))
        C[:-1, 1:] = C_coefs[:-1, 1:] * np.flipud(np.cumsum(np.flipud(H[1:, 1:]), axis=0))

        return A - B - C

    def get_candidate_change_point(self, interval: slice) -> CandidateChangePoint:
        """Find the best candidate change point within series[interval].

        Computes all Q-hat values and returns the index τ that maximises the
        dissimilarity between series[start:τ] and series[τ:κ].
        """
        start = 0 if interval.start is None else interval.start
        end = len(self.series) if interval.stop is None else interval.stop
        assert end - start > 1, f'interval must be non-empty, but array[{start}:{end}] was given'

        Q = self._get_Q_vals(start, end)
        i, j = np.unravel_index(np.argmax(Q), Q.shape)
        return CandidateChangePoint(index=int(i + 1 + start), qhat=float(Q[i][j]))
