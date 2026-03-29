"""Unit tests for the scenario CSV generator."""

from __future__ import annotations

from pathlib import Path

from generate import generate_scenario_rows, load_scenario


def test_load_scenario() -> None:
    scenario = load_scenario(Path('scenarios/stable.yaml'))
    assert scenario['name'] == 'stable'
    assert 'metrics' in scenario
    assert scenario['interval_minutes'] > 0


def test_generate_stable_returns_rows_with_expected_fields() -> None:
    scenario = load_scenario(Path('scenarios/stable.yaml'))
    rows = generate_scenario_rows(scenario)
    assert len(rows) > 0
    for row in rows[:5]:
        assert 'timestamp' in row
        assert 'metric_name' in row
        assert 'value' in row


def test_generate_is_deterministic() -> None:
    scenario = load_scenario(Path('scenarios/stable.yaml'))
    rows1 = generate_scenario_rows(scenario)
    rows2 = generate_scenario_rows(scenario)
    assert rows1 == rows2


def test_main_merges_scenarios_into_shared_namespace() -> None:
    """Multiple scenarios targeting the same namespace produce merged CSV."""
    scenarios_dir = Path('scenarios')
    all_scenarios = [load_scenario(p) for p in sorted(scenarios_dir.glob('*.yaml'))]

    # Collect expected metric names per namespace
    expected: dict[str, set[str]] = {}
    for scenario in all_scenarios:
        namespaces = scenario.get('namespaces', [scenario['name']])
        for ns in namespaces:
            expected.setdefault(ns, set()).update(scenario['metrics'].keys())

    # Generate via main() into temp dir and verify all metrics present
    ns_rows: dict[str, list[dict[str, str]]] = {}
    for scenario in all_scenarios:
        rows = generate_scenario_rows(scenario)
        for ns in scenario.get('namespaces', [scenario['name']]):
            ns_rows.setdefault(ns, []).extend(rows)

    for ns, rows in ns_rows.items():
        metric_names = {r['metric_name'] for r in rows}
        assert expected[ns] == metric_names, f'namespace {ns}: expected {expected[ns]}, got {metric_names}'
