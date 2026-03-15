"""Pydantic schemas for SLO definition versioned CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SLODefinitionCreate(BaseModel):
    """Request body for creating an SLO definition."""

    name: str
    display_name: str | None = None
    slo_yaml: str
    notes: str | None = None
    author: str | None = None
    meta: dict[str, Any] = {}


class SLODefinitionRead(BaseModel):
    """Response schema for an SLO definition."""

    id: uuid.UUID
    name: str
    display_name: str | None
    version: int
    slo_yaml: str
    notes: str | None
    author: str | None
    meta: dict[str, Any]
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SLOValidateRequest(BaseModel):
    """Request body for SLO YAML validation."""

    slo_yaml: str


class SLOValidationError(BaseModel):
    """A single validation error."""

    field: str
    message: str


class SLOValidationResult(BaseModel):
    """Response from SLO validation endpoint."""

    valid: bool
    errors: list[SLOValidationError]
    objectives: list[dict[str, Any]] | None = None


class BaselineConfig(BaseModel):
    """Configuration for baseline comparison in SLO test."""

    mode: Literal["none", "asset_history", "manual"] = "none"
    limit: int = 3
    values: dict[str, float] | None = None


class SLOTestRequest(BaseModel):
    """Request body for SLO test (dry-run evaluation)."""

    slo_yaml: str
    sli_name: str
    data_source_name: str
    asset_name: str
    period_start: datetime
    period_end: datetime
    baseline: BaselineConfig | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class SLOTestResult(BaseModel):
    """Response from SLO test endpoint."""

    result: str
    score: float
    indicator_results: list[dict[str, Any]]
    baseline_mode: str
    metrics_fetched: dict[str, float]
    fetch_errors: dict[str, str]
    compared_values: dict[str, float] | None
