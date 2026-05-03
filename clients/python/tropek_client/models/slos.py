"""SLO definition models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from tropek_client.models.evaluations import IndicatorResult

from tropek_client.models.common import AggregateFunction


class ChangePointConfigInput(BaseModel):
    """Change point detection config for SLO objective (create/update)."""

    enabled: bool | None = None
    higher_is_better: bool | None = None
    window_size: int | None = None
    max_pvalue: float | int | None = None
    min_magnitude: float | int | None = None
    min_sample_size: int | None = None


class ChangePointConfigRead(BaseModel):
    """Change point detection config as returned by the API."""

    slo_objective_id: UUID
    enabled: bool
    higher_is_better: bool
    window_size: int
    max_pvalue: float | int
    min_magnitude: float | int
    min_sample_size: int


class SLOObjectiveIn(BaseModel):
    """SLO objective for create/update requests."""

    sli: str
    display_name: str = ''
    pass_threshold: list[str] | None = None
    warning_threshold: list[str] | None = None
    weight: int = 1
    key_sli: bool = False
    change_point: ChangePointConfigInput | None = None


class SLOObjectiveRead(BaseModel):
    """SLO objective as returned by the API."""

    sli: str
    display_name: str = ''
    pass_threshold: list[str] | None = None
    warning_threshold: list[str] | None = None
    weight: int = 1
    key_sli: bool = False
    sort_order: int
    change_point: ChangePointConfigRead | None = None


class ComparisonConfig(BaseModel):
    """Comparison configuration for SLO create/update."""

    compare_with: str | None = None
    include_result_with_score: str | None = None
    number_of_comparison_results: int | None = None
    aggregate_function: AggregateFunction | None = None
    scope_tags: list[str] | None = None


class ComparisonConfigRead(BaseModel):
    """Comparison configuration as returned by the API."""

    compare_with: str | None = None
    include_result_with_score: str | None = None
    number_of_comparison_results: int | None = None
    aggregate_function: str | None = None
    scope_tags: list[str] | None = None


class MethodCriteriaOverride(BaseModel):
    """Per-method criteria override for SLO create/update."""

    method: str | None = None
    aggregation: str | None = None
    pass_threshold: list[str] | None = None
    warning_threshold: list[str] | None = None
    weight: int | None = None
    key_sli: bool | None = None


class MethodCriteriaOverrideRead(BaseModel):
    """Per-method criteria override as returned by the API."""

    method: str | None = None
    aggregation: str | None = None
    pass_threshold: list[str] | None = None
    warning_threshold: list[str] | None = None
    weight: int | None = None
    key_sli: bool | None = None


class BaselineConfig(BaseModel):
    """Baseline configuration for SLO test requests."""

    mode: str = 'none'
    limit: int = 3
    values: dict[str, Any] | None = None


CompareToValue = bool | str


class ComparisonRule(BaseModel):
    """Rule mapping tag match criteria to comparison target values."""

    match: dict[str, str]
    compare_to: dict[str, CompareToValue]


class SLODefinitionCreate(BaseModel):
    """Request body for creating a new SLO definition."""

    name: str
    display_name: str | None = None
    objectives: list[SLOObjectiveIn]
    total_score_pass_threshold: float | int = 90.0
    total_score_warning_threshold: float | int = 75.0
    comparison: ComparisonConfig | None = None
    notes: str | None = None
    author: str | None = None
    tags: dict[str, str] | None = None
    variables: dict[str, str] | None = None
    comparable_from_version: int | None = None
    kind: str = 'standard'
    sli_name: str | None = None
    sli_version: int | None = None
    method_criteria: dict[str, MethodCriteriaOverride] | None = None


class SLODefinitionRead(BaseModel):
    """SLO definition as returned by the API."""

    id: UUID
    name: str
    display_name: str | None = None
    version: int
    comparable_from_version: int
    active: bool
    objectives: list[SLOObjectiveRead]
    total_score_pass_threshold: float | int
    total_score_warning_threshold: float | int
    comparison: ComparisonConfigRead
    notes: str | None = None
    author: str | None = None
    tags: dict[str, str]
    variables: dict[str, str]
    kind: str
    method_criteria: dict[str, MethodCriteriaOverrideRead] | None = None
    sli_definition_id: UUID | None = None
    sli_name: str | None = None
    sli_version: int | None = None
    created_at: datetime


class SLOValidateRequest(BaseModel):
    """Request body for SLO validation."""

    objectives: list[SLOObjectiveIn]
    total_score_pass_threshold: float | int = 90.0
    total_score_warning_threshold: float | int = 75.0
    comparison: ComparisonConfig | None = None


class SLOValidationError(BaseModel):
    """Single validation error returned by the SLO validate endpoint."""

    var_field: str = Field(alias='field')
    message: str


class SLOValidationResult(BaseModel):
    """Response from the SLO validate endpoint."""

    valid: bool
    errors: list[SLOValidationError]
    objectives: list[SLOObjectiveIn] | None = None


class SLOTestRequest(BaseModel):
    """Request body for testing an SLO against live data."""

    objectives: list[SLOObjectiveIn]
    total_score_pass_threshold: float | int = 90.0
    total_score_warning_threshold: float | int = 75.0
    comparison: ComparisonConfig | None = None
    sli_name: str
    data_source_name: str
    asset_name: str
    period_start: datetime
    period_end: datetime
    evaluation_name: str = ''
    baseline: BaselineConfig | None = None
    variables: dict[str, str] | None = None


class SLOTestResult(BaseModel):
    """Response from the SLO test endpoint."""

    result: str
    score: float | int
    indicator_results: list[IndicatorResult]
    baseline_mode: str
    metrics_fetched: dict[str, float | int]
    fetch_errors: dict[str, str]
    compared_values: dict[str, float | int] | None = None
