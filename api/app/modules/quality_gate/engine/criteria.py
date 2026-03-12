from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel


class CriteriaType(str, Enum):
    FIXED = "fixed"
    RELATIVE = "relative"


class ParsedCriteria(BaseModel):
    raw: str
    operator: str
    type: CriteriaType
    threshold: float = 0.0
    relative_pct: float = 0.0
    relative_direction: str = "+"

    def compute_target_value(self, baseline: float | None) -> float:
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
    # Normalise: strip outer whitespace, collapse internal whitespace
    normalised = re.sub(r"\s+", "", raw.strip())

    m = _PATTERN.match(normalised)
    if not m:
        raise ValueError(f"Cannot parse criteria string: {raw!r}")

    op = m.group("op")
    sign = m.group("sign")
    value = float(m.group("value"))
    is_pct = m.group("pct") is not None

    # An explicit sign (+ or -) without % still means relative (e.g. "<=+10"
    # means "baseline + 10"), matching Keptn lighthouse-service behaviour.
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
        case "<":  return value < target
        case "<=": return value <= target
        case ">":  return value > target
        case ">=": return value >= target
        case "=":  return value == target
        case _:    return False


def evaluate_criteria(
    criteria: ParsedCriteria,
    value: float,
    baseline: float | None,
) -> bool:
    """Evaluate a single parsed criteria against a metric value.

    Relative criteria with no baseline always pass — no history means
    we cannot penalise.
    """
    if criteria.type == CriteriaType.RELATIVE and baseline is None:
        return True
    target = criteria.compute_target_value(baseline)
    return _compare(criteria.operator, value, target)


def aggregate_values(values: list[float], function: str) -> float:
    """Aggregate baseline values using the specified function.

    Supported: avg, p50, p90, p95, p99.
    Matches Keptn lighthouse-service aggregateValues() behaviour.
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
