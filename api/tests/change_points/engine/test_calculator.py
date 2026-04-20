"""Tests for Q-hat distance calculator — ported from Apache Otava test suite."""

from __future__ import annotations

import numpy as np

from tropek.modules.change_points.engine.calculator import PairDistanceCalculator

SEQUENCE = np.array([
    0.3, 2.4, 1.5, -0.9, -0.5,
    99.7, 98.3, 99.1,
    149.0, 149.7, 149.5, 149.1, 148.8, 150.0,
])


def _compute_q_brute_force(sequence: np.ndarray) -> tuple[np.ndarray, float, int]:
    """Brute-force Q-hat computation for verification (O(n^4))."""
    series_len = len(sequence)
    Q = np.zeros((series_len - 1, series_len - 1))
    q_max = 0.0
    candidate_index = 0
    for tau in range(1, series_len):
        for kappa in range(tau + 1, series_len + 1):
            left, right = sequence[:tau], sequence[tau:kappa]
            n_left, n_right = len(left), len(right)

            a_sum = sum(abs(x - y) for x in left for y in right)
            a_val = 2 / (n_right + n_left) * a_sum

            b_sum = sum(
                abs(left[i] - left[k])
                for i in range(n_left - 1)
                for k in range(i + 1, n_left)
            )
            b_val = 2 * n_right / (n_right + n_left) / (n_left - 1) * b_sum if n_left > 1 else 0

            c_sum = sum(
                abs(right[j] - right[k])
                for j in range(n_right - 1)
                for k in range(j, n_right)
            )
            c_val = 2 * n_left / (n_right + n_left) / (n_right - 1) * c_sum if n_right > 1 else 0

            Q[tau - 1, kappa - 2] = a_val - b_val - c_val
            if Q[tau - 1, kappa - 2] > q_max:
                q_max = Q[tau - 1, kappa - 2]
                candidate_index = tau

    return Q, q_max, candidate_index


def test_calculator_matches_brute_force() -> None:
    """Vectorised Q-hat matrix must match the brute-force reference implementation."""
    sequence = SEQUENCE.copy()
    calc = PairDistanceCalculator(sequence)
    Q = calc._get_Q_vals(start=0, end=len(sequence))

    brute_Q, brute_q_max, brute_candidate_index = _compute_q_brute_force(sequence)
    assert np.allclose(brute_Q, Q)

    whole_interval = slice(None, None)
    candidate = calc.get_candidate_change_point(whole_interval)
    assert np.allclose(brute_q_max, candidate.qhat)
    assert brute_candidate_index == candidate.index
