"""FastAPI exception handlers for quality gate domain exceptions."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from app.modules.quality_gate.exceptions import (
    AssetNotFoundError,
    DataSourceNotFoundError,
    DuplicateEvaluationError,
    EvaluationNotFoundError,
    SLONotConfiguredError,
)


async def asset_not_found_handler(request: Request, exc: AssetNotFoundError) -> JSONResponse:
    """Map AssetNotFoundError to 404."""
    return JSONResponse(status_code=404, content={"detail": str(exc)})


async def evaluation_not_found_handler(
    request: Request, exc: EvaluationNotFoundError
) -> JSONResponse:
    """Map EvaluationNotFoundError to 404."""
    return JSONResponse(status_code=404, content={"detail": str(exc)})


async def slo_not_configured_handler(request: Request, exc: SLONotConfiguredError) -> JSONResponse:
    """Map SLONotConfiguredError to 422."""
    return JSONResponse(status_code=422, content={"detail": str(exc)})


async def datasource_not_found_handler(
    request: Request, exc: DataSourceNotFoundError
) -> JSONResponse:
    """Map DataSourceNotFoundError to 404."""
    return JSONResponse(status_code=404, content={"detail": str(exc)})


async def duplicate_evaluation_handler(
    request: Request, exc: DuplicateEvaluationError
) -> JSONResponse:
    """Map DuplicateEvaluationError to 409."""
    return JSONResponse(status_code=409, content={"detail": str(exc)})
