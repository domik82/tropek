"""Re-export hub for all engine domain models.

Import from this module to get any engine type without caring which sub-module
defines it.  Internal sub-modules (slo, parsed_criteria, results) are
implementation details and may be reorganised without breaking callers.
"""

from __future__ import annotations

from app.modules.quality_gate.engine.constants import (
    AggregateFunction,
    CompareWith,
    CriteriaType,
    EvaluationOutcome,
    IncludeResultWithScore,
    IndicatorStatus,
)
from app.modules.quality_gate.engine.parsed_criteria import ParsedCriteria
from app.modules.quality_gate.engine.results import EvaluationResult, ObjectiveResult, TotalScore
from app.modules.quality_gate.engine.slo import (
    SLO,
    SLOComparison,
    SLOCriteria,
    SLOObjective,
    SLOParseError,
    SLOTotalScore,
)

__all__ = [
    "SLO",
    "AggregateFunction",
    "CompareWith",
    "CriteriaType",
    "EvaluationOutcome",
    "EvaluationResult",
    "IncludeResultWithScore",
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
