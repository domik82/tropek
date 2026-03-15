"""Tests for Pydantic model validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tropek_client.models import (
    SLIDefinitionCreate,
    SLODefinitionCreate,
    SLOValidationResult,
)
from tropek_client.models import (
    ValidationError as TropekValError,
)


def test_sli_definition_create_requires_name():
    with pytest.raises(ValidationError):
        SLIDefinitionCreate(indicators={"cpu": "avg(cpu)"})  # type: ignore[call-arg]


def test_sli_definition_create_requires_indicators():
    with pytest.raises(ValidationError):
        SLIDefinitionCreate(name="test")  # type: ignore[call-arg]


def test_sli_definition_valid():
    sli = SLIDefinitionCreate(name="test-sli", indicators={"cpu": "avg(cpu_usage)"})
    assert sli.name == "test-sli"
    assert sli.indicators == {"cpu": "avg(cpu_usage)"}


def test_slo_definition_create_valid():
    slo = SLODefinitionCreate(name="test-slo", slo_yaml="spec_version: '1.0'")
    assert slo.name == "test-slo"


def test_slo_validation_result_valid():
    result = SLOValidationResult(valid=True, errors=[])
    assert result.valid is True
    assert result.errors == []


def test_slo_validation_result_with_errors():
    result = SLOValidationResult(
        valid=False,
        errors=[TropekValError(field="slo_yaml", message="empty slo yaml")],
    )
    assert result.valid is False
    assert len(result.errors) == 1
    assert result.errors[0].field == "slo_yaml"
