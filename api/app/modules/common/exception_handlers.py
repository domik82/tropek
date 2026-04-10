"""FastAPI exception handlers for domain exceptions."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from app.modules.common.exceptions import (
    ConflictError,
    DomainValidationError,
    NotFoundError,
)


async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    """Map NotFoundError to 404."""
    return JSONResponse(status_code=404, content={'detail': str(exc)})


async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
    """Map ConflictError to 409."""
    return JSONResponse(status_code=409, content={'detail': str(exc)})


async def domain_validation_handler(request: Request, exc: DomainValidationError) -> JSONResponse:
    """Map DomainValidationError to 422."""
    return JSONResponse(status_code=422, content={'detail': str(exc)})
