from __future__ import annotations

import pytest
from app.modules.quality_gate.engine.evaluator import EvaluationResult, evaluate

SLO_YAML = """
spec_version: '1.0'
comparison:
  compare_with: several_results
  number_of_comparison_results: 3
  include_result_with_score: pass_or_warn
  aggregate_function: avg
  scope_tags: [os]
indicators:
  response_time_p99: 'query()'
  error_rate: 'query()'
  compilation_s: 'query()'
objectives:
  - sli: response_time_p99
    pass:
      - criteria: ["<600", "<=+10%"]
    warning:
      - criteria: ["<800"]
    weight: 2
    key_sli: false
  - sli: error_rate
    pass:
      - criteria: ["=0"]
    weight: 3
    key_sli: true
  - sli: compilation_s
    pass:
      - criteria: ["<=+5%"]
    weight: 1
total_score:
  pass: "90%"
  warning: "75%"
"""


def test_all_pass_no_baseline() -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 0.0, "compilation_s": 45.0}
    result = evaluate(SLO_YAML, metrics, baselines={})
    assert result.result == "pass"
    assert result.score > 0


def test_key_sli_fail_overrides_score() -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 1.0, "compilation_s": 45.0}
    result = evaluate(SLO_YAML, metrics, baselines={})
    assert result.result == "fail"


def test_missing_metric_fails_objective() -> None:
    # compilation_s missing — fails that objective (weight=1), rest pass
    # max=6, achieved=5 (2+3) → 83% → below 90% → fail
    metrics = {"response_time_p99": 550.0, "error_rate": 0.0}
    result = evaluate(SLO_YAML, metrics, baselines={})
    assert result.result in ("fail", "warning")


def test_relative_criteria_with_baseline_pass() -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 0.0, "compilation_s": 45.0}
    # pass criteria AND block: ["<600", "<=+10%"]
    # <600: 550 < 600 → True
    # <=+10%: baseline=500, target=550, 550 <= 550 → True
    # both pass → status=pass
    result = evaluate(SLO_YAML, metrics, baselines={"response_time_p99": 500.0})
    rt = next(r for r in result.indicator_results if r["metric"] == "response_time_p99")
    assert rt["status"] == "pass"


def test_relative_criteria_exceeded_falls_to_warning() -> None:
    metrics = {"response_time_p99": 700.0, "error_rate": 0.0, "compilation_s": 45.0}
    # baseline=550, +10%=605 → 700 fails pass, but <800 → warning
    result = evaluate(SLO_YAML, metrics, baselines={"response_time_p99": 550.0})
    rt = next(r for r in result.indicator_results if r["metric"] == "response_time_p99")
    assert rt["status"] == "warning"


def test_indicator_results_count() -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 0.0, "compilation_s": 45.0}
    result = evaluate(SLO_YAML, metrics, baselines={})
    assert len(result.indicator_results) == 3


def test_indicator_results_contain_all_metrics() -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 0.0, "compilation_s": 45.0}
    result = evaluate(SLO_YAML, metrics, baselines={})
    names = {r["metric"] for r in result.indicator_results}
    assert names == {"response_time_p99", "error_rate", "compilation_s"}


def test_change_relative_pct_computed() -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 0.0, "compilation_s": 45.0}
    result = evaluate(
        SLO_YAML, metrics,
        baselines={"response_time_p99": 500.0},
    )
    rt = next(r for r in result.indicator_results if r["metric"] == "response_time_p99")
    assert rt["change_relative_pct"] == pytest.approx(10.0)
    assert rt["change_absolute"] == pytest.approx(50.0)


def test_compared_evaluation_ids_stored() -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 0.0, "compilation_s": 45.0}
    result = evaluate(SLO_YAML, metrics, baselines={}, compared_evaluation_ids=["id1", "id2"])
    assert result.compared_evaluation_ids == ["id1", "id2"]


def test_pass_targets_included() -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 0.0, "compilation_s": 45.0}
    result = evaluate(SLO_YAML, metrics, baselines={"response_time_p99": 500.0})
    rt = next(r for r in result.indicator_results if r["metric"] == "response_time_p99")
    criteria_strs = [t["criteria"] for t in rt["pass_targets"]]
    assert "<600" in criteria_strs
    assert "<=+10%" in criteria_strs
