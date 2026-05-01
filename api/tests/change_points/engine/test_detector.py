"""Tests for E-Divisive change point detector — ported from Apache Otava test suite."""

from __future__ import annotations

import numpy as np
import pytest

from tropek.modules.change_points.engine.analysis import TTestSignificanceTester, TTestStats, split
from tropek.modules.change_points.engine.base import ChangePoint
from tropek.modules.change_points.engine.calculator import PairDistanceCalculator
from tropek.modules.change_points.engine.detector import ChangePointDetector
from tropek.modules.change_points.engine.significance_test import PermutationsSignificanceTester

SEQUENCE = np.array([
    0.3, 2.4, 1.5, -0.9, -0.5,
    99.7, 98.3, 99.1,
    149.0, 149.7, 149.5, 149.1, 148.8, 150.0,
])
EXPECTED_CHANGE_POINT_INDICES = [5, 8]


def test_permutation_calculation() -> None:
    """Permutation statistics are computed correctly."""
    sequence = SEQUENCE.copy()
    calc = PairDistanceCalculator(sequence)
    whole_interval = slice(None, None)
    candidate = calc.get_candidate_change_point(whole_interval)

    seed = 1
    tester = PermutationsSignificanceTester(
        max_pvalue=0.05, permutations=1, calculator=PairDistanceCalculator, seed=seed,
    )
    change_point = tester.change_point(candidate=candidate, series=sequence, intervals=[whole_interval])

    reference_rng = np.random.default_rng(seed)
    rand_sequence = sequence.copy()
    reference_rng.shuffle(rand_sequence)
    rand_calc = PairDistanceCalculator(rand_sequence)
    rand_Q = rand_calc._get_Q_vals(0, len(rand_sequence))
    rand_q_max = float(np.max(rand_Q))

    assert int(rand_q_max >= candidate.qhat) == change_point.stats.extreme_qhat_perm
    assert np.allclose(rand_q_max, change_point.stats.permuted_qhats[0])


def test_permutation_test_finds_known_change_points() -> None:
    """E-Divisive with permutation tester finds both CPs in the test sequence."""
    seed = 1
    sequence = SEQUENCE.copy()
    tester = PermutationsSignificanceTester(
        max_pvalue=0.01, permutations=100, calculator=PairDistanceCalculator, seed=seed,
    )
    detector = ChangePointDetector(significance_tester=tester, calculator=PairDistanceCalculator)
    change_points = detector.get_change_points(series=sequence)
    assert [cp.index for cp in change_points] == EXPECTED_CHANGE_POINT_INDICES


def test_ttest_finds_known_change_points() -> None:
    """E-Divisive with t-test tester finds both CPs in the test sequence."""
    sequence = SEQUENCE.copy()
    tester = TTestSignificanceTester(max_pvalue=0.01)
    detector = ChangePointDetector(significance_tester=tester, calculator=PairDistanceCalculator)
    change_points = detector.get_change_points(series=sequence)
    assert [cp.index for cp in change_points] == EXPECTED_CHANGE_POINT_INDICES


def test_get_intervals_requires_sorted_change_points() -> None:
    """get_intervals raises AssertionError when change points are not sorted."""
    tester = TTestSignificanceTester(max_pvalue=0.01)
    stats = TTestStats(mean_1=1.0, mean_2=2.0, std_1=0.1, std_2=0.1, pvalue=0.001)

    sorted_change_points = [
        ChangePoint(index=5, qhat=1.0, stats=stats),
        ChangePoint(index=10, qhat=1.0, stats=stats),
        ChangePoint(index=15, qhat=1.0, stats=stats),
    ]
    intervals = tester.get_intervals(sorted_change_points)
    assert len(intervals) == 4
    assert intervals[0] == slice(0, 5)
    assert intervals[1] == slice(5, 10)
    assert intervals[2] == slice(10, 15)
    assert intervals[3] == slice(15, None)

    unsorted_change_points = [
        ChangePoint(index=10, qhat=1.0, stats=stats),
        ChangePoint(index=5, qhat=1.0, stats=stats),
        ChangePoint(index=15, qhat=1.0, stats=stats),
    ]
    with pytest.raises(AssertionError, match='change points must be sorted by index'):
        tester.get_intervals(unsorted_change_points)


def test_boundary_cp_does_not_crash() -> None:
    """Regression test: split() on a step series must not raise ValueError.

    Upstream Otava bug — the detector can return a CP at index == len(series),
    producing an empty segment that crashes compare(). Our vendored engine
    filters these boundary CPs.
    """
    series = np.array([10.0] * 15 + [50.0] * 15, dtype=np.float64)
    result = split(series, window_len=30, max_pvalue=0.01)
    assert len(result) >= 1
    assert all(0 < cp.index < len(series) for cp in result)
