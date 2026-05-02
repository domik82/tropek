"""Datasource models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class DataSourceCreate(BaseModel):
    """Request body for registering a new datasource."""

    name: str
    display_name: str | None = None
    adapter_type: str
    adapter_url: str
    tags: dict[str, str] | None = None
    token: str | None = None


class DataSourceRead(BaseModel):
    """Datasource as returned by the API."""

    id: UUID
    name: str
    display_name: str | None = None
    adapter_type: str
    adapter_url: str
    tags: dict[str, Any]
    has_token: bool = False
    created_at: datetime
    updated_at: datetime


class DataSourceUpdate(BaseModel):
    """Request body for updating a datasource."""

    name: str | None = None
    display_name: str | None = None
    adapter_type: str | None = None
    adapter_url: str | None = None
    tags: dict[str, str] | None = None
    token: str | None = None
