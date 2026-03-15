"""Typed exceptions for TROPEK API errors."""

from __future__ import annotations


class TropekAPIError(Exception):
    """Base exception for all TROPEK API errors."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


class TropekNotFoundError(TropekAPIError):
    """Raised when a resource is not found (404)."""

    def __init__(self, detail: str) -> None:
        super().__init__(404, detail)


class TropekConflictError(TropekAPIError):
    """Raised when a resource conflict occurs (409)."""

    def __init__(self, detail: str) -> None:
        super().__init__(409, detail)


class TropekValidationError(TropekAPIError):
    """Raised when request validation fails (422)."""

    def __init__(self, detail: str) -> None:
        super().__init__(422, detail)
