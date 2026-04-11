from __future__ import annotations

import pytest
from tropek.modules.quality_gate.evaluation_engine.criteria import (
    CriteriaType,
    aggregate_values,
    evaluate_criteria,
    parse_criteria_string,
)

# --- parse_criteria_string ---


def test_parse_fixed_lt() -> None:
    c = parse_criteria_string('<600')
    assert c.operator == '<'
    assert c.type == CriteriaType.FIXED
    assert c.threshold == 600.0


def test_parse_fixed_lte() -> None:
    c = parse_criteria_string('<=500')
    assert c.operator == '<='
    assert c.threshold == 500.0


def test_parse_fixed_eq() -> None:
    c = parse_criteria_string('=0')
    assert c.operator == '='
    assert c.threshold == 0.0


def test_parse_fixed_gte() -> None:
    c = parse_criteria_string('>=10')
    assert c.operator == '>='
    assert c.threshold == 10.0


def test_parse_relative_plus_pct() -> None:
    c = parse_criteria_string('<=+10%')
    assert c.type == CriteriaType.RELATIVE
    assert c.operator == '<='
    assert c.relative_pct == 10.0
    assert c.relative_direction == '+'


def test_parse_relative_minus_pct() -> None:
    c = parse_criteria_string('>=-5%')
    assert c.type == CriteriaType.RELATIVE
    assert c.relative_pct == 5.0
    assert c.relative_direction == '-'


def test_parse_relative_no_sign_defaults_plus() -> None:
    c = parse_criteria_string('<=10%')
    assert c.type == CriteriaType.RELATIVE
    assert c.relative_direction == '+'


def test_parse_decimal_percentage() -> None:
    c = parse_criteria_string('<=+10.5%')
    assert c.type == CriteriaType.RELATIVE
    assert c.relative_pct == 10.5


def test_parse_whitespace_in_criteria() -> None:
    """Keptn lighthouse allowed whitespace around operator and % sign."""
    c = parse_criteria_string('  <=+10   %')
    assert c.type == CriteriaType.RELATIVE
    assert c.operator == '<='
    assert c.relative_pct == 10.0
    assert c.relative_direction == '+'


def test_parse_sign_without_pct_is_relative() -> None:
    """<=+10 (no %) with explicit sign → relative, matching Go behaviour."""
    c = parse_criteria_string('<=+10')
    assert c.type == CriteriaType.RELATIVE
    assert c.relative_pct == 10.0
    assert c.relative_direction == '+'


def test_parse_negative_sign_without_pct_is_relative() -> None:
    c = parse_criteria_string('>=-10')
    assert c.type == CriteriaType.RELATIVE
    assert c.relative_direction == '-'
    assert c.relative_pct == 10.0


def test_invalid_criteria_raises() -> None:
    with pytest.raises(ValueError, match='Cannot parse'):
        parse_criteria_string('?????')


# --- evaluate_criteria fixed ---


def test_fixed_lt_pass() -> None:
    assert evaluate_criteria(parse_criteria_string('<600'), 550.0, None) is True


def test_fixed_lt_fail() -> None:
    assert evaluate_criteria(parse_criteria_string('<600'), 600.0, None) is False


def test_fixed_lte_pass_equal() -> None:
    assert evaluate_criteria(parse_criteria_string('<=600'), 600.0, None) is True


def test_fixed_eq_pass() -> None:
    assert evaluate_criteria(parse_criteria_string('=0'), 0.0, None) is True


def test_fixed_eq_fail() -> None:
    assert evaluate_criteria(parse_criteria_string('=0'), 1.0, None) is False


def test_fixed_gt_pass() -> None:
    assert evaluate_criteria(parse_criteria_string('>10'), 11.0, None) is True


# --- evaluate_criteria relative ---


def test_relative_plus_within_threshold() -> None:
    # value=110, baseline=100, +10% → target=110 → 110 <= 110 → pass
    assert evaluate_criteria(parse_criteria_string('<=+10%'), 110.0, 100.0) is True


def test_relative_plus_exceeds_threshold() -> None:
    # value=111, baseline=100, +10% → target=110 → 111 > 110 → fail
    assert evaluate_criteria(parse_criteria_string('<=+10%'), 111.0, 100.0) is False


def test_relative_minus_pct() -> None:
    # value=92, baseline=100, >=-10% → target=90 → 92 >= 90 → pass
    assert evaluate_criteria(parse_criteria_string('>=-10%'), 92.0, 100.0) is True


def test_relative_no_baseline_always_passes() -> None:
    assert evaluate_criteria(parse_criteria_string('<=+10%'), 999.0, None) is True


# --- compute_target_value ---


def test_target_value_fixed() -> None:
    assert parse_criteria_string('<600').compute_target_value(None) == 600.0


def test_target_value_relative_plus() -> None:
    assert parse_criteria_string('<=+10%').compute_target_value(100.0) == 110.0


def test_target_value_relative_minus() -> None:
    assert parse_criteria_string('>=-10%').compute_target_value(100.0) == 90.0


def test_target_value_relative_no_baseline() -> None:
    assert parse_criteria_string('<=+10%').compute_target_value(None) == 0.0


# --- aggregate_values (matches Go's aggregateValues) ---


def test_aggregate_avg() -> None:
    assert aggregate_values([10.0, 5.0, 15.0], 'avg') == pytest.approx(10.0)


def test_aggregate_p50() -> None:
    # Go test: p50 of [10.0, 5.0] sorted → [5.0, 10.0], idx=1 → 10.0
    # Our impl: idx = int(2 * 50 / 100) = 1 → sorted[1] = 10.0
    result = aggregate_values([10.0, 5.0], 'p50')
    assert result == pytest.approx(10.0)


def test_aggregate_p90() -> None:
    # 10 values, idx = int(10 * 90/100) = 9, sorted[9] = 10.0
    # Matches Go's calculatePercentile behaviour exactly
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    result = aggregate_values(values, 'p90')
    assert result == pytest.approx(10.0)


def test_aggregate_p95() -> None:
    values = list(range(1, 21))  # 1..20
    result = aggregate_values([float(v) for v in values], 'p95')
    # idx = int(20 * 95 / 100) = 19, sorted[19] = 20.0
    assert result == pytest.approx(20.0)


def test_aggregate_single_value() -> None:
    assert aggregate_values([42.0], 'avg') == pytest.approx(42.0)


def test_aggregate_unknown_function_raises() -> None:
    with pytest.raises(ValueError, match='Unknown aggregate function'):
        aggregate_values([1.0, 2.0], 'median')


def test_aggregate_empty_raises() -> None:
    with pytest.raises(ValueError, match='empty'):
        aggregate_values([], 'avg')
