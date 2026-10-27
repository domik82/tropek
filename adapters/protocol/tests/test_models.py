"""Validation of the optional ``error_kinds`` response field."""

import pytest
from pydantic import ValidationError
from tropek_adapter_protocol.testing import assert_query_response_valid


@pytest.mark.parametrize(
    ('error_kinds', 'accepted'),
    [
        (None, True),
        ({'a': 'transient'}, True),
        ({'a': 'transient', 'b': 'data'}, True),
        ({'other': 'transient'}, False),
        ({'a': 'foo'}, False),
    ],
)
def test_error_kinds_validation(error_kinds: dict[str, str] | None, accepted: bool) -> None:
    body: dict[str, object] = {'values': {'a': None, 'b': None}, 'errors': {'a': 'x', 'b': 'y'}}
    if error_kinds is not None:
        body['error_kinds'] = error_kinds
    if accepted:
        assert assert_query_response_valid(body).error_kinds == (error_kinds or {})
    else:
        with pytest.raises(ValidationError, match='error_kinds'):
            assert_query_response_valid(body)
