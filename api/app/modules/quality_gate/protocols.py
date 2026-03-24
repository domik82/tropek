"""Protocol types for repository interfaces used by trigger resolution.

These structural-subtyping protocols decouple the trigger logic from concrete
repository implementations, improving testability and type safety.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from app.db.models import Asset, AssetSLOLink, DataSource, SLIDefinition, SLOBinding, SLODefinition


class AssetReader(Protocol):
    """Read-only protocol for asset lookup by name."""

    async def get_by_name(self, name: str) -> Asset | None:
        """Return asset by unique name, or None."""
        ...


class SLOLinkReader(Protocol):
    """Read-only protocol for listing SLO links bound to an asset."""

    async def list_by_asset(self, asset_id: uuid.UUID) -> list[AssetSLOLink]:
        """Return all SLO links for an asset."""
        ...


class SLIReader(Protocol):
    """Read-only protocol for SLI definition lookup."""

    async def get_latest(self, name: str) -> SLIDefinition | None:
        """Return the latest active version, or None."""
        ...

    async def get_version(self, name: str, version: int) -> SLIDefinition | None:
        """Return a specific version, or None."""
        ...


class SLOReader(Protocol):
    """Read-only protocol for SLO definition lookup."""

    async def get_latest(self, name: str) -> SLODefinition | None:
        """Return the latest version, or None."""
        ...

    async def get_version(self, name: str, version: int) -> SLODefinition | None:
        """Return a specific version, or None."""
        ...


class SLOBindingReader(Protocol):
    """Read-only protocol for SLO binding lookup."""

    async def find_for_asset(self, asset_id: uuid.UUID, slo_name: str) -> SLOBinding | None:
        """Find a binding for an asset+SLO pair (direct or via group)."""
        ...


class DataSourceReader(Protocol):
    """Read-only protocol for data source lookup by name."""

    async def get_by_name(self, name: str) -> DataSource | None:
        """Return datasource by unique name, or None."""
        ...
