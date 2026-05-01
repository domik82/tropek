"""Tests for analysis module — ported from Apache Otava test suite."""

from __future__ import annotations

import numpy as np
from tropek.modules.change_points.engine.analysis import (
    TTestSignificanceTester,
    merge,
    split,
)
from tropek.modules.change_points.engine.base import CandidateChangePoint, fill_missing


def test_fill_missing_forward() -> None:
    data = [1.0, 1.2, None, None, 4.3]
    fill_missing(data)
    assert data == [1.0, 1.2, 1.2, 1.2, 4.3]


def test_fill_missing_backward() -> None:
    data = [None, None, 1.0, 1.2, 0.5]
    fill_missing(data)
    assert data == [1.0, 1.0, 1.0, 1.2, 0.5]


def test_fill_missing_trailing() -> None:
    data = [1.0, 1.2, 0.5, None, None]
    fill_missing(data)
    assert data == [1.0, 1.2, 0.5, 0.5, 0.5]


def test_single_series_detects_step() -> None:
    """Two-phase split+merge detects a single step change at index 10."""
    series = [
        1.02,
        0.95,
        0.99,
        1.00,
        1.12,
        1.00,
        1.01,
        0.98,
        1.01,
        0.96,
        0.50,
        0.51,
        0.48,
        0.48,
        0.55,
        0.50,
        0.49,
        0.51,
        0.50,
        0.49,
    ]
    max_pvalue = 0.0001
    first_pass_pvalue = max_pvalue * 10
    weak_change_points = split(series, window_len=10, max_pvalue=first_pass_pvalue)
    final_change_points = merge(weak_change_points, series, max_pvalue, min_magnitude=0.0)
    indices = [cp.index for cp in final_change_points]
    assert indices == [10]


def test_significance_tester_not_significant() -> None:
    """Flat series with no real change should produce a non-significant p-value."""
    tester = TTestSignificanceTester(0.001)
    series = np.array([1.00, 1.02, 1.05, 0.95, 0.98, 1.00, 1.02, 1.05, 0.95, 0.98])
    candidate = CandidateChangePoint(index=5, qhat=0.0)
    change_point = tester.change_point(candidate, series, intervals=[slice(None, None)])
    assert not tester.is_significant(change_point)
    assert 0.99 < change_point.stats.pvalue < 1.01


def test_significance_tester_significant() -> None:
    """Clear step change should produce a highly significant p-value."""
    tester = TTestSignificanceTester(0.001)
    series = np.array([1.00, 1.02, 1.05, 0.95, 0.98, 0.80, 0.82, 0.85, 0.79, 0.77])
    candidate = CandidateChangePoint(index=5, qhat=0.0)
    change_point = tester.change_point(candidate, series, intervals=[slice(None, None)])
    assert tester.is_significant(change_point)
    assert 0.00 < change_point.stats.pvalue < 0.001
