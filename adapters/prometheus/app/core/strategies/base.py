"""Strategy interface for query mode execution."""

from typing import Protocol


class QueryStrategy(Protocol):
    """Each query mode implements this interface."""

    async def execute(
        self,
        *,
        sli_name: str,
        query_spec: dict,
        variables: dict[str, str],
        start: str,
        end: str,
    ) -> tuple[dict[str, float | None], dict[str, str], dict | None]:
        """Execute a query and return (values, errors, metadata).

        Returns:
            values: {metric_name: float_value} — for raw mode, single entry.
            errors: {metric_name: error_message} — for failed queries.
            metadata: Optional metadata dict (sample counts, etc.). None for raw mode.
        """
        ...
