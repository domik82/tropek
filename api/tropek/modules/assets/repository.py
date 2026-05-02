"""Asset-family repositories: types, assets, groups."""

from __future__ import annotations

import random
import uuid
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.cache.redis_cache import RedisCache
from tropek.db.models import (
    Asset,
    AssetGroup,
    AssetGroupLink,
    AssetGroupMember,
    AssetType,
)
from tropek.modules.assets.params import AssetCreateParams, AssetGroupCreateParams
from tropek.modules.assets.schemas import (
    AssetGroupMemberRead,
    AssetGroupRead,
    AssetGroupSubgroupRead,
    AssetGroupTreeResponse,
)
from tropek.modules.common.exceptions import ConflictError, NotFoundError
from tropek.modules.common.tag_mixin import TagQueryMixin

GROUP_COLOR_PALETTE = [
    '#6897BB',
    '#E8915A',
    '#A371F7',
    '#7DC540',
    '#F85149',
    '#58A6FF',
    '#D4A032',
    '#2DD4A0',
    '#DB61A2',
    '#8B949E',
]


class AssetTypeRepository:
    """CRUD for asset_types table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, name: str, *, is_default: bool = False) -> AssetType:
        """Create a new asset type.

        Args:
            name: Unique name for this asset type.
            is_default: Whether this type is the default.

        Returns:
            The newly created AssetType record.
        """
        at = AssetType(id=uuid.uuid4(), name=name, is_default=is_default)
        self._session.add(at)
        await self._session.flush()
        return at

    async def get_by_name(self, name: str) -> AssetType | None:
        """Return asset type by unique name, or None."""
        result = await self._session.execute(select(AssetType).where(AssetType.name == name))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[AssetType]:
        """Return all asset types ordered by name."""
        result = await self._session.execute(select(AssetType).order_by(AssetType.name))
        return list(result.scalars().all())

    async def set_default(self, name: str) -> AssetType | None:
        """Atomically unset old default and set new one. Returns None if name not found."""
        # Check existence FIRST — otherwise a typo clears the current default with no replacement
        result = await self._session.execute(select(AssetType).where(AssetType.name == name))
        at = result.scalar_one_or_none()
        if at is None:
            return None
        await self._session.execute(update(AssetType).values(is_default=False))
        await self._session.execute(update(AssetType).where(AssetType.name == name).values(is_default=True))
        await self._session.refresh(at)
        return at

    async def delete(self, name: str) -> bool:
        """Hard-delete if not referenced by any asset. Returns False if name not found, raises 409 if in use."""
        existing = await self.get_by_name(name)
        if existing is None:
            return False
        in_use = await self._session.execute(select(Asset.id).where(Asset.type_name == name).limit(1))
        if in_use.scalar_one_or_none() is not None:
            raise ConflictError('asset type', name, 'in use by one or more assets')
        await self._session.execute(delete(AssetType).where(AssetType.name == name))
        return True

    async def rename(self, old_name: str, new_name: str) -> AssetType | None:
        """Rename an asset type. Returns None if old_name not found, raises 409 if new_name taken."""
        existing = await self.get_by_name(old_name)
        if existing is None:
            return None
        conflict = await self.get_by_name(new_name)
        if conflict is not None:
            raise ConflictError('asset type', new_name, 'already exists')
        await self._session.execute(update(AssetType).where(AssetType.name == old_name).values(name=new_name))
        # Also update all assets referencing this type
        await self._session.execute(update(Asset).where(Asset.type_name == old_name).values(type_name=new_name))
        return await self.get_by_name(new_name)

    async def get_asset_counts(self) -> dict[str, int]:
        """Return count of assets per type name."""
        result = await self._session.execute(select(Asset.type_name, func.count(Asset.id)).group_by(Asset.type_name))
        return {row[0]: row[1] for row in result}


class AssetRepository(TagQueryMixin):
    """CRUD for assets table."""

    _tag_model = Asset

    def __init__(self, session: AsyncSession, cache: RedisCache | None = None) -> None:
        self._session = session
        self._cache = cache

    async def create(self, params: AssetCreateParams) -> Asset:
        """Create a new asset.

        Args:
            params: Validated parameters for the new asset.

        Returns:
            The newly created Asset record.
        """
        asset = Asset(
            id=uuid.uuid4(),
            name=params.name,
            display_name=params.display_name,
            color=params.color,
            type_name=params.type_name,
            tags=params.tags,
            variables=params.variables,
            heatmap_config=params.heatmap_config,
        )
        self._session.add(asset)
        await self._session.flush()
        return asset

    async def get_by_name(self, name: str) -> Asset | None:
        """Return asset by unique name, or None."""
        result = await self._session.execute(select(Asset).where(Asset.name == name))
        return result.scalar_one_or_none()

    async def list_all(
        self,
        *,
        type_name: str | None = None,
        tag_key: str | None = None,
        tag_val: str | None = None,
    ) -> list[Asset]:
        """Return all assets, optionally filtered by type or tag.

        Args:
            type_name: When given, only return assets of this type.
            tag_key: Tag key to filter by (requires tag_val).
            tag_val: Tag value to filter by (requires tag_key).

        Returns:
            Matching Asset records ordered by name.
        """
        q = select(Asset)
        if type_name:
            q = q.where(Asset.type_name == type_name)
        if tag_key and tag_val:
            q = q.where(Asset.tags[tag_key].as_string() == tag_val)
        q = q.order_by(Asset.name)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def update(self, name: str, **kwargs: Any) -> Asset:
        """Update mutable fields on an existing asset. Raises 404 if not found.

        Args:
            name: Unique asset name to update.
            **kwargs: Fields to update (display_name, type_name, tags, variables).

        Returns:
            Updated Asset record.
        """
        if kwargs:
            await self._session.execute(update(Asset).where(Asset.name == name).values(**kwargs))
        asset = await self.get_by_name(name)
        if asset is None:
            raise NotFoundError('asset', name)
        if self._cache:
            await self._cache.invalidate(f'asset:{asset.id}')
            await self._cache.invalidate(f'asset:name:{name}')
        return asset

    async def delete(self, name: str) -> bool:
        """Delete an asset by name, removing all group memberships."""
        asset = await self.get_by_name(name)
        if asset is None:
            return False
        # Remove group memberships
        await self._session.execute(delete(AssetGroupMember).where(AssetGroupMember.asset_id == asset.id))
        # Delete the asset itself
        await self._session.execute(delete(Asset).where(Asset.id == asset.id))
        if self._cache:
            await self._cache.invalidate(f'asset:{asset.id}')
            await self._cache.invalidate(f'asset:name:{name}')
        return True


class AssetGroupRepository:
    """CRUD for asset_groups, asset_group_members, and asset_group_links tables."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _build_read(self, group: AssetGroup) -> AssetGroupRead:
        """Load members + subgroups with denormalised names and build AssetGroupRead."""
        # Members: join with assets to get asset_name
        member_rows = await self._session.execute(
            select(
                AssetGroupMember,
                Asset.name.label('asset_name'),
                Asset.display_name.label('asset_display_name'),
                Asset.type_name.label('asset_type_name'),
            )
            .join(Asset, AssetGroupMember.asset_id == Asset.id)
            .where(AssetGroupMember.asset_group_id == group.id)
        )
        members = [
            AssetGroupMemberRead(
                asset_id=row.AssetGroupMember.asset_id,
                asset_name=row.asset_name,
                asset_display_name=row.asset_display_name,
                asset_type_name=row.asset_type_name,
                weight=row.AssetGroupMember.weight,
            )
            for row in member_rows
        ]

        # Subgroups: join with asset_groups to get group_name
        subgroup_rows = await self._session.execute(
            select(AssetGroupLink, AssetGroup.name.label('group_name'))
            .join(AssetGroup, AssetGroupLink.child_asset_group_id == AssetGroup.id)
            .where(AssetGroupLink.parent_asset_group_id == group.id)
        )
        subgroups = [
            AssetGroupSubgroupRead(
                group_id=row.AssetGroupLink.child_asset_group_id,
                group_name=row.group_name,
                weight=row.AssetGroupLink.weight,
            )
            for row in subgroup_rows
        ]

        return AssetGroupRead(
            id=group.id,
            name=group.name,
            display_name=group.display_name,
            description=group.description,
            color=group.color,
            members=members,
            subgroups=subgroups,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )

    async def create(self, params: AssetGroupCreateParams) -> AssetGroupRead:
        """Create a new asset group with optional members and subgroups.

        Args:
            params: Validated parameters for the new asset group.

        Returns:
            The newly created AssetGroupRead with members and subgroups.
        """
        group = AssetGroup(
            id=uuid.uuid4(),
            name=params.name,
            display_name=params.display_name,
            description=params.description,
            color=params.color if params.color is not None else random.choice(GROUP_COLOR_PALETTE),  # noqa: S311
        )
        self._session.add(group)
        await self._session.flush()  # get group.id

        for m in params.members:
            self._session.add(AssetGroupMember(asset_group_id=group.id, asset_id=m.asset_id, weight=m.weight))
        for sg in params.subgroups:
            self._session.add(
                AssetGroupLink(
                    parent_asset_group_id=group.id,
                    child_asset_group_id=sg.child_group_id,
                    weight=sg.weight,
                )
            )
        await self._session.flush()
        return await self._build_read(group)

    async def get_by_name(self, name: str) -> AssetGroupRead | None:
        """Return asset group by unique name with members and subgroups, or None."""
        result = await self._session.execute(select(AssetGroup).where(AssetGroup.name == name))
        group = result.scalar_one_or_none()
        if group is None:
            return None
        return await self._build_read(group)

    async def update(self, name: str, **kwargs: Any) -> AssetGroupRead | None:
        """Update mutable fields on an existing asset group.

        Args:
            name: Unique group name to update.
            **kwargs: Fields to update (display_name, description, color).

        Returns:
            Updated AssetGroupRead, or None if not found.
        """
        if kwargs:
            await self._session.execute(update(AssetGroup).where(AssetGroup.name == name).values(**kwargs))
        result = await self._session.execute(select(AssetGroup).where(AssetGroup.name == name))
        group = result.scalar_one_or_none()
        if group is None:
            return None
        return await self._build_read(group)

    async def _collect_subgroup_ids(self, group_id: uuid.UUID) -> list[uuid.UUID]:
        """Recursively collect all descendant group IDs."""
        result = await self._session.execute(
            select(AssetGroupLink.child_asset_group_id).where(AssetGroupLink.parent_asset_group_id == group_id)
        )
        child_ids = list(result.scalars().all())
        all_ids: list[uuid.UUID] = []
        for cid in child_ids:
            all_ids.append(cid)
            all_ids.extend(await self._collect_subgroup_ids(cid))
        return all_ids

    async def delete_group(self, name: str, *, deactivate_slos: bool = False) -> bool:
        """Delete an asset group and all its descendants.

        Args:
            name: Unique group name to delete.
            deactivate_slos: Ignored — kept for API compatibility. SLO deactivation is
                now handled via the assignment layer.

        Returns:
            True if the group was found and deleted, False if not found.
        """
        result = await self._session.execute(select(AssetGroup).where(AssetGroup.name == name))
        group = result.scalar_one_or_none()
        if group is None:
            return False
        all_group_ids = [group.id, *await self._collect_subgroup_ids(group.id)]
        for gid in reversed(all_group_ids):
            await self._session.execute(delete(AssetGroup).where(AssetGroup.id == gid))
        await self._session.flush()
        return True

    async def list_group_ids_for_asset(self, asset_id: uuid.UUID) -> list[uuid.UUID]:
        """Return IDs of all groups that contain this asset as a direct member."""
        result = await self._session.execute(
            select(AssetGroupMember.asset_group_id).where(AssetGroupMember.asset_id == asset_id)
        )
        return list(result.scalars().all())

    async def list_all(self) -> list[AssetGroupRead]:
        """Return all asset groups ordered by name, each with members and subgroups."""
        result = await self._session.execute(select(AssetGroup).order_by(AssetGroup.name))
        groups = list(result.scalars().all())
        return [await self._build_read(g) for g in groups]

    async def get_tree(self) -> AssetGroupTreeResponse:
        """Return the full group hierarchy with top-level and all groups.

        Returns:
            AssetGroupTreeResponse with top_level (not children of any group) and all_groups.
        """
        # child_ids = groups that appear as a child of some other group
        child_ids_result = await self._session.execute(select(AssetGroupLink.child_asset_group_id).distinct())
        child_ids = set(child_ids_result.scalars())

        all_result = await self._session.execute(select(AssetGroup).order_by(AssetGroup.name))
        all_groups = list(all_result.scalars().all())
        all_reads = [await self._build_read(g) for g in all_groups]
        top_level = [r for r in all_reads if r.id not in child_ids]
        return AssetGroupTreeResponse(top_level=top_level, all_groups=all_reads)

    async def add_member(self, group_name: str, asset_id: uuid.UUID, *, weight: float = 1.0) -> AssetGroupRead:
        """Add an asset as a member of a group. Raises 404 if group not found.

        Args:
            group_name: Name of the parent group.
            asset_id: UUID of the asset to add.
            weight: Relative weight of this member.

        Returns:
            Updated AssetGroupRead with the new member.
        """
        result = await self._session.execute(select(AssetGroup).where(AssetGroup.name == group_name))
        group = result.scalar_one_or_none()
        if group is None:
            raise NotFoundError('asset group', group_name)
        self._session.add(AssetGroupMember(asset_group_id=group.id, asset_id=asset_id, weight=weight))
        await self._session.flush()
        return await self._build_read(group)

    async def remove_member(self, group_name: str, asset_id: uuid.UUID) -> None:
        """Remove a member asset from a group. Raises 404 if group not found.

        Args:
            group_name: Name of the parent group.
            asset_id: UUID of the asset to remove.
        """
        result = await self._session.execute(select(AssetGroup).where(AssetGroup.name == group_name))
        group = result.scalar_one_or_none()
        if group is None:
            raise NotFoundError('asset group', group_name)
        await self._session.execute(
            delete(AssetGroupMember).where(
                AssetGroupMember.asset_group_id == group.id,
                AssetGroupMember.asset_id == asset_id,
            )
        )

    async def add_subgroup(self, parent_name: str, child_group_id: uuid.UUID, *, weight: float = 1.0) -> AssetGroupRead:
        """Add a child group as a subgroup of a parent. Raises 404 if parent not found.

        Args:
            parent_name: Name of the parent group.
            child_group_id: UUID of the child group to add.
            weight: Relative weight of this subgroup.

        Returns:
            Updated AssetGroupRead with the new subgroup.
        """
        result = await self._session.execute(select(AssetGroup).where(AssetGroup.name == parent_name))
        group = result.scalar_one_or_none()
        if group is None:
            raise NotFoundError('asset group', parent_name)
        self._session.add(
            AssetGroupLink(parent_asset_group_id=group.id, child_asset_group_id=child_group_id, weight=weight)
        )
        await self._session.flush()
        return await self._build_read(group)

    async def remove_subgroup(self, parent_name: str, child_group_id: uuid.UUID) -> None:
        """Remove a child group from a parent. Raises 404 if parent not found.

        Args:
            parent_name: Name of the parent group.
            child_group_id: UUID of the child group to remove.
        """
        result = await self._session.execute(select(AssetGroup).where(AssetGroup.name == parent_name))
        group = result.scalar_one_or_none()
        if group is None:
            raise NotFoundError('asset group', parent_name)
        await self._session.execute(
            delete(AssetGroupLink).where(
                AssetGroupLink.parent_asset_group_id == group.id,
                AssetGroupLink.child_asset_group_id == child_group_id,
            )
        )
