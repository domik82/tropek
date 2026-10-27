"""Strategy interface for query mode execution."""

from __future__ import annotations

from typing import Any, Protocol

from tropek_prometheus.core.strategies.models import StrategyResult


class QueryStrategy(Protocol):
    """Each query mode implements this interface."""

    async def execute(
        self,
        *,
        sli_name: str,
        query_spec: dict[str, Any],
        variables: dict[str, str],
        start: str,
        end: str,
    ) -> StrategyResult:
        """Execute a query and return one outcome per indicator.

        Indicators are keyed by metric name (a single entry for raw mode). An outcome with ``error`` set
        failed; its ``error_kind`` is ``'transient'`` when a retry may succeed (the fetch failed) and
        ``'data'`` when the source has no answer (a rejected query, an unresolved variable, or a
        complete but empty result). ``metadata`` carries sample counts and is ``None`` for raw mode.
        """
        ...
