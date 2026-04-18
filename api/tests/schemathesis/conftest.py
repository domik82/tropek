"""Conftest for Schemathesis property-based tests.

Loads the OpenAPI schema directly from the FastAPI app via ASGI. The schema
exposed at ``/openapi.json`` matches the committed ``api/openapi.json`` file
(kept fresh by Phase 1 codegen), and binding to the app lets ``case.call()``
dispatch through the ASGI layer without opening a network port.
"""

from __future__ import annotations

import schemathesis
from schemathesis.specs.openapi.schemas import OpenApiSchema

from tropek.main import app


def load_schema() -> OpenApiSchema:
    """Load the OpenAPI schema from the FastAPI app via ASGI transport."""
    return schemathesis.openapi.from_asgi('/openapi.json', app)


schema = load_schema()
