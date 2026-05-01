"""Unit tests for constrained input types in tropek.modules.common.schemas."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError
from tropek.modules.common.schemas import IdentifierKey, TagKey, Tags, TagValue


class _TagKeyModel(BaseModel):
    value: TagKey


class _TagValueModel(BaseModel):
    value: TagValue


class _TagsModel(BaseModel):
    tags: Tags


class _IdentifierKeyModel(BaseModel):
    value: IdentifierKey


# ---- TagKey ----


@pytest.mark.parametrize(
    'good',
    [
        'a',
        'app',
        'App1',
        'my-key',
        'my_key',
        'my.key',
        'v1.2.3',
        'A' * 63,
    ],
)
def test_tag_key_accepts_valid(good: str) -> None:
    assert _TagKeyModel(value=good).value == good


@pytest.mark.parametrize(
    'bad',
    [
        '',  # empty
        '-leading',  # leading non-alphanumeric
        '.leading',  # leading non-alphanumeric
        '_leading',  # leading non-alphanumeric
        'trailing-',  # trailing non-alphanumeric
        'trailing.',  # trailing non-alphanumeric
        'trailing_',  # trailing non-alphanumeric
        'has space',  # invalid char
        'has/slash',  # invalid char
        'null\x00byte',  # null byte
        'ctrl\x07char',  # control char
        'rtl\u202eoverride',  # RTL override
        'A' * 64,  # over length
    ],
)
def test_tag_key_rejects_invalid(bad: str) -> None:
    with pytest.raises(ValidationError):
        _TagKeyModel(value=bad)


# ---- TagValue ----


@pytest.mark.parametrize(
    'good',
    [
        '',  # empty allowed for values
        'a',
        'prod',
        'v1.2.3',
        'my-value_ok.1',
        'A' * 63,
    ],
)
def test_tag_value_accepts_valid(good: str) -> None:
    assert _TagValueModel(value=good).value == good


@pytest.mark.parametrize(
    'bad',
    [
        '-leading',
        '.leading',
        '_leading',
        'trailing-',
        'trailing.',
        'trailing_',
        'has space',
        'null\x00byte',
        'ctrl\x07char',
        'rtl\u202eoverride',
        'A' * 64,
    ],
)
def test_tag_value_rejects_invalid(bad: str) -> None:
    with pytest.raises(ValidationError):
        _TagValueModel(value=bad)


# ---- Tags (dict[TagKey, TagValue]) ----


def test_tags_accepts_valid_mapping() -> None:
    payload = {'env': 'prod', 'app.name': 'tropek', 'v1': ''}
    assert _TagsModel(tags=payload).tags == payload


def test_tags_rejects_invalid_key() -> None:
    with pytest.raises(ValidationError):
        _TagsModel(tags={'-bad': 'ok'})


def test_tags_rejects_invalid_value() -> None:
    with pytest.raises(ValidationError):
        _TagsModel(tags={'ok': 'bad-'})


def test_tags_rejects_null_byte_in_key() -> None:
    with pytest.raises(ValidationError):
        _TagsModel(tags={'k\x00ey': 'ok'})


# ---- IdentifierKey ----


@pytest.mark.parametrize(
    'good',
    [
        '_',
        'a',
        'response_time',
        '_private',
        'http_requests_total',
        'A' * 128,
    ],
)
def test_identifier_key_accepts_valid(good: str) -> None:
    assert _IdentifierKeyModel(value=good).value == good


@pytest.mark.parametrize(
    'bad',
    [
        '',  # empty
        '1leading',  # leading digit
        '-leading',  # leading non-identifier
        '.leading',  # leading non-identifier
        'has space',  # invalid char
        'has-dash',  # dash not allowed
        'has.dot',  # dot not allowed
        'null\x00byte',  # null byte
        'ctrl\x07char',  # control char
        'rtl\u202eoverride',  # RTL override
        'A' * 129,  # over length
    ],
)
def test_identifier_key_rejects_invalid(bad: str) -> None:
    with pytest.raises(ValidationError):
        _IdentifierKeyModel(value=bad)
