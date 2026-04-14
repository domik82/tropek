"""Resolve pass/warning targets from criteria strings at read time.

Computes pass_targets/warning_targets from SLO criteria at read time.
Uses the same criteria parsing logic from the engine.
"""

from __future__ import annotations

from tropek.modules.quality_gate.evaluation_engine.criteria import (
    ParsedCriteria,
    evaluate_criteria,
    parse_criteria_string,
)
from tropek.modules.quality_gate.schemas.evaluations import PassTarget


def resolve_targets(
    criteria: list[str] | None,
    *,
    value: float | None,
    compared_value: float | None,
) -> list[PassTarget] | None:
    """Compute target list from raw criteria strings.

    Returns None if criteria is None (info-only objective).
    Returns [] if criteria is an empty list.
    """
    if criteria is None:
        return None
    targets: list[PassTarget] = []
    for raw in criteria:
        parsed = parse_criteria_string(raw)
        target_value = parsed.compute_target_value(compared_value)
        violated = not evaluate_criteria(parsed, value, compared_value) if value is not None else True
        targets.append(
            PassTarget(
                criteria=raw,
                target_value=target_value,
                violated=violated,
            )
        )
    return targets


def resolve_targets_from_parsed(
    parsed_criteria: list[ParsedCriteria] | None,
    raw_criteria: list[str] | None,
    *,
    value: float | None,
    compared_value: float | None,
) -> list[PassTarget] | None:
    """Compute target list from pre-parsed criteria.

    Hot-path variant of resolve_targets: the caller has pre-parsed the
    criteria strings once per objective (per fragment), so cell-level
    calls reuse the parsed form instead of re-parsing.

    Returns None when criteria is None (info-only objective). Returns []
    when the objective has an empty criteria list.
    """
    if parsed_criteria is None or raw_criteria is None:
        return None
    targets: list[PassTarget] = []
    for parsed, raw in zip(parsed_criteria, raw_criteria, strict=True):
        target_value = parsed.compute_target_value(compared_value)
        violated = not evaluate_criteria(parsed, value, compared_value) if value is not None else True
        targets.append(
            PassTarget(
                criteria=raw,
                target_value=target_value,
                violated=violated,
            )
        )
    return targets
