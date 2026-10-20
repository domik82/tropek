"""Shape tests for the two optional reliability fields."""

import pytest
from pydantic import ValidationError
from tropek_adapter_protocol.models import AdapterQueryRequest, AdapterQueryResponse
from tropek_adapter_protocol.testing import assert_query_response_valid


def test_request_timeout_seconds_is_optional() -> None:
    body = {
        'queries': {'m': {'mode': 'raw', 'query': 'up'}},
        'start': '2026-01-01T00:00:00Z',
        'end': '2026-01-02T00:00:00Z',
    }
    assert AdapterQueryRequest.model_validate(body).timeout_seconds is None
    assert AdapterQueryRequest.model_validate({**body, 'timeout_seconds': 300}).timeout_seconds == 300


def test_response_error_kinds_default_empty() -> None:
    parsed = AdapterQueryResponse.model_validate({'values': {'m': None}, 'errors': {'m': 'boom'}})
    assert parsed.error_kinds == {}


def test_error_kinds_must_name_an_errored_metric() -> None:
    with pytest.raises(ValidationError, match='error_kinds'):
        assert_query_response_valid({'values': {}, 'errors': {}, 'error_kinds': {'m': 'transient'}})


def test_error_kinds_accepts_both_kinds() -> None:
    parsed = assert_query_response_valid(
        {
            'values': {'a': None, 'b': None},
            'errors': {'a': 'x', 'b': 'y'},
            'error_kinds': {'a': 'transient', 'b': 'data'},
        }
    )
    assert parsed.error_kinds == {'a': 'transient', 'b': 'data'}
