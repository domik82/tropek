from __future__ import annotations

import pytest
from app.modules.quality_gate.evaluation_engine.variables import (
    UnresolvedVariableError,
    build_variables,
    substitute_slo_variables,
    substitute_variables,
)


def test_substitutes_single_variable() -> None:
    result = substitute_variables('cpu{instance="$vm_ip"}', {'vm_ip': '10.0.0.1'})
    assert result == 'cpu{instance="10.0.0.1"}'


def test_substitutes_multiple_variables() -> None:
    result = substitute_variables(
        'query{os="$os", arch="$arch"}',
        {'os': 'windows-11', 'arch': 'x64'},
    )
    assert result == 'query{os="windows-11", arch="x64"}'


def test_unresolved_variable_raises() -> None:
    with pytest.raises(UnresolvedVariableError, match='vm_ip'):
        substitute_variables('cpu{instance="$vm_ip"}', {})


def test_no_variables_returns_unchanged() -> None:
    template = 'avg_over_time(cpu[5m])'
    assert substitute_variables(template, {}) == template


def test_substitute_slo_variables_replaces_in_yaml() -> None:
    slo_yaml = """
spec_version: '1.0'
indicators:
  cpu: 'avg_over_time(cpu{instance="$vm_ip"}[5m])'
objectives:
  - sli: cpu
    pass:
      - criteria: ["<90"]
    weight: 1
total_score:
  pass: "90%"
  warning: "75%"
"""
    result = substitute_slo_variables(slo_yaml, {'vm_ip': '10.0.0.5'})
    assert '$vm_ip' not in result
    assert '10.0.0.5' in result


def test_build_variables_merges_metadata() -> None:
    variables = build_variables(
        {'os': 'windows-11', 'vm_ip': '10.0.0.1'},
        asset_name='vm-win11-01',
        evaluation_name='compilation-test',
    )
    assert variables['os'] == 'windows-11'
    assert variables['asset_name'] == 'vm-win11-01'
    assert variables['evaluation_name'] == 'compilation-test'
    assert variables['test_name'] == 'compilation-test'  # alias


def test_build_variables_arbitrary_metadata_passthrough() -> None:
    variables = build_variables({'abc123': 'custom-value', 'region': 'eu-west-1'})
    assert variables['abc123'] == 'custom-value'
    assert variables['region'] == 'eu-west-1'
    result = substitute_variables('$abc123 in $region', variables)
    assert result == 'custom-value in eu-west-1'


def test_build_variables_start_end() -> None:
    variables = build_variables(
        {},
        start='2026-03-12T10:00:00Z',
        end='2026-03-12T10:30:00Z',
    )
    assert variables['start'] == '2026-03-12T10:00:00Z'
    assert variables['end'] == '2026-03-12T10:30:00Z'


def test_build_variables_evaluation_name() -> None:
    variables = build_variables(
        {},
        evaluation_name='nightly-run',
    )
    assert variables['evaluation_name'] == 'nightly-run'
    assert variables['test_name'] == 'nightly-run'


def test_build_variables_evaluation_name_substitution() -> None:
    variables = build_variables({}, evaluation_name='run-42')
    result = substitute_variables('check_$evaluation_name', variables)
    assert result == 'check_run-42'
    result_old = substitute_variables('check_$test_name', variables)
    assert result_old == 'check_run-42'
