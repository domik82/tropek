"""Tests for the OpenAPI schema post-processor.

Pydantic v2 emits ``patternProperties`` for ``dict[TagKey, ...]`` fields but
does NOT emit ``propertyNames.pattern``. hypothesis-jsonschema (the engine
behind schemathesis) honors ``propertyNames.pattern`` when generating dict
keys and only consults ``patternProperties`` to pick value schemas after
keys are generated. The ``_inject_property_names_pattern`` post-processor
closes that gap.
"""

from tropek.main import _inject_property_names_pattern


def test_single_pattern_property_injected_when_property_names_absent() -> None:
    schema = {
        'type': 'object',
        'patternProperties': {'^[a-z]+$': {'type': 'string'}},
    }
    _inject_property_names_pattern(schema)
    assert schema['propertyNames'] == {'pattern': '^[a-z]+$'}


def test_existing_property_names_pattern_left_alone() -> None:
    schema = {
        'type': 'object',
        'patternProperties': {'^[a-z]+$': {'type': 'string'}},
        'propertyNames': {'pattern': '^existing$'},
    }
    _inject_property_names_pattern(schema)
    assert schema['propertyNames'] == {'pattern': '^existing$'}


def test_property_names_min_length_preserved_and_pattern_added() -> None:
    schema = {
        'type': 'object',
        'patternProperties': {'^[a-z]+$': {'type': 'string'}},
        'propertyNames': {'minLength': 1, 'maxLength': 63},
    }
    _inject_property_names_pattern(schema)
    assert schema['propertyNames'] == {
        'minLength': 1,
        'maxLength': 63,
        'pattern': '^[a-z]+$',
    }


def test_multiple_pattern_properties_skipped() -> None:
    schema = {
        'type': 'object',
        'patternProperties': {
            '^[a-z]+$': {'type': 'string'},
            '^[0-9]+$': {'type': 'integer'},
        },
    }
    _inject_property_names_pattern(schema)
    assert 'propertyNames' not in schema


def test_nested_schema_walked_and_injected() -> None:
    schema = {
        'type': 'object',
        'properties': {
            'foo': {
                'type': 'object',
                'patternProperties': {'^key_[a-z]+$': {'type': 'string'}},
            },
            'bar': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'patternProperties': {'^item_[0-9]+$': {'type': 'integer'}},
                },
            },
        },
    }
    _inject_property_names_pattern(schema)
    assert schema['properties']['foo']['propertyNames'] == {'pattern': '^key_[a-z]+$'}
    assert schema['properties']['bar']['items']['propertyNames'] == {'pattern': '^item_[0-9]+$'}


def test_non_dict_input_returns_without_error() -> None:
    _inject_property_names_pattern(None)  # type: ignore[arg-type]
    _inject_property_names_pattern('string')  # type: ignore[arg-type]
    _inject_property_names_pattern(42)  # type: ignore[arg-type]
