"""Top-level evaluation function — orchestrates scoring and result assembly."""

from __future__ import annotations

from tropek.modules.quality_gate.evaluation_engine.criteria import evaluate_criteria, parse_criteria_string
from tropek.modules.quality_gate.evaluation_engine.result_models import (
    CriteriaTarget,
    EvaluationResult,
    IndicatorResult,
    ObjectiveResult,
    TotalScore,
)
from tropek.modules.quality_gate.evaluation_engine.scoring import calculate_total_score, score_objective
from tropek.modules.quality_gate.evaluation_engine.slo_models import SLO, SLOObjective


def _build_targets(
    objective: SLOObjective,
    value: float | None,
    baseline: float | None,
    *,
    is_pass: bool,
) -> list[CriteriaTarget]:
    """Build the pass or warning target list for a single objective."""
    criteria_list = objective.pass_threshold if is_pass else objective.warning_threshold
    targets: list[CriteriaTarget] = []
    for raw in criteria_list:
        c = parse_criteria_string(raw)
        target_value = c.compute_target_value(baseline)
        violated = not evaluate_criteria(c, value, baseline) if value is not None else True
        targets.append(
            CriteriaTarget(
                criteria=raw,
                target_value=target_value,
                violated=violated,
            )
        )
    return targets


def evaluate(
    slo: SLO,
    metrics: dict[str, float | None],
    baselines: dict[str, float | None],
    compared_evaluation_ids: list[str] | None = None,
) -> EvaluationResult:
    """Evaluate a set of metric values against an SLO definition.

    Pure function — no I/O, no database calls. Fully unit-testable in isolation.

    Args:
        slo: Validated SLO model containing objectives, comparison, and score thresholds.
        metrics: Metric name -> scalar value. None means not retrieved.
        baselines: Metric name -> aggregated baseline for relative criteria.
        compared_evaluation_ids: IDs of evaluations used for baseline computation.

    Returns:
        EvaluationResult with overall result, score, and per-indicator breakdown.
    """
    objective_results: list[ObjectiveResult] = []
    indicator_results: list[IndicatorResult] = []

    for obj in slo.objectives:
        value = metrics.get(obj.sli)
        baseline = baselines.get(obj.sli)
        obj_result = score_objective(obj, value, baseline)
        objective_results.append(obj_result)

        pass_targets = _build_targets(obj, value, baseline, is_pass=True)
        warning_targets = _build_targets(obj, value, baseline, is_pass=False)

        ir = IndicatorResult(
            metric=obj.sli,
            display_name=obj.display_name,
            value=value,
            compared_value=baseline,
            status=obj_result.status.value,
            score=obj_result.score,
            weight=obj.weight,
            key_sli=obj.key_sli,
            pass_targets=pass_targets,
            warning_targets=warning_targets if obj.warning_threshold else None,
            change_absolute=((value - baseline) if value is not None and baseline is not None else None),
            change_relative_pct=(
                ((value / baseline) - 1) * 100 if value is not None and baseline is not None and baseline != 0 else None
            ),
        )
        indicator_results.append(ir)

    total: TotalScore = calculate_total_score(objective_results, slo.total_score)

    return EvaluationResult(
        result=total.result,
        score=round(total.score, 2),
        indicator_results=indicator_results,
        compared_evaluation_ids=compared_evaluation_ids or [],
    )
