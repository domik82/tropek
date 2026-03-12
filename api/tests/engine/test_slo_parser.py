from __future__ import annotations

import pytest
from app.modules.quality_gate.engine.slo_parser import SLOParseError, parse_slo
from pydantic import ValidationError


def test_parse_minimal_slo(slo_data) -> None:
    slo = parse_slo(slo_data("minimal.yaml"))
    assert slo.spec_version == "1.0"
    assert len(slo.objectives) == 1
    assert slo.objectives[0].sli == "response_time_p99"
    assert slo.objectives[0].weight == 1
    assert slo.objectives[0].key_sli is False
    assert slo.total_score.pass_pct == 90.0
    assert slo.total_score.warning_pct == 75.0


def test_parse_indicators_block(slo_data) -> None:
    slo = parse_slo(slo_data("minimal.yaml"))
    assert "response_time_p99" in slo.indicators
    assert slo.indicators["response_time_p99"] == "avg_over_time(http_duration_seconds[5m])"


def test_parse_comparison_defaults(slo_data) -> None:
    """A minimal SLO without a comparison block gets sensible defaults."""
    slo = parse_slo(slo_data("minimal.yaml"))
    assert slo.comparison.compare_with == "single_result"
    assert slo.comparison.number_of_comparison_results == 3
    assert slo.comparison.include_result_with_score == "all"
    assert slo.comparison.aggregate_function == "avg"
    assert slo.comparison.scope_tags == ["os"]


def test_parse_relative_slo_comparison(slo_data) -> None:
    slo = parse_slo(slo_data("relative_comparison.yaml"))
    assert slo.comparison.compare_with == "several_results"
    assert slo.comparison.scope_tags == ["os", "arch"]


def test_parse_key_sli(slo_data) -> None:
    slo = parse_slo(slo_data("relative_comparison.yaml"))
    assert slo.objectives[0].key_sli is True


def test_parse_weight_default(slo_data) -> None:
    """Objectives without an explicit weight default to 1."""
    slo = parse_slo(slo_data("minimal.yaml"))
    assert slo.objectives[0].weight == 1


def test_missing_spec_version_raises() -> None:
    with pytest.raises(SLOParseError, match="spec_version"):
        parse_slo("objectives:\n  - sli: m\n")


def test_objective_references_missing_indicator_raises() -> None:
    bad_yaml = """
spec_version: '1.0'
indicators:
  other: 'query()'
objectives:
  - sli: nonexistent
    pass:
      - criteria: ["<100"]
total_score:
  pass: "90%"
  warning: "75%"
"""
    with pytest.raises(SLOParseError, match="nonexistent"):
        parse_slo(bad_yaml)


def test_change_point_detection_field_accepted() -> None:
    """change_point_detection is a reserved field — must be accepted without error."""
    yaml_with_cpd = """
spec_version: '1.0'
indicators:
  m: 'query()'
objectives:
  - sli: m
    pass:
      - criteria: ["<100"]
    change_point_detection:
      enabled: true
      algorithm: otava
      sensitivity: 0.05
      min_history: 10
      fail_on_detection: true
total_score:
  pass: "90%"
  warning: "75%"
"""
    slo = parse_slo(yaml_with_cpd)
    assert slo.objectives[0].sli == "m"


def test_invalid_aggregate_function_raises() -> None:
    """aggregate_function values not in AggregateFunction are rejected by Pydantic."""
    bad_yaml = """
spec_version: '1.0'
comparison:
  aggregate_function: median
indicators:
  m: 'query()'
objectives:
  - sli: m
    pass:
      - criteria: ["<100"]
total_score:
  pass: "90%"
  warning: "75%"
"""
    with pytest.raises(ValidationError):
        parse_slo(bad_yaml)


def test_invalid_compare_with_raises() -> None:
    """compare_with values not in CompareWith are rejected by Pydantic."""
    bad_yaml = """
spec_version: '1.0'
comparison:
  compare_with: rolling_window
indicators:
  m: 'query()'
objectives:
  - sli: m
    pass:
      - criteria: ["<100"]
total_score:
  pass: "90%"
  warning: "75%"
"""
    with pytest.raises(ValidationError):
        parse_slo(bad_yaml)


def test_invalid_include_result_with_score_raises() -> None:
    """include_result_with_score values not in IncludeResultWithScore are rejected."""
    bad_yaml = """
spec_version: '1.0'
comparison:
  include_result_with_score: only_green
indicators:
  m: 'query()'
objectives:
  - sli: m
    pass:
      - criteria: ["<100"]
total_score:
  pass: "90%"
  warning: "75%"
"""
    with pytest.raises(ValidationError):
        parse_slo(bad_yaml)
