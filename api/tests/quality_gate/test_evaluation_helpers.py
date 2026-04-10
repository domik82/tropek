"""Tests for shared evaluation helper functions."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.modules.quality_gate.evaluation_helpers import build_eval_variables, build_slo_model


def test_build_eval_variables_merge_priority() -> None:
    """Variables merge with correct priority: reserved < asset.variables < asset.tags < slo < eval."""
    result = build_eval_variables(
        asset_name='vm-01',
        evaluation_name='nightly',
        start='2026-03-15T10:00:00',
        end='2026-03-15T10:30:00',
        asset_variables={'region': 'us-east', 'env': 'prod'},
        asset_tags={'team': 'platform', 'env': 'staging'},
        slo_variables={'threshold': '500', 'env': 'slo-env'},
        eval_variables={'run_id': '42', 'env': 'override'},
    )
    # Reserved vars present
    assert result['TROPEK_ASSET'] == 'vm-01'
    assert result['TROPEK_EVALUATION'] == 'nightly'
    # asset.variables take precedence over tags for 'env'
    assert result['region'] == 'us-east'
    assert result['team'] == 'platform'
    # slo_variables override asset-level
    assert result['threshold'] == '500'
    # eval_variables have highest priority
    assert result['run_id'] == '42'
    assert result['env'] == 'override'


def test_build_eval_variables_empty_inputs() -> None:
    result = build_eval_variables(
        asset_name='vm-01',
        evaluation_name='test',
        start='2026-01-01T00:00:00',
        end='2026-01-01T01:00:00',
        asset_variables={},
        asset_tags={},
        slo_variables={},
        eval_variables={},
    )
    assert 'TROPEK_ASSET' in result
    assert 'TROPEK_EVALUATION' in result


def test_build_eval_variables_none_inputs() -> None:
    result = build_eval_variables(
        asset_name='vm-01',
        evaluation_name='test',
        start='2026-01-01T00:00:00',
        end='2026-01-01T01:00:00',
        asset_variables=None,
        asset_tags=None,
        slo_variables=None,
        eval_variables=None,
    )
    assert 'TROPEK_ASSET' in result


# -- build_slo_model (pre-extraction regression test) -------------------------


def testbuild_slo_model_creates_slo_from_definition() -> None:
    """build_slo_model converts an SLODefinition-like object to an engine SLO."""
    obj = MagicMock()
    obj.sli = 'response_time'
    obj.display_name = 'Response Time'
    obj.weight = 1
    obj.key_sli = False
    obj.pass_threshold = ['<600']
    obj.warning_threshold = ['<800']

    slo_def = MagicMock()
    slo_def.objectives = [obj]
    slo_def.total_score_pass_threshold = 90.0
    slo_def.total_score_warning_threshold = 75.0
    slo_def.comparison = {
        'compare_with': 'single_result',
        'number_of_comparison_results': 1,
    }

    slo = build_slo_model(slo_def)
    assert slo is not None
    assert len(slo.objectives) == 1
    assert slo.objectives[0].sli == 'response_time'
    assert slo.objectives[0].key_sli is False
    assert slo.total_score.pass_threshold == 90.0
    assert slo.total_score.warning_threshold == 75.0


def testbuild_slo_model_copies_thresholds_as_lists() -> None:
    """Thresholds are copied via list() — no mutable reference sharing."""
    original_pass = ['<600']
    original_warn = ['<800']

    obj = MagicMock()
    obj.sli = 'rt'
    obj.display_name = 'RT'
    obj.weight = 1
    obj.key_sli = False
    obj.pass_threshold = original_pass
    obj.warning_threshold = original_warn

    slo_def = MagicMock()
    slo_def.objectives = [obj]
    slo_def.total_score_pass_threshold = 90.0
    slo_def.total_score_warning_threshold = 75.0
    slo_def.comparison = {}

    slo = build_slo_model(slo_def)
    # Mutating the original should not affect the built SLO
    original_pass.append('<999')
    assert '<999' not in slo.objectives[0].pass_threshold
