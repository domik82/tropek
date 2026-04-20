"""Unit tests for the Otava change point detector — pure function, no DB."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tropek.modules.change_points.detector import ChangePointResult, detect_change_points

_BASE = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)


def _timestamps(count: int) -> list[datetime]:
    return [_BASE + timedelta(hours=i) for i in range(count)]


class TestDetectChangePoints:
    """Tests for the detect_change_points pure function."""

    def test_no_change_in_flat_series(self) -> None:
        values = [10.0] * 30
        results = detect_change_points(
            values=values,
            timestamps=_timestamps(30),
            higher_is_better=False,
        )
        assert results == []

    def test_detects_step_regression_lower_is_better(self) -> None:
        values = [10.0] * 15 + [50.0] * 15
        results = detect_change_points(
            values=values,
            timestamps=_timestamps(30),
            higher_is_better=False,
        )
        assert len(results) >= 1
        change_point = results[0]
        assert change_point.direction == 'regression'
        assert change_point.change_absolute > 0
        assert change_point.pre_segment_mean < change_point.post_segment_mean

    def test_detects_step_improvement_lower_is_better(self) -> None:
        values = [50.0] * 15 + [10.0] * 15
        results = detect_change_points(
            values=values,
            timestamps=_timestamps(30),
            higher_is_better=False,
        )
        assert len(results) >= 1
        assert results[0].direction == 'improvement'

    def test_detects_regression_higher_is_better(self) -> None:
        values = [100.0] * 15 + [50.0] * 15
        results = detect_change_points(
            values=values,
            timestamps=_timestamps(30),
            higher_is_better=True,
        )
        assert len(results) >= 1
        assert results[0].direction == 'regression'

    def test_too_few_samples_returns_empty(self) -> None:
        values = [10.0, 50.0, 50.0]
        results = detect_change_points(
            values=values,
            timestamps=_timestamps(3),
            higher_is_better=False,
            min_sample_size=10,
        )
        assert results == []

    def test_result_has_all_fields(self) -> None:
        values = [10.0] * 15 + [50.0] * 15
        results = detect_change_points(
            values=values,
            timestamps=_timestamps(30),
            higher_is_better=False,
        )
        assert len(results) >= 1
        change_point = results[0]
        assert isinstance(change_point, ChangePointResult)
        assert isinstance(change_point.position, int)
        assert isinstance(change_point.timestamp, datetime)
        assert change_point.direction in ('regression', 'improvement')
        assert isinstance(change_point.change_relative_pct, float)
        assert isinstance(change_point.change_absolute, float)
        assert isinstance(change_point.t_statistic, float)
        assert isinstance(change_point.pre_segment_mean, float)
        assert isinstance(change_point.post_segment_mean, float)
