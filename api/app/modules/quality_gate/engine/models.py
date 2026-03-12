"""Pydantic domain models for the SLO evaluation engine.

All data structures used across the engine modules are defined here.
Functions live in the individual modules (slo_parser, criteria, scoring, evaluator, variables).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.modules.quality_gate.engine.constants import (
    CriteriaType,
    EvaluationOutcome,
    IndicatorStatus,
)

__all__ = [
    "SLO",
    "CriteriaType",
    "EvaluationOutcome",
    "EvaluationResult",
    "IndicatorStatus",
    "ObjectiveResult",
    "ParsedCriteria",
    "SLOComparison",
    "SLOCriteria",
    "SLOObjective",
    "SLOParseError",
    "SLOTotalScore",
    "TotalScore",
]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SLOParseError(ValueError):
    """Raised when an SLO YAML document is invalid or references unknown indicators."""


# ---------------------------------------------------------------------------
# SLO definition models (parsed from YAML)
# ---------------------------------------------------------------------------


class SLOCriteria(BaseModel):
    """A single block of criteria strings evaluated with AND logic.

    Multiple SLOCriteria on the same objective use OR logic across blocks.
    """

    criteria: list[str]


class SLOObjective(BaseModel):
    """A single SLO objective — one metric with pass/warning thresholds and weighting."""

    sli: str
    display_name: str = ""
    pass_criteria: list[SLOCriteria] = Field(default_factory=list)
    warning_criteria: list[SLOCriteria] = Field(default_factory=list)
    weight: int = 1
    key_sli: bool = False


class SLOComparison(BaseModel):
    """Configuration for historical baseline comparison used in relative criteria."""

    compare_with: str = "single_result"
    number_of_comparison_results: int = 3
    include_result_with_score: str = "all"
    aggregate_function: str = "avg"
    scope_tags: list[str] = Field(default_factory=lambda: ["os"])


class SLOTotalScore(BaseModel):
    """Pass and warning percentage thresholds for the overall weighted score."""

    pass_pct: float = 90.0
    warning_pct: float = 75.0


class SLO(BaseModel):
    """Parsed and validated SLO document combining indicators, objectives, and thresholds."""

    spec_version: str
    indicators: dict[str, str]
    objectives: list[SLOObjective]
    comparison: SLOComparison
    total_score: SLOTotalScore


# ---------------------------------------------------------------------------
# Criteria models
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Scoring / result models
# ---------------------------------------------------------------------------


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
