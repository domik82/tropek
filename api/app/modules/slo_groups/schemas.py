"""Pydantic schemas for SLO groups."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.modules.common.schemas import StrictInput


class SLOGroupCreate(StrictInput):
    """Request body for creating an SLO group."""

    name: str
    display_name: str | None = None
    template_slo_name: str
    template_slo_version: int
    gen_variables: dict[str, list[str]]
    tags: dict[str, Any] = {}
    author: str | None = None


class SLOGroupUpdate(StrictInput):
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
    template_slo_definition_id: uuid.UUID
    gen_variables: dict[str, list[str]]
    tags: dict[str, Any]
    author: str | None
    version: int
    active: bool
    created_at: datetime
    updated_at: datetime
    generated_slo_count: int

    model_config = ConfigDict(from_attributes=True)


class ExtractRequest(StrictInput):
    """Request body for extracting a generated SLO to standalone."""

    slo_name: str
    new_name: str
