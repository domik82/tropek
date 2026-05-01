"""TROPEK Python client — typed API client with declarative YAML setup."""

# from tropek_client.client import TropekClient  # TODO: uncomment after all models are created
from tropek_client.exceptions import (
    TropekAPIError,
    TropekConflictError,
    TropekNotFoundError,
    TropekValidationError,
)

__all__ = [
    'TropekAPIError',
    # 'TropekClient',  # TODO: uncomment after all models are created
    'TropekConflictError',
    'TropekNotFoundError',
    'TropekValidationError',
]
