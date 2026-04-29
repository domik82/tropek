"""Pydantic schemas for SLO definition versioned CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from annotated_types import MinLen
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from tropek.modules.change_points.schemas import ChangePointConfigInput, ChangePointConfigRead
from tropek.modules.common.schemas import (
    FloatNotBool,
    IdentifierKey,
    IntNotBool,
    SafeStr,
    StrictInput,
    Tags,
)
from tropek.modules.quality_gate.evaluation_engine.constants import AggregateFunction
from tropek.modules.quality_gate.schemas import IndicatorResult


class ComparisonConfig(BaseModel):
    """Per-SLO comparison configuration (input). All fields optional."""

    compare_with: SafeStr | None = None
    include_result_with_score: SafeStr | None = None
    number_of_comparison_results: IntNotBool | None = None
    aggregate_function: AggregateFunction | None = None
    scope_tags: list[SafeStr] | None = None


class ComparisonConfigRead(BaseModel):
    """Per-SLO comparison configuration (response). Accepts any stored value."""

    compare_with: str | None = None
    include_result_with_score: str | None = None
    number_of_comparison_results: int | None = None
    aggregate_function: str | None = None
    scope_tags: list[str] | None = None


class MethodCriteriaOverride(BaseModel):
    """Per-method override for template Level-2 expansion.

    Mirrors the four override-capable fields of SLOObjectiveIn
    (pass_threshold, warning_threshold, weight, key_sli), plus
    two method/aggregation hints. All fields optional — only the
    fields explicitly set on an override are applied during template
    instantiation; unset fields inherit from the template's objective.

    Stored on SLODefinition.method_criteria and consumed during
    slo_groups/generator.py Level-2 expansion (not yet implemented,
    tracked as a follow-up).
    """

    method: SafeStr | None = None
    aggregation: SafeStr | None = None
    pass_threshold: list[SafeStr] | None = None
    warning_threshold: list[SafeStr] | None = None
    weight: IntNotBool | None = None
    key_sli: StrictBool | None = None


class MethodCriteriaOverrideRead(BaseModel):
    """Per-method override in responses. Accepts any stored value without strict validation."""

    method: str | None = None
    aggregation: str | None = None
    pass_threshold: list[str] | None = None
    warning_threshold: list[str] | None = None
    weight: int | None = None
    key_sli: bool | None = None


class _SLOObjectiveBase(StrictInput):
    """Shared fields for SLO objective input and response schemas."""

    sli: SafeStr
    display_name: SafeStr = ''
    pass_threshold: list[SafeStr] = Field(default_factory=list)
    warning_threshold: list[SafeStr] = Field(default_factory=list)
    weight: IntNotBool = 1
    key_sli: StrictBool = False


class SLOObjectiveIn(_SLOObjectiveBase):
    """SLO objective for create/validate requests."""

    change_point: ChangePointConfigInput | None = None


class SLOObjectiveRead(_SLOObjectiveBase):
    """SLO objective in responses — includes sort_order for round-trip export."""

    sort_order: int
    change_point: ChangePointConfigRead | None = None

    model_config = ConfigDict(from_attributes=True)


class SLODefinitionCreate(StrictInput):
    """Request body for creating an SLO definition."""

    name: SafeStr
    display_name: SafeStr | None = None
    objectives: list[SLOObjectiveIn]
    total_score_pass_threshold: FloatNotBool = 90.0
    total_score_warning_threshold: FloatNotBool = 75.0
    comparison: ComparisonConfig = Field(default_factory=ComparisonConfig)
    notes: SafeStr | None = None
    author: SafeStr | None = None
    tags: Tags = Field(default_factory=dict)
    variables: dict[IdentifierKey, SafeStr] = Field(default_factory=dict)
    comparable_from_version: IntNotBool | None = None
    kind: SafeStr = 'standard'
    sli_name: SafeStr | None = None
    sli_version: IntNotBool | None = None
    method_criteria: dict[IdentifierKey, MethodCriteriaOverride] | None = None


class SLODefinitionRead(BaseModel):
    """Response schema for an SLO definition."""

    id: uuid.UUID
    name: str
    display_name: str | None
    version: int
    comparable_from_version: int
    active: bool
    objectives: list[SLOObjectiveRead]
    total_score_pass_threshold: float
    total_score_warning_threshold: float
    comparison: ComparisonConfigRead
    notes: str | None
    author: str | None
    tags: dict[str, str]
    variables: dict[str, str]
    kind: str
    method_criteria: dict[str, MethodCriteriaOverrideRead] | None
    sli_definition_id: uuid.UUID | None
    sli_name: str | None = None
    sli_version: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode='before')
    @classmethod
    def resolve_sli(cls, data: Any) -> Any:
        """Flatten sli_definition relationship into top-level fields."""
        if not isinstance(data, dict):
            sli = getattr(data, 'sli_definition', None)
            if sli is not None:
                return {
                    **{f: getattr(data, f) for f in cls.model_fields if hasattr(data, f)},
                    'sli_name': sli.name,
                    'sli_version': sli.version,
                }
        return data


class SLOValidateRequest(StrictInput):
    """Request body for SLO validation (no save)."""

    objectives: list[SLOObjectiveIn]
    total_score_pass_threshold: FloatNotBool = 90.0
    total_score_warning_threshold: FloatNotBool = 75.0
    comparison: ComparisonConfig = Field(default_factory=ComparisonConfig)


class SLOValidationError(BaseModel):
    """A single validation error."""

    field: str
    message: str


class SLOValidationResult(BaseModel):
    """Response from SLO validation endpoint."""

    valid: bool
    errors: list[SLOValidationError]
    objectives: list[SLOObjectiveIn] | None = None


class BaselineConfig(StrictInput):
    """Configuration for baseline comparison in SLO test."""

    mode: Literal['none', 'asset_history', 'manual'] = 'none'
    limit: int = 3
    values: dict[IdentifierKey, float] | None = None


class SLOTestRequest(StrictInput):
    """Request body for SLO test (dry-run evaluation)."""

    # SLO content — replaces slo_yaml
    objectives: Annotated[list[SLOObjectiveIn], MinLen(1)]
    total_score_pass_threshold: FloatNotBool = 90.0
    total_score_warning_threshold: FloatNotBool = 75.0
    comparison: ComparisonConfig = Field(default_factory=ComparisonConfig)
    # Evaluation context — unchanged
    sli_name: SafeStr
    data_source_name: SafeStr
    asset_name: SafeStr
    period_start: datetime
    period_end: datetime
    evaluation_name: SafeStr = ''
    baseline: BaselineConfig | None = None
    variables: dict[IdentifierKey, SafeStr] = Field(default_factory=dict)


class SLOTestResult(BaseModel):
    """Response from SLO test endpoint."""

    result: str
    score: float
    indicator_results: list[IndicatorResult]
    baseline_mode: str
    metrics_fetched: dict[str, float]
    fetch_errors: dict[str, str]
    compared_values: dict[str, float] | None
