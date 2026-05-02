"""Drift tests: validate client models match the OpenAPI spec."""

import json
from enum import Enum
from pathlib import Path
from typing import Any

import pytest
import tropek_client.models as client_models

OPENAPI_PATH = Path(__file__).resolve().parents[3] / 'api' / 'openapi.json'

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
