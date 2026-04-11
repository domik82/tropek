"""Result models — output of the SLO evaluation engine.

These models carry the evaluation outcome from scoring.py and evaluator.py
to callers. They depend on the SLO domain models (for SLOObjective) and
on the constants (for IndicatorStatus and EvaluationOutcome).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.quality_gate.evaluation_engine.constants import EvaluationOutcome, IndicatorStatus
from app.modules.quality_gate.evaluation_engine.slo_models import SLOObjective


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


class CriteriaTarget(BaseModel):
    """A single pass/warning criteria target with violation flag.

    Attributes:
        criteria: Raw criteria string (e.g. "<600", "<=+10%").
        target_value: Computed threshold value after resolving baseline.
        violated: Whether the metric value violated this criteria.
    """

    criteria: str
    target_value: float | None
    violated: bool


class IndicatorResult(BaseModel):
    """Typed evaluation result for a single SLI indicator.

    Replaces the untyped dict[str, Any] that was previously used in the engine.
    This model is serialized to JSONB when stored in the database.

    Attributes:
        metric: SLI metric name (matches objective.sli).
        display_name: Human-readable name for the metric.
        value: Measured metric value, or None if not retrieved.
        compared_value: Aggregated baseline value used for comparison.
        status: Indicator outcome — pass, warning, fail, or info.
        score: Points contributed by this indicator.
        weight: Objective weight from the SLO definition.
        key_sli: Whether this is a key SLI that vetoes the overall result.
        pass_targets: Criteria targets for the pass threshold.
        warning_targets: Criteria targets for the warning threshold, or None.
        change_absolute: Absolute difference from baseline (value - baseline).
        change_relative_pct: Relative percent change from baseline.
    """

    metric: str
    display_name: str
    value: float | None
    compared_value: float | None
    status: str
    score: float
    weight: float
    key_sli: bool
    pass_targets: list[CriteriaTarget]
    warning_targets: list[CriteriaTarget] | None
    change_absolute: float | None
    change_relative_pct: float | None


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
    indicator_results: list[IndicatorResult] = Field(default_factory=list)
    compared_evaluation_ids: list[str] = Field(default_factory=list)
