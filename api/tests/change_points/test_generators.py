"""Tests for distribution-based time series generators."""

from __future__ import annotations

import numpy as np
from scipy.stats import norm
from tropek.modules.change_points.detector import detect_change_points

from tests.helpers.data_generators import (
    DriftGenerator,
    MultipleChangePointGenerator,
    StableGenerator,
    StepChangeGenerator,
    VarianceChangeGenerator,
    make_timestamps,
)

SERIES_LEN = 100
HALF = SERIES_LEN // 2


class TestStableGenerator:
    def test_produces_correct_count(self) -> None:
        gen = StableGenerator(dist=norm, params={'loc': 100, 'scale': 5}, seed=42)
        series = gen.generate(50)
        assert len(series) == 50

    def test_no_false_positives(self) -> None:
        gen = StableGenerator(dist=norm, params={'loc': 100, 'scale': 5}, seed=42)
        series = gen.generate(SERIES_LEN)
        results = detect_change_points(
            values=series,
            timestamps=make_timestamps(SERIES_LEN),
            higher_is_better=False,
        )
        assert results == []

    def test_deterministic_with_seed(self) -> None:
        gen1 = StableGenerator(dist=norm, params={'loc': 100, 'scale': 5}, seed=42)
        gen2 = StableGenerator(dist=norm, params={'loc': 100, 'scale': 5}, seed=42)
        assert gen1.generate(20) == gen2.generate(20)


class TestStepChangeGenerator:
    def test_detector_finds_step_change(self) -> None:
        gen = StepChangeGenerator(
            dist=norm,
            before={'loc': 100, 'scale': 5},
            after={'loc': 150, 'scale': 5},
            changepoint=HALF,
            seed=42,
        )
        series = gen.generate(SERIES_LEN)
        results = detect_change_points(
            values=series,
            timestamps=make_timestamps(SERIES_LEN),
            higher_is_better=False,
        )
        assert len(results) >= 1
        assert results[0].direction == 'regression'
        assert abs(results[0].position - HALF) <= 5

    def test_same_mean_moderate_variance_change_missed_by_edivisive(self) -> None:
        """E-Divisive detects mean shifts, not variance changes.

        A moderate variance increase (scale 5→12) keeps the mean unchanged
        but makes the series noisier. E-Divisive should not flag this — a
        dedicated variance detector (Levene's test) would be needed.
        """
        gen = VarianceChangeGenerator(
            dist=norm,
            loc=100,
            scale_before=5,
            scale_after=15,
            changepoint=HALF,
            seed=17,
        )
        series = gen.generate(SERIES_LEN)
        results = detect_change_points(
            values=series,
            timestamps=make_timestamps(SERIES_LEN),
            higher_is_better=False,
        )
        assert results == []


class TestDriftGenerator:
    def test_gradual_drift_series_shape(self) -> None:
        gen = DriftGenerator(
            dist=norm,
            before={'loc': 100, 'scale': 3},
            after={'loc': 130, 'scale': 3},
            changepoint=30,
            steps=40,
            seed=42,
        )
        series = gen.generate(SERIES_LEN)
        assert len(series) == SERIES_LEN
        before_mean = np.mean(series[:20])
        after_mean = np.mean(series[80:])
        assert after_mean > before_mean + 20

    def test_slow_drift_may_evade_edivisive(self) -> None:
        gen = DriftGenerator(
            dist=norm,
            before={'loc': 100, 'scale': 5},
            after={'loc': 110, 'scale': 5},
            changepoint=30,
            steps=50,
            seed=42,
        )
        series = gen.generate(SERIES_LEN)
        results = detect_change_points(
            values=series,
            timestamps=make_timestamps(SERIES_LEN),
            higher_is_better=False,
        )
        assert len(results) <= 1


class TestMultipleChangePointGenerator:
    def test_three_segments(self) -> None:
        gen = MultipleChangePointGenerator(
            dist=norm,
            segments=[
                (0, {'loc': 100, 'scale': 3}),
                (35, {'loc': 150, 'scale': 3}),
                (70, {'loc': 80, 'scale': 3}),
            ],
            seed=42,
        )
        series = gen.generate(SERIES_LEN)
        results = detect_change_points(
            values=series,
            timestamps=make_timestamps(SERIES_LEN),
            higher_is_better=False,
        )
        assert len(results) >= 2
        positions = sorted(r.position for r in results)
        assert abs(positions[0] - 35) <= 5
        assert abs(positions[1] - 70) <= 5


class TestMakeTimestamps:
    def test_correct_count_and_spacing(self) -> None:
        timestamps = make_timestamps(10)
        assert len(timestamps) == 10
        for i in range(1, len(timestamps)):
            delta = timestamps[i] - timestamps[i - 1]
            assert delta.total_seconds() == 3600
