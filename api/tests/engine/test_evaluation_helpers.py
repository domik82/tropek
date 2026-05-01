from tropek.modules.quality_gate.workflows.execution.evaluation_helpers import resolve_comparison_name


def test_resolve_comparison_name_returns_explicit_name():
    result = resolve_comparison_name({'evaluation_name': 'main-load-test'}, 'feature-test')
    assert result == 'main-load-test'


def test_resolve_comparison_name_returns_self_when_compare_to_is_none():
    result = resolve_comparison_name(None, 'load-test')
    assert result == 'load-test'


def test_resolve_comparison_name_returns_self_when_compare_to_is_empty():
    result = resolve_comparison_name({}, 'load-test')
    assert result == 'load-test'


def test_resolve_comparison_name_ignores_other_keys():
    result = resolve_comparison_name({'os': 'linux'}, 'load-test')
    assert result == 'load-test'
