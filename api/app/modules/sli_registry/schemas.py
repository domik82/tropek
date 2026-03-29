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
    indicators: dict[str, str] = {}
    notes: str | None = None
    author: str | None = None
    tags: dict[str, Any] = {}
    comparable_from_version: int | None = None
    mode: str = 'raw'
    query_template: str | None = None
    interval: str | None = None
    methods: list[str] | None = None


class SLIDefinitionRead(BaseModel):
    """Response schema for an SLI definition."""

    id: uuid.UUID
    name: str
    adapter_type: str
    display_name: str | None
    version: int
    comparable_from_version: int
    indicators: dict[str, str]
    notes: str | None
    author: str | None
    tags: dict[str, Any]
    mode: str
    query_template: str | None
    interval: str | None
    methods: list[str] | None
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
