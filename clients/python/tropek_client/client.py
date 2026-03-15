"""TropekClient — typed HTTP client for the TROPEK API."""

from __future__ import annotations

from typing import Any

import httpx

from tropek_client.exceptions import (
    TropekAPIError,
    TropekConnectionError,
    TropekNotFoundError,
    TropekValidationError,
)
from tropek_client.models import (
    SLIDefinition,
    SLIDefinitionCreate,
    SLIPagedResponse,
    SLODefinition,
    SLODefinitionCreate,
    SLOPagedResponse,
    SLOValidationResult,
)


def _raise_for_status(resp: httpx.Response) -> None:
    """Raise a typed exception for non-2xx responses."""
    if resp.status_code == 404:
        detail = resp.json().get("detail", "not found")
        raise TropekNotFoundError(404, detail)
    if resp.status_code == 422:
        detail = resp.json().get("detail", "validation error")
        raise TropekValidationError(422, str(detail))
    if resp.status_code >= 400:
        detail = resp.json().get("detail", resp.text)
        raise TropekAPIError(resp.status_code, str(detail))


class SLIResource:
    """Operations on SLI definitions."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def list(self) -> SLIPagedResponse:
        """List all active SLI definitions."""
        try:
            resp = self._client.get("/sli-definitions")
        except httpx.ConnectError as e:
            raise TropekConnectionError(str(e)) from e
        _raise_for_status(resp)
        return SLIPagedResponse.model_validate(resp.json())

    def get(self, name: str) -> SLIDefinition:
        """Get a specific SLI definition by name."""
        try:
            resp = self._client.get(f"/sli-definitions/{name}")
        except httpx.ConnectError as e:
            raise TropekConnectionError(str(e)) from e
        _raise_for_status(resp)
        return SLIDefinition.model_validate(resp.json())

    def create(self, payload: SLIDefinitionCreate) -> SLIDefinition:
        """Create a new SLI definition."""
        try:
            resp = self._client.post("/sli-definitions", json=payload.model_dump(exclude_none=True))
        except httpx.ConnectError as e:
            raise TropekConnectionError(str(e)) from e
        _raise_for_status(resp)
        return SLIDefinition.model_validate(resp.json())

    def delete(self, name: str) -> None:
        """Soft-delete a SLI definition."""
        try:
            resp = self._client.delete(f"/sli-definitions/{name}")
        except httpx.ConnectError as e:
            raise TropekConnectionError(str(e)) from e
        _raise_for_status(resp)


class SLOResource:
    """Operations on SLO definitions."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def list(self) -> SLOPagedResponse:
        """List all active SLO definitions."""
        try:
            resp = self._client.get("/slo-definitions")
        except httpx.ConnectError as e:
            raise TropekConnectionError(str(e)) from e
        _raise_for_status(resp)
        return SLOPagedResponse.model_validate(resp.json())

    def get(self, name: str) -> SLODefinition:
        """Get a specific SLO definition by name."""
        try:
            resp = self._client.get(f"/slo-definitions/{name}")
        except httpx.ConnectError as e:
            raise TropekConnectionError(str(e)) from e
        _raise_for_status(resp)
        return SLODefinition.model_validate(resp.json())

    def create(self, payload: SLODefinitionCreate) -> SLODefinition:
        """Create a new SLO definition."""
        try:
            resp = self._client.post("/slo-definitions", json=payload.model_dump(exclude_none=True))
        except httpx.ConnectError as e:
            raise TropekConnectionError(str(e)) from e
        _raise_for_status(resp)
        return SLODefinition.model_validate(resp.json())

    def delete(self, name: str) -> None:
        """Soft-delete a SLO definition."""
        try:
            resp = self._client.delete(f"/slo-definitions/{name}")
        except httpx.ConnectError as e:
            raise TropekConnectionError(str(e)) from e
        _raise_for_status(resp)

    def validate(self, slo_yaml: str) -> SLOValidationResult:
        """Validate SLO YAML without saving."""
        try:
            resp = self._client.post("/slo-definitions/validate", json={"slo_yaml": slo_yaml})
        except httpx.ConnectError as e:
            raise TropekConnectionError(str(e)) from e
        _raise_for_status(resp)
        return SLOValidationResult.model_validate(resp.json())


class TropekClient:
    """Synchronous TROPEK API client.

    Usage::

        with TropekClient("http://localhost:8080") as client:
            slis = client.sli.list()
    """

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        headers: dict[str, str] = {}
        if api_key:
            headers["X-API-Key"] = api_key
        self._http = httpx.Client(
            base_url=base_url.rstrip("/") + "/api",
            headers=headers,
            timeout=timeout,
        )
        self.sli = SLIResource(self._http)
        self.slo = SLOResource(self._http)

    def __enter__(self) -> TropekClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self._http.close()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._http.close()
