"""Pydantic schemas for SLI definition versioned CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SLIDefinitionCreate(BaseModel):
    """Request body for creating an SLI definition."""

    name: str
    adapter_type: str
    display_name: str | None = None
    indicators: dict[str, str]
    notes: str | None = None
    author: str | None = None
    meta: dict[str, Any] = {}


class SLIDefinitionRead(BaseModel):
    """Response schema for an SLI definition."""

    id: uuid.UUID
    name: str
    adapter_type: str
    display_name: str | None
    version: int
    indicators: dict[str, str]
    notes: str | None
    author: str | None
    meta: dict[str, Any]
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
