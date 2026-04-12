"""Pydantic parameter models for asset repository methods."""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field

from tropek.modules.assets.schemas import AssetGroupMemberCreate, AssetGroupSubgroupCreate
from tropek.modules.common.schemas import StrictInput


class AssetCreateParams(StrictInput):
    """Parameters for AssetRepository.create()."""

    name: str
    type_name: str = 'vm'
    display_name: str | None = None
    color: str | None = None
    tags: dict[str, Any] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)


class AssetGroupCreateParams(StrictInput):
    """Parameters for AssetGroupRepository.create()."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    display_name: str | None = None
    description: str | None = None
    color: str | None = None
    members: list[AssetGroupMemberCreate] = Field(default_factory=list)
    subgroups: list[AssetGroupSubgroupCreate] = Field(default_factory=list)
