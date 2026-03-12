"""Criteria string parsing, evaluation, and baseline aggregation."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel


class CriteriaType(StrEnum):
    """Whether a criterion compares against a fixed value or a relative baseline."""

    FIXED = "fixed"
    RELATIVE = "relative"


class ParsedCriteria(BaseModel):
    """A single parsed criterion ready for evaluation.

    Attributes:
        raw: Original criteria string as written in the SLO YAML.
        operator: Comparison operator: <, <=, =, >=, >.
        type: FIXED for absolute thresholds; RELATIVE for baseline-percentage comparisons.
        threshold: Target value for FIXED criteria.
        relative_pct: Percentage delta for RELATIVE criteria.
        relative_direction: '+' means baseline + pct; '-' means baseline - pct.
    """

    raw: str
    operator: str
    type: CriteriaType
    threshold: float = 0.0
    relative_pct: float = 0.0
    relative_direction: str = "+"

    def compute_target_value(self, baseline: float | None) -> float:
        """Compute the concrete target value to compare the metric against.

        Args:
            baseline: Aggregated value from previous evaluations. Required for
                RELATIVE criteria; ignored for FIXED.

        Returns:
            The target value. Returns 0.0 for RELATIVE criteria when baseline is None.
        """
        if self.type == CriteriaType.FIXED:
            return self.threshold
        if baseline is None:
            return 0.0
        delta = baseline * (self.relative_pct / 100.0)
        if self.relative_direction == "+":
            return baseline + delta
        return baseline - delta


_PATTERN = re.compile(
    r"^(?P<op><=|>=|<|>|=)"
    r"\s*"
    r"(?P<sign>[+-])?"
    r"(?P<value>\d+(?:\.\d+)?)"
    r"\s*"
    r"(?P<pct>%)?"
    r"$"
)


def parse_criteria_string(raw: str) -> ParsedCriteria:
    """Parse a criteria string from an SLO YAML into a structured model.

    Supports fixed thresholds (`<600`, `=0`) and relative comparisons
    (`<=+10%`, `>=-5%`, `<=+10`). Whitespace is normalised before parsing.
    An explicit sign (+/-) without % is treated as relative, matching
    Keptn lighthouse-service behaviour.

    Args:
        raw: Criteria string e.g. `"<600"`, `"<=+10%"`, `"  <=+10   %"`.

    Returns:
        ParsedCriteria with operator, type, and threshold/percentage fields set.

    Raises:
        ValueError: If the string cannot be parsed.
    """
    # str.split() on no argument splits on any whitespace; join eliminates all spaces.
    # This normalises "  <=+10   %" → "<=+10%" without needing a regex.
    normalised = "".join(raw.split())

    m = _PATTERN.match(normalised)
    if not m:
        raise ValueError(f"Cannot parse criteria string: {raw!r}")

    op = m.group("op")
    sign = m.group("sign")
    value = float(m.group("value"))
    is_pct = m.group("pct") is not None
    is_relative = is_pct or sign is not None

    if is_relative:
        return ParsedCriteria(
            raw=raw,
            operator=op,
            type=CriteriaType.RELATIVE,
            relative_pct=value,
            relative_direction=sign or "+",
        )
    return ParsedCriteria(
        raw=raw,
        operator=op,
        type=CriteriaType.FIXED,
        threshold=value,
    )


def _compare(operator: str, value: float, target: float) -> bool:
    match operator:
        case "<":
            return value < target
        case "<=":
            return value <= target
        case ">":
            return value > target
        case ">=":
            return value >= target
        case "=":
            return value == target
        case _:
            return False


def evaluate_criteria(
    criteria: ParsedCriteria,
    value: float,
    baseline: float | None,
) -> bool:
    """Evaluate a single parsed criteria against a metric value.

    Relative criteria with no baseline always pass — no history means
    no penalty for the first evaluation.

    Args:
        criteria: Parsed criteria to evaluate.
        value: Current metric value.
        baseline: Aggregated baseline from previous evaluations (may be None).

    Returns:
        True if the criteria is satisfied, False otherwise.
    """
    if criteria.type == CriteriaType.RELATIVE and baseline is None:
        return True
    target = criteria.compute_target_value(baseline)
    return _compare(criteria.operator, value, target)


def aggregate_values(values: list[float], function: str) -> float:
    """Aggregate a list of baseline values using the specified function.

    Matches Keptn lighthouse-service `aggregateValues()` behaviour exactly.
    Supported functions: avg, p50, p90, p95, p99.

    Args:
        values: Non-empty list of floats to aggregate.
        function: One of 'avg', 'p50', 'p90', 'p95', 'p99'.

    Returns:
        The aggregated scalar value.

    Raises:
        ValueError: If values is empty or function is unknown.
    """
    if not values:
        raise ValueError("Cannot aggregate empty values list")
    sorted_vals = sorted(values)
    match function:
        case "avg":
            return sum(sorted_vals) / len(sorted_vals)
        case "p50":
            return _percentile(sorted_vals, 50)
        case "p90":
            return _percentile(sorted_vals, 90)
        case "p95":
            return _percentile(sorted_vals, 95)
        case "p99":
            return _percentile(sorted_vals, 99)
        case _:
            raise ValueError(f"Unknown aggregate function: {function!r}")


def _percentile(sorted_values: list[float], pct: int) -> float:
    if not sorted_values:
        raise ValueError("Cannot calculate percentile of empty list")
    idx = int(len(sorted_values) * pct / 100)
    return sorted_values[min(idx, len(sorted_values) - 1)]
