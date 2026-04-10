"""Pydantic schemas for asset types, assets, asset groups, and SLO bindings."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.modules.common.schemas import StrictInput

# ---- Asset Types ----


class AssetTypeCreate(StrictInput):
    """Request body for creating an asset type."""

    name: str
    is_default: bool = False


class AssetTypeUpdate(StrictInput):
    """Request body for renaming an asset type."""

    name: str | None = None


class AssetTypeRead(BaseModel):
    """Response schema for an asset type."""

    id: uuid.UUID
    name: str
    is_default: bool
    asset_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# ---- Assets ----


class AssetCreate(StrictInput):
    """Request body for creating an asset."""

    name: str
    display_name: str | None = None
    type_name: str
    tags: dict[str, str] = {}
    variables: dict[str, str] = {}
    color: str | None = None


class AssetUpdate(StrictInput):
    """Request body for updating an asset."""

    display_name: str | None = None
    type_name: str | None = None
    tags: dict[str, str] | None = None
    variables: dict[str, str] | None = None
    heatmap_config: dict[str, Any] | None = None
    color: str | None = None


class AssetRead(BaseModel):
    """Response schema for an asset."""

    id: uuid.UUID
    name: str
    display_name: str | None
    type_name: str
    tags: dict[str, Any]
    variables: dict[str, Any]
    heatmap_config: dict[str, Any] | None = None
    color: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---- Asset Groups ----


class AssetGroupMemberCreate(BaseModel):
    """Request body for adding an asset to a group."""

    asset_id: uuid.UUID
    weight: float = 1.0


class AssetGroupSubgroupCreate(BaseModel):
    """Request body for adding a subgroup to a group."""

    child_group_id: uuid.UUID
    weight: float = 1.0


class AssetGroupCreate(StrictInput):
    """Request body for creating an asset group."""

    name: str
    display_name: str | None = None
    description: str | None = None
    color: str | None = None
    members: list[AssetGroupMemberCreate] = []
    subgroups: list[AssetGroupSubgroupCreate] = []


class AssetGroupUpdate(StrictInput):
    """Request body for updating an asset group."""

    display_name: str | None = None
    description: str | None = None
    color: str | None = None


class AssetGroupMemberRead(BaseModel):
    """Read schema for a group member entry."""

    asset_id: uuid.UUID
    asset_name: str
    asset_display_name: str | None = None
    asset_type_name: str
    weight: float


class AssetGroupSubgroupRead(BaseModel):
    """Read schema for a subgroup entry."""

    group_id: uuid.UUID
    group_name: str
    weight: float


class AssetGroupRead(BaseModel):
    """Response schema for an asset group with members and subgroups."""

    id: uuid.UUID
    name: str
    display_name: str | None
    description: str | None
    color: str | None = None
    members: list[AssetGroupMemberRead]
    subgroups: list[AssetGroupSubgroupRead]
    created_at: datetime
    updated_at: datetime

    # AssetGroup ORM has no relationships for members/subgroups.
    # Always construct explicitly — never use model_validate(orm_obj).


class AssetGroupTreeResponse(BaseModel):
    """Response for the group tree endpoint."""

    top_level: list[AssetGroupRead]
    all_groups: list[AssetGroupRead]


class AddMemberRequest(StrictInput):
    """Request body for POST /asset-groups/{name}/members."""

    asset_id: uuid.UUID
    weight: float = 1.0


class AddSubgroupRequest(StrictInput):
    """Request body for POST /asset-groups/{name}/subgroups."""

    child_group_id: uuid.UUID
    weight: float = 1.0


