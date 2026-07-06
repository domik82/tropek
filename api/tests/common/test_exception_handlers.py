"""Unit tests for the shared HTTP exception handlers (no database required)."""

from __future__ import annotations

from starlette.exceptions import HTTPException
from starlette.requests import Request
from tropek.modules.common.exception_handlers import (
    _BODY_PARSE_ERROR_DETAIL,
    body_parse_error_handler,
)


def _request() -> Request:
    return Request({'type': 'http', 'method': 'GET', 'path': '/', 'headers': [], 'query_string': b''})


async def test_body_parse_error_remapped_to_422() -> None:
    """The generic body-parse 400 is re-emitted as a structured 422."""
    exc = HTTPException(status_code=400, detail=_BODY_PARSE_ERROR_DETAIL)
    response = await body_parse_error_handler(_request(), exc)
    assert response.status_code == 422
    assert b'body_parse_error' in response.body


async def test_no_body_status_yields_empty_body() -> None:
    """A no-body status (304) must not carry a JSON body, matching FastAPI's default."""
    exc = HTTPException(status_code=304)
    response = await body_parse_error_handler(_request(), exc)
    assert response.status_code == 304
    assert response.body == b''


async def test_dict_detail_preserved() -> None:
    """A conflict carrying a dict detail (e.g. baseline pin conflict) passes through intact."""
    exc = HTTPException(status_code=409, detail={'error': 'conflict', 'pin_id': 'abc'})
    response = await body_parse_error_handler(_request(), exc)
    assert response.status_code == 409
    assert b'pin_id' in response.body


async def test_headers_preserved() -> None:
    """Headers on the HTTPException survive the handler."""
    exc = HTTPException(status_code=405, detail='nope', headers={'Allow': 'GET'})
    response = await body_parse_error_handler(_request(), exc)
    assert response.status_code == 405
    assert response.headers['Allow'] == 'GET'
