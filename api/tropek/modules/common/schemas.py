"""Shared Pydantic schemas."""

from __future__ import annotations

from typing import Annotated

from fastapi import Query
from pydantic import AfterValidator, BaseModel, ConfigDict, Field


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
