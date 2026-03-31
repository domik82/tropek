"""Tests for SLO objectives with missing criteria: info-only, warning-only, no criteria."""

from __future__ import annotations

from app.modules.quality_gate.engine.constants import EvaluationOutcome, IndicatorStatus
from app.modules.quality_gate.engine.evaluator import evaluate
from app.modules.quality_gate.engine.scoring import calculate_total_score, score_objective
from app.modules.quality_gate.engine.slo_models import (
    SLO,
    SLOComparison,
    SLOObjective,
    SLOTotalScore,
)


def _make_slo(objectives: list[SLOObjective]) -> SLO:
    return SLO(
        objectives=objectives,
        comparison=SLOComparison(),
        total_score=SLOTotalScore(pass_threshold=90.0, warning_threshold=75.0),
    )


def _get_indicator(result: object, metric_name: str) -> dict:
    """Get an indicator result by metric name, handling both dict and object forms."""
    for ir in result.indicator_results:  # type: ignore[attr-defined]
        name = ir.metric if hasattr(ir, 'metric') else ir['metric']
        if name == metric_name:
            return ir
    msg = f'no indicator with metric={metric_name!r}'
    raise ValueError(msg)


def _status(ir: object) -> str:
    """Get status from an indicator result (dict or IndicatorResult object)."""
    return ir.status if hasattr(ir, 'status') else ir['status']  # type: ignore[union-attr]


# --- score_objective with no pass_threshold ---


def test_objective_with_only_warning_threshold_returns_info() -> None:
    """Objective with warning_threshold but no pass_threshold returns INFO status."""
    obj = SLOObjective(
        sli='cpu',
        display_name='CPU',
        pass_threshold=[],
        warning_threshold=['<90'],
        weight=1,
    )
    result = score_objective(obj, value=50.0, baseline=None)
    assert result.status == IndicatorStatus.INFO
    assert result.score == 0.0
    assert result.contributes_to_score is False


def test_objective_with_no_criteria_returns_info() -> None:
    """Objective with neither pass nor warning criteria is informational only."""
    obj = SLOObjective(
        sli='cpu',
        display_name='CPU',
        pass_threshold=[],
        warning_threshold=[],
        weight=1,
    )
    result = score_objective(obj, value=50.0, baseline=None)
    assert result.status == IndicatorStatus.INFO
    assert result.contributes_to_score is False


def test_objective_with_no_criteria_none_value() -> None:
    """INFO objective with None value still returns INFO (not FAIL)."""
    obj = SLOObjective(
        sli='cpu',
        display_name='CPU',
        pass_threshold=[],
        warning_threshold=[],
        weight=1,
    )
    result = score_objective(obj, value=None, baseline=None)
    assert result.status == IndicatorStatus.INFO


# --- calculate_total_score with all INFO ---


def test_all_info_objectives_result_is_pass() -> None:
    """When all objectives are INFO, maximum is 0 and result is PASS with 100% score."""
    obj1 = SLOObjective(sli='a', pass_threshold=[], weight=1)
    obj2 = SLOObjective(sli='b', pass_threshold=[], weight=2)

    results = [
        score_objective(obj1, value=10.0, baseline=None),
        score_objective(obj2, value=20.0, baseline=None),
    ]
    total = calculate_total_score(results, SLOTotalScore(pass_threshold=90.0, warning_threshold=75.0))
    assert total.result == EvaluationOutcome.PASS
    assert total.score == 100.0


# --- Full evaluate() with mixed info and scored ---


def test_evaluate_mixed_info_and_scored() -> None:
    """Mix of info-only and scored objectives: only scored contribute to final score."""
    slo = _make_slo(
        [
            SLOObjective(sli='cpu', display_name='CPU', pass_threshold=['<90'], weight=1),
            SLOObjective(sli='mem', display_name='Memory', pass_threshold=[], weight=1),
        ]
    )
    metrics = {'cpu': 50.0, 'mem': 80.0}
    result = evaluate(slo, metrics, baselines={})
    # cpu passes (weight 1), mem is info (does not contribute)
    # maximum = 1 (only cpu), achieved = 1 -> 100%
    assert result.result == EvaluationOutcome.PASS
    assert result.score == 100.0

    # Check individual indicators
    assert len(result.indicator_results) == 2
    cpu_ir = _get_indicator(result, 'cpu')
    mem_ir = _get_indicator(result, 'mem')
    assert _status(cpu_ir) == 'pass'
    assert _status(mem_ir) == 'info'


def test_evaluate_all_info_objectives() -> None:
    """All objectives are info-only: result should be pass."""
    slo = _make_slo(
        [
            SLOObjective(sli='a', display_name='A', pass_threshold=[], weight=1),
            SLOObjective(sli='b', display_name='B', pass_threshold=[], weight=2),
        ]
    )
    metrics = {'a': 10.0, 'b': 20.0}
    result = evaluate(slo, metrics, baselines={})
    assert result.result == EvaluationOutcome.PASS
    assert result.score == 100.0
