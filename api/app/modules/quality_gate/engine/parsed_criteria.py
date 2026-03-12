"""ParsedCriteria model — structured output of criteria string parsing.

Kept separate from criteria.py (which contains the parsing functions) to
avoid a circular import: criteria.py imports this model, models.py re-exports
it, and nothing in this file needs to import from either of them.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.modules.quality_gate.engine.constants import CriteriaType


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
