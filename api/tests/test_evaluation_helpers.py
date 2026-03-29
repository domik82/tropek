"""Tests for shared evaluation helper functions."""

from __future__ import annotations

from app.modules.quality_gate.evaluation_helpers import build_eval_variables


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
