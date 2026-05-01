"""TROPEK API — FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from sqlalchemy.exc import IntegrityError

from tropek.cache.redis_cache import RedisCache
from tropek.config import get_settings
from tropek.db.middleware import SessionMiddleware
from tropek.db.session import get_session_factory
from tropek.logging_config import configure_logging
from tropek.modules.asset_meta.router import router as asset_meta_router
from tropek.modules.assets.router import router as assets_router
from tropek.modules.assignments.router import router as assignments_router
from tropek.modules.change_points.router import router as change_points_router
from tropek.modules.configuration.router import router as configuration_router
from tropek.modules.common.exception_handlers import (
    conflict_handler,
    domain_validation_handler,
    integrity_error_handler,
    not_found_handler,
)
from tropek.modules.common.exceptions import (
    ConflictError,
    DomainValidationError,
    NotFoundError,
)
from tropek.modules.common.method_not_allowed import MethodNotAllowedMiddleware
from tropek.modules.datasource.router import router as datasource_router
from tropek.modules.display_groups.router import router as display_groups_router
from tropek.modules.quality_gate.router import router as quality_gate_router
from tropek.modules.sli_registry.router import router as sli_router
from tropek.modules.slo_groups.router import router as slo_groups_router
from tropek.modules.slo_registry.router import router as slo_router
from tropek.queue import create_arq_pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Validate config, configure logging, and open the arq pool at startup; close it on shutdown."""
    settings = get_settings()
    settings.validate_required()
    configure_logging()
    app.state.arq_pool = await create_arq_pool()
    cache_redis = aioredis.from_url(settings.cache.url)
    app.state.cache = RedisCache(cache_redis)
    yield
    await cache_redis.aclose()  # type: ignore[attr-defined]
    await app.state.arq_pool.close()


app = FastAPI(title='TROPEK API', version='0.2.0', lifespan=lifespan)
app.add_middleware(SessionMiddleware, session_factory=get_session_factory())

# Domain exception handlers — convert domain errors to HTTP responses
app.add_exception_handler(NotFoundError, not_found_handler)  # type: ignore[arg-type]
app.add_exception_handler(ConflictError, conflict_handler)  # type: ignore[arg-type]
app.add_exception_handler(DomainValidationError, domain_validation_handler)  # type: ignore[arg-type]
app.add_exception_handler(IntegrityError, integrity_error_handler)  # type: ignore[arg-type]

# No prefix= — every router defines full absolute paths
app.include_router(asset_meta_router)
app.include_router(assets_router)
app.include_router(datasource_router)
app.include_router(sli_router)
app.include_router(slo_router)
app.include_router(slo_groups_router)
app.include_router(quality_gate_router)
app.include_router(assignments_router)
app.include_router(change_points_router)
app.include_router(configuration_router)
app.include_router(display_groups_router)


@app.get('/health')
async def health() -> dict[str, str]:
    """Return service health status."""
    return {'status': 'ok'}


# Must run after every router is registered so the middleware can snapshot the
# final route list. Placed outermost so it intercepts before Starlette's router
# would otherwise route a literal-path request onto a parameterised sibling.
app.add_middleware(MethodNotAllowedMiddleware, routes=app.routes)


@app.get('/config/ui')
async def ui_config() -> dict[str, int | bool | str]:
    """Return UI-facing configuration limits."""
    settings = get_settings()
    return {
        'maxEvaluations': settings.ui.max_evaluations,
        'pageSize': settings.ui.page_size,
        'heatmapSloGroupsExpandedByDefault': settings.ui.heatmap_slo_groups_expanded_by_default,
        'dataStartDate': settings.ui.data_start_date,
    }


# Every operation can reach these error branches through the shared
# exception handlers (integrity → 409, NotFoundError → 404, domain/pydantic
# validation → 422). FastAPI only auto-documents 422 for operations that
# declare a body, so endpoints that reach validation via query params or
# custom validators look undocumented to contract tests. Inject the missing
# status codes into every operation so the OpenAPI doc matches reality.
_openapi_logger = logging.getLogger(__name__)


def _inject_property_names_pattern(schema: Any) -> None:
    """Inject propertyNames.pattern from patternProperties.

    Pydantic v2 emits ``patternProperties`` for ``dict[TagKey, ...]`` but not
    ``propertyNames.pattern`` — hypothesis-jsonschema (schemathesis) honors
    the latter for key generation. Without this transform, schemathesis
    generates dict keys that violate our Pydantic key patterns. Shim for an
    upstream gap; delete when Pydantic emits ``propertyNames.pattern``
    natively.
    """
    if not isinstance(schema, dict):
        return
    pattern_properties = schema.get('patternProperties')
    if isinstance(pattern_properties, dict) and pattern_properties:
        if len(pattern_properties) == 1:
            key_regex = next(iter(pattern_properties.keys()))
            property_names = schema.setdefault('propertyNames', {})
            if isinstance(property_names, dict) and 'pattern' not in property_names:
                property_names['pattern'] = key_regex
        else:
            _openapi_logger.warning(
                'skipping propertyNames.pattern injection: multiple patternProperties '
                'keys are ambiguous (keys=%s)',
                list(pattern_properties.keys()),
            )
    for value in schema.values():
        if isinstance(value, dict):
            _inject_property_names_pattern(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _inject_property_names_pattern(item)


_HTTP_VALIDATION_ERROR = {'$ref': '#/components/schemas/HTTPValidationError'}
_ERROR_MESSAGE = {
    'type': 'object',
    'title': 'ErrorMessage',
    'properties': {'detail': {'type': 'string', 'title': 'Detail'}},
    'required': ['detail'],
}


def _custom_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )
    components = schema.setdefault('components', {}).setdefault('schemas', {})
    components.setdefault('ErrorMessage', _ERROR_MESSAGE)
    error_message_ref = {'$ref': '#/components/schemas/ErrorMessage'}
    error_message_response = {
        'description': 'Error',
        'content': {'application/json': {'schema': error_message_ref}},
    }
    validation_error_response = {
        'description': 'Validation Error',
        'content': {'application/json': {'schema': _HTTP_VALIDATION_ERROR}},
    }
    bad_request_response = {
        'description': 'Bad Request',
        'content': {'application/json': {'schema': error_message_ref}},
    }
    mutating_methods = {'post', 'put', 'patch', 'delete'}
    for path_item in schema.get('paths', {}).values():
        for method, operation in path_item.items():
            if method not in {'get', 'post', 'put', 'patch', 'delete'}:
                continue
            responses = operation.setdefault('responses', {})
            # 422: validation error (FastAPI only auto-adds when a body is declared)
            responses.setdefault('422', validation_error_response)
            # 404: any operation may reference a resource that doesn't exist,
            # either via path params or query params (e.g. GET /evaluations?asset_name=x)
            responses.setdefault('404', error_message_response)
            # 409: integrity / conflict from DB or domain logic
            if method in mutating_methods:
                responses.setdefault('409', error_message_response)
            # 400: FastAPI returns 400 for malformed JSON bodies (not 422)
            responses.setdefault('400', bad_request_response)
    _inject_property_names_pattern(schema)
    app.openapi_schema = schema
    return schema


app.openapi = _custom_openapi  # type: ignore[method-assign]
