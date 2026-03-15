"""Typed exception hierarchy for tropek-client."""

from __future__ import annotations


class TropekError(Exception):
    """Base exception for all tropek-client errors."""


class TropekAPIError(TropekError):
    """HTTP error returned by the TROPEK API."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API error {status_code}: {detail}")


class TropekNotFoundError(TropekAPIError):
    """Resource not found (404)."""


class TropekValidationError(TropekAPIError):
    """Validation error (422)."""


class TropekConnectionError(TropekError):
    """Could not connect to the TROPEK API."""
