"""Structured exceptions for TROPEK API errors."""

from __future__ import annotations

import re

from pydantic import BaseModel


class ValidationDetail(BaseModel):
    """A single validation error from a 422 response."""

    loc: list[str]
    msg: str
    type: str


class TropekAPIError(Exception):
    """Base exception for all TROPEK API errors."""

    def __init__(self, status_code: int, detail: str, *, request_id: str | None = None) -> None:
        self.status_code = status_code
        self.detail = detail
        self.request_id = request_id
        super().__init__(f'HTTP {status_code}: {detail}')


class TropekNotFoundError(TropekAPIError):
    """Raised when a resource is not found (404)."""

    def __init__(
        self,
        status_code: int = 404,
        detail: str = '',
        *,
        entity: str | None = None,
        name: str | None = None,
        request_id: str | None = None,
    ) -> None:
        self.entity = entity
        self.name = name
        super().__init__(status_code, detail, request_id=request_id)


class TropekConflictError(TropekAPIError):
    """Raised when a resource conflict occurs (409)."""

    def __init__(
        self,
        status_code: int = 409,
        detail: str = '',
        *,
        entity: str | None = None,
        name: str | None = None,
        reason: str | None = None,
        request_id: str | None = None,
    ) -> None:
        self.entity = entity
        self.name = name
        self.reason = reason
        super().__init__(status_code, detail, request_id=request_id)


class TropekValidationError(TropekAPIError):
    """Raised when request validation fails (422)."""

    def __init__(
        self,
        status_code: int = 422,
        detail: str = '',
        *,
        errors: list[ValidationDetail] | None = None,
        request_id: str | None = None,
    ) -> None:
        self.errors = errors or []
        super().__init__(status_code, detail, request_id=request_id)


class TropekServerError(TropekAPIError):
    """Raised when the server returns a 5xx error."""


class TropekConnectionError(TropekAPIError):
    """Raised when the client cannot connect to the server."""

    def __init__(self, detail: str, *, request_id: str | None = None) -> None:
        super().__init__(0, detail, request_id=request_id)


_NOT_FOUND_PATTERN = re.compile(r"^(\w[\w\s]*?)\s+'([^']+)'\s+not found$")
_CONFLICT_PATTERN = re.compile(r"^(\w[\w\s]*?)\s+'([^']+)':\s+(.+)$")

_HTTP_NOT_FOUND = 404
_HTTP_CONFLICT = 409
_HTTP_UNPROCESSABLE = 422
_HTTP_SERVER_ERROR_THRESHOLD = 500


def parse_error_response(status_code: int, body: dict) -> TropekAPIError:
    """Parse an API error response body into a structured exception."""
    detail_raw = body.get('detail', '')

    if status_code == _HTTP_NOT_FOUND:
        detail_str = str(detail_raw)
        entity, name = None, None
        match = _NOT_FOUND_PATTERN.match(detail_str)
        if match:
            entity, name = match.group(1), match.group(2)
        return TropekNotFoundError(detail=detail_str, entity=entity, name=name)

    if status_code == _HTTP_CONFLICT:
        detail_str = str(detail_raw)
        entity, name, reason = None, None, None
        match = _CONFLICT_PATTERN.match(detail_str)
        if match:
            entity, name, reason = match.group(1), match.group(2), match.group(3)
        return TropekConflictError(detail=detail_str, entity=entity, name=name, reason=reason)

    if status_code == _HTTP_UNPROCESSABLE:
        errors: list[ValidationDetail] = []
        if isinstance(detail_raw, list):
            for item in detail_raw:
                loc = [str(part) for part in item.get('loc', [])]
                errors.append(ValidationDetail(loc=loc, msg=item.get('msg', ''), type=item.get('type', '')))
        detail_str = str(detail_raw) if not errors else 'validation failed'
        return TropekValidationError(detail=detail_str, errors=errors)

    if status_code >= _HTTP_SERVER_ERROR_THRESHOLD:
        return TropekServerError(status_code, str(detail_raw))

    return TropekAPIError(status_code, str(detail_raw))
