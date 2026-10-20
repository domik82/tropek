"""HTTP implementation of the AdapterClient protocol."""

from __future__ import annotations

import asyncio
import math
import random
import time
from datetime import UTC, datetime
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
    error_kinds: dict[str, str] = Field(default_factory=dict)


_RETRYABLE_STATUS = frozenset({429, 502, 503, 504})
_GATEWAY_TIMEOUT = 504
# A 504 whose JSON ``detail`` mentions the budget: the adapter waited the whole budget for its job.
_BUDGET_EXHAUSTED_MARKER = 'budget'
_MAX_BACKOFF_SECONDS = 60.0


class AdapterRetryPolicy(BaseModel):
    """How the worker retries a failed hop to the adapter."""

    attempts: int = Field(default=3, ge=1)
    backoff_seconds: float = Field(default=2.0, ge=0)
    jitter: float = Field(default=0.25, ge=0, lt=1)


class AdapterFetchError(Exception):
    """The adapter could not be reached or kept answering with an error after all attempts.

    ``retryable`` is False when a rerun of the job cannot help (a 4xx other than 429, a malformed answer);
    the job then stores the evaluation ``failed`` at once instead of retrying it.
    """

    def __init__(
        self,
        cause: str,
        *,
        attempts: int,
        last_status: int | None,
        elapsed_s: float,
        retryable: bool = True,
    ) -> None:
        super().__init__(cause)
        self.cause = cause
        self.attempts = attempts
        self.last_status = last_status
        self.elapsed_s = elapsed_s
        self.retryable = retryable

    def as_attempt_record(self) -> dict[str, Any]:
        """Describe this failure as one attempt-history entry.

        Returns:
            Dict with ``cause``, ``status``, ``elapsed_s`` and ``at`` (ISO-8601 UTC timestamp).
        """
        return {
            'cause': self.cause,
            'status': self.last_status,
            'elapsed_s': round(self.elapsed_s, 3),
            'at': datetime.now(UTC).isoformat(),
        }


def _compute_backoff(attempt: int, *, base_seconds: float, retry_after: str | None, jitter: float = 0.25) -> float:
    """Return the seconds to wait after a failed attempt, never more than 60.

    A numeric, finite ``Retry-After`` wins; an HTTP-date or non-finite value is ignored and the
    exponential value ``base_seconds * 2 ** (attempt - 1)`` with +/- ``jitter`` noise is used.

    Args:
        attempt: The 1-based number of the attempt that just failed.
        base_seconds: Delay after the first failed attempt; doubles for each further one.
        retry_after: Raw ``Retry-After`` header value, or ``None`` when the response had none.
        jitter: Relative noise applied to the exponential delay (``0`` disables it).

    Returns:
        Seconds to sleep before the next attempt, between 0 and 60.
    """
    delay: float | None = None
    if retry_after is not None:
        try:
            parsed = float(retry_after)
        except ValueError:
            parsed = math.nan
        if math.isfinite(parsed):
            delay = parsed
    if delay is None:
        delay = base_seconds * (2.0 ** (attempt - 1))
        if jitter:
            delay *= 1 + random.uniform(-jitter, jitter)  # noqa: S311 - not security sensitive
    return min(max(delay, 0.0), _MAX_BACKOFF_SECONDS)


def _is_budget_exhausted(response: httpx.Response) -> bool:
    """Tell whether a 504 says the adapter waited its whole budget (as opposed to a quick gateway error)."""
    if response.status_code != _GATEWAY_TIMEOUT:
        return False
    try:
        body = response.json()
    except ValueError:
        return False
    detail = body.get('detail') if isinstance(body, dict) else None
    return isinstance(detail, str) and _BUDGET_EXHAUSTED_MARKER in detail


def _raise_unless_quick_failure(response: httpx.Response, *, cause: str, attempt: int, started: float) -> None:
    """Raise for an error answer that must not be retried over HTTP; return for a quick, retryable one.

    Args:
        response: A non-2xx adapter answer.
        cause: The cause recorded for this attempt.
        attempt: The 1-based number of the attempt that got the answer.
        started: ``time.perf_counter()`` when the first attempt started.

    Raises:
        AdapterFetchError: For a budget-exhausted 504 (retryable by the job) or a status outside
            429/502/503/504 (retryable by the job unless it is a 4xx, which would fail the same way).
    """
    if _is_budget_exhausted(response):
        raise AdapterFetchError(
            f'{cause}: budget exhausted',
            attempts=attempt,
            last_status=response.status_code,
            elapsed_s=time.perf_counter() - started,
        )
    if response.status_code not in _RETRYABLE_STATUS:
        raise AdapterFetchError(
            cause,
            attempts=attempt,
            last_status=response.status_code,
            elapsed_s=time.perf_counter() - started,
            retryable=not response.is_client_error,
        )


class HttpAdapterClient:
    """Concrete adapter client that queries adapters over HTTP.

    Quick failures (transport errors other than timeouts, 429, 502, 503, a plain 504) are retried over HTTP.
    Long failures (a timeout, a 504 whose budget was exhausted) and any attempt that would not finish before
    the job deadline are raised at once as a retryable ``AdapterFetchError``, so the job-level retry, which
    the database counts, takes over.
    """

    def __init__(
        self,
        timeout: float,
        http_client: httpx.AsyncClient | None = None,
        *,
        policy: AdapterRetryPolicy | None = None,
        budget_seconds: int | None = None,
        deadline_seconds: float | None = None,
    ) -> None:
        """Build the client.

        Args:
            timeout: Read timeout of one attempt in seconds; also the time one attempt may take.
            http_client: Shared HTTP client; one is created per request when ``None``.
            policy: Retry policy for quick failures.
            budget_seconds: Sent to the adapter as ``timeout_seconds`` when set.
            deadline_seconds: Seconds from now after which no attempt may still be running; an attempt is
                not started when less than ``timeout`` remains. ``None`` disables the deadline.
        """
        self._timeout = timeout
        self._http_client = http_client
        self._policy = policy or AdapterRetryPolicy()
        self._budget_seconds = budget_seconds
        self._deadline = None if deadline_seconds is None else time.monotonic() + deadline_seconds

    async def query(
        self,
        *,
        adapter_url: str,
        datasource_name: str,
        queries: dict[str, dict[str, Any]],
        variables: dict[str, str],
        start: str,
        end: str,
        token: str | None = None,
    ) -> tuple[dict[str, float | None], dict[str, str], dict[str, Any], dict[str, str]]:
        """Send metric queries to the adapter and return (values, errors, metadata, error_kinds).

        Retries quick transport errors and 429/502/503/504 answers up to ``policy.attempts`` times within the
        deadline, honouring a numeric ``Retry-After``; timeouts and a budget-exhausted 504 are not retried here
        (see the class docstring). The budget, when set, is sent as ``timeout_seconds``.

        Args:
            adapter_url: Base URL of the adapter service.
            datasource_name: Datasource name forwarded in the X-Datasource-Name header.
            queries: Metric name to mode-aware query spec mapping.
            variables: Variable dict forwarded to the adapter for substitution.
            start: ISO timestamp for the evaluation period start.
            end: ISO timestamp for the evaluation period end.
            token: Datasource token, presented as `Authorization: Bearer`. Adapters that
                configure no token accept requests without it.

        Returns:
            Tuple of (metrics_fetched, fetch_errors, metadata, error_kinds); ``error_kinds`` maps each failed
            metric to ``transient`` or ``data`` and is empty when the adapter does not report it.

        Raises:
            AdapterFetchError: If attempts or the deadline are exhausted, the failure is a long one, or the
                adapter answers a non-retryable error or a malformed 2xx (``retryable`` tells the job which).
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
        payload: dict[str, Any] = {
            'queries': queries,
            'variables': variables,
            'start': start,
            'end': end,
        }
        if self._budget_seconds is not None:
            payload['timeout_seconds'] = self._budget_seconds
        headers = {'X-Datasource-Name': datasource_name}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        request_started = time.perf_counter()
        resp, attempts = await self._post_with_retry(url, headers=headers, payload=payload)
        request_elapsed_s = round(time.perf_counter() - request_started, 3)

        try:
            parsed = AdapterQueryResponse.model_validate(resp.json())
        except ValueError as error:  # JSON decoding and pydantic validation errors are both ValueErrors
            raise AdapterFetchError(
                f'adapter returned a malformed {resp.status_code} response: {type(error).__name__}',
                attempts=attempts,
                last_status=resp.status_code,
                elapsed_s=request_elapsed_s,
                retryable=False,
            ) from error
        metrics_fetched: dict[str, float | None] = dict(parsed.values)
        fetch_errors: dict[str, str] = dict(parsed.errors)
        metadata: dict[str, Any] = dict(parsed.metadata)
        error_kinds: dict[str, str] = dict(parsed.error_kinds)
        logger.info(
            'adapter response',
            url=url,
            elapsed_s=request_elapsed_s,
            values_count=len(metrics_fetched),
            errors_count=len(fetch_errors),
            values=metrics_fetched,
            errors=fetch_errors,
            error_kinds=error_kinds,
            metadata=metadata,
        )
        return metrics_fetched, fetch_errors, metadata, error_kinds

    async def _post_once(self, url: str, *, headers: dict[str, str], payload: dict[str, Any]) -> httpx.Response:
        if self._http_client is not None:
            return await self._http_client.post(url, headers=headers, json=payload)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await client.post(url, headers=headers, json=payload)

    async def _post_with_retry(
        self,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> tuple[httpx.Response, int]:
        """POST, retrying quick failures per the policy and within the deadline.

        Returns:
            The successful response and the number of attempts it took.

        Raises:
            AdapterFetchError: See ``query``.
        """
        started = time.perf_counter()
        last_cause = 'unknown'
        last_status: int | None = None
        if self._misses_deadline(after_seconds=0.0):
            raise AdapterFetchError(
                f'job deadline leaves less than one adapter attempt ({self._timeout}s)',
                attempts=0,
                last_status=None,
                elapsed_s=0.0,
            )
        for attempt in range(1, self._policy.attempts + 1):
            retry_after: str | None = None
            try:
                response = await self._post_once(url, headers=headers, payload=payload)
            except httpx.TimeoutException as error:
                raise AdapterFetchError(
                    f'{type(error).__name__}: {error}',
                    attempts=attempt,
                    last_status=None,
                    elapsed_s=time.perf_counter() - started,
                ) from error
            except httpx.TransportError as error:
                last_cause, last_status = f'{type(error).__name__}: {error}', None
            else:
                if response.is_success:
                    return response, attempt
                last_cause, last_status = f'adapter returned {response.status_code}', response.status_code
                _raise_unless_quick_failure(response, cause=last_cause, attempt=attempt, started=started)
                retry_after = response.headers.get('Retry-After')
            if attempt == self._policy.attempts:
                break
            delay = _compute_backoff(
                attempt,
                base_seconds=self._policy.backoff_seconds,
                retry_after=retry_after,
                jitter=self._policy.jitter,
            )
            if self._misses_deadline(after_seconds=delay):
                raise AdapterFetchError(
                    f'{last_cause}; job deadline leaves no room for another attempt',
                    attempts=attempt,
                    last_status=last_status,
                    elapsed_s=time.perf_counter() - started,
                )
            logger.warning(
                'adapter request retried',
                url=url,
                attempt=attempt,
                max_attempts=self._policy.attempts,
                backoff_s=round(delay, 2),
                cause=last_cause,
            )
            await asyncio.sleep(delay)
        raise AdapterFetchError(
            f'{last_cause} after {self._policy.attempts} attempts',
            attempts=self._policy.attempts,
            last_status=last_status,
            elapsed_s=time.perf_counter() - started,
        )

    def _misses_deadline(self, *, after_seconds: float) -> bool:
        """Tell whether an attempt starting ``after_seconds`` from now could still run past the deadline."""
        if self._deadline is None:
            return False
        return self._deadline - time.monotonic() - after_seconds < self._timeout

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
