"""Unit tests for the SLO group generator — pure functions, no DB."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from app.modules.slo_groups.generator import (
    generate_slo_specs,
    validate_gen_variables,
)


@dataclass
class FakeTemplate:
    """Minimal template matching TemplateInput protocol."""

    name: str = 'app/$__gen_process_name'
    sli_name: str | None = 'test-sli'
    sli_version: int | None = 1
    variables: dict[str, Any] = field(
        default_factory=lambda: {
            'process_name': '$__gen_process_name',
            'AGGREGATION_WINDOW': '5m',
        }
    )
    objectives: list[dict[str, Any]] = field(default_factory=lambda: [{'sli': 'cpu', 'pass_criteria': ['<80']}])
    total_score_pass_pct: float = 90.0
    total_score_warning_pct: float = 75.0
    comparison: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, Any] = field(default_factory=lambda: {'env': 'prod'})


def test_generate_happy_path() -> None:
    """3 gen_variables rows produce 3 specs with correct substitution."""
    tpl = FakeTemplate()
    gen_vars = {'process_name': ['auth', 'cache', 'db']}
    result = generate_slo_specs(tpl, gen_vars, group_name='my-group')

    assert len(result.specs) == 3
    assert result.specs[0].name == 'app/auth'
    assert result.specs[1].name == 'app/cache'
    assert result.specs[2].name == 'app/db'
    assert result.specs[0].variables['process_name'] == 'auth'
    assert result.specs[0].variables['AGGREGATION_WINDOW'] == '5m'
    assert result.specs[0].sli_name == 'test-sli'
    assert result.specs[0].sli_version == 1
    assert result.specs[0].tags['slo_group'] == 'my-group'
    assert result.specs[0].tags['generated'] == 'true'
    assert result.specs[0].tags['env'] == 'prod'
    assert not result.warnings


def test_generate_multi_variable() -> None:
    """Multiple gen_variables produce row-aligned substitution."""
    tpl = FakeTemplate(
        name='$__gen_host/$__gen_process_name',
        variables={'process_name': '$__gen_process_name', 'host': '$__gen_host'},
    )
    gen_vars = {
        'process_name': ['auth', 'cache'],
        'host': ['vm-1', 'vm-2'],
    }
    result = generate_slo_specs(tpl, gen_vars, group_name='g')
    assert result.specs[0].name == 'vm-1/auth'
    assert result.specs[1].name == 'vm-2/cache'
    assert result.specs[0].variables['host'] == 'vm-1'


def test_generate_mismatched_lengths() -> None:
    """Mismatched gen_variables list lengths raise ValueError."""
    gen_vars = {'a': ['1', '2'], 'b': ['1']}
    with pytest.raises(ValueError, match='equal length'):
        generate_slo_specs(FakeTemplate(), gen_vars, group_name='g')


def test_generate_empty_list() -> None:
    """Empty gen_variables list raises ValueError."""
    gen_vars = {'a': []}
    with pytest.raises(ValueError, match='must not be empty'):
        generate_slo_specs(FakeTemplate(), gen_vars, group_name='g')


def test_generate_no_keys() -> None:
    """Empty gen_variables dict raises ValueError."""
    with pytest.raises(ValueError, match='at least one key'):
        generate_slo_specs(FakeTemplate(), {}, group_name='g')


def test_generate_warns_no_gen_placeholders() -> None:
    """Template without $__gen_ placeholders produces a warning."""
    tpl = FakeTemplate(name='static-name', variables={'key': 'static-value'})
    gen_vars = {'x': ['1']}
    result = generate_slo_specs(tpl, gen_vars, group_name='g')
    assert len(result.warnings) == 1
    assert 'no $__gen_ placeholders' in result.warnings[0]


def test_generate_objectives_not_substituted() -> None:
    """Objectives are copied as-is — $__gen_ in objectives is NOT substituted."""
    tpl = FakeTemplate(objectives=[{'sli': '$__gen_x', 'pass_criteria': ['<80']}])
    gen_vars = {'x': ['replaced']}
    result = generate_slo_specs(tpl, gen_vars, group_name='g')
    assert result.specs[0].objectives[0]['sli'] == '$__gen_x'


def test_generate_special_chars_in_values() -> None:
    """Special characters in gen_variable values are preserved."""
    tpl = FakeTemplate()
    gen_vars = {'process_name': ['auth/v2.0', 'cache (primary)', 'db-main_01']}
    result = generate_slo_specs(tpl, gen_vars, group_name='g')
    assert result.specs[0].name == 'app/auth/v2.0'
    assert result.specs[1].variables['process_name'] == 'cache (primary)'


def test_validate_gen_variables_valid() -> None:
    """Valid gen_variables return no errors."""
    assert validate_gen_variables({'a': ['1', '2'], 'b': ['x', 'y']}) == []
