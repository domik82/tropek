"""Pydantic schemas for SLO definition versioned CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tropek.modules.common.schemas import SafeStr, StrictInput
from tropek.modules.quality_gate.schemas import IndicatorResult


class ComparisonConfig(BaseModel):
    """Per-SLO comparison configuration. All fields optional."""

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

    method: str | None = None
    aggregation: str | None = None
    pass_threshold: list[str] | None = None
    warning_threshold: list[str] | None = None
    weight: int | None = None
    key_sli: bool | None = None


class SLOObjectiveIn(StrictInput):
    """SLO objective for create/validate requests."""

    sli: SafeStr
    display_name: SafeStr = ''
    pass_threshold: list[SafeStr] = Field(default_factory=list)
    warning_threshold: list[SafeStr] = Field(default_factory=list)
    weight: int = 1
    key_sli: bool = False


class SLOObjectiveRead(SLOObjectiveIn):
    """SLO objective in responses — includes sort_order for round-trip export."""

    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class SLODefinitionCreate(StrictInput):
    """Request body for creating an SLO definition."""

    name: SafeStr
    display_name: SafeStr | None = None
    objectives: list[SLOObjectiveIn]
    total_score_pass_threshold: float = 90.0
    total_score_warning_threshold: float = 75.0
    comparison: ComparisonConfig = Field(default_factory=ComparisonConfig)
    notes: SafeStr | None = None
    author: SafeStr | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    variables: dict[str, str] = Field(default_factory=dict)
    comparable_from_version: int | None = None
    kind: SafeStr = 'standard'
    sli_name: SafeStr | None = None
    sli_version: int | None = None
    method_criteria: dict[str, MethodCriteriaOverride] | None = None


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
    comparison: ComparisonConfig
    notes: str | None
    author: str | None
    tags: dict[str, str]
    variables: dict[str, str]
    kind: str
    method_criteria: dict[str, MethodCriteriaOverride] | None
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
    total_score_pass_threshold: float = 90.0
    total_score_warning_threshold: float = 75.0
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


class BaselineConfig(BaseModel):
    """Configuration for baseline comparison in SLO test."""

    mode: Literal['none', 'asset_history', 'manual'] = 'none'
    limit: int = 3
    values: dict[str, float] | None = None


class SLOTestRequest(StrictInput):
    """Request body for SLO test (dry-run evaluation)."""

    # SLO content — replaces slo_yaml
    objectives: list[SLOObjectiveIn]
    total_score_pass_threshold: float = 90.0
    total_score_warning_threshold: float = 75.0
    comparison: ComparisonConfig = Field(default_factory=ComparisonConfig)
    # Evaluation context — unchanged
    sli_name: SafeStr
    data_source_name: SafeStr
    asset_name: SafeStr
    period_start: datetime
    period_end: datetime
    evaluation_name: SafeStr = ''
    baseline: BaselineConfig | None = None
    variables: dict[str, str] = Field(default_factory=dict)


class SLOTestResult(BaseModel):
    """Response from SLO test endpoint."""

    result: str
    score: float
    indicator_results: list[IndicatorResult]
    baseline_mode: str
    metrics_fetched: dict[str, float]
    fetch_errors: dict[str, str]
    compared_values: dict[str, float] | None
