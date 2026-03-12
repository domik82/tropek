from __future__ import annotations

import pytest
from app.modules.quality_gate.engine.slo_parser import SLOParseError, parse_slo

MINIMAL_SLO = """
spec_version: '1.0'
indicators:
  response_time_p99: 'avg_over_time(http_duration_seconds[5m])'
objectives:
  - sli: response_time_p99
    pass:
      - criteria: ["<600"]
    weight: 1
total_score:
  pass: "90%"
  warning: "75%"
"""

RELATIVE_SLO = """
spec_version: '1.0'
comparison:
  compare_with: several_results
  number_of_comparison_results: 3
  include_result_with_score: pass_or_warn
  aggregate_function: avg
  scope_tags:
    - os
    - arch
indicators:
  cpu_usage: 'avg_over_time(cpu[5m])'
objectives:
  - sli: cpu_usage
    pass:
      - criteria: ["<=+10%"]
    warning:
      - criteria: ["<=+20%"]
    weight: 2
    key_sli: true
total_score:
  pass: "90%"
  warning: "75%"
"""


def test_parse_minimal_slo() -> None:
    slo = parse_slo(MINIMAL_SLO)
    assert slo.spec_version == "1.0"
    assert len(slo.objectives) == 1
    assert slo.objectives[0].sli == "response_time_p99"
    assert slo.objectives[0].weight == 1
    assert slo.objectives[0].key_sli is False
    assert slo.total_score.pass_pct == 90.0
    assert slo.total_score.warning_pct == 75.0


def test_parse_indicators_block() -> None:
    slo = parse_slo(MINIMAL_SLO)
    assert "response_time_p99" in slo.indicators
    assert slo.indicators["response_time_p99"] == "avg_over_time(http_duration_seconds[5m])"


def test_parse_comparison_defaults() -> None:
    slo = parse_slo(MINIMAL_SLO)
    assert slo.comparison.compare_with == "single_result"
    assert slo.comparison.number_of_comparison_results == 3
    assert slo.comparison.include_result_with_score == "all"
    assert slo.comparison.aggregate_function == "avg"
    assert slo.comparison.scope_tags == ["os"]


def test_parse_relative_slo_comparison() -> None:
    slo = parse_slo(RELATIVE_SLO)
    assert slo.comparison.compare_with == "several_results"
    assert slo.comparison.scope_tags == ["os", "arch"]


def test_parse_key_sli() -> None:
    slo = parse_slo(RELATIVE_SLO)
    assert slo.objectives[0].key_sli is True


def test_parse_weight_default() -> None:
    yaml_text = """
spec_version: '1.0'
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
    slo = parse_slo(yaml_text)
    assert slo.objectives[0].weight == 1


def test_missing_spec_version_raises() -> None:
    with pytest.raises(SLOParseError, match="spec_version"):
        parse_slo("objectives:\n  - sli: m\n")


def test_objective_references_missing_indicator_raises() -> None:
    bad = """
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
        parse_slo(bad)


def test_change_point_detection_field_accepted() -> None:
    """change_point_detection is reserved — must be accepted without error."""
    yaml_text = """
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
total_score:
  pass: "90%"
  warning: "75%"
"""
    slo = parse_slo(yaml_text)
    assert slo.objectives[0].sli == "m"
