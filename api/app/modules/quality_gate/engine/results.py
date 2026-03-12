"""Result models — output of the SLO evaluation engine.

These models carry the evaluation outcome from scoring.py and evaluator.py
to callers. They depend on the SLO domain models (for SLOObjective) and
on the constants (for IndicatorStatus and EvaluationOutcome).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.modules.quality_gate.engine.constants import EvaluationOutcome, IndicatorStatus
from app.modules.quality_gate.engine.slo import SLOObjective


class ObjectiveResult(BaseModel):
    """Evaluation result for a single SLO objective.

    Attributes:
        objective: The SLO objective that was evaluated.
        status: Pass / warning / fail / info result for this indicator.
        score: Points contributed to the total (0, 0.5 * weight, or weight).
        contributes_to_score: False for informational-only objectives (no pass criteria).
        key_sli_failed: True if this is a key SLI and it failed — vetoes the overall result.
    """

    objective: SLOObjective
    status: IndicatorStatus
    score: float
    contributes_to_score: bool
    key_sli_failed: bool


class TotalScore(BaseModel):
    """Overall evaluation result after applying weights and thresholds.

    Attributes:
        result: Overall outcome — pass, warning, or fail.
        score: Achieved percentage (0-100).
    """

    result: EvaluationOutcome
    score: float


class EvaluationResult(BaseModel):
    """Result of evaluating a full SLO against a set of metric values.

    Attributes:
        result: Overall outcome — pass, warning, or fail.
        score: Weighted score as a percentage (0.0-100.0).
        indicator_results: Per-SLI breakdown with values, targets, and violation flags.
        compared_evaluation_ids: IDs of previous evaluations used as comparison baseline.
    """

    result: EvaluationOutcome
    score: float
    indicator_results: list[dict[str, Any]] = Field(default_factory=list)
    compared_evaluation_ids: list[str] = Field(default_factory=list)
