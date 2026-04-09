"""Formal adapter query contract as a Protocol.

Defines the interface that any adapter client (HTTP, mock, etc.) must satisfy
for querying metric values from data source adapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class AdapterQueryRequest:
    """Request payload for an adapter metric query."""

    queries: dict[str, dict[str, Any]]  # metric_name → {"mode": "raw", "query": "..."} or aggregated spec
    variables: dict[str, str] = field(default_factory=dict)
    start: str = ''
    end: str = ''


@dataclass
class AdapterQueryResponse:
    """Response payload from an adapter metric query."""

    values: dict[str, float | None] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, dict[str, Any]] = field(default_factory=dict)


class AdapterClient(Protocol):
    """Protocol defining the adapter client contract."""

    async def query(
        self,
        *,
        adapter_url: str,
        datasource_name: str,
        queries: dict[str, dict[str, Any]],
        variables: dict[str, str],
        start: str,
        end: str,
    ) -> tuple[dict[str, float | None], dict[str, str]]:
        """Query an adapter for metric values. Returns (values, errors)."""
        ...

    async def health(self, adapter_url: str) -> bool:
        """Check adapter health."""
        ...
