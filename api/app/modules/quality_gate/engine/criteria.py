from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class CriteriaType(Enum):
    FIXED = "fixed"
    RELATIVE = "relative"


@dataclass
class ParsedCriteria:
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
    r"(?P<sign>[+-])?"
    r"(?P<value>\d+(?:\.\d+)?)"
    r"(?P<pct>%)?"
    r"$"
)


def parse_criteria_string(raw: str) -> ParsedCriteria:
    raw = raw.strip()
    m = _PATTERN.match(raw)
    if not m:
        raise ValueError(f"Cannot parse criteria string: {raw!r}")

    op = m.group("op")
    sign = m.group("sign")
    value = float(m.group("value"))
    is_pct = m.group("pct") is not None

    if is_pct:
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

    Relative criteria with no baseline always pass — no history yet means
    we cannot penalise.
    """
    if criteria.type == CriteriaType.RELATIVE and baseline is None:
        return True
    target = criteria.compute_target_value(baseline)
    return _compare(criteria.operator, value, target)
