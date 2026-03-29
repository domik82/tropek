"""Health check endpoints."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Request

from app.config import Settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness() -> dict[str, str]:
    """Return 200 if the process is alive."""
    return {"status": "ok"}


@router.get("/ready")
async def readiness(request: Request) -> dict[str, Any]:
    """Return 200 with component status. Checks Prometheus reachability."""
    settings = Settings()
    prom_url = f"{settings.prometheus_url.rstrip('/')}/-/ready"
    prom_ok = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(prom_url)
            prom_ok = resp.is_success
    except (httpx.ConnectError, httpx.TimeoutException):
        pass

    return {
        "status": "ok" if prom_ok else "degraded",
        "prometheus": "ok" if prom_ok else "unreachable",
        "prometheus_url": settings.prometheus_url,
    }
