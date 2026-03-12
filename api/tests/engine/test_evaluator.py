from __future__ import annotations

import pytest
from app.modules.quality_gate.engine.evaluator import evaluate


def test_all_pass_no_baseline(slo_data) -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 0.0, "compilation_s": 45.0}
    result = evaluate(slo_data("full_evaluation.yaml"), metrics, baselines={})
    assert result.result == "pass"
    assert result.score > 0


def test_key_sli_fail_overrides_score(slo_data) -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 1.0, "compilation_s": 45.0}
    result = evaluate(slo_data("full_evaluation.yaml"), metrics, baselines={})
    assert result.result == "fail"


def test_missing_metric_fails_objective(slo_data) -> None:
    # compilation_s missing — max=6, achieved=5 (rt=2 + error=3) → 83% → fail
    metrics = {"response_time_p99": 550.0, "error_rate": 0.0}
    result = evaluate(slo_data("full_evaluation.yaml"), metrics, baselines={})
    assert result.result in ("fail", "warning")


def test_relative_criteria_with_baseline_pass(slo_data) -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 0.0, "compilation_s": 45.0}
    # AND block: ["<600", "<=+10%"] — baseline=500, target=550 → both pass
    result = evaluate(
        slo_data("full_evaluation.yaml"),
        metrics,
        baselines={"response_time_p99": 500.0},
    )
    rt = next(r for r in result.indicator_results if r["metric"] == "response_time_p99")
    assert rt["status"] == "pass"


def test_relative_criteria_exceeded_falls_to_warning(slo_data) -> None:
    metrics = {"response_time_p99": 700.0, "error_rate": 0.0, "compilation_s": 45.0}
    # baseline=550, +10%=605 → 700 fails pass; warning <800 → passes
    result = evaluate(
        slo_data("full_evaluation.yaml"),
        metrics,
        baselines={"response_time_p99": 550.0},
    )
    rt = next(r for r in result.indicator_results if r["metric"] == "response_time_p99")
    assert rt["status"] == "warning"


def test_indicator_results_count(slo_data) -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 0.0, "compilation_s": 45.0}
    result = evaluate(slo_data("full_evaluation.yaml"), metrics, baselines={})
    assert len(result.indicator_results) == 3


def test_indicator_results_contain_all_metrics(slo_data) -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 0.0, "compilation_s": 45.0}
    result = evaluate(slo_data("full_evaluation.yaml"), metrics, baselines={})
    names = {r["metric"] for r in result.indicator_results}
    assert names == {"response_time_p99", "error_rate", "compilation_s"}


def test_change_relative_pct_computed(slo_data) -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 0.0, "compilation_s": 45.0}
    result = evaluate(
        slo_data("full_evaluation.yaml"),
        metrics,
        baselines={"response_time_p99": 500.0},
    )
    rt = next(r for r in result.indicator_results if r["metric"] == "response_time_p99")
    assert rt["change_relative_pct"] == pytest.approx(10.0)
    assert rt["change_absolute"] == pytest.approx(50.0)


def test_compared_evaluation_ids_stored(slo_data) -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 0.0, "compilation_s": 45.0}
    result = evaluate(
        slo_data("full_evaluation.yaml"),
        metrics,
        baselines={},
        compared_evaluation_ids=["id1", "id2"],
    )
    assert result.compared_evaluation_ids == ["id1", "id2"]


def test_pass_targets_included(slo_data) -> None:
    metrics = {"response_time_p99": 550.0, "error_rate": 0.0, "compilation_s": 45.0}
    result = evaluate(
        slo_data("full_evaluation.yaml"),
        metrics,
        baselines={"response_time_p99": 500.0},
    )
    rt = next(r for r in result.indicator_results if r["metric"] == "response_time_p99")
    criteria_strs = [t["criteria"] for t in rt["pass_targets"]]
    assert "<600" in criteria_strs
    assert "<=+10%" in criteria_strs
