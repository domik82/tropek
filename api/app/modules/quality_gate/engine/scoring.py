"""Per-objective scoring and total score calculation."""

from __future__ import annotations

from app.modules.quality_gate.engine.constants import EvaluationOutcome, IndicatorStatus
from app.modules.quality_gate.engine.criteria import evaluate_criteria, parse_criteria_string
from app.modules.quality_gate.engine.result_models import ObjectiveResult, TotalScore
from app.modules.quality_gate.engine.slo_models import SLOCriteria, SLOObjective, SLOTotalScore


def _evaluate_criteria_block(
    criteria_list: list[str],
    value: float,
    baseline: float | None,
) -> bool:
    """Evaluate a single criteria block with AND logic — all must pass."""
    for raw in criteria_list:
        c = parse_criteria_string(raw)
        if not evaluate_criteria(c, value, baseline):
            return False
    return True


def _evaluate_or_blocks(
    criteria_blocks: list[SLOCriteria],
    value: float,
    baseline: float | None,
) -> bool:
    """Evaluate multiple criteria blocks with OR logic — any one passing is sufficient."""
    if not criteria_blocks:
        return False
    return any(
        _evaluate_criteria_block(block.criteria, value, baseline) for block in criteria_blocks
    )


def score_objective(
    objective: SLOObjective,
    value: float | None,
    baseline: float | None,
) -> ObjectiveResult:
    """Score a single SLO objective against a metric value and optional baseline.

    Args:
        objective: The SLO objective containing criteria and weight.
        value: Current metric value. None means the metric was not retrieved.
        baseline: Aggregated value from previous evaluations for relative criteria.

    Returns:
        ObjectiveResult with status, score contribution, and key_sli_failed flag.
    """
    # Bug 2231 parity: pass: [] (empty list) treated same as no pass criteria.
    has_pass = bool(objective.pass_criteria) and any(
        block.criteria for block in objective.pass_criteria
    )

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
            status=IndicatorStatus.FAIL,
            score=0.0,
            contributes_to_score=True,
            key_sli_failed=objective.key_sli,
        )

    if _evaluate_or_blocks(objective.pass_criteria, value, baseline):
        return ObjectiveResult(
            objective=objective,
            status=IndicatorStatus.PASS,
            score=float(objective.weight),
            contributes_to_score=True,
            key_sli_failed=False,
        )

    if _evaluate_or_blocks(objective.warning_criteria, value, baseline):
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
    """Calculate the overall evaluation result from individual objective scores.

    A key_sli failure immediately forces 'fail' regardless of the total percentage.
    If no objectives have pass criteria (maximum achievable score is zero),
    returns pass at 100% — matches Keptn lighthouse-service behaviour.

    Args:
        results: Scored results for every objective in the SLO.
        total_score: Pass and warning percentage thresholds.

    Returns:
        TotalScore with the overall result string and achieved percentage.
    """
    maximum = sum(r.objective.weight for r in results if r.contributes_to_score)

    if maximum == 0:
        return TotalScore(result=EvaluationOutcome.PASS, score=100.0)

    achieved = sum(r.score for r in results)
    pct = 100.0 * achieved / maximum

    key_sli_failed = any(r.key_sli_failed for r in results)
    if key_sli_failed:
        return TotalScore(result=EvaluationOutcome.FAIL, score=pct)
    if pct >= total_score.pass_pct:
        return TotalScore(result=EvaluationOutcome.PASS, score=pct)
    if pct >= total_score.warning_pct:
        return TotalScore(result=EvaluationOutcome.WARNING, score=pct)
    return TotalScore(result=EvaluationOutcome.FAIL, score=pct)
