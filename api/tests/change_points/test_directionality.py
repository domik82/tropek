"""Unit tests for metric directionality derivation from SLO criteria."""

from __future__ import annotations

from tropek.modules.change_points.directionality import is_higher_better


class TestDirectionality:
    """Tests for is_higher_better derivation from pass_threshold criteria."""

    def test_less_than_means_lower_is_better(self) -> None:
        assert is_higher_better(['<600']) is False

    def test_less_equal_means_lower_is_better(self) -> None:
        assert is_higher_better(['<=1000']) is False

    def test_greater_than_means_higher_is_better(self) -> None:
        assert is_higher_better(['>95']) is True

    def test_greater_equal_means_higher_is_better(self) -> None:
        assert is_higher_better(['>=99.9']) is True

    def test_relative_increase_means_lower_is_better(self) -> None:
        assert is_higher_better(['<=+10%']) is False

    def test_relative_absolute_means_lower_is_better(self) -> None:
        assert is_higher_better(['<=+50']) is False

    def test_empty_threshold_defaults_false(self) -> None:
        assert is_higher_better([]) is False

    def test_multiple_criteria_uses_first(self) -> None:
        assert is_higher_better(['<600', '<=+10%']) is False
        assert is_higher_better(['>95', '<=100']) is True
