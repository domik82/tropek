"""TROPEK API — FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.modules.assets.router import router as assets_router
from app.modules.datasource.router import router as datasource_router
from app.modules.quality_gate.router import router as quality_gate_router
from app.modules.sli_registry.router import router as sli_router
from app.modules.slo_registry.router import router as slo_router
from app.queue import create_arq_pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the arq pool at startup; close it on shutdown."""
    app.state.arq_pool = await create_arq_pool()
    yield
    await app.state.arq_pool.close()


app = FastAPI(title="TROPEK API", version="0.2.0", lifespan=lifespan)

# No prefix= — every router defines full absolute paths
app.include_router(assets_router)
app.include_router(datasource_router)
app.include_router(sli_router)
app.include_router(slo_router)
app.include_router(quality_gate_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok"}
