"""Unit tests for target resolution from criteria strings."""

from __future__ import annotations

from tropek.modules.quality_gate.workflows.presentation.target_resolver import resolve_targets


def test_fixed_threshold_not_violated():
    result = resolve_targets(['<600'], value=580.0, compared_value=None)
    assert len(result) == 1
    assert result[0]['criteria'] == '<600'
    assert result[0]['target_value'] == 600.0
    assert result[0]['violated'] is False


def test_fixed_threshold_violated():
    result = resolve_targets(['<600'], value=610.0, compared_value=None)
    assert result[0]['violated'] is True


def test_relative_percent_not_violated():
    result = resolve_targets(['<=+10%'], value=105.0, compared_value=100.0)
    assert result[0]['target_value'] == 110.0
    assert result[0]['violated'] is False


def test_relative_percent_violated():
    result = resolve_targets(['<=+10%'], value=115.0, compared_value=100.0)
    assert result[0]['violated'] is True


def test_relative_no_percent_sign():
    """<=+50 is parsed as <=+50% (relative percent) by the engine — no separate 'absolute' mode."""
    result = resolve_targets(['<=+50'], value=700.0, compared_value=500.0)
    # +50 means +50% of compared_value → 500 + 250 = 750
    assert result[0]['target_value'] == 750.0
    assert result[0]['violated'] is False


def test_null_value_always_violated():
    result = resolve_targets(['<600'], value=None, compared_value=None)
    assert result[0]['violated'] is True


def test_empty_criteria_returns_empty():
    result = resolve_targets([], value=100.0, compared_value=None)
    assert result == []


def test_none_criteria_returns_none():
    result = resolve_targets(None, value=100.0, compared_value=None)
    assert result is None
