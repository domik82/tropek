"""HTTP implementation of the AdapterClient protocol."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class AdapterQueryResponse(BaseModel):
    """Expected JSON shape returned by any TROPEK-compatible adapter's POST /query."""

    values: dict[str, float | None] = Field(default_factory=dict)
    errors: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, dict[str, Any]] = Field(default_factory=dict)


_TRANSIENT_ERRORS = (httpx.ReadError, httpx.ConnectError)
_MAX_RETRIES = 3
_RETRY_BACKOFF_SECONDS = (0.5, 1.0, 2.0)


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

        Retries up to 3 times on transient connection errors (broken keep-alive,
        connection reset) with exponential backoff.

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
            httpx.ConnectError: If the adapter is unreachable after all retries.
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
        payload = {
            'queries': queries,
            'variables': variables,
            'start': start,
            'end': end,
        }
        headers = {'X-Datasource-Name': datasource_name}

        resp = await self._post_with_retry(url, headers=headers, payload=payload)

        resp.raise_for_status()
        parsed = AdapterQueryResponse.model_validate(resp.json())
        metrics_fetched: dict[str, float | None] = dict(parsed.values)
        fetch_errors: dict[str, str] = dict(parsed.errors)
        metadata: dict[str, Any] = dict(parsed.metadata)
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

    async def _post_with_retry(
        self,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> httpx.Response:
        """POST with retry on transient connection errors."""
        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                if self._http_client is not None:
                    return await self._http_client.post(url, headers=headers, json=payload)
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    return await client.post(url, headers=headers, json=payload)
            except _TRANSIENT_ERRORS as error:
                last_error = error
                backoff = _RETRY_BACKOFF_SECONDS[attempt]
                logger.warning(
                    'adapter request failed, retrying',
                    url=url,
                    attempt=attempt + 1,
                    max_retries=_MAX_RETRIES,
                    backoff_seconds=backoff,
                    error=str(error),
                )
                await asyncio.sleep(backoff)
        raise last_error  # type: ignore[misc]

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
