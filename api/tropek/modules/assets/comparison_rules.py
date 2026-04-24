"""Pydantic validation for comparison rules on AssetSLOLink.

Comparison rules control which prior evaluations are eligible as baselines
for a given evaluation. Rules are stored as a JSONB array on AssetSLOLink
and validated at write time via these models.

Rule semantics:
- match: tag conditions on the current evaluation's metadata
  - {"branch": "main"} — exact match
  - {"branch": "!main"} — negation (any value except "main")
  - {} — catch-all (matches everything)
- compare_to: tag filters applied to baseline query
  - {"branch": "main"} — baselines must have branch=main
  - {"pinned": true} — only use baselines at/after pinned evaluation
  - {} — no tag filtering
"""

from __future__ import annotations

from typing import Any

from tropek.modules.common.schemas import StrictInput


class ComparisonRule(StrictInput):
    """A single comparison rule entry."""

    match: dict[str, str]
    compare_to: dict[str, str | bool]


def validate_comparison_rules(
    raw: list[dict[str, Any]],
) -> list[ComparisonRule]:
    """Validate and return parsed comparison rules.

    Raises ValueError if:
    - More than one catch-all rule (match == {})
    - Catch-all rule is not last in the list
    """
    rules = [ComparisonRule.model_validate(r) for r in raw]

    catch_all_indices = [i for i, r in enumerate(rules) if r.match == {}]

    if len(catch_all_indices) > 1:
        msg = 'at most one catch-all rule (match: {}) is allowed'
        raise ValueError(msg)

    if len(catch_all_indices) == 1 and catch_all_indices[0] != len(rules) - 1:
        msg = 'catch-all rule (match: {}) must be last in the list'
        raise ValueError(msg)

    return rules
