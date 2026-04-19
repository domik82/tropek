"""Pydantic schemas for DataSource CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from tropek.modules.common.schemas import SafeStr, StrictInput


class DataSourceCreate(StrictInput):
    """Request body for creating a datasource."""

    name: SafeStr
    display_name: SafeStr | None = None
    adapter_type: SafeStr
    adapter_url: SafeStr
    tags: dict[str, str] = {}
    token: SafeStr | None = None


class DataSourceUpdate(StrictInput):
    """Request body for updating a datasource."""

    display_name: SafeStr | None = None
    adapter_url: SafeStr | None = None
    tags: dict[str, str] | None = None
    token: SafeStr | None = None


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
