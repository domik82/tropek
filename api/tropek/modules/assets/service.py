"""Asset service layer — orchestration logic for asset/group resolution."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from tropek.modules.assets.repository import AssetGroupRepository, AssetRepository
from tropek.modules.common.exceptions import NotFoundError


@dataclass(frozen=True)
class ResolvedAssetScope:
    """Result of resolving asset/group names to internal IDs.

    ``asset_id`` narrows to a single asset; ``asset_ids`` narrows to a set
    (typically the members of a group). Either, both, or neither may be set
    depending on which filters the caller provided.
    """

    asset_id: uuid.UUID | None
    asset_ids: list[uuid.UUID] | None


class AssetService:
    """Encapsulates asset/group name resolution for query endpoints."""

    def __init__(self, asset_repo: AssetRepository, group_repo: AssetGroupRepository) -> None:
        self._asset_repo = asset_repo
        self._group_repo = group_repo

    async def resolve_asset_ids(
        self,
        asset_name: str | None,
        group_name: str | None,
    ) -> ResolvedAssetScope:
        """Resolve optional asset/group names to a query scope.

        Args:
            asset_name: If given, must refer to an existing asset.
            group_name: If given, names an asset group whose members constrain the scope.
                A missing group is treated as an empty scope (asset_ids stays None).

        Returns:
            ResolvedAssetScope with the asset_id and/or asset_ids fields populated.

        Raises:
            NotFoundError: If ``asset_name`` is given but no such asset exists.
        """
        resolved_asset_id: uuid.UUID | None = None
        asset_ids: list[uuid.UUID] | None = None

        if asset_name:
            asset = await self._asset_repo.get_by_name(asset_name)
            if asset is None:
                raise NotFoundError('asset', asset_name)
            resolved_asset_id = asset.id

        if group_name:
            group = await self._group_repo.get_by_name(group_name)
            if group:
                asset_ids = [m.asset_id for m in group.members]

        return ResolvedAssetScope(asset_id=resolved_asset_id, asset_ids=asset_ids)
