"""Per-objective scoring and total score calculation."""

from __future__ import annotations

from tropek.modules.quality_gate.evaluation_engine.constants import EvaluationOutcome, IndicatorStatus
from tropek.modules.quality_gate.evaluation_engine.criteria import evaluate_criteria, parse_criteria_string
from tropek.modules.quality_gate.evaluation_engine.result_models import ObjectiveResult, TotalScore
from tropek.modules.quality_gate.evaluation_engine.slo_models import SLOObjective, SLOTotalScore


def _evaluate_criteria_block(
    criteria_list: list[str],
    value: float,
    baseline: float | None,
) -> bool:
    """Evaluate a flat criteria list with AND logic — all must pass."""
    for raw in criteria_list:
        c = parse_criteria_string(raw)
        if not evaluate_criteria(c, value, baseline):
            return False
    return True


def score_objective(
    objective: SLOObjective,
    value: float | None,
    baseline: float | None,
) -> ObjectiveResult:
    """Score a single SLO objective against a metric value and optional baseline."""
    has_pass = bool(objective.pass_threshold)

    if not has_pass:
        return ObjectiveResult(
            objective=objective,
            status=IndicatorStatus.INFO,
            score=0.0,
            contributes_to_score=False,
            key_sli_failed=False,
        )

    if value is None:
        return ObjectiveResult(
            objective=objective,
            status=IndicatorStatus.ERROR,
            score=0.0,
            contributes_to_score=True,
            key_sli_failed=objective.key_sli,
        )

    if _evaluate_criteria_block(objective.pass_threshold, value, baseline):
        return ObjectiveResult(
            objective=objective,
            status=IndicatorStatus.PASS,
            score=float(objective.weight),
            contributes_to_score=True,
            key_sli_failed=False,
        )

    if objective.warning_threshold and _evaluate_criteria_block(objective.warning_threshold, value, baseline):
        return ObjectiveResult(
            objective=objective,
            status=IndicatorStatus.WARNING,
            score=0.5 * objective.weight,
            contributes_to_score=True,
            key_sli_failed=False,
        )

    return ObjectiveResult(
        objective=objective,
        status=IndicatorStatus.FAIL,
        score=0.0,
        contributes_to_score=True,
        key_sli_failed=objective.key_sli,
    )


def calculate_total_score(
    results: list[ObjectiveResult],
    total_score: SLOTotalScore,
) -> TotalScore:
    """Calculate the overall evaluation result from individual objective scores."""
    maximum = sum(r.objective.weight for r in results if r.contributes_to_score)

    if maximum == 0:
        return TotalScore(result=EvaluationOutcome.PASS, score=100.0)

    achieved = sum(r.score for r in results)
    pct = 100.0 * achieved / maximum

    key_sli_failed = any(r.key_sli_failed for r in results)
    if key_sli_failed:
        return TotalScore(result=EvaluationOutcome.FAIL, score=pct)
    if pct >= total_score.pass_threshold:
        return TotalScore(result=EvaluationOutcome.PASS, score=pct)
    if pct >= total_score.warning_threshold:
        return TotalScore(result=EvaluationOutcome.WARNING, score=pct)
    return TotalScore(result=EvaluationOutcome.FAIL, score=pct)
