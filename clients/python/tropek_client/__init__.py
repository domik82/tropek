"""TROPEK Python client — typed API client with declarative YAML setup."""

from tropek_client.client import TropekClient
from tropek_client.exceptions import (
    TropekAPIError,
    TropekConflictError,
    TropekConnectionError,
    TropekNotFoundError,
    TropekServerError,
    TropekValidationError,
    ValidationDetail,
)

__all__ = [
    'TropekAPIError',
    'TropekClient',
    'TropekConflictError',
    'TropekConnectionError',
    'TropekNotFoundError',
    'TropekServerError',
    'TropekValidationError',
    'ValidationDetail',
]
