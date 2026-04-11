"""SLO constructor — builds validated SLO models from structured data."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from tropek.modules.quality_gate.evaluation_engine.slo_models import (
    SLO,
    SLOComparison,
    SLOObjective,
    SLOParseError,
    SLOTotalScore,
)


def build_slo(
    objectives: list[dict[str, Any]],
    total_score_pass_threshold: float = 90.0,
    total_score_warning_threshold: float = 75.0,
    comparison: dict[str, Any] | None = None,
) -> SLO:
    """Build and validate an SLO model from structured data.

    Args:
        objectives: List of objective dicts matching SLOObjective fields.
        total_score_pass_threshold: Minimum % to pass. Default 90.0.
        total_score_warning_threshold: Minimum % to warn. Default 75.0.
        comparison: Optional comparison config dict. Empty/None uses all defaults.

    Returns:
        Validated SLO model.

    Raises:
        SLOParseError: If objectives is empty or data is structurally invalid.
    """
    if not objectives:
        raise SLOParseError('objectives list is empty')
    try:
        parsed_objectives = [SLOObjective.model_validate(o) for o in objectives]
        parsed_comparison = SLOComparison.model_validate(comparison or {})
    except ValidationError as e:
        raise SLOParseError(f'invalid slo structure: {e}') from e
    return SLO(
        objectives=parsed_objectives,
        comparison=parsed_comparison,
        total_score=SLOTotalScore(
            pass_threshold=total_score_pass_threshold,
            warning_threshold=total_score_warning_threshold,
        ),
    )
