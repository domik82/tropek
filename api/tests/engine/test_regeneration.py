"""Unit tests for the regeneration engine — pure functions, no DB."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.slo_groups.generator import GeneratedSLOSpec
from app.modules.slo_groups.regeneration import plan_regeneration


@dataclass
class FakeOldSLO:
    """Minimal old SLO matching OldSLOState protocol."""

    name: str
    comparable_from_version: int = 1


def _spec(name: str) -> GeneratedSLOSpec:
    return GeneratedSLOSpec(
        name=name,
        variables={},
        objectives=[],
        total_score_pass_threshold=90.0,
        total_score_warning_threshold=75.0,
        comparison={},
        tags={},
    )


def test_criteria_only_change_preserves_baseline() -> None:
    """When only criteria change (same SLI, same queries), preserve comparable_from_version."""
    old = [FakeOldSLO('a', comparable_from_version=1)]
    new = [_spec('a')]
    indicators = {'cpu': 'rate(cpu[5m])'}

    plan = plan_regeneration(old, new, indicators, indicators, template_variables_changed=False)

    assert len(plan.to_update) == 1
    assert plan.to_update[0].comparable_from_version == 1
    assert plan.to_create == []
    assert plan.to_deactivate == []


def test_sli_version_bump_same_queries_preserves() -> None:
    """SLI version bump with identical queries preserves baseline."""
    old = [FakeOldSLO('a', comparable_from_version=1)]
    new = [_spec('a')]
    indicators = {'cpu': 'rate(cpu[5m])'}

    plan = plan_regeneration(old, new, indicators, indicators, template_variables_changed=False)
    assert plan.to_update[0].comparable_from_version == 1


def test_sli_version_bump_different_queries_breaks_baseline() -> None:
    """SLI version bump with changed queries breaks baseline."""
    old = [FakeOldSLO('a', comparable_from_version=1)]
    new = [_spec('a')]
    old_ind = {'cpu': 'rate(cpu[5m])'}
    new_ind = {'cpu': 'rate(cpu[10m])'}

    plan = plan_regeneration(old, new, old_ind, new_ind, template_variables_changed=False)
    assert plan.to_update[0].comparable_from_version is None  # signals "set to new version"


def test_template_variables_changed_breaks_baseline() -> None:
    """Changed template variables break baseline."""
    old = [FakeOldSLO('a', comparable_from_version=1)]
    new = [_spec('a')]
    indicators = {'cpu': 'rate(cpu[5m])'}

    plan = plan_regeneration(old, new, indicators, indicators, template_variables_changed=True)
    assert plan.to_update[0].comparable_from_version is None


def test_new_rows_added() -> None:
    """New gen_variables rows appear in to_create."""
    old = [FakeOldSLO('a')]
    new = [_spec('a'), _spec('b')]
    indicators = {'cpu': 'rate(cpu[5m])'}

    plan = plan_regeneration(old, new, indicators, indicators, template_variables_changed=False)
    assert len(plan.to_create) == 1
    assert plan.to_create[0].name == 'b'
    assert len(plan.to_update) == 1


def test_rows_removed() -> None:
    """Removed gen_variables rows appear in to_deactivate."""
    old = [FakeOldSLO('a'), FakeOldSLO('b')]
    new = [_spec('a')]
    indicators = {'cpu': 'rate(cpu[5m])'}

    plan = plan_regeneration(old, new, indicators, indicators, template_variables_changed=False)
    assert plan.to_deactivate == ['b']
    assert len(plan.to_update) == 1


def test_mixed_scenario() -> None:
    """Mixed: add, update, deactivate in one plan."""
    old = [FakeOldSLO('a', 1), FakeOldSLO('b', 2)]
    new = [_spec('a'), _spec('c')]
    indicators = {'cpu': 'rate(cpu[5m])'}

    plan = plan_regeneration(old, new, indicators, indicators, template_variables_changed=False)
    assert len(plan.to_create) == 1
    assert plan.to_create[0].name == 'c'
    assert len(plan.to_update) == 1
    assert plan.to_update[0].spec.name == 'a'
    assert plan.to_deactivate == ['b']


def test_indicator_key_added_breaks_baseline() -> None:
    """Adding an indicator key counts as query change."""
    old = [FakeOldSLO('a', 1)]
    new = [_spec('a')]
    old_ind = {'cpu': 'rate(cpu[5m])'}
    new_ind = {'cpu': 'rate(cpu[5m])', 'mem': 'node_memory_bytes'}

    plan = plan_regeneration(old, new, old_ind, new_ind, template_variables_changed=False)
    assert plan.to_update[0].comparable_from_version is None


def test_indicator_key_removed_breaks_baseline() -> None:
    """Removing an indicator key counts as query change."""
    old = [FakeOldSLO('a', 1)]
    new = [_spec('a')]
    old_ind = {'cpu': 'rate(cpu[5m])', 'mem': 'node_memory_bytes'}
    new_ind = {'cpu': 'rate(cpu[5m])'}

    plan = plan_regeneration(old, new, old_ind, new_ind, template_variables_changed=False)
    assert plan.to_update[0].comparable_from_version is None
