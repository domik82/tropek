"""Tests for evaluation failure scenarios: all/some metrics None, key_sli failures."""

from __future__ import annotations

from app.modules.quality_gate.engine.constants import EvaluationOutcome
from app.modules.quality_gate.engine.evaluator import evaluate
from app.modules.quality_gate.engine.result_models import EvaluationResult
from app.modules.quality_gate.engine.slo_models import (
    SLO,
    SLOComparison,
    SLOObjective,
    SLOTotalScore,
)

# Force Pydantic to fully resolve forward references.
EvaluationResult.model_rebuild()


def _make_slo(objectives: list[SLOObjective]) -> SLO:
    return SLO(
        objectives=objectives,
        comparison=SLOComparison(),
        total_score=SLOTotalScore(pass_threshold=90.0, warning_threshold=75.0),
    )


def _ir_attr(ir: object, attr: str) -> object:
    """Access an indicator result attribute (handles both dict and IndicatorResult)."""
    return getattr(ir, attr) if hasattr(ir, attr) else ir[attr]  # type: ignore[index]


def test_all_metrics_return_none() -> None:
    """When all SLI queries return None (adapter error), result should be fail."""
    slo = _make_slo(
        [
            SLOObjective(sli='response_time', display_name='RT', pass_threshold=['<600'], weight=1),
            SLOObjective(sli='error_rate', display_name='Err', pass_threshold=['<1'], weight=1),
        ]
    )
    metrics: dict[str, float | None] = {'response_time': None, 'error_rate': None}
    result = evaluate(slo, metrics, baselines={})
    assert result.result == EvaluationOutcome.FAIL
    assert result.score == 0.0


def test_some_metrics_return_none() -> None:
    """When some metrics succeed and some fail, score is based on available ones."""
    slo = _make_slo(
        [
            SLOObjective(sli='response_time', display_name='RT', pass_threshold=['<600'], weight=1),
            SLOObjective(sli='error_rate', display_name='Err', pass_threshold=['<1'], weight=1),
        ]
    )
    metrics: dict[str, float | None] = {'response_time': 500.0, 'error_rate': None}
    result = evaluate(slo, metrics, baselines={})
    # response_time passes (1 out of 2 weight), error_rate fails -> score = 50%
    assert result.score == 50.0
    assert result.result == EvaluationOutcome.FAIL  # 50 < 75 (warning threshold)


def test_key_sli_fails_means_overall_fail() -> None:
    """If a key_sli objective fails, overall result is fail regardless of score."""
    slo = _make_slo(
        [
            SLOObjective(
                sli='response_time',
                display_name='RT',
                pass_threshold=['<600'],
                weight=1,
                key_sli=False,
            ),
            SLOObjective(
                sli='error_rate',
                display_name='Err',
                pass_threshold=['<1'],
                weight=1,
                key_sli=True,
            ),
        ]
    )
    # response_time passes, error_rate fails (key_sli)
    metrics: dict[str, float | None] = {'response_time': 500.0, 'error_rate': 5.0}
    result = evaluate(slo, metrics, baselines={})
    assert result.result == EvaluationOutcome.FAIL
    # Score is 50% (only response_time passes), but key_sli vetoes
    assert result.score == 50.0


def test_key_sli_none_value_fails_overall() -> None:
    """key_sli with None metric value should fail the overall evaluation."""
    slo = _make_slo(
        [
            SLOObjective(
                sli='response_time',
                display_name='RT',
                pass_threshold=['<600'],
                weight=1,
                key_sli=False,
            ),
            SLOObjective(
                sli='error_rate',
                display_name='Err',
                pass_threshold=['<1'],
                weight=1,
                key_sli=True,
            ),
        ]
    )
    metrics: dict[str, float | None] = {'response_time': 500.0, 'error_rate': None}
    result = evaluate(slo, metrics, baselines={})
    assert result.result == EvaluationOutcome.FAIL


def test_all_passing_with_baselines() -> None:
    """All metrics pass with relative criteria and baselines."""
    slo = _make_slo(
        [
            SLOObjective(
                sli='response_time',
                display_name='RT',
                pass_threshold=['<600', '<=+10%'],
                weight=2,
            ),
            SLOObjective(sli='error_rate', display_name='Err', pass_threshold=['<1'], weight=1),
        ]
    )
    metrics: dict[str, float | None] = {'response_time': 500.0, 'error_rate': 0.0}
    baselines: dict[str, float | None] = {'response_time': 480.0}
    result = evaluate(slo, metrics, baselines)
    assert result.result == EvaluationOutcome.PASS
    assert result.score == 100.0


def test_missing_metric_key_not_in_dict() -> None:
    """Metric not present in dict at all (not even as None) should be treated as None."""
    slo = _make_slo(
        [
            SLOObjective(sli='response_time', display_name='RT', pass_threshold=['<600'], weight=1),
            SLOObjective(sli='error_rate', display_name='Err', pass_threshold=['<1'], weight=1),
        ]
    )
    # error_rate not in metrics dict at all
    metrics: dict[str, float | None] = {'response_time': 500.0}
    result = evaluate(slo, metrics, baselines={})
    # error_rate missing -> None -> fails -> 50%
    assert result.score == 50.0
