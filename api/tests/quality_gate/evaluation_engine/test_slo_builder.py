"""Unit tests for build_slo — structured SLO constructor."""

from __future__ import annotations

import pytest
from app.modules.quality_gate.evaluation_engine.slo_models import SLOParseError
from app.modules.quality_gate.evaluation_engine.slo_parser import build_slo


def test_build_minimal_slo() -> None:
    slo = build_slo(objectives=[{'sli': 'm', 'pass_threshold': ['<100']}])
    assert len(slo.objectives) == 1
    assert slo.objectives[0].sli == 'm'
    assert slo.objectives[0].pass_threshold == ['<100']
    assert slo.total_score.pass_threshold == 90.0
    assert slo.total_score.warning_threshold == 75.0


def test_build_slo_comparison_defaults() -> None:
    slo = build_slo(objectives=[{'sli': 'm'}])
    assert slo.comparison.compare_with == 'single_result'
    assert slo.comparison.number_of_comparison_results == 3
    assert slo.comparison.scope_tags == ['os']


def test_build_slo_comparison_overridden() -> None:
    slo = build_slo(
        objectives=[{'sli': 'm'}],
        comparison={'compare_with': 'several_results', 'scope_tags': ['os', 'arch']},
    )
    assert slo.comparison.compare_with == 'several_results'
    assert slo.comparison.scope_tags == ['os', 'arch']


def test_empty_objectives_raises() -> None:
    with pytest.raises(SLOParseError, match='empty'):
        build_slo(objectives=[])


def test_invalid_comparison_raises() -> None:
    with pytest.raises(SLOParseError):
        build_slo(
            objectives=[{'sli': 'm'}],
            comparison={'aggregate_function': 'median'},  # not a valid AggregateFunction
        )


def test_objective_defaults() -> None:
    slo = build_slo(objectives=[{'sli': 'm'}])
    obj = slo.objectives[0]
    assert obj.display_name == ''
    assert obj.pass_threshold == []
    assert obj.warning_threshold == []
    assert obj.weight == 1
    assert obj.key_sli is False


def test_score_defaults() -> None:
    slo = build_slo(objectives=[{'sli': 'm'}])
    assert slo.total_score.pass_threshold == 90.0
    assert slo.total_score.warning_threshold == 75.0


def test_score_overridden() -> None:
    slo = build_slo(objectives=[{'sli': 'm'}], total_score_pass_threshold=95.0, total_score_warning_threshold=80.0)
    assert slo.total_score.pass_threshold == 95.0
    assert slo.total_score.warning_threshold == 80.0
