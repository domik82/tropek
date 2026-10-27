"""Async HTTP wrapper for the Prometheus query API."""

from __future__ import annotations

import asyncio
import logging
import math
from typing import Any

import httpx

from tropek_prometheus.core.retry import compute_backoff

logger = logging.getLogger(__name__)

HTTP_OK = 200
_TRANSIENT_STATUS = frozenset({429, 500, 502, 503, 504})


class PrometheusQueryError(Exception):
    """Raised when a Prometheus query fails or returns invalid data.

    Attributes:
        transient: ``True`` when retrying the same request may succeed (timeout, overload, 5xx).
        retry_after: Raw ``Retry-After`` response header, when the failing response carried one.
    """

    def __init__(self, message: str, *, transient: bool = False, retry_after: str | None = None) -> None:
        super().__init__(message)
        self.transient = transient
        self.retry_after = retry_after


class PrometheusClient:
    """Thin async client for Prometheus instant and range queries."""

    def __init__(
        self,
        base_url: str,
        timeout: float,
        auth: tuple[str, str] | None = None,
        *,
        retry_attempts: int = 3,
        retry_backoff_seconds: float = 1.0,
        max_in_flight: int = 8,
    ) -> None:
        self._base_url = base_url.rstrip('/')
        self._timeout = timeout
        self._auth = auth
        self._retry_attempts = retry_attempts
        self._retry_backoff_seconds = retry_backoff_seconds
        self._request_slots = asyncio.Semaphore(max_in_flight)
        self._in_flight = 0
        logger.info(f'prometheus client configured: url={self._base_url} timeout={self._timeout}')

    @property
    def in_flight(self) -> int:
        """Number of Prometheus requests currently in flight across all callers."""
        return self._in_flight

    async def instant_query(self, query: str, *, time: str) -> float:
        """Execute an instant query and return a single float value.

        Raises PrometheusQueryError on any failure.
        """
        params = {'query': query, 'time': time}
        data = await self._get('/api/v1/query', params)
        return self._extract_scalar(data)

    async def range_query(
        self,
        query: str,
        *,
        start: str,
        end: str,
        step: str,
    ) -> list[float]:
        """Execute a range query and return a flat list of float values.

        All series in the matrix result are concatenated into a single list. Callers that need to
        know how many series the query fanned out to should use :meth:`range_query_series` instead.
        NaN/Inf values are preserved (caller is responsible for filtering).

        Raises PrometheusQueryError on any failure.
        """
        series = await self.range_query_series(query, start=start, end=end, step=step)
        return [value for bucket in series for value in bucket]

    async def range_query_series(
        self,
        query: str,
        *,
        start: str,
        end: str,
        step: str,
    ) -> list[list[float]]:
        """Execute a range query and return one list of float values per series.

        Preserving the series boundaries lets callers reason about sample coverage: a query that
        fans out to N series returns N buckets, each holding that series' own points.
        NaN/Inf values are preserved (caller is responsible for filtering).

        :param str query: PromQL query to evaluate.
        :param str start: Range start, as accepted by the Prometheus API.
        :param str end: Range end, as accepted by the Prometheus API.
        :param str step: Query resolution step.
        :returns: One list of values per series in the matrix result.
        :rtype: list[list[float]]
        :raises PrometheusQueryError: On transport failure, a non-200 response, or a non-matrix result.
        """
        params = {'query': query, 'start': start, 'end': end, 'step': step}
        data = await self._get('/api/v1/query_range', params)
        return self._extract_matrix_series(data)

    def _extract_matrix_series(self, data: dict[str, Any]) -> list[list[float]]:
        result_type = data['resultType']
        if result_type != 'matrix':
            raise PrometheusQueryError(f'expected matrix result type, got: {result_type}')

        return [[float(raw) for _ts, raw in series['values']] for series in data['result']]

    async def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        """Run a GET against Prometheus, retrying transient failures with backoff.

        Every attempt holds a slot of the process-wide semaphore only while the request is in flight, so
        the backoff sleep does not starve other callers.

        Args:
            path: API path, e.g. ``/api/v1/query``.
            params: Query-string parameters.

        Returns:
            The ``data`` object of a successful Prometheus response.

        Raises:
            PrometheusQueryError: On a final failure, or when transient failures exhaust the attempts.
        """
        url = f'{self._base_url}{path}'
        logger.info(f'prometheus query: GET {url} query={params.get("query", "?")}')
        auth = httpx.BasicAuth(*self._auth) if self._auth else None
        attempt = 1
        while True:
            async with self._request_slots:
                self._in_flight += 1
                try:
                    attempt_result = await self._get_once(path, params, auth)
                finally:
                    self._in_flight -= 1
            if isinstance(attempt_result, dict):
                return attempt_result
            if attempt_result.transient and attempt < self._retry_attempts:
                delay = compute_backoff(
                    attempt, base_seconds=self._retry_backoff_seconds, retry_after=attempt_result.retry_after
                )
                logger.warning(
                    f'prometheus request retried: url={url} attempt={attempt}/{self._retry_attempts} '
                    f'backoff={delay:.2f}s cause={attempt_result}'
                )
                await asyncio.sleep(delay)
                attempt += 1
                continue
            logger.error(
                f'prometheus request failed: url={url} cause={attempt_result}',
                exc_info=attempt_result if attempt_result.__cause__ is not None else None,
            )
            if attempt_result.transient:
                raise PrometheusQueryError(
                    f'{attempt_result} (after {self._retry_attempts} attempts)', transient=True
                ) from attempt_result
            raise attempt_result

    async def _get_once(
        self, path: str, params: dict[str, str], auth: httpx.BasicAuth | None
    ) -> dict[str, Any] | PrometheusQueryError:
        """Perform one request and classify the outcome instead of raising.

        Failures are not logged here: ``_get`` logs a retried attempt as a warning and the final one with its cause.

        Args:
            path: API path, e.g. ``/api/v1/query``.
            params: Query-string parameters.
            auth: Basic-auth handler, or ``None`` to query without credentials.

        Returns:
            The ``data`` object on success, otherwise a ``PrometheusQueryError`` whose ``transient`` flag says
            whether retrying can help. A transport failure is attached as the error's ``__cause__``.
        """
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout, auth=auth) as client:
                response = await client.get(path, params=params)
        except httpx.ConnectError as transport_error:
            return self._transport_failure(f'could not connect to prometheus at {self._base_url}', transport_error)
        except httpx.TimeoutException as transport_error:
            return self._transport_failure(f'prometheus request timed out after {self._timeout}s', transport_error)
        except httpx.TransportError as transport_error:
            # A dropped or garbled connection (ReadError, RemoteProtocolError, ...) says nothing about the
            # query; escaping unwrapped it would be recorded as a data error and never retried.
            return self._transport_failure(
                f'prometheus transport error: {type(transport_error).__name__}: {transport_error}', transport_error
            )
        if response.status_code != HTTP_OK:
            return PrometheusQueryError(
                f'prometheus returned {response.status_code}: {response.text[:200]}',
                transient=response.status_code in _TRANSIENT_STATUS,
                retry_after=response.headers.get('Retry-After'),
            )
        body: dict[str, Any] = response.json()
        if body.get('status') != 'success':
            return PrometheusQueryError(f'prometheus error: {body.get("error", "unknown")}')
        data: dict[str, Any] = body['data']
        return data

    @staticmethod
    def _transport_failure(message: str, transport_error: httpx.TransportError) -> PrometheusQueryError:
        """Build a transient error for a transport failure and keep the original as its cause.

        Args:
            message: Description of the failure.
            transport_error: The httpx error, attached as ``__cause__`` so the final log keeps its traceback.

        Returns:
            A ``PrometheusQueryError`` with ``transient=True``.
        """
        error = PrometheusQueryError(message, transient=True)
        error.__cause__ = transport_error
        return error

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
