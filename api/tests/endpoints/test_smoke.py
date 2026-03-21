"""Smoke test to verify endpoint test infrastructure."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_health_endpoint(async_client: AsyncClient) -> None:
    resp = await async_client.get("/health")
    assert resp.status_code == 200
