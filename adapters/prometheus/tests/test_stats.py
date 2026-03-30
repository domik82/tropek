"""Tests for statistical computation module."""

import pytest
from app.core.methods import AggregationMethod
from app.core.stats import compute_statistics


class TestComputeStatistics:
    """Tests for the compute_statistics function."""

    def test_mean_of_simple_array(self) -> None:
        result = compute_statistics([1.0, 2.0, 3.0, 4.0, 5.0], [AggregationMethod.MEAN])
        assert result == {AggregationMethod.MEAN: pytest.approx(3.0)}

    def test_min_max(self) -> None:
        result = compute_statistics([10.0, 1.0, 5.0, 9.0], [AggregationMethod.MIN, AggregationMethod.MAX])
        assert result == {
            AggregationMethod.MIN: pytest.approx(1.0),
            AggregationMethod.MAX: pytest.approx(10.0),
        }

    def test_sum(self) -> None:
        result = compute_statistics([1.0, 2.0, 3.0], [AggregationMethod.SUM])
        assert result == {AggregationMethod.SUM: pytest.approx(6.0)}

    def test_std_population(self) -> None:
        result = compute_statistics([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0], [AggregationMethod.STD])
        assert result == {AggregationMethod.STD: pytest.approx(2.0)}

    def test_median(self) -> None:
        result = compute_statistics([1.0, 3.0, 5.0, 7.0, 9.0], [AggregationMethod.MEDIAN])
        assert result == {AggregationMethod.MEDIAN: pytest.approx(5.0)}

    def test_median_even_count(self) -> None:
        result = compute_statistics([1.0, 3.0, 5.0, 7.0], [AggregationMethod.MEDIAN])
        assert result == {AggregationMethod.MEDIAN: pytest.approx(4.0)}

    def test_p99_large_array(self) -> None:
        data = [float(i) for i in range(1, 101)]
        result = compute_statistics(data, [AggregationMethod.P99])
        assert result[AggregationMethod.P99] == pytest.approx(99.01)

    def test_p90(self) -> None:
        data = [float(i) for i in range(1, 101)]
        result = compute_statistics(data, [AggregationMethod.P90])
        assert result[AggregationMethod.P90] == pytest.approx(90.1)

    def test_p95(self) -> None:
        data = [float(i) for i in range(1, 101)]
        result = compute_statistics(data, [AggregationMethod.P95])
        assert result[AggregationMethod.P95] == pytest.approx(95.05)

    def test_p75(self) -> None:
        data = [float(i) for i in range(1, 101)]
        result = compute_statistics(data, [AggregationMethod.P75])
        assert result[AggregationMethod.P75] == pytest.approx(75.25)

    def test_multiple_methods_at_once(self) -> None:
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        methods = [AggregationMethod.MEAN, AggregationMethod.MIN, AggregationMethod.MAX]
        result = compute_statistics(data, methods)
        assert result == {
            AggregationMethod.MEAN: pytest.approx(3.0),
            AggregationMethod.MIN: pytest.approx(1.0),
            AggregationMethod.MAX: pytest.approx(5.0),
        }

    def test_single_element(self) -> None:
        methods = [
            AggregationMethod.MEAN,
            AggregationMethod.MIN,
            AggregationMethod.MAX,
            AggregationMethod.MEDIAN,
        ]
        result = compute_statistics([42.0], methods)
        for m in methods:
            assert result[m] == pytest.approx(42.0)

    def test_std_single_element_is_zero(self) -> None:
        result = compute_statistics([42.0], [AggregationMethod.STD])
        assert result == {AggregationMethod.STD: pytest.approx(0.0)}

    def test_empty_array_returns_none_for_all(self) -> None:
        methods = [
            AggregationMethod.MEAN,
            AggregationMethod.MIN,
            AggregationMethod.MAX,
            AggregationMethod.STD,
            AggregationMethod.P99,
        ]
        result = compute_statistics([], methods)
        for m in methods:
            assert result[m] is None

    def test_only_requested_methods_computed(self) -> None:
        result = compute_statistics([1.0, 2.0, 3.0], [AggregationMethod.MEAN])
        assert list(result.keys()) == [AggregationMethod.MEAN]

    def test_enum_has_all_ten_methods(self) -> None:
        assert len(AggregationMethod) == 10

    def test_nan_values_filtered_out(self) -> None:
        result = compute_statistics([1.0, float('nan'), 3.0, float('nan'), 5.0], [AggregationMethod.MEAN])
        assert result == {AggregationMethod.MEAN: pytest.approx(3.0)}

    def test_all_nan_returns_none(self) -> None:
        result = compute_statistics(
            [float('nan'), float('nan')],
            [AggregationMethod.MEAN, AggregationMethod.P99],
        )
        assert result == {AggregationMethod.MEAN: None, AggregationMethod.P99: None}

    def test_enum_values_are_strings(self) -> None:
        """StrEnum values work as plain strings in dicts and f-strings."""
        assert AggregationMethod.P99 == 'p99'
        assert f'cpu.{AggregationMethod.P99}' == 'cpu.p99'
