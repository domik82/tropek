"""Async HTTP wrapper for the Prometheus query API."""

from __future__ import annotations

import logging
import math
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class PrometheusQueryError(Exception):
    """Raised when a Prometheus query fails or returns invalid data."""


class PrometheusClient:
    """Thin async client for Prometheus instant and range queries."""

    def __init__(
        self,
        base_url: str,
        timeout: float,
        auth: tuple[str, str] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip('/')
        self._timeout = timeout
        self._auth = auth
        logger.info('prometheus client configured: url=%s timeout=%s', self._base_url, self._timeout)

    async def instant_query(self, query: str, *, time: str) -> float:
        """Execute an instant query and return a single float value.

        Raises PrometheusQueryError on any failure.
        """
        params = {'query': query, 'time': time}
        data = await self._get('/api/v1/query', params)
        return self._extract_scalar(data)

    async def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        url = f'{self._base_url}{path}'
        logger.debug('prometheus request: GET %s params=%s', url, params)
        auth = httpx.BasicAuth(*self._auth) if self._auth else None
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout, auth=auth) as client:
                resp = await client.get(path, params=params)
        except httpx.ConnectError as exc:
            logger.exception('prometheus unreachable at %s', self._base_url)
            raise PrometheusQueryError(f'could not connect to prometheus at {self._base_url}') from exc
        except httpx.TimeoutException as exc:
            logger.exception('prometheus request timed out: %s (timeout=%ss)', url, self._timeout)
            raise PrometheusQueryError(f'prometheus request timed out after {self._timeout}s') from exc
        if resp.status_code != 200:  # noqa: PLR2004
            logger.error('prometheus error: status=%d body=%s', resp.status_code, resp.text[:200])
            raise PrometheusQueryError(f'prometheus returned {resp.status_code}: {resp.text[:200]}')
        body: dict[str, Any] = resp.json()
        if body.get('status') != 'success':
            logger.error('prometheus query failed: %s', body.get('error', 'unknown'))
            raise PrometheusQueryError(f'prometheus error: {body.get("error", "unknown")}')
        data: dict[str, Any] = body['data']
        return data

    def _extract_scalar(self, data: dict[str, Any]) -> float:
        result_type = data['resultType']

        if result_type == 'scalar':
            return self._parse_value(data['result'][1])

        if result_type == 'vector':
            results = data['result']
            if len(results) == 0:
                raise PrometheusQueryError('query returned 0 results')
            if len(results) > 1:
                raise PrometheusQueryError(f'query returned {len(results)} results, expected exactly 1')
            return self._parse_value(results[0]['value'][1])

        raise PrometheusQueryError(f'unexpected result type: {result_type}')

    def _parse_value(self, raw: str) -> float:
        val = float(raw)
        if math.isnan(val) or math.isinf(val):
            raise PrometheusQueryError(f'query returned {raw}')
        return val
