"""Unit tests for comparison rule validation models."""

from __future__ import annotations

import pytest
from app.modules.assets.comparison_rules import validate_comparison_rules
from pydantic import ValidationError


def test_valid_single_rule() -> None:
    rules = validate_comparison_rules(
        [
            {"match": {"branch": "main"}, "compare_to": {"branch": "main"}},
        ]
    )
    assert len(rules) == 1
    assert rules[0].match == {"branch": "main"}
    assert rules[0].compare_to == {"branch": "main"}


def test_valid_negation_rule() -> None:
    rules = validate_comparison_rules(
        [
            {"match": {"branch": "!main"}, "compare_to": {"branch": "main"}},
        ]
    )
    assert rules[0].match == {"branch": "!main"}


def test_valid_pinned_compare_to() -> None:
    rules = validate_comparison_rules(
        [
            {"match": {"branch": "release-*"}, "compare_to": {"pinned": True}},
        ]
    )
    assert rules[0].compare_to == {"pinned": True}


def test_valid_catch_all_last() -> None:
    rules = validate_comparison_rules(
        [
            {"match": {"branch": "main"}, "compare_to": {"branch": "main"}},
            {"match": {}, "compare_to": {}},
        ]
    )
    assert len(rules) == 2
    assert rules[1].match == {}


def test_catch_all_not_last_rejected() -> None:
    with pytest.raises(ValueError, match=r"catch-all.*must be last"):
        validate_comparison_rules(
            [
                {"match": {}, "compare_to": {}},
                {"match": {"branch": "main"}, "compare_to": {"branch": "main"}},
            ]
        )


def test_multiple_catch_alls_rejected() -> None:
    with pytest.raises(ValueError, match="at most one catch-all"):
        validate_comparison_rules(
            [
                {"match": {}, "compare_to": {}},
                {"match": {}, "compare_to": {"branch": "main"}},
            ]
        )


def test_empty_rules_valid() -> None:
    rules = validate_comparison_rules([])
    assert rules == []


def test_invalid_match_type_rejected() -> None:
    with pytest.raises((ValidationError, ValueError)):
        validate_comparison_rules(
            [
                {"match": "not-a-dict", "compare_to": {}},
            ]
        )


def test_invalid_compare_to_type_rejected() -> None:
    with pytest.raises((ValidationError, ValueError)):
        validate_comparison_rules(
            [
                {"match": {}, "compare_to": "not-a-dict"},
            ]
        )
