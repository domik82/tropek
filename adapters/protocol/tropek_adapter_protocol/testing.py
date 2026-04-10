"""Test utilities for adapter conformance testing.

Usage in adapter test suites:

    from tropek_adapter_protocol.testing import assert_query_response_valid

    async def test_query_endpoint(client):
        resp = await client.post('/query', json={...})
        assert_query_response_valid(resp.json())
"""

from __future__ import annotations

from typing import Any

from tropek_adapter_protocol.models import AdapterHealthResponse, AdapterQueryResponse


def assert_query_response_valid(data: dict[str, Any]) -> AdapterQueryResponse:
    """Validate a raw JSON dict conforms to AdapterQueryResponse.

    Raises pydantic.ValidationError with details if the response shape is wrong.
    Returns the parsed model on success.
    """
    return AdapterQueryResponse.model_validate(data)


def assert_health_response_valid(data: dict[str, Any]) -> AdapterHealthResponse:
    """Validate a raw JSON dict conforms to AdapterHealthResponse."""
    return AdapterHealthResponse.model_validate(data)
