"""Asset-family Pydantic schemas — stub for repository tests."""

from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel


class AssetGroupMemberCreate(BaseModel):
    """Payload for adding an asset to a group with an optional weight."""

    asset_id: uuid.UUID
    weight: float = 1.0


class AssetGroupSubgroupCreate(BaseModel):
    """Payload for nesting a child group inside a parent group."""

    child_group_id: uuid.UUID
    weight: float = 1.0


class AssetSLOLinkCreate(BaseModel):
    """Payload for creating a named SLO/SLI/DataSource binding on an asset or group."""

    link_name: str
    slo_name: str
    sli_name: str
    data_source_name: str


class AssetGroupMemberRead(BaseModel):
    """Denormalised read model for an asset member of a group."""

    asset_id: uuid.UUID
    asset_name: str
    weight: float


class AssetGroupSubgroupRead(BaseModel):
    """Denormalised read model for a child group nested inside a parent group."""

    child_group_id: uuid.UUID
    group_name: str
    weight: float


class AssetGroupRead(BaseModel):
    """Full read model for an asset group, including members and subgroups."""

    id: uuid.UUID
    name: str
    display_name: str | None = None
    description: str | None = None
    members: list[AssetGroupMemberRead] = []
    subgroups: list[AssetGroupSubgroupRead] = []
    created_at: datetime.datetime
    updated_at: datetime.datetime


class AssetGroupTreeResponse(BaseModel):
    """Response model for the group tree endpoint: top-level groups plus all groups."""

    top_level: list[AssetGroupRead]
    all_groups: list[AssetGroupRead]
