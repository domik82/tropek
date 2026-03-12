from __future__ import annotations

import pytest
from app.modules.quality_gate.engine.slo_parser import parse_slo
from app.modules.quality_gate.engine.scoring import (
    IndicatorStatus,
    ObjectiveResult,
    calculate_total_score,
    score_objective,
)

SIMPLE_SLO = """
spec_version: '1.0'
indicators:
  m1: 'q()'
  m2: 'q()'
  m3: 'q()'
objectives:
  - sli: m1
    pass:
      - criteria: ["<100"]
    warning:
      - criteria: ["<200"]
    weight: 2
    key_sli: false
  - sli: m2
    pass:
      - criteria: ["<50"]
    weight: 1
    key_sli: true
  - sli: m3
    displayName: Info only
    weight: 1
total_score:
  pass: "90%"
  warning: "75%"
"""


def _slo():
    return parse_slo(SIMPLE_SLO)


# --- score_objective ---

def test_objective_passes() -> None:
    result = score_objective(_slo().objectives[0], value=80.0, baseline=None)
    assert result.status == IndicatorStatus.PASS
    assert result.score == 2.0


def test_objective_warns() -> None:
    result = score_objective(_slo().objectives[0], value=150.0, baseline=None)
    assert result.status == IndicatorStatus.WARNING
    assert result.score == 1.0  # 0.5 * weight(2)


def test_objective_fails() -> None:
    result = score_objective(_slo().objectives[0], value=250.0, baseline=None)
    assert result.status == IndicatorStatus.FAIL
    assert result.score == 0.0


def test_objective_missing_metric_fails() -> None:
    result = score_objective(_slo().objectives[0], value=None, baseline=None)
    assert result.status == IndicatorStatus.FAIL
    assert result.score == 0.0


def test_objective_no_pass_criteria_is_informational() -> None:
    result = score_objective(_slo().objectives[2], value=999.0, baseline=None)
    assert result.status == IndicatorStatus.INFO
    assert result.score == 0.0
    assert result.contributes_to_score is False


def test_or_criteria_second_block_passes() -> None:
    slo = parse_slo("""
spec_version: '1.0'
indicators:
  m: 'q()'
objectives:
  - sli: m
    pass:
      - criteria: ["<50", "<30"]
      - criteria: ["<200"]
    weight: 1
total_score:
  pass: "90%"
  warning: "75%"
""")
    # First block fails (<50 AND <30 with value=100), second block passes (<200)
    result = score_objective(slo.objectives[0], value=100.0, baseline=None)
    assert result.status == IndicatorStatus.PASS


def test_key_sli_failure_flagged() -> None:
    result = score_objective(_slo().objectives[1], value=999.0, baseline=None)
    assert result.status == IndicatorStatus.FAIL
    assert result.key_sli_failed is True


def test_key_sli_pass_not_flagged() -> None:
    result = score_objective(_slo().objectives[1], value=10.0, baseline=None)
    assert result.key_sli_failed is False


def test_empty_pass_criteria_list_is_informational() -> None:
    """Bug 2231: pass: [] (empty list) must be treated same as no pass criteria."""
    slo = parse_slo("""
spec_version: '1.0'
indicators:
  m: 'q()'
objectives:
  - sli: m
    pass: []
    weight: 1
total_score:
  pass: "90%"
  warning: "75%"
""")
    result = score_objective(slo.objectives[0], value=50.0, baseline=None)
    assert result.status == IndicatorStatus.INFO
    assert result.contributes_to_score is False
    assert result.score == 0.0


def test_sign_without_pct_relative_scoring() -> None:
    """<=+10 without % sign should be treated as relative (baseline + 10)."""
    slo = parse_slo("""
spec_version: '1.0'
indicators:
  m: 'q()'
objectives:
  - sli: m
    pass:
      - criteria: ["<=+10"]
    weight: 1
total_score:
  pass: "90%"
  warning: "75%"
""")
    # baseline=100, target=110, value=105 → pass
    result = score_objective(slo.objectives[0], value=105.0, baseline=100.0)
    assert result.status == IndicatorStatus.PASS

    # baseline=100, target=110, value=115 → fail
    result2 = score_objective(slo.objectives[0], value=115.0, baseline=100.0)
    assert result2.status == IndicatorStatus.FAIL


# --- calculate_total_score ---

def test_total_score_all_pass() -> None:
    slo = _slo()
    results = [
        ObjectiveResult(slo.objectives[0], IndicatorStatus.PASS, 2.0, True, False),
        ObjectiveResult(slo.objectives[1], IndicatorStatus.PASS, 1.0, True, False),
        ObjectiveResult(slo.objectives[2], IndicatorStatus.INFO, 0.0, False, False),
    ]
    total = calculate_total_score(results, slo.total_score)
    assert total.result == "pass"
    assert total.score == pytest.approx(100.0)


def test_total_score_key_sli_fails_regardless_of_score() -> None:
    slo = _slo()
    results = [
        ObjectiveResult(slo.objectives[0], IndicatorStatus.PASS, 2.0, True, False),
        ObjectiveResult(slo.objectives[1], IndicatorStatus.FAIL, 0.0, True, True),
        ObjectiveResult(slo.objectives[2], IndicatorStatus.INFO, 0.0, False, False),
    ]
    total = calculate_total_score(results, slo.total_score)
    assert total.result == "fail"


def test_total_score_no_pass_criteria_returns_pass_100() -> None:
    slo = parse_slo("""
spec_version: '1.0'
indicators:
  m: 'q()'
objectives:
  - sli: m
    weight: 1
total_score:
  pass: "90%"
  warning: "75%"
""")
    results = [ObjectiveResult(slo.objectives[0], IndicatorStatus.INFO, 0.0, False, False)]
    total = calculate_total_score(results, slo.total_score)
    assert total.result == "pass"
    assert total.score == 100.0


def test_total_score_warning_band() -> None:
    slo = _slo()
    # achieved=1 of max=3 → 33% → below 75% warning → fail
    results = [
        ObjectiveResult(slo.objectives[0], IndicatorStatus.FAIL, 0.0, True, False),
        ObjectiveResult(slo.objectives[1], IndicatorStatus.PASS, 1.0, True, False),
        ObjectiveResult(slo.objectives[2], IndicatorStatus.INFO, 0.0, False, False),
    ]
    total = calculate_total_score(results, slo.total_score)
    assert total.result == "fail"


def test_total_score_warning_result() -> None:
    slo = parse_slo("""
spec_version: '1.0'
indicators:
  m1: 'q()'
  m2: 'q()'
objectives:
  - sli: m1
    pass:
      - criteria: ["<100"]
    weight: 1
  - sli: m2
    pass:
      - criteria: ["<100"]
    weight: 1
total_score:
  pass: "100%"
  warning: "50%"
""")
    results = [
        ObjectiveResult(slo.objectives[0], IndicatorStatus.PASS, 1.0, True, False),
        ObjectiveResult(slo.objectives[1], IndicatorStatus.FAIL, 0.0, True, False),
    ]
    total = calculate_total_score(results, slo.total_score)
    assert total.result == "warning"
    assert total.score == pytest.approx(50.0)
