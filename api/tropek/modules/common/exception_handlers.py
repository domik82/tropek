"""FastAPI exception handlers for domain exceptions."""

from __future__ import annotations

from fastapi import Request
from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException

from tropek.modules.common.exceptions import (
    ConflictError,
    DomainValidationError,
    NotFoundError,
)

_BODY_PARSE_ERROR_DETAIL = 'There was an error parsing the body'
_BODY_PARSE_STATUS = 400


async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    """Map NotFoundError to 404."""
    return JSONResponse(status_code=404, content={'detail': str(exc)})


async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
    """Map ConflictError to 409."""
    return JSONResponse(status_code=409, content={'detail': str(exc)})


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Map unhandled DB IntegrityError (unique, FK, not-null) to 409.

    Individual routers still raise ``ConflictError`` for friendlier messages
    where they know the constraint context; this is a safety net so raw
    integrity failures never surface as 500s.
    """
    return JSONResponse(status_code=409, content={'detail': 'integrity constraint violated'})


async def body_parse_error_handler(request: Request, exc: HTTPException) -> Response:
    """Re-emit FastAPI's generic 400 body-parse error as 422.

    FastAPI catches non-JSONDecodeError exceptions from request.json() (e.g.
    UnicodeDecodeError for non-UTF-8 bodies) and raises HTTPException(400).
    This maps them to 422 so all request validation failures use the same
    documented status code.

    Registering a handler for ``StarletteHTTPException`` overrides FastAPI's
    default for *every* HTTPException (404s, the 409 baseline-pin conflict,
    405s), so any exception that is not the body-parse case is delegated to
    FastAPI's own default handler — keeping behaviour (empty body on no-body
    statuses, dict details, headers) identical to a stock app.
    """
    if exc.status_code == _BODY_PARSE_STATUS and exc.detail == _BODY_PARSE_ERROR_DETAIL:
        return JSONResponse(
            status_code=422,
            content={
                'detail': [
                    {
                        'loc': ['body'],
                        'msg': 'could not parse request body',
                        'type': 'body_parse_error',
                    }
                ]
            },
        )
    return await default_http_exception_handler(request, exc)


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
