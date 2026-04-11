"""Protocol types for repository interfaces used by trigger resolution."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.db.models import Asset, DataSource, SLIDefinition, SLODefinition
from app.modules.assignments.repository import ResolvedAssignment


class AssetReader(Protocol):
    """Read-only protocol for asset lookup by name."""

    async def get_by_name(self, name: str) -> Asset | None:
        """Return asset by unique name, or None."""
        ...


class SLIReader(Protocol):
    """Read-only protocol for SLI definition lookup."""

    async def get_latest(self, name: str) -> SLIDefinition | None:
        """Return the latest active version, or None."""
        ...

    async def get_version(self, name: str, version: int) -> SLIDefinition | None:
        """Return a specific version, or None."""
        ...

    async def get_by_id(self, sli_id: uuid.UUID) -> SLIDefinition | None:
        """Return a definition by primary key, or None."""
        ...


class SLOReader(Protocol):
    """Read-only protocol for SLO definition lookup."""

    async def get_latest(self, name: str) -> SLODefinition | None:
        """Return the latest version, or None."""
        ...

    async def get_version(self, name: str, version: int) -> SLODefinition | None:
        """Return a specific version, or None."""
        ...

    async def get_by_id(self, slo_id: uuid.UUID) -> SLODefinition | None:
        """Return a definition by primary key, or None."""
        ...


class AssignmentReader(Protocol):
    """Read-only protocol for assignment resolution."""

    async def resolve_for_asset(
        self, asset_id: uuid.UUID, group_ids: list[uuid.UUID]
    ) -> list[ResolvedAssignment]:
        """Return all resolved assignments for an asset (direct + group)."""
        ...

    async def find_for_asset(
        self, asset_id: uuid.UUID, group_ids: list[uuid.UUID], slo_name: str
    ) -> ResolvedAssignment | None:
        """Return the winning assignment for a specific SLO name, or None."""
        ...


class DataSourceReader(Protocol):
    """Read-only protocol for data source lookup."""

    async def get_by_id(self, ds_id: uuid.UUID) -> DataSource | None:
        """Return datasource by primary key, or None."""
        ...
