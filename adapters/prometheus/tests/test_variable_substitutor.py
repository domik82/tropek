import pytest

from app.core.variable_substitutor import substitute, UnresolvedVariableError


def test_simple_substitution():
    result = substitute(
        template='rate(http_requests{job="$SERVICE"}[$interval])',
        variables={"SERVICE": "carts", "interval": "5m"},
    )
    assert result == 'rate(http_requests{job="carts"}[5m])'


def test_multiple_occurrences_of_same_variable():
    result = substitute(
        template="$X + $X",
        variables={"X": "1"},
    )
    assert result == "1 + 1"


def test_no_variables():
    result = substitute(
        template="rate(http_requests[5m])",
        variables={},
    )
    assert result == "rate(http_requests[5m])"


def test_unresolved_variable_raises():
    with pytest.raises(UnresolvedVariableError, match="MISSING"):
        substitute(
            template="rate($MISSING[5m])",
            variables={},
        )


def test_dollar_sign_in_value_not_treated_as_variable():
    result = substitute(
        template='query{label="$VALUE"}',
        variables={"VALUE": "$literal"},
    )
    assert result == 'query{label="$literal"}'


def test_underscore_and_dot_in_variable_name():
    result = substitute(
        template="$LABEL.host + $my_var",
        variables={"LABEL.host": "10.0.0.1", "my_var": "test"},
    )
    assert result == "10.0.0.1 + test"


def test_duration_seconds_auto_computed():
    result = substitute(
        template="rate(metric[$DURATION_SECONDS])",
        variables={},
        start_iso="2026-01-15T10:00:00Z",
        end_iso="2026-01-15T10:05:00Z",
    )
    assert result == "rate(metric[300s])"


def test_duration_seconds_not_overridden_if_provided():
    result = substitute(
        template="rate(metric[$DURATION_SECONDS])",
        variables={"DURATION_SECONDS": "600s"},
    )
    assert result == "rate(metric[600s])"


def test_interval_reserved_in_aggregated_mode():
    """When interval_override is set, $interval resolves to it, not variables dict."""
    result = substitute(
        template="rate(metric[$interval])",
        variables={"interval": "should_be_ignored"},
        interval_override="1m",
    )
    assert result == "rate(metric[1m])"
