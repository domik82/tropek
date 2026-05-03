"""Drift tests: validate client models and routes match the OpenAPI spec."""

import json
import re
from enum import Enum
from pathlib import Path
from typing import Any

import pytest
import tropek_client.models as client_models

OPENAPI_PATH = Path(__file__).resolve().parents[3] / 'api' / 'openapi.json'
CLIENT_PATH = Path(__file__).resolve().parents[1] / 'tropek_client' / 'client.py'

SKIP_SCHEMAS = {
    'HTTPValidationError',
    'ValidationError',
}

SCHEMA_MODEL_MAP: dict[str, type] = {}
ENUM_NAMES: set[str] = set()


def _register_models():
    for name in dir(client_models):
        obj = getattr(client_models, name)
        if isinstance(obj, type) and hasattr(obj, 'model_fields'):
            SCHEMA_MODEL_MAP[name] = obj
        elif isinstance(obj, type) and issubclass(obj, Enum):
            ENUM_NAMES.add(name)


_register_models()


@pytest.fixture(scope='module')
def openapi_schemas() -> dict[str, Any]:
    with open(OPENAPI_PATH) as f:
        spec = json.load(f)
    return spec['components']['schemas']


def _model_field_aliases(model: type) -> set[str]:
    """Return the JSON-facing field names (aliases where set, otherwise field name)."""
    aliases: set[str] = set()
    for field_name, field_info in model.model_fields.items():
        alias = field_info.alias if field_info.alias else field_name
        aliases.add(alias)
    return aliases


class TestModelDrift:
    def test_openapi_file_exists(self):
        assert OPENAPI_PATH.exists(), f'OpenAPI spec not found at {OPENAPI_PATH}'

    def test_all_response_schemas_have_models(self, openapi_schemas):
        missing = []
        for schema_name in openapi_schemas:
            if schema_name in SKIP_SCHEMAS:
                continue
            if schema_name.startswith('PagedResponse_'):
                continue
            if schema_name in ENUM_NAMES:
                continue
            if schema_name not in SCHEMA_MODEL_MAP:
                missing.append(schema_name)
        if missing:
            pytest.fail(f'Missing client models for OpenAPI schemas: {sorted(missing)}')

    @pytest.mark.parametrize('schema_name', sorted(SCHEMA_MODEL_MAP.keys()))
    def test_fields_match(self, schema_name, openapi_schemas):
        if schema_name not in openapi_schemas:
            pytest.skip(f'{schema_name} not in OpenAPI spec (may be a base class)')

        schema = openapi_schemas[schema_name]
        model = SCHEMA_MODEL_MAP[schema_name]

        schema_field_names = set(schema.get('properties', {}).keys())
        model_field_names = _model_field_aliases(model)

        if 'allOf' in schema:
            for ref_or_obj in schema['allOf']:
                if '$ref' in ref_or_obj:
                    parent_name = ref_or_obj['$ref'].split('/')[-1]
                    parent_schema = openapi_schemas.get(parent_name, {})
                    schema_field_names |= set(parent_schema.get('properties', {}).keys())
                if 'properties' in ref_or_obj:
                    schema_field_names |= set(ref_or_obj['properties'].keys())

        missing_in_model = schema_field_names - model_field_names
        extra_in_model = model_field_names - schema_field_names

        assert not missing_in_model, f'{schema_name}: fields in OpenAPI but not in model: {missing_in_model}'
        assert not extra_in_model, f'{schema_name}: fields in model but not in OpenAPI: {extra_in_model}'


def _normalize_path(path: str) -> str:
    """Normalize a path by replacing path params with {param} placeholder."""
    return re.sub(r'\{[^}]+\}', '{param}', path)


def _extract_client_routes() -> set[tuple[str, str]]:
    """Parse client.py for all HTTP method calls, return set of (METHOD, normalized_path)."""
    source = CLIENT_PATH.read_text()
    pattern = re.compile(r"self\._http\.(get|post|put|patch|delete)\(\s*f?['\"]([^'\"]+)['\"]")
    routes: set[tuple[str, str]] = set()
    for match in pattern.finditer(source):
        method = match.group(1).upper()
        raw_path = match.group(2)
        normalized = re.sub(r'\{[^}]*\}', '{param}', raw_path)
        routes.add((method, normalized))
    return routes


def _extract_openapi_routes() -> set[tuple[str, str]]:
    """Parse openapi.json for all routes, return set of (METHOD, normalized_path)."""
    with open(OPENAPI_PATH) as f:
        spec = json.load(f)
    routes: set[tuple[str, str]] = set()
    for path, methods in spec['paths'].items():
        for method in ('get', 'post', 'put', 'patch', 'delete'):
            if method in methods:
                routes.add((method.upper(), _normalize_path(path)))
    return routes


ROUTES_NOT_IN_CLIENT = {
    ('GET', '/health'),
    ('GET', '/config/ui'),
    ('GET', '/change-points'),
    ('GET', '/change-points/{param}'),
    ('PATCH', '/change-points/bulk-triage'),
    ('GET', '/change-points/config/{param}'),
    ('PUT', '/change-points/config/{param}'),
    ('DELETE', '/change-points/config/{param}'),
    ('GET', '/evaluations/column-annotations'),
    ('GET', '/evaluations/trend-annotations'),
    ('DELETE', '/evaluations/heatmap/cache'),
    ('PATCH', '/asset-types/{param}/set-default'),
    ('DELETE', '/note-categories/{param}'),
    ('POST', '/evaluation-run/{param}/annotations'),
    ('POST', '/evaluation/{param}/annotations/{param}/hide'),
}


class TestRouteDrift:
    def test_client_routes_exist_in_openapi(self):
        """Every route the client calls must exist in openapi.json."""
        client_routes = _extract_client_routes()
        openapi_routes = _extract_openapi_routes()
        missing = client_routes - openapi_routes
        if missing:
            formatted = '\n'.join(f'  {m} {p}' for m, p in sorted(missing))
            pytest.fail(f'Client routes not in OpenAPI spec:\n{formatted}')

    def test_openapi_routes_covered_by_client(self):
        """Every API route should be wrapped by the client (or explicitly skipped)."""
        client_routes = _extract_client_routes()
        openapi_routes = _extract_openapi_routes()
        uncovered = openapi_routes - client_routes - ROUTES_NOT_IN_CLIENT
        if uncovered:
            formatted = '\n'.join(f'  {m} {p}' for m, p in sorted(uncovered))
            pytest.fail(f'OpenAPI routes not covered by client (add to client or ROUTES_NOT_IN_CLIENT):\n{formatted}')
