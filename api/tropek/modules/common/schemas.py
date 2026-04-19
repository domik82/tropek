"""Shared Pydantic schemas."""

from __future__ import annotations

from typing import Annotated

from fastapi import Query
from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field


def reject_null_bytes(value: str) -> str:
    r"""Reject strings containing null bytes (\x00), which break asyncpg."""
    if '\x00' in value:
        raise ValueError('null bytes are not allowed')
    return value


# SafeStr — validates null bytes are absent and declares the constraint in the
# JSON Schema via a pattern so schemathesis (and other tooling) will not
# generate strings containing \x00, avoiding spurious RejectedPositiveData
# failures on all request-body string fields.
SafeStr = Annotated[
    str,
    Field(pattern=r'^[^\x00]*$'),
    AfterValidator(reject_null_bytes),
]

# SafeQueryStr — use as a FastAPI query-parameter type to apply the same
# null-byte validation that SafeStr provides for request body fields.
SafeQueryStr = Annotated[str, Query(pattern=r'^[^\x00]*$'), AfterValidator(reject_null_bytes)]


def _strict_bool_str(value: object) -> bool:
    """Reject non-boolean strings like '0', '1', 'yes', 'no', 'on', 'off'.

    FastAPI's default bool query-param parsing is lenient (accepts integers and
    many string aliases). This validator restricts acceptance to the canonical
    'true' / 'false' strings and actual Python booleans so that schemathesis
    negative-data checks (sending 0 for a boolean parameter) get the expected 422.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in ('true', 'false'):
        return value.lower() == 'true'
    raise ValueError('value is not a valid boolean')


# StrictQueryBool — a strict boolean for FastAPI query parameters that only
# accepts 'true'/'false' strings (case-insensitive), rejecting integer-like
# values ('0', '1') that FastAPI's lenient bool parsing would otherwise accept.
StrictQueryBool = Annotated[bool, Query(), BeforeValidator(_strict_bool_str)]


class StrictInput(BaseModel):
    """Base for all API request body models — rejects unknown fields."""

    model_config = ConfigDict(extra='forbid')


class PagedResponse[T](BaseModel):
    """Generic paginated list response."""

    items: list[T]
    total: int


class TagKeyCount(BaseModel):
    """A tag key with its usage count."""

    key: str
    count: int


class TagValueCount(BaseModel):
    """A tag value with its usage count for a specific key."""

    value: str
    count: int
