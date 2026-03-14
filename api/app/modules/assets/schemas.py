"""Pydantic schemas for asset types, assets, asset groups, and SLO bindings."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

# ---- Asset Types ----


class AssetTypeCreate(BaseModel):
    """Request body for creating an asset type."""

    name: str
    is_default: bool = False


class AssetTypeRead(BaseModel):
    """Response schema for an asset type."""

    id: uuid.UUID
    name: str
    is_default: bool

    model_config = ConfigDict(from_attributes=True)


# ---- Assets ----


class AssetCreate(BaseModel):
    """Request body for creating an asset."""

    name: str
    display_name: str | None = None
    type_name: str
    labels: dict[str, str] = {}


class AssetUpdate(BaseModel):
    """Request body for updating an asset."""

    display_name: str | None = None
    type_name: str | None = None
    labels: dict[str, str] | None = None


class AssetRead(BaseModel):
    """Response schema for an asset."""

    id: uuid.UUID
    name: str
    display_name: str | None
    type_name: str
    labels: dict[str, Any]
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


class AssetGroupCreate(BaseModel):
    """Request body for creating an asset group."""

    name: str
    display_name: str | None = None
    description: str | None = None
    members: list[AssetGroupMemberCreate] = []
    subgroups: list[AssetGroupSubgroupCreate] = []


class AssetGroupMemberRead(BaseModel):
    """Read schema for a group member entry."""

    asset_id: uuid.UUID
    asset_name: str
    weight: float


class AssetGroupSubgroupRead(BaseModel):
    """Read schema for a subgroup entry."""

    child_group_id: uuid.UUID
    group_name: str
    weight: float


class AssetGroupRead(BaseModel):
    """Response schema for an asset group with members and subgroups."""

    id: uuid.UUID
    name: str
    display_name: str | None
    description: str | None
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


class AddMemberRequest(BaseModel):
    """Request body for POST /asset-groups/{name}/members."""

    asset_id: uuid.UUID
    weight: float = 1.0


class AddSubgroupRequest(BaseModel):
    """Request body for POST /asset-groups/{name}/subgroups."""

    child_group_id: uuid.UUID
    weight: float = 1.0


# ---- Bindings ----


class AssetSLOLinkCreate(BaseModel):
    """Request body for creating an asset SLO link."""

    link_name: str
    slo_name: str
    sli_name: str
    data_source_name: str


class AssetSLOLinkRead(BaseModel):
    """Response schema for an asset SLO link."""

    id: uuid.UUID
    link_name: str
    asset_id: uuid.UUID
    slo_name: str
    sli_name: str
    data_source_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssetGroupSLOLinkCreate(BaseModel):
    """Request body for creating an asset group SLO link."""

    link_name: str
    slo_name: str
    sli_name: str
    data_source_name: str


class AssetGroupSLOLinkRead(BaseModel):
    """Response schema for an asset group SLO link."""

    id: uuid.UUID
    link_name: str
    group_id: uuid.UUID
    slo_name: str
    sli_name: str
    data_source_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
