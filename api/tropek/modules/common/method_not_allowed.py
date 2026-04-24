"""ASGI middleware that returns 405 for paths hit with an unsupported method.

Starlette's router walks routes in registration order and picks the first method
match, so a request like ``PATCH /datasources/tag-keys`` is captured by the
parameterised ``PATCH /datasources/{name}`` route (with ``name='tag-keys'``)
instead of responding 405. OpenAPI clients, fuzzers (Schemathesis), and
security scanners flag this as a contract violation.

This middleware precomputes two lookup structures at app start:

* ``_literal_allowed_methods`` — a ``path -> set[method]`` map for routes with no
  path parameters (fast exact-string match).
* ``_parameterized_routes`` — a list of ``(path_regex, set[method])`` pairs for
  routes that contain path parameters.  Checked only when no literal match is
  found; the first regex match whose methods do *not* include the request method
  triggers a 405.

A path that matches no route at all — neither literal nor parameterised — falls
through to the normal router, which returns the appropriate 404.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from fastapi.responses import JSONResponse
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send


class MethodNotAllowedMiddleware:
    """ASGI middleware that returns 405 Method Not Allowed for recognised paths called with an unsupported method."""

    def __init__(self, app: ASGIApp, routes: Iterable[object]) -> None:
        self.app = app
        self._literal_allowed_methods: dict[str, set[str]] = {}
        self._parameterized_routes: list[tuple[re.Pattern[str], set[str]]] = []

        for route in routes:
            if not isinstance(route, Route) or route.methods is None:
                continue
            if '{' in route.path:
                self._parameterized_routes.append((route.path_regex, set(route.methods)))
            else:
                self._literal_allowed_methods.setdefault(route.path, set()).update(route.methods)

    def _allowed_methods_for_path(self, request_path: str) -> set[str] | None:
        """Return the set of allowed methods for *request_path*, or ``None`` if no route matches.

        Parameterised routes are checked in registration order, mirroring how Starlette's own
        router walks routes.  When the first matching regex is found we collect *all* methods
        declared on every route that shares the same regex pattern (multiple ``@router.get`` /
        ``@router.delete`` decorators produce separate ``Route`` objects with the same path),
        then stop — routes registered later with a broader pattern (e.g. ``{name:path}``) are
        not consulted.
        """
        literal_methods = self._literal_allowed_methods.get(request_path)
        if literal_methods is not None:
            return literal_methods

        # Walk parameterised routes in registration order, stopping at the first matching regex.
        # Collect all methods for routes sharing that exact same compiled regex pattern.
        first_matching_regex: re.Pattern[str] | None = None
        matched_methods: set[str] = set()
        for path_regex, route_methods in self._parameterized_routes:
            if first_matching_regex is None:
                if path_regex.match(request_path):
                    first_matching_regex = path_regex
                    matched_methods.update(route_methods)
            elif path_regex is first_matching_regex:
                matched_methods.update(route_methods)

        return matched_methods if matched_methods else None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle an incoming ASGI request, intercepting unsupported-method calls with 405."""
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        allowed = self._allowed_methods_for_path(scope['path'])
        if allowed is not None and scope['method'] not in allowed:
            response = JSONResponse(
                status_code=405,
                content={'detail': 'method not allowed'},
                headers={'Allow': ', '.join(sorted(allowed))},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
