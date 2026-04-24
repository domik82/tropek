"""Shared Pydantic schemas."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Query
from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field


def reject_null_bytes(value: str) -> str:
    r"""Reject strings containing null bytes (\x00), which break asyncpg."""
    if '\x00' in value:
        raise ValueError('null bytes are not allowed')
    return value


def reject_null_bytes_recursive(value: object) -> object:
    r"""Recursively reject null bytes (\x00) in any string within a JSONB structure.

    Walks dicts, lists, and strings. For dicts it also validates that no key
    contains a null byte. Used on request-body fields typed as dict[str, Any]
    (e.g. annotation tags, heatmap_config) where schemathesis can nest arbitrary
    structures past the top-level `reject_null_bytes_in_dict` check.
    """
    if isinstance(value, str):
        if '\x00' in value:
            raise ValueError('null bytes are not allowed')
    elif isinstance(value, dict):
        for dict_key, dict_value in value.items():
            if isinstance(dict_key, str) and '\x00' in dict_key:
                raise ValueError('null bytes are not allowed in dict keys')
            reject_null_bytes_recursive(dict_value)
    elif isinstance(value, list):
        for item in value:
            reject_null_bytes_recursive(item)
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
SafeJsonDict = Annotated[dict[str, str], AfterValidator(reject_null_bytes_in_dict)]

# SafeJsonAny — for JSONB request-body fields that accept arbitrarily nested
# structures (e.g. annotation tags, heatmap_config). Walks the full tree and
# rejects null bytes in any key or string value, converting asyncpg's
# UntranslatableCharacterError (500) into a 422.
SafeJsonAny = Annotated[dict[str, Any], AfterValidator(reject_null_bytes_recursive)]

# SafeQueryStr — use as a FastAPI query-parameter type to apply the same
# null-byte validation that SafeStr provides for request body fields.
SafeQueryStr = Annotated[str, Query(pattern=r'^[^\x00]*$'), AfterValidator(reject_null_bytes)]


# TagKey — K8s label key syntax: alphanumeric with -_. separators, must start
# and end with alphanumeric. 1-63 chars. Used for Tags dict keys so schemathesis
# generates realistic values that the DB/UI will accept.
TagKey = Annotated[
    str,
    Field(
        min_length=1,
        max_length=63,
        pattern=r'^[A-Za-z0-9]([-A-Za-z0-9_.]{0,61}[A-Za-z0-9])?$',
        description='alphanumeric with -_. separators, 1-63 chars, K8s label key syntax',
    ),
]

# TagValue — K8s label value syntax: alphanumeric with -_. separators, must
# start and end with alphanumeric if non-empty. 0-63 chars (empty allowed).
TagValue = Annotated[
    str,
    Field(
        max_length=63,
        pattern=r'^(([A-Za-z0-9][-A-Za-z0-9_.]{0,61})?[A-Za-z0-9])?$',
        description='alphanumeric with -_. separators, 0-63 chars, K8s label value syntax',
    ),
]

# Tags — dict of constrained K8s-style key/value string pairs. Replaces
# dict[str, Any]/dict[str, str] tag fields so fuzzers generate realistic
# payloads and unconstrained edge cases (null bytes, control chars) are
# rejected by the schema rather than a downstream validator.
Tags = dict[TagKey, TagValue]

# IdentifierKey — programming-identifier / Prometheus label name style: starts
# with letter or underscore, followed by letters, digits, or underscores.
# 1-128 chars. Used for dict keys that represent SLI indicator names or
# template variable names.
IdentifierKey = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r'^[A-Za-z_][A-Za-z0-9_]*$',
        description='programming-identifier style key (Prometheus label name style)',
    ),
]


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


def _reject_bool(value: object) -> object:
    """Reject Python booleans passed where a number is expected.

    isinstance(True, int) is True, so plain `int`/`float` fields accept booleans
    by default. Pure StrictInt/StrictFloat rejects bools *but also* rejects
    JSON whole-number-float representations like 2147483646.0 that are
    wire-valid for integer fields. This BeforeValidator rejects only bools,
    leaving Pydantic's default coercion of whole-number floats intact.
    """
    if isinstance(value, bool):
        raise ValueError('boolean is not a valid number')
    return value


# IntNotBool — accepts int or JSON whole-number-float, rejects bool.
# Use on request-body int fields where schemathesis would otherwise send
# 2147483646.0 and hit StrictInt rejection.  Range clamped to int32 to
# match PostgreSQL INTEGER columns.
IntNotBool = Annotated[int, Field(ge=-(2**31), le=2**31 - 1), BeforeValidator(_reject_bool)]

# FloatNotBool — same rationale for float fields.
FloatNotBool = Annotated[float, BeforeValidator(_reject_bool)]


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
