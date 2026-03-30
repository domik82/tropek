"""Pydantic schemas for SLO groups and template bindings."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SLOGroupCreate(BaseModel):
    """Request body for creating an SLO group."""

    name: str
    display_name: str | None = None
    template_slo_name: str
    template_slo_version: int
    gen_variables: dict[str, list[str]]
    tags: dict[str, Any] = {}
    author: str | None = None


class SLOGroupUpdate(BaseModel):
    """Request body for updating an SLO group (triggers regeneration)."""

    template_slo_name: str | None = None
    template_slo_version: int | None = None
    gen_variables: dict[str, list[str]] | None = None
    display_name: str | None = None
    tags: dict[str, Any] | None = None


class SLOGroupRead(BaseModel):
    """Response schema for an SLO group."""

    id: uuid.UUID
    name: str
    display_name: str | None
    template_slo_name: str
    template_slo_version: int
    gen_variables: dict[str, list[str]]
    tags: dict[str, Any]
    author: str | None
    version: int
    active: bool
    created_at: datetime
    updated_at: datetime
    generated_slo_count: int

    model_config = ConfigDict(from_attributes=True)


class ExtractRequest(BaseModel):
    """Request body for extracting a generated SLO to standalone."""

    slo_name: str
    new_name: str


class TemplateBindingCreate(BaseModel):
    """Request body for creating a template binding."""

    template_group_name: str
    data_source_name: str


class TemplateBindingRead(BaseModel):
    """Response schema for a template binding."""

    id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    template_group_name: str
    data_source_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
