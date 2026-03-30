from __future__ import annotations

from collections.abc import Callable

import pytest
from app.modules.quality_gate.engine.scoring import (
    IndicatorStatus,
    ObjectiveResult,
    calculate_total_score,
    score_objective,
)
from app.modules.quality_gate.engine.slo_models import SLO
from app.modules.quality_gate.engine.slo_parser import build_slo


# All criteria use AND logic — OR-block semantics were deliberately removed
def _slo(slo_fixture: Callable[[str], SLO]) -> SLO:
    return slo_fixture('multi_objective_weighted.yaml')


# --- score_objective ---


def test_objective_passes(slo_fixture) -> None:
    result = score_objective(_slo(slo_fixture).objectives[0], value=80.0, baseline=None)
    assert result.status == IndicatorStatus.PASS
    assert result.score == 2.0


def test_objective_warns(slo_fixture) -> None:
    result = score_objective(_slo(slo_fixture).objectives[0], value=150.0, baseline=None)
    assert result.status == IndicatorStatus.WARNING
    assert result.score == 1.0  # 0.5 * weight(2)


def test_objective_fails(slo_fixture) -> None:
    result = score_objective(_slo(slo_fixture).objectives[0], value=250.0, baseline=None)
    assert result.status == IndicatorStatus.FAIL
    assert result.score == 0.0


def test_objective_missing_metric_fails(slo_fixture) -> None:
    result = score_objective(_slo(slo_fixture).objectives[0], value=None, baseline=None)
    assert result.status == IndicatorStatus.FAIL
    assert result.score == 0.0


def test_objective_no_pass_threshold_is_informational(slo_fixture) -> None:
    result = score_objective(_slo(slo_fixture).objectives[2], value=999.0, baseline=None)
    assert result.status == IndicatorStatus.INFO
    assert result.score == 0.0
    assert result.contributes_to_score is False


def test_key_sli_failure_flagged(slo_fixture) -> None:
    result = score_objective(_slo(slo_fixture).objectives[1], value=999.0, baseline=None)
    assert result.status == IndicatorStatus.FAIL
    assert result.key_sli_failed is True


def test_key_sli_pass_not_flagged(slo_fixture) -> None:
    result = score_objective(_slo(slo_fixture).objectives[1], value=10.0, baseline=None)
    assert result.key_sli_failed is False


def test_empty_pass_threshold_list_is_informational() -> None:
    """Empty pass_threshold list must be treated same as no pass criteria."""
    slo = build_slo(objectives=[{'sli': 'm', 'pass_threshold': [], 'weight': 1}])
    result = score_objective(slo.objectives[0], value=50.0, baseline=None)
    assert result.status == IndicatorStatus.INFO
    assert result.contributes_to_score is False
    assert result.score == 0.0


def test_sign_without_pct_relative_scoring() -> None:
    """<=+10 without % treated as relative (baseline + 10), matching Go behaviour."""
    slo = build_slo(objectives=[{'sli': 'm', 'pass_threshold': ['<=+10'], 'weight': 1}])
    assert score_objective(slo.objectives[0], value=105.0, baseline=100.0).status == IndicatorStatus.PASS
    assert score_objective(slo.objectives[0], value=115.0, baseline=100.0).status == IndicatorStatus.FAIL


# --- calculate_total_score ---


def _make_result(objective, status, score, contributes, key_sli_failed):
    """Helper: construct ObjectiveResult with keyword args (Pydantic requirement)."""
    return ObjectiveResult(
        objective=objective,
        status=status,
        score=score,
        contributes_to_score=contributes,
        key_sli_failed=key_sli_failed,
    )


def test_total_score_all_pass(slo_fixture) -> None:
    slo = _slo(slo_fixture)
    results = [
        _make_result(slo.objectives[0], IndicatorStatus.PASS, 2.0, True, False),
        _make_result(slo.objectives[1], IndicatorStatus.PASS, 1.0, True, False),
        _make_result(slo.objectives[2], IndicatorStatus.INFO, 0.0, False, False),
    ]
    total = calculate_total_score(results, slo.total_score)
    assert total.result == 'pass'
    assert total.score == pytest.approx(100.0)


def test_total_score_key_sli_fails_regardless_of_score(slo_fixture) -> None:
    slo = _slo(slo_fixture)
    results = [
        _make_result(slo.objectives[0], IndicatorStatus.PASS, 2.0, True, False),
        _make_result(slo.objectives[1], IndicatorStatus.FAIL, 0.0, True, True),
        _make_result(slo.objectives[2], IndicatorStatus.INFO, 0.0, False, False),
    ]
    total = calculate_total_score(results, slo.total_score)
    assert total.result == 'fail'


def test_total_score_no_pass_threshold_returns_pass_100() -> None:
    slo = build_slo(objectives=[{'sli': 'm', 'weight': 1}])
    results = [_make_result(slo.objectives[0], IndicatorStatus.INFO, 0.0, False, False)]
    total = calculate_total_score(results, slo.total_score)
    assert total.result == 'pass'
    assert total.score == 100.0


def test_total_score_warning_band(slo_fixture) -> None:
    slo = _slo(slo_fixture)
    # achieved=1 of max=3 → 33% → below 75% → fail
    results = [
        _make_result(slo.objectives[0], IndicatorStatus.FAIL, 0.0, True, False),
        _make_result(slo.objectives[1], IndicatorStatus.PASS, 1.0, True, False),
        _make_result(slo.objectives[2], IndicatorStatus.INFO, 0.0, False, False),
    ]
    total = calculate_total_score(results, slo.total_score)
    assert total.result == 'fail'


def test_total_score_warning_result() -> None:
    slo = build_slo(
        objectives=[
            {'sli': 'm1', 'pass_threshold': ['<100'], 'weight': 1},
            {'sli': 'm2', 'pass_threshold': ['<100'], 'weight': 1},
        ],
        total_score_pass_threshold=100.0,
        total_score_warning_threshold=50.0,
    )
    results = [
        _make_result(slo.objectives[0], IndicatorStatus.PASS, 1.0, True, False),
        _make_result(slo.objectives[1], IndicatorStatus.FAIL, 0.0, True, False),
    ]
    total = calculate_total_score(results, slo.total_score)
    assert total.result == 'warning'
    assert total.score == pytest.approx(50.0)
