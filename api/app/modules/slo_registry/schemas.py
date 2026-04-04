"""Pydantic schemas for SLO definition versioned CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.quality_gate.schemas import IndicatorResult


class SLOObjectiveIn(BaseModel):
    """SLO objective for create/validate requests."""

    sli: str
    display_name: str = ''
    pass_threshold: list[str] = Field(default_factory=list)
    warning_threshold: list[str] = Field(default_factory=list)
    weight: int = 1
    key_sli: bool = False


class SLOObjectiveRead(SLOObjectiveIn):
    """SLO objective in responses — includes sort_order for round-trip export."""

    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class SLODefinitionCreate(BaseModel):
    """Request body for creating an SLO definition."""

    name: str
    display_name: str | None = None
    objectives: list[SLOObjectiveIn]
    total_score_pass_threshold: float = 90.0
    total_score_warning_threshold: float = 75.0
    comparison: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    author: str | None = None
    tags: dict[str, Any] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    comparable_from_version: int | None = None
    kind: str = 'standard'
    sli_name: str | None = None
    sli_version: int | None = None
    method_criteria: dict[str, Any] | None = None


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
    comparison: dict[str, Any]
    notes: str | None
    author: str | None
    tags: dict[str, Any]
    variables: dict[str, Any]
    kind: str
    method_criteria: dict[str, Any] | None
    sli_definition_id: uuid.UUID | None
    sli_name: str | None
    sli_version: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SLOValidateRequest(BaseModel):
    """Request body for SLO validation (no save)."""

    objectives: list[SLOObjectiveIn]
    total_score_pass_threshold: float = 90.0
    total_score_warning_threshold: float = 75.0
    comparison: dict[str, Any] = Field(default_factory=dict)


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


class SLOTestRequest(BaseModel):
    """Request body for SLO test (dry-run evaluation)."""

    # SLO content — replaces slo_yaml
    objectives: list[SLOObjectiveIn]
    total_score_pass_threshold: float = 90.0
    total_score_warning_threshold: float = 75.0
    comparison: dict[str, Any] = Field(default_factory=dict)
    # Evaluation context — unchanged
    sli_name: str
    data_source_name: str
    asset_name: str
    period_start: datetime
    period_end: datetime
    evaluation_name: str = ''
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
