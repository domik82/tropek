"""SLO YAML parser — converts raw YAML text into validated SLO domain models."""

from __future__ import annotations

from typing import Any

import yaml

from app.modules.quality_gate.engine.constants import (
    AggregateFunction,
    CompareWith,
    IncludeResultWithScore,
)
from app.modules.quality_gate.engine.slo_models import (
    SLO,
    SLOComparison,
    SLOCriteria,
    SLOObjective,
    SLOParseError,
    SLOTotalScore,
)


def _parse_pct(value: str) -> float:
    return float(str(value).strip().rstrip("%"))


def parse_slo(yaml_text: str) -> SLO:
    """Parse and validate an SLO YAML document.

    Args:
        yaml_text: Full SLO YAML content including the indicators block.

    Returns:
        Validated SLO model with defaults applied.

    Raises:
        SLOParseError: If the YAML is invalid, missing spec_version, or an
            objective references an indicator not defined in the indicators block.
    """
    try:
        data: dict[str, Any] = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError as e:
        raise SLOParseError(f"Invalid YAML: {e}") from e

    if "spec_version" not in data:
        raise SLOParseError("Missing required field: spec_version")

    indicators: dict[str, str] = {str(k): str(v) for k, v in (data.get("indicators") or {}).items()}

    raw_cmp = data.get("comparison") or {}
    comparison = SLOComparison(
        compare_with=raw_cmp.get("compare_with", CompareWith.SINGLE_RESULT),
        number_of_comparison_results=int(raw_cmp.get("number_of_comparison_results", 3)),
        include_result_with_score=raw_cmp.get(
            "include_result_with_score", IncludeResultWithScore.ALL
        ),
        aggregate_function=raw_cmp.get("aggregate_function", AggregateFunction.AVG),
        scope_tags=list(raw_cmp.get("scope_tags", ["os"])),
    )

    raw_score = data.get("total_score") or {}
    total_score = SLOTotalScore(
        pass_pct=_parse_pct(raw_score.get("pass", "90%")),
        warning_pct=_parse_pct(raw_score.get("warning", "75%")),
    )

    objectives: list[SLOObjective] = []
    for raw_obj in data.get("objectives") or []:
        sli_name = str(raw_obj.get("sli", ""))
        if sli_name not in indicators:
            raise SLOParseError(
                f"Objective references unknown indicator: {sli_name!r}. "
                f"Available: {list(indicators)}"
            )

        pass_criteria = [
            SLOCriteria(criteria=list(block.get("criteria", [])))
            for block in (raw_obj.get("pass") or [])
        ]
        warning_criteria = [
            SLOCriteria(criteria=list(block.get("criteria", [])))
            for block in (raw_obj.get("warning") or [])
        ]

        objectives.append(
            SLOObjective(
                sli=sli_name,
                display_name=str(raw_obj.get("displayName", sli_name)),
                pass_criteria=pass_criteria,
                warning_criteria=warning_criteria,
                weight=int(raw_obj.get("weight", 1)),
                key_sli=bool(raw_obj.get("key_sli", False)),
            )
        )

    return SLO(
        spec_version=str(data["spec_version"]),
        indicators=indicators,
        objectives=objectives,
        comparison=comparison,
        total_score=total_score,
    )
