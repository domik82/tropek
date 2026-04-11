"""Shared domain exception types used across all modules."""

from __future__ import annotations


class DomainError(Exception):
    """Base for all domain errors."""


class NotFoundError(DomainError):
    """Entity not found."""

    def __init__(self, entity: str, name: str) -> None:
        self.entity = entity
        self.name = name
        super().__init__(f'{entity} {name!r} not found')


class ConflictError(DomainError):
    """Operation conflicts with existing state."""

    def __init__(self, entity: str, name: str, reason: str) -> None:
        self.entity = entity
        self.name = name
        self.reason = reason
        super().__init__(f'{entity} {name!r}: {reason}')


class DomainValidationError(DomainError):
    """Domain-level validation failure (not HTTP or Pydantic validation)."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)
