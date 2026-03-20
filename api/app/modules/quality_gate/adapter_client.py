"""HTTP implementation of the AdapterClient protocol."""

from __future__ import annotations

import httpx


class HttpAdapterClient:
    """Concrete adapter client that queries adapters over HTTP."""

    def __init__(self, timeout: float) -> None:
        self._timeout = timeout

    async def query(
        self,
        *,
        adapter_url: str,
        datasource_name: str,
        queries: dict[str, str],
        start: str,
        end: str,
    ) -> tuple[dict[str, float | None], dict[str, str]]:
        """Send metric queries to the adapter and return (values, errors).

        Args:
            adapter_url: Base URL of the adapter service.
            datasource_name: Datasource name forwarded in the X-Datasource-Name header.
            queries: Metric name to query string mapping (variables substituted).
            start: ISO timestamp for the evaluation period start.
            end: ISO timestamp for the evaluation period end.

        Returns:
            Tuple of (metrics_fetched, fetch_errors).

        Raises:
            httpx.ConnectError: If the adapter is unreachable.
            httpx.TimeoutException: If the adapter does not respond in time.
            httpx.HTTPStatusError: If the adapter returns a non-2xx response.
        """
        async with httpx.AsyncClient(timeout=self._timeout) as http_client:
            resp = await http_client.post(
                f"{adapter_url}/query",
                headers={"X-Datasource-Name": datasource_name},
                json={"queries": queries, "start": start, "end": end},
            )
            resp.raise_for_status()
            data = resp.json()

        metrics_fetched: dict[str, float | None] = {
            name: float(val) if val is not None else None
            for name, val in data.get("values", {}).items()
        }
        fetch_errors: dict[str, str] = {
            name: str(err) for name, err in data.get("errors", {}).items()
        }
        return metrics_fetched, fetch_errors

    async def health(self, adapter_url: str) -> bool:
        """Check adapter health by hitting the /health endpoint.

        Args:
            adapter_url: Base URL of the adapter service.

        Returns:
            True if the adapter responds with a 2xx status, False otherwise.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as http_client:
                resp = await http_client.get(f"{adapter_url}/health")
                return bool(resp.is_success)
        except (httpx.ConnectError, httpx.TimeoutException):
            return False
