"""Asset group models for TROPEK API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AssetGroupMemberCreate(BaseModel):
    """Asset group member creation request."""

    asset_id: UUID
    weight: float | int | None = None


class AssetGroupMemberRead(BaseModel):
    """Asset group member response."""

    asset_id: UUID
    asset_name: str
    asset_display_name: str | None = None
    asset_type_name: str
    weight: float | int


class AssetGroupSubgroupCreate(BaseModel):
    """Asset group subgroup creation request."""

    child_group_id: UUID
    weight: float | int | None = None


class AssetGroupSubgroupRead(BaseModel):
    """Asset group subgroup response."""

    group_id: UUID
    group_name: str
    weight: float | int


class AssetGroupCreate(BaseModel):
    """Asset group creation request."""

    name: str
    display_name: str | None = None
    description: str | None = None
    color: str | None = None
    members: list[AssetGroupMemberCreate] | None = None
    subgroups: list[AssetGroupSubgroupCreate] | None = None


class AssetGroupRead(BaseModel):
    """Asset group response."""

    id: UUID
    name: str
    display_name: str | None
    description: str | None
    color: str | None = None
    members: list[AssetGroupMemberRead]
    subgroups: list[AssetGroupSubgroupRead]
    created_at: datetime
    updated_at: datetime


class AssetGroupUpdate(BaseModel):
    """Asset group update request."""

    display_name: str | None = None
    description: str | None = None
    color: str | None = None


class AssetGroupTreeResponse(BaseModel):
    """Asset group tree response."""

    top_level: list[AssetGroupRead]
    all_groups: list[AssetGroupRead]


class AddMemberRequest(BaseModel):
    """Add asset group member request."""

    asset_id: UUID
    weight: float | int | None = None


class AddSubgroupRequest(BaseModel):
    """Add asset group subgroup request."""

    child_group_id: UUID
    weight: float | int | None = None


class AssetScope(BaseModel):
    """Asset scope for evaluations."""

    kind: str
    asset_name: str
