"""HTTP session wrapper with logging, auth, and error mapping."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from tropek_client.exceptions import TropekConnectionError, parse_error_response

logger = logging.getLogger('tropek_client')


class HttpSession:
    """Thin httpx wrapper that maps errors to structured exceptions."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
        verify: bool = True,
    ) -> None:
        request_headers: dict[str, str] = {}
        if api_key:
            request_headers['X-API-Key'] = api_key
        if headers:
            request_headers.update(headers)
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers=request_headers,
            verify=verify,
        )
        self._slow_threshold = 5.0

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> httpx.Response:
        return self._request('GET', path, params=params)

    def post(self, path: str, *, json: Any = None, params: dict[str, Any] | None = None) -> httpx.Response:
        return self._request('POST', path, json=json, params=params)

    def put(self, path: str, *, json: Any = None) -> httpx.Response:
        return self._request('PUT', path, json=json)

    def patch(self, path: str, *, json: Any = None) -> httpx.Response:
        return self._request('PATCH', path, json=json)

    def delete(self, path: str) -> httpx.Response:
        return self._request('DELETE', path)

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        start = time.monotonic()
        try:
            response = self._client.request(method, path, **kwargs)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            duration_ms = (time.monotonic() - start) * 1000
            logger.exception('%s %s failed after %.0fms', method, path, duration_ms)
            raise TropekConnectionError(str(exc)) from exc

        duration_ms = (time.monotonic() - start) * 1000

        if response.is_success:
            logger.info('%s %s %d (%.0fms)', method, path, response.status_code, duration_ms)
            if duration_ms > self._slow_threshold * 1000:
                logger.warning('%s %s took %.0fms (slow)', method, path, duration_ms)
        else:
            self._raise_for_status(response, duration_ms)

        return response

    def _raise_for_status(self, response: httpx.Response, duration_ms: float) -> None:
        try:
            body = response.json()
        except (ValueError, TypeError):
            body = {'detail': response.text}

        if not isinstance(body, dict):
            body = {'detail': str(body)}

        request_id = response.headers.get('x-request-id')
        error = parse_error_response(response.status_code, body)
        error.request_id = request_id

        logger.error(
            '%s %s %d (%.0fms): %s',
            response.request.method,
            response.request.url.path,
            response.status_code,
            duration_ms,
            error.detail,
        )
        raise error

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpSession:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
