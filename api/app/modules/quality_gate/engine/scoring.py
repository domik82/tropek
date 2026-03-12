from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from app.modules.quality_gate.engine.criteria import evaluate_criteria, parse_criteria_string
from app.modules.quality_gate.engine.slo_parser import SLOObjective, SLOTotalScore


class IndicatorStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    INFO = "info"
    ERROR = "error"


class ObjectiveResult(BaseModel):
    objective: SLOObjective
    status: IndicatorStatus
    score: float
    contributes_to_score: bool
    key_sli_failed: bool

    model_config = {"arbitrary_types_allowed": True}


class TotalScore(BaseModel):
    result: str  # pass | warning | fail
    score: float  # 0–100


def _evaluate_criteria_block(
    criteria_list: list[str],
    value: float,
    baseline: float | None,
) -> bool:
    """AND logic: all criteria in the block must pass."""
    for raw in criteria_list:
        c = parse_criteria_string(raw)
        if not evaluate_criteria(c, value, baseline):
            return False
    return True


def _evaluate_or_blocks(
    criteria_blocks: list,
    value: float,
    baseline: float | None,
) -> bool:
    """OR logic across blocks: any single block passing means overall pass."""
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
    maximum = sum(r.objective.weight for r in results if r.contributes_to_score)

    if maximum == 0:
        # No objectives have pass criteria — informational SLO, always passes
        return TotalScore(result="pass", score=100.0)

    achieved = sum(r.score for r in results)
    pct = 100.0 * achieved / maximum

    key_sli_failed = any(r.key_sli_failed for r in results)
    if key_sli_failed:
        return TotalScore(result="fail", score=pct)
    if pct >= total_score.pass_pct:
        return TotalScore(result="pass", score=pct)
    if pct >= total_score.warning_pct:
        return TotalScore(result="warning", score=pct)
    return TotalScore(result="fail", score=pct)
