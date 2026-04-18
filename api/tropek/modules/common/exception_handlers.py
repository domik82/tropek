"""FastAPI exception handlers for domain exceptions."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from tropek.modules.common.exceptions import (
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
    """Map DomainValidationError to 422 using FastAPI's HTTPValidationError shape.

    FastAPI documents the 422 response as ``HTTPValidationError`` whose
    ``detail`` is a list of ``ValidationError`` entries. Emitting a plain
    string here broke OpenAPI conformance; wrap the message so clients and
    schemathesis both see the expected structure.
    """
    return JSONResponse(
        status_code=422,
        content={'detail': [{'loc': ['body'], 'msg': str(exc), 'type': 'domain_validation'}]},
    )
