"""SLO definition models — structural representations of SLO objectives and thresholds."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.quality_gate.engine.constants import (
    AggregateFunction,
    CompareWith,
    IncludeResultWithScore,
)


class SLOParseError(ValueError):
    """Raised when SLO data is structurally invalid."""


class SLOObjective(BaseModel):
    """A single SLO objective — one metric with pass/warning thresholds and weighting."""

    sli: str
    display_name: str = ""
    pass_criteria: list[str] = Field(default_factory=list)
    warning_criteria: list[str] = Field(default_factory=list)
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
    """Validated SLO combining objectives, comparison config, and score thresholds."""

    objectives: list[SLOObjective]
    comparison: SLOComparison
    total_score: SLOTotalScore
