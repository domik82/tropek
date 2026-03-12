"""Top-level evaluation function — orchestrates parsing, scoring, and result assembly."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.modules.quality_gate.engine.criteria import evaluate_criteria, parse_criteria_string
from app.modules.quality_gate.engine.scoring import (
    ObjectiveResult,
    TotalScore,
    calculate_total_score,
    score_objective,
)
from app.modules.quality_gate.engine.slo_parser import SLOObjective, parse_slo


class EvaluationResult(BaseModel):
    """Result of evaluating a full SLO against a set of metric values.

    Attributes:
        result: Overall result: 'pass', 'warning', or 'fail'.
        score: Weighted score as a percentage (0.0-100.0).
        indicator_results: Per-SLI breakdown with values, targets, and violation flags.
        compared_evaluation_ids: IDs of previous evaluations used as comparison baseline.
    """

    result: str
    score: float
    indicator_results: list[dict[str, Any]] = Field(default_factory=list)
    compared_evaluation_ids: list[str] = Field(default_factory=list)


def _build_targets(
    objective: SLOObjective,
    value: float | None,
    baseline: float | None,
    is_pass: bool,
) -> list[dict[str, Any]]:
    """Build the pass or warning target list for a single objective's indicator result."""
    blocks = objective.pass_criteria if is_pass else objective.warning_criteria
    targets = []
    for block in blocks:
        for raw in block.criteria:
            c = parse_criteria_string(raw)
            target_value = c.compute_target_value(baseline)
            violated = not evaluate_criteria(c, value, baseline) if value is not None else True
            targets.append(
                {
                    "criteria": raw,
                    "target_value": target_value,
                    "violated": violated,
                }
            )
    return targets


def evaluate(
    slo_yaml: str,
    metrics: dict[str, float | None],
    baselines: dict[str, float | None],
    compared_evaluation_ids: list[str] | None = None,
) -> EvaluationResult:
    """Evaluate a set of metric values against an SLO definition.

    This is a pure function — no I/O, no database calls. Fully unit-testable
    in isolation. Ported from Keptn's lighthouse-service Go implementation.

    Args:
        slo_yaml: Full SLO YAML text including the indicators block.
        metrics: Metric name → scalar value. None means the metric was not retrieved.
        baselines: Metric name → aggregated baseline value for relative criteria.
            Values are sourced from previous passing evaluations.
        compared_evaluation_ids: IDs of the evaluations used to compute the baselines.

    Returns:
        EvaluationResult with overall result, score, and per-indicator breakdown.
    """
    slo = parse_slo(slo_yaml)
    objective_results: list[ObjectiveResult] = []
    indicator_results: list[dict[str, Any]] = []

    for obj in slo.objectives:
        value = metrics.get(obj.sli)
        baseline = baselines.get(obj.sli)
        obj_result = score_objective(obj, value, baseline)
        objective_results.append(obj_result)

        pass_targets = _build_targets(obj, value, baseline, is_pass=True)
        warning_targets = _build_targets(obj, value, baseline, is_pass=False)

        ir: dict[str, Any] = {
            "metric": obj.sli,
            "display_name": obj.display_name,
            "value": value,
            "compared_value": baseline,
            "status": obj_result.status.value,
            "score": obj_result.score,
            "weight": obj.weight,
            "key_sli": obj.key_sli,
            "pass_targets": pass_targets,
            "warning_targets": warning_targets if obj.warning_criteria else None,
            "change_absolute": (value - baseline)
            if value is not None and baseline is not None
            else None,
            "change_relative_pct": (
                ((value / baseline) - 1) * 100
                if value is not None and baseline is not None and baseline != 0
                else None
            ),
        }
        indicator_results.append(ir)

    total: TotalScore = calculate_total_score(objective_results, slo.total_score)

    return EvaluationResult(
        result=total.result,
        score=round(total.score, 2),
        indicator_results=indicator_results,
        compared_evaluation_ids=compared_evaluation_ids or [],
    )
