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


def reject_null_bytes_in_dict(input_dict: dict[str, object]) -> dict[str, object]:
    r"""Reject JSONB dict keys or string values containing null bytes (\x00).

    asyncpg raises UntranslatableCharacterError when a null byte appears in any
    PostgreSQL text value, including JSONB keys and string values.  This validator
    walks every key and every value that is a plain string and raises ValueError on
    the first occurrence, converting what would be a 500 into a 422.

    Non-string values (int, float, bool, None, nested dicts/lists) are left
    untouched — the check is deliberately shallow; it does not recurse into nested
    structures because TROPEK's JSONB fields that use this type are flat string maps.

    Note: Pydantic v2 / OpenAPI does not have a clean way to emit patternProperties
    on dict keys, so the null-byte constraint is enforced only at the validator level
    (not in the generated JSON Schema).  The 500→422 conversion is the primary goal.
    """
    for dict_key, dict_value in input_dict.items():
        if '\x00' in dict_key:
            raise ValueError('null bytes are not allowed in dict keys')
        if isinstance(dict_value, str) and '\x00' in dict_value:
            raise ValueError('null bytes are not allowed in dict values')
    return input_dict


# SafeStr — validates null bytes are absent and declares the constraint in the
# JSON Schema via a pattern so schemathesis (and other tooling) will not
# generate strings containing \x00, avoiding spurious RejectedPositiveData
# failures on all request-body string fields.
SafeStr = Annotated[
    str,
    Field(pattern=r'^[^\x00]*$'),
    AfterValidator(reject_null_bytes),
]

# SafeJsonDict — validates that no JSONB dict key or string value contains null
# bytes, preventing asyncpg UntranslatableCharacterError (500) on write.
# Pydantic v2 does not support patternProperties on dict keys in OpenAPI output,
# so the constraint is runtime-only (no JSON Schema annotation).  The validator
# still converts 500 → 422 for schemathesis and real clients.
SafeJsonDict = Annotated[dict[str, str | None], AfterValidator(reject_null_bytes_in_dict)]

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
