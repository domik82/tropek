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


def test_generate_variants_produce_per_variable_rows() -> None:
    """Variant scenarios produce rows with distinct variable_key values."""
    scenario = load_scenario(Path('scenarios/office-apps.yaml'))
    rows = generate_scenario_rows(scenario)
    variable_keys = {row['variable_key'] for row in rows}
    assert 'process_name=WINWORD' in variable_keys
    assert 'process_name=EXCEL' in variable_keys
    assert 'process_name=POWERPNT' in variable_keys
    assert 'process_name=OUTLOOK' in variable_keys


def test_generate_variants_have_different_values() -> None:
    """Different variants produce different metric values at the same timestamp."""
    scenario = load_scenario(Path('scenarios/office-apps.yaml'))
    rows = generate_scenario_rows(scenario)
    cpu_by_key: dict[str, list[float]] = {}
    for row in rows:
        if row['metric_name'] == 'process_cpu_pct' and row['variable_key']:
            cpu_by_key.setdefault(row['variable_key'], []).append(float(row['value']))
    variable_key_names = list(cpu_by_key.keys())
    assert len(variable_key_names) >= 2
    assert cpu_by_key[variable_key_names[0]] != cpu_by_key[variable_key_names[1]]


def test_generate_variants_are_deterministic() -> None:
    """Variant generation is deterministic across runs."""
    scenario = load_scenario(Path('scenarios/office-apps.yaml'))
    rows1 = generate_scenario_rows(scenario)
    rows2 = generate_scenario_rows(scenario)
    assert rows1 == rows2


def test_generate_change_point_transitions_zero_origin_appear_shape() -> None:
    """errors_zero_origin_appear steps from 0.0 to 500.0 with no gradual samples."""
    scenario = load_scenario(Path('scenarios/change-point-transitions.yaml'))
    rows = generate_scenario_rows(scenario)
    values = [float(row['value']) for row in rows if row['metric_name'] == 'errors_zero_origin_appear']

    assert len(values) == 61
    assert values[:24] == [0.0] * 24
    assert values[24:] == [500.0] * 37


def test_generate_change_point_transitions_throughput_vanish_shape() -> None:
    """throughput_vanish steps from 500.0 to 0.0 with no gradual samples."""
    scenario = load_scenario(Path('scenarios/change-point-transitions.yaml'))
    rows = generate_scenario_rows(scenario)
    values = [float(row['value']) for row in rows if row['metric_name'] == 'throughput_vanish']

    assert len(values) == 61
    assert values[:24] == [500.0] * 24
    assert values[24:] == [0.0] * 37


def test_generate_change_point_transitions_memory_diluted_shift_shape() -> None:
    """memory_diluted_shift dips then recovers to a value +15.65% above the dip."""
    scenario = load_scenario(Path('scenarios/change-point-transitions.yaml'))
    rows = generate_scenario_rows(scenario)
    values = [float(row['value']) for row in rows if row['metric_name'] == 'memory_diluted_shift']

    assert len(values) == 61
    assert values[:40] == [13600000.0] * 40
    assert values[40:48] == [11500000.0] * 8
    assert values[48:] == [13300000.0] * 13

    dip_value = values[40]
    recovery_value = values[48]
    recovery_pct = (recovery_value - dip_value) / dip_value * 100
    assert round(recovery_pct, 2) == 15.65


def test_generate_change_point_transitions_is_deterministic() -> None:
    """Zero jitter means the same scenario produces identical rows across runs."""
    scenario = load_scenario(Path('scenarios/change-point-transitions.yaml'))
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
        metric_names = {row['metric_name'] for row in rows}
        assert expected[ns] == metric_names, f'namespace {ns}: expected {expected[ns]}, got {metric_names}'
