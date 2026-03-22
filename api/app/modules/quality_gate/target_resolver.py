"""Resolve pass/warning targets from criteria strings at read time.

Computes pass_targets/warning_targets from SLO criteria at read time.
Uses the same criteria parsing logic from the engine.
"""

from __future__ import annotations

from typing import Any

from app.modules.quality_gate.engine.criteria import evaluate_criteria, parse_criteria_string


def resolve_targets(
    criteria: list[str] | None,
    *,
    value: float | None,
    compared_value: float | None,
) -> list[dict[str, Any]] | None:
    """Compute target list from raw criteria strings.

    Returns None if criteria is None (info-only objective).
    Returns [] if criteria is an empty list.
    """
    if criteria is None:
        return None
    targets: list[dict[str, Any]] = []
    for raw in criteria:
        c = parse_criteria_string(raw)
        target_value = c.compute_target_value(compared_value)
        violated = not evaluate_criteria(c, value, compared_value) if value is not None else True
        targets.append(
            {
                "criteria": raw,
                "target_value": target_value,
                "violated": violated,
            }
        )
    return targets
