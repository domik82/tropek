"""Edge-case tests for criteria evaluation: zero/negative baselines, aggregation boundaries."""

from __future__ import annotations

import pytest
from app.modules.quality_gate.engine.criteria import (
    aggregate_values,
    evaluate_criteria,
    parse_criteria_string,
)

# --- Relative criteria with zero baseline ---


def test_relative_percent_with_zero_baseline() -> None:
    """<=+10% with baseline=0: target = 0 + 0*10% = 0. Value 0.5 > 0 → fail, not ZeroDivisionError."""
    criteria = parse_criteria_string("<=+10%")
    result = evaluate_criteria(criteria, value=0.5, baseline=0.0)
    assert result is False


def test_relative_percent_zero_baseline_zero_value() -> None:
    """<=+10% with baseline=0, value=0: target=0, 0 <= 0 → pass."""
    criteria = parse_criteria_string("<=+10%")
    result = evaluate_criteria(criteria, value=0.0, baseline=0.0)
    assert result is True


def test_relative_percent_with_negative_baseline() -> None:
    """<=+10% with baseline=-100: target = -100 + (-100*10/100) = -110. Value -90 > -110 → fail."""
    criteria = parse_criteria_string("<=+10%")
    result = evaluate_criteria(criteria, value=-90.0, baseline=-100.0)
    assert result is False


def test_relative_minus_pct_with_negative_baseline() -> None:
    """>=-10% with baseline=-100: target = -100 - (-100*10/100) = -90. Value -95 < -90 → fail."""
    criteria = parse_criteria_string(">=-10%")
    result = evaluate_criteria(criteria, value=-95.0, baseline=-100.0)
    assert result is False


def test_relative_minus_pct_negative_baseline_pass() -> None:
    """>=-10% with baseline=-100: target = -90. Value -85 >= -90 → pass."""
    criteria = parse_criteria_string(">=-10%")
    result = evaluate_criteria(criteria, value=-85.0, baseline=-100.0)
    assert result is True


# --- Aggregation edge cases ---


def test_aggregate_empty_values_raises() -> None:
    """Aggregating empty list raises ValueError."""
    with pytest.raises(ValueError, match="empty"):
        aggregate_values([], "avg")


def test_aggregate_single_value_p90() -> None:
    """Single value returns that value for any percentile function."""
    result = aggregate_values([42.0], "p90")
    assert result == 42.0


def test_aggregate_single_value_p99() -> None:
    result = aggregate_values([42.0], "p99")
    assert result == 42.0


def test_aggregate_p99_with_two_values() -> None:
    """p99 of [10, 20]: idx = int(2 * 99 / 100) = 1 → sorted[1] = 20."""
    result = aggregate_values([10.0, 20.0], "p99")
    assert isinstance(result, float)
    assert result == 20.0


def test_aggregate_p50_with_three_values() -> None:
    """p50 of [1, 2, 3]: idx = int(3 * 50 / 100) = 1 → sorted[1] = 2."""
    result = aggregate_values([3.0, 1.0, 2.0], "p50")
    assert result == 2.0


def test_aggregate_avg_with_negative_values() -> None:
    """Average handles negative values correctly."""
    result = aggregate_values([-10.0, 10.0], "avg")
    assert result == pytest.approx(0.0)
