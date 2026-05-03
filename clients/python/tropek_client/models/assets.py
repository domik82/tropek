"""Asset models for TROPEK API."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AssetCreate(BaseModel):
    """Asset creation request."""

    name: str
    display_name: str | None = None
    type_name: str
    tags: dict[str, Any] | None = None
    variables: dict[str, Any] | None = None
    color: str | None = None
    heatmap_config: dict[str, Any] | None = None


class AssetRead(BaseModel):
    """Asset response."""

    id: UUID
    name: str
    display_name: str | None
    type_name: str
    tags: dict[str, str]
    variables: dict[str, str]
    heatmap_config: dict[str, Any] | None = None
    color: str | None = None
    created_at: datetime
    updated_at: datetime


class AssetUpdate(BaseModel):
    """Asset update request."""

    display_name: str | None = None
    type_name: str | None = None
    tags: dict[str, Any] | None = None
    variables: dict[str, Any] | None = None
    heatmap_config: dict[str, Any] | None = None
    color: str | None = None


class AssetSnapshot(BaseModel):
    """Asset snapshot for evaluation context."""

    asset_id: str | None = None
    name: str
    display_name: str | None = None
    tags: dict[str, str] | None = None
    primary_version: str | None = None
    build_ref: str | None = None
