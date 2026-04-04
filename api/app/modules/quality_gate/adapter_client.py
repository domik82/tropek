"""HTTP implementation of the AdapterClient protocol."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger()


class HttpAdapterClient:
    """Concrete adapter client that queries adapters over HTTP."""

    def __init__(self, timeout: float, http_client: httpx.AsyncClient | None = None) -> None:
        self._timeout = timeout
        self._http_client = http_client

    async def query(
        self,
        *,
        adapter_url: str,
        datasource_name: str,
        queries: dict[str, dict[str, Any]],
        variables: dict[str, str],
        start: str,
        end: str,
    ) -> tuple[dict[str, float | None], dict[str, str], dict[str, Any]]:
        """Send metric queries to the adapter and return (values, errors, metadata).

        Args:
            adapter_url: Base URL of the adapter service.
            datasource_name: Datasource name forwarded in the X-Datasource-Name header.
            queries: Metric name to mode-aware query spec mapping.
            variables: Variable dict forwarded to the adapter for substitution.
            start: ISO timestamp for the evaluation period start.
            end: ISO timestamp for the evaluation period end.

        Returns:
            Tuple of (metrics_fetched, fetch_errors, metadata).

        Raises:
            httpx.ConnectError: If the adapter is unreachable.
            httpx.TimeoutException: If the adapter does not respond in time.
            httpx.HTTPStatusError: If the adapter returns a non-2xx response.
        """
        url = f'{adapter_url}/query'
        logger.info(
            'adapter request',
            url=url,
            datasource=datasource_name,
            query_count=len(queries),
            start=start,
            end=end,
            timeout=self._timeout,
        )
        if self._http_client is not None:
            resp = await self._http_client.post(
                url,
                headers={'X-Datasource-Name': datasource_name},
                json={
                    'queries': queries,
                    'variables': variables,
                    'start': start,
                    'end': end,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        else:
            async with httpx.AsyncClient(timeout=self._timeout) as http_client:
                resp = await http_client.post(
                    url,
                    headers={'X-Datasource-Name': datasource_name},
                    json={
                        'queries': queries,
                        'variables': variables,
                        'start': start,
                        'end': end,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

        metrics_fetched: dict[str, float | None] = {
            name: float(val) if val is not None else None for name, val in data.get('values', {}).items()
        }
        fetch_errors: dict[str, str] = {name: str(err) for name, err in data.get('errors', {}).items()}
        metadata: dict[str, Any] = data.get('metadata', {})
        logger.info(
            'adapter response',
            url=url,
            values_count=len(metrics_fetched),
            errors_count=len(fetch_errors),
            values=metrics_fetched,
            errors=fetch_errors,
            metadata=metadata,
        )
        return metrics_fetched, fetch_errors, metadata

    async def health(self, adapter_url: str) -> bool:
        """Check adapter health by hitting the /health endpoint.

        Args:
            adapter_url: Base URL of the adapter service.

        Returns:
            True if the adapter responds with a 2xx status, False otherwise.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as http_client:
                resp = await http_client.get(f'{adapter_url}/health')
                return bool(resp.is_success)
        except (httpx.ConnectError, httpx.TimeoutException):
            return False
