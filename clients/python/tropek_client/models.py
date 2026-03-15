"""Pydantic models mirroring TROPEK API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SLIDefinition(BaseModel):
    """SLI definition as returned by GET /sli-definitions/{name}."""

    id: str
    name: str
    display_name: str | None = None
    version: int
    indicators: dict[str, str]
    notes: str | None = None
    author: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    active: bool
    created_at: datetime


class SLIDefinitionCreate(BaseModel):
    """Payload for POST /sli-definitions."""

    name: str
    display_name: str | None = None
    indicators: dict[str, str]
    notes: str | None = None
    author: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class SLODefinition(BaseModel):
    """SLO definition as returned by GET /slo-definitions/{name}."""

    id: str
    name: str
    display_name: str | None = None
    version: int
    slo_yaml: str
    notes: str | None = None
    author: str | None = None
    active: bool
    created_at: datetime


class SLODefinitionCreate(BaseModel):
    """Payload for POST /slo-definitions."""

    name: str
    display_name: str | None = None
    slo_yaml: str
    notes: str | None = None
    author: str | None = None


class PagedResponse(BaseModel):
    """Generic paged response wrapper."""

    items: list[Any]
    total: int


class SLIPagedResponse(BaseModel):
    """Paged response for SLI definitions."""

    items: list[SLIDefinition]
    total: int


class SLOPagedResponse(BaseModel):
    """Paged response for SLO definitions."""

    items: list[SLODefinition]
    total: int


class ValidationError(BaseModel):
    """A single SLO validation error."""

    field: str
    message: str


class SLOValidationResult(BaseModel):
    """Response from POST /slo-definitions/validate."""

    valid: bool
    errors: list[ValidationError]
    objectives: list[dict[str, Any]] | None = None
