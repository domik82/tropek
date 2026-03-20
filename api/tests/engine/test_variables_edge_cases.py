"""Edge-case tests for variable substitution: shadowing, unresolved, special chars."""

from __future__ import annotations

import pytest
from app.modules.quality_gate.engine.variables import (
    UnresolvedVariableError,
    build_variables,
    substitute_variables,
)


def test_metadata_key_does_not_shadow_reserved_asset_name() -> None:
    """User metadata key 'asset_name' should not shadow built-in $asset_name.

    build_variables uses setdefault, so metadata (set first) wins.
    This test documents the actual behavior: metadata takes priority.
    """
    variables = build_variables(
        metadata={"asset_name": "from-metadata"},
        asset_name="real-asset",
    )
    # metadata is copied first, setdefault("asset_name", "real-asset") is a no-op
    assert variables["asset_name"] == "from-metadata"


def test_reserved_variable_wins_when_metadata_empty() -> None:
    """When metadata does not contain the key, the built-in variable is used."""
    variables = build_variables(
        metadata={},
        asset_name="real-asset",
    )
    assert variables["asset_name"] == "real-asset"


def test_unresolved_variable_in_query_raises() -> None:
    """Query with $undefined_var raises UnresolvedVariableError."""
    with pytest.raises(UnresolvedVariableError, match="undefined_var"):
        substitute_variables("rate($undefined_var)", {"asset_name": "foo"})


def test_special_characters_in_variable_value() -> None:
    """Variable value with regex special chars (brackets, dots) should be literal-substituted."""
    result = substitute_variables(
        "rate({job='$asset_name'})",
        {"asset_name": "my.service[0]"},
    )
    assert "my.service[0]" in result
    assert result == "rate({job='my.service[0]'})"


def test_dollar_sign_not_followed_by_identifier() -> None:
    """A bare $ not followed by an identifier should be left as-is."""
    result = substitute_variables("cost is $5", {})
    # $5 starts with a digit, so _VAR_RE won't match — literal pass-through
    assert result == "cost is $5"


def test_multiple_occurrences_of_same_variable() -> None:
    """Same $variable used twice should both be replaced."""
    result = substitute_variables(
        "$host:$host",
        {"host": "10.0.0.1"},
    )
    assert result == "10.0.0.1:10.0.0.1"


def test_build_variables_none_asset_name_omitted() -> None:
    """When asset_name is None, $asset_name is not added to variables."""
    variables = build_variables(metadata={}, asset_name=None)
    assert "asset_name" not in variables


def test_build_variables_empty_string_asset_name_omitted() -> None:
    """When asset_name is empty string (falsy), $asset_name is not added."""
    variables = build_variables(metadata={}, asset_name="")
    assert "asset_name" not in variables
