"""TROPEK adapter protocol — canonical contract for data source adapters."""

from tropek_adapter_protocol.models import (
    AdapterHealthResponse,
    AdapterQueryRequest,
    AdapterQueryResponse,
)

__all__ = [
    'AdapterHealthResponse',
    'AdapterQueryRequest',
    'AdapterQueryResponse',
]
