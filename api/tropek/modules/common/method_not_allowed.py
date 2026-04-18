"""ASGI middleware that returns 405 for literal paths hit with an unsupported method.

Starlette's router walks routes in registration order and picks the first method
match, so a request like ``PATCH /datasources/tag-keys`` is captured by the
parameterised ``PATCH /datasources/{name}`` route (with ``name='tag-keys'``)
instead of responding 405. OpenAPI clients, fuzzers (Schemathesis), and
security scanners flag this as a contract violation.

This middleware precomputes the literal-path -> allowed-methods map at app
start and, for any request whose path exactly matches a literal route,
short-circuits with 405 + ``Allow`` header when the method is not one of the
route's declared methods.

Parameterised paths are unaffected: if a request hits a ``/{name}`` pattern
but not a literal sibling, routing proceeds as before.
"""

from __future__ import annotations

from collections.abc import Iterable

from fastapi.responses import JSONResponse
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send


class MethodNotAllowedMiddleware:
    def __init__(self, app: ASGIApp, routes: Iterable[object]) -> None:
        self.app = app
        self._literal_methods: dict[str, set[str]] = {}
        for route in routes:
            if not isinstance(route, Route) or '{' in route.path:
                continue
            if route.methods is None:
                continue
            self._literal_methods.setdefault(route.path, set()).update(route.methods)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        allowed = self._literal_methods.get(scope['path'])
        if allowed is not None and scope['method'] not in allowed:
            response = JSONResponse(
                status_code=405,
                content={'detail': 'method not allowed'},
                headers={'Allow': ', '.join(sorted(allowed))},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
