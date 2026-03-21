"""Pydantic schemas for DataSource CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DataSourceCreate(BaseModel):
    """Request body for creating a datasource."""

    name: str
    display_name: str | None = None
    adapter_type: str
    adapter_url: str
    tags: dict[str, str] = {}
    token: str | None = None


class DataSourceUpdate(BaseModel):
    """Request body for updating a datasource."""

    display_name: str | None = None
    adapter_url: str | None = None
    tags: dict[str, str] | None = None
    token: str | None = None


class DataSourceRead(BaseModel):
    """Response schema for a datasource."""

    id: uuid.UUID
    name: str
    display_name: str | None
    adapter_type: str
    adapter_url: str
    tags: dict[str, Any]
    has_token: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
