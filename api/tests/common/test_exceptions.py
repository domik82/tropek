"""Tests for shared domain exceptions."""

from __future__ import annotations

from tropek.modules.common.exceptions import (
    ConflictError,
    DomainError,
    DomainValidationError,
    NotFoundError,
)


def test_not_found_error_message() -> None:
    exc = NotFoundError('asset', 'vm-01')
    assert str(exc) == "asset 'vm-01' not found"
    assert exc.entity == 'asset'
    assert exc.name == 'vm-01'


def test_not_found_is_domain_error() -> None:
    assert issubclass(NotFoundError, DomainError)


def test_conflict_error_message() -> None:
    exc = ConflictError('asset type', 'host', 'in use by 3 assets')
    assert str(exc) == "asset type 'host': in use by 3 assets"
    assert exc.entity == 'asset type'
    assert exc.name == 'host'
    assert exc.reason == 'in use by 3 assets'


def test_conflict_is_domain_error() -> None:
    assert issubclass(ConflictError, DomainError)


def test_domain_validation_error_message() -> None:
    exc = DomainValidationError('slo name is required')
    assert str(exc) == 'slo name is required'
    assert exc.detail == 'slo name is required'


def test_domain_validation_is_domain_error() -> None:
    assert issubclass(DomainValidationError, DomainError)
