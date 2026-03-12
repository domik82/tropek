"""SLO definition models — parsed from YAML by slo_parser.

These are the structural representations of the Keptn 1.0 SLO document:
indicators, objectives, comparison configuration, and pass/warning thresholds.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.quality_gate.engine.constants import (
    AggregateFunction,
    CompareWith,
    IncludeResultWithScore,
)


class SLOParseError(ValueError):
    """Raised when an SLO YAML document is invalid or references unknown indicators."""


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

    compare_with: CompareWith = CompareWith.SINGLE_RESULT
    number_of_comparison_results: int = 3
    include_result_with_score: IncludeResultWithScore = IncludeResultWithScore.ALL
    aggregate_function: AggregateFunction = AggregateFunction.AVG
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
