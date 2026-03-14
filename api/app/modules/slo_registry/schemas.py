"""Pydantic schemas for SLO definition versioned CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


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
