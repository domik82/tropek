"""Asset-family repositories: types, assets, groups, and SLO bindings."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis_cache import RedisCache
from app.db.models import (
    Asset,
    AssetGroup,
    AssetGroupLink,
    AssetGroupMember,
    AssetGroupSLOLink,
    AssetSLOLink,
    AssetType,
    SLODefinition,
)
from app.modules.assets.schemas import (
    AssetGroupMemberCreate,
    AssetGroupMemberRead,
    AssetGroupRead,
    AssetGroupSubgroupCreate,
    AssetGroupSubgroupRead,
    AssetGroupTreeResponse,
)


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
        await self._session.execute(
            update(AssetType).where(AssetType.name == name).values(is_default=True)
        )
        await self._session.refresh(at)
        return at

    async def delete(self, name: str) -> bool:
        """Hard-delete if not referenced by any asset. Returns False if name not found, raises 409 if in use."""
        existing = await self.get_by_name(name)
        if existing is None:
            return False
        in_use = await self._session.execute(
            select(Asset.id).where(Asset.type_name == name).limit(1)
        )
        if in_use.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=409,
                detail=f"asset type '{name}' is in use by one or more assets",
            )
        await self._session.execute(delete(AssetType).where(AssetType.name == name))
        return True

    async def rename(self, old_name: str, new_name: str) -> AssetType | None:
        """Rename an asset type. Returns None if old_name not found, raises 409 if new_name taken."""
        existing = await self.get_by_name(old_name)
        if existing is None:
            return None
        conflict = await self.get_by_name(new_name)
        if conflict is not None:
            raise HTTPException(
                status_code=409,
                detail=f"asset type '{new_name}' already exists",
            )
        await self._session.execute(
            update(AssetType).where(AssetType.name == old_name).values(name=new_name)
        )
        # Also update all assets referencing this type
        await self._session.execute(
            update(Asset).where(Asset.type_name == old_name).values(type_name=new_name)
        )
        return await self.get_by_name(new_name)

    async def get_asset_counts(self) -> dict[str, int]:
        """Return count of assets per type name."""
        result = await self._session.execute(
            select(Asset.type_name, func.count(Asset.id)).group_by(Asset.type_name)
        )
        return {row[0]: row[1] for row in result}


class AssetRepository:
    """CRUD for assets table."""

    def __init__(self, session: AsyncSession, cache: RedisCache | None = None) -> None:
        self._session = session
        self._cache = cache

    async def create(
        self,
        name: str,
        *,
        type_name: str = "vm",
        display_name: str | None = None,
        tags: dict[str, Any] | None = None,
        variables: dict[str, Any] | None = None,
    ) -> Asset:
        """Create a new asset.

        Args:
            name: Unique name for this asset.
            type_name: Asset type name (must exist in asset_types).
            display_name: Optional human-readable label.
            tags: Optional free-form metadata tags.
            variables: Optional template variable bindings.

        Returns:
            The newly created Asset record.
        """
        asset = Asset(
            id=uuid.uuid4(),
            name=name,
            display_name=display_name,
            type_name=type_name,
            tags=tags or {},
            variables=variables or {},
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
        filtered = {k: v for k, v in kwargs.items() if v is not None}
        if filtered:
            await self._session.execute(update(Asset).where(Asset.name == name).values(**filtered))
        asset = await self.get_by_name(name)
        if asset is None:
            raise HTTPException(status_code=404, detail=f"asset '{name}' not found")
        if self._cache:
            await self._cache.invalidate(f"asset:{asset.id}")
            await self._cache.invalidate(f"asset:name:{name}")
        return asset

    async def delete(self, name: str) -> bool:
        """Delete an asset by name, removing all group memberships and SLO links.

        Returns False if asset not found.
        """
        asset = await self.get_by_name(name)
        if asset is None:
            return False
        # Remove group memberships
        await self._session.execute(
            delete(AssetGroupMember).where(AssetGroupMember.asset_id == asset.id)
        )
        # Remove SLO links
        await self._session.execute(delete(AssetSLOLink).where(AssetSLOLink.asset_id == asset.id))
        # Delete the asset itself
        await self._session.execute(delete(Asset).where(Asset.id == asset.id))
        if self._cache:
            await self._cache.invalidate(f"asset:{asset.id}")
            await self._cache.invalidate(f"asset:name:{name}")
        return True

    async def get_tag_keys(self) -> dict[str, int]:
        """Return all distinct tag keys with count of assets using each."""
        result = await self._session.execute(
            text(
                "SELECT key, COUNT(*) as cnt "
                "FROM assets, jsonb_object_keys(tags) AS key "
                "GROUP BY key ORDER BY cnt DESC"
            )
        )
        return {row[0]: row[1] for row in result}

    async def get_tag_values(self, key: str) -> dict[str, int]:
        """Return all distinct values for a tag key with usage counts."""
        result = await self._session.execute(
            text(
                "SELECT tags->>:key AS val, COUNT(*) as cnt "
                "FROM assets "
                "WHERE tags ? :key "
                "GROUP BY val ORDER BY cnt DESC"
            ),
            {"key": key},
        )
        return {row[0]: row[1] for row in result}


class AssetGroupRepository:
    """CRUD for asset_groups, asset_group_members, and asset_group_links tables."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _build_read(self, group: AssetGroup) -> AssetGroupRead:
        """Load members + subgroups with denormalised names and build AssetGroupRead."""
        # Members: join with assets to get asset_name
        member_rows = await self._session.execute(
            select(AssetGroupMember, Asset.name.label("asset_name"))
            .join(Asset, AssetGroupMember.asset_id == Asset.id)
            .where(AssetGroupMember.group_id == group.id)
        )
        members = [
            AssetGroupMemberRead(
                asset_id=row.AssetGroupMember.asset_id,
                asset_name=row.asset_name,
                weight=row.AssetGroupMember.weight,
            )
            for row in member_rows
        ]

        # Subgroups: join with asset_groups to get group_name
        subgroup_rows = await self._session.execute(
            select(AssetGroupLink, AssetGroup.name.label("group_name"))
            .join(AssetGroup, AssetGroupLink.child_group_id == AssetGroup.id)
            .where(AssetGroupLink.parent_group_id == group.id)
        )
        subgroups = [
            AssetGroupSubgroupRead(
                group_id=row.AssetGroupLink.child_group_id,
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
            members=members,
            subgroups=subgroups,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )

    async def create(
        self,
        name: str,
        *,
        display_name: str | None = None,
        description: str | None = None,
        members: list[AssetGroupMemberCreate] | None = None,
        subgroups: list[AssetGroupSubgroupCreate] | None = None,
    ) -> AssetGroupRead:
        """Create a new asset group with optional members and subgroups.

        Args:
            name: Unique name for this group.
            display_name: Optional human-readable label.
            description: Optional description text.
            members: Initial member assets to add.
            subgroups: Initial child groups to add.

        Returns:
            The newly created AssetGroupRead with members and subgroups.
        """
        group = AssetGroup(
            id=uuid.uuid4(),
            name=name,
            display_name=display_name,
            description=description,
        )
        self._session.add(group)
        await self._session.flush()  # get group.id

        for m in members or []:
            self._session.add(
                AssetGroupMember(group_id=group.id, asset_id=m.asset_id, weight=m.weight)
            )
        for sg in subgroups or []:
            self._session.add(
                AssetGroupLink(
                    parent_group_id=group.id,
                    child_group_id=sg.child_group_id,
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
            **kwargs: Fields to update (display_name, description).

        Returns:
            Updated AssetGroupRead, or None if not found.
        """
        filtered = {k: v for k, v in kwargs.items() if v is not None}
        if filtered:
            await self._session.execute(
                update(AssetGroup).where(AssetGroup.name == name).values(**filtered)
            )
        result = await self._session.execute(select(AssetGroup).where(AssetGroup.name == name))
        group = result.scalar_one_or_none()
        if group is None:
            return None
        return await self._build_read(group)

    async def _collect_subgroup_ids(self, group_id: uuid.UUID) -> list[uuid.UUID]:
        """Recursively collect all descendant group IDs."""
        result = await self._session.execute(
            select(AssetGroupLink.child_group_id).where(AssetGroupLink.parent_group_id == group_id)
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
            deactivate_slos: When True, soft-delete SLOs linked to the group tree.

        Returns:
            True if the group was found and deleted, False if not found.
        """
        result = await self._session.execute(select(AssetGroup).where(AssetGroup.name == name))
        group = result.scalar_one_or_none()
        if group is None:
            return False
        all_group_ids = [group.id, *await self._collect_subgroup_ids(group.id)]
        if deactivate_slos:
            slo_names_result = await self._session.execute(
                select(AssetGroupSLOLink.slo_name)
                .where(AssetGroupSLOLink.group_id.in_(all_group_ids))
                .distinct()
            )
            slo_names = list(slo_names_result.scalars().all())
            if slo_names:
                await self._session.execute(
                    update(SLODefinition)
                    .where(SLODefinition.name.in_(slo_names))
                    .values(active=False)
                )
        for gid in reversed(all_group_ids):
            await self._session.execute(delete(AssetGroup).where(AssetGroup.id == gid))
        await self._session.flush()
        return True

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
        child_ids_result = await self._session.execute(
            select(AssetGroupLink.child_group_id).distinct()
        )
        child_ids = {row for row in child_ids_result.scalars()}

        all_result = await self._session.execute(select(AssetGroup).order_by(AssetGroup.name))
        all_groups = list(all_result.scalars().all())
        all_reads = [await self._build_read(g) for g in all_groups]
        top_level = [r for r in all_reads if r.id not in child_ids]
        return AssetGroupTreeResponse(top_level=top_level, all_groups=all_reads)

    async def add_member(
        self, group_name: str, asset_id: uuid.UUID, *, weight: float = 1.0
    ) -> AssetGroupRead:
        """Add an asset as a member of a group. Raises 404 if group not found.

        Args:
            group_name: Name of the parent group.
            asset_id: UUID of the asset to add.
            weight: Relative weight of this member.

        Returns:
            Updated AssetGroupRead with the new member.
        """
        result = await self._session.execute(
            select(AssetGroup).where(AssetGroup.name == group_name)
        )
        group = result.scalar_one_or_none()
        if group is None:
            raise HTTPException(status_code=404, detail=f"asset group '{group_name}' not found")
        self._session.add(AssetGroupMember(group_id=group.id, asset_id=asset_id, weight=weight))
        await self._session.flush()
        return await self._build_read(group)

    async def remove_member(self, group_name: str, asset_id: uuid.UUID) -> None:
        """Remove a member asset from a group. Raises 404 if group not found.

        Args:
            group_name: Name of the parent group.
            asset_id: UUID of the asset to remove.
        """
        result = await self._session.execute(
            select(AssetGroup).where(AssetGroup.name == group_name)
        )
        group = result.scalar_one_or_none()
        if group is None:
            raise HTTPException(status_code=404, detail=f"asset group '{group_name}' not found")
        await self._session.execute(
            delete(AssetGroupMember).where(
                AssetGroupMember.group_id == group.id,
                AssetGroupMember.asset_id == asset_id,
            )
        )

    async def add_subgroup(
        self, parent_name: str, child_group_id: uuid.UUID, *, weight: float = 1.0
    ) -> AssetGroupRead:
        """Add a child group as a subgroup of a parent. Raises 404 if parent not found.

        Args:
            parent_name: Name of the parent group.
            child_group_id: UUID of the child group to add.
            weight: Relative weight of this subgroup.

        Returns:
            Updated AssetGroupRead with the new subgroup.
        """
        result = await self._session.execute(
            select(AssetGroup).where(AssetGroup.name == parent_name)
        )
        group = result.scalar_one_or_none()
        if group is None:
            raise HTTPException(status_code=404, detail=f"asset group '{parent_name}' not found")
        self._session.add(
            AssetGroupLink(parent_group_id=group.id, child_group_id=child_group_id, weight=weight)
        )
        await self._session.flush()
        return await self._build_read(group)

    async def remove_subgroup(self, parent_name: str, child_group_id: uuid.UUID) -> None:
        """Remove a child group from a parent. Raises 404 if parent not found.

        Args:
            parent_name: Name of the parent group.
            child_group_id: UUID of the child group to remove.
        """
        result = await self._session.execute(
            select(AssetGroup).where(AssetGroup.name == parent_name)
        )
        group = result.scalar_one_or_none()
        if group is None:
            raise HTTPException(status_code=404, detail=f"asset group '{parent_name}' not found")
        await self._session.execute(
            delete(AssetGroupLink).where(
                AssetGroupLink.parent_group_id == group.id,
                AssetGroupLink.child_group_id == child_group_id,
            )
        )


class AssetSLOLinkRepository:
    """CRUD for asset_slo_links."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        asset_id: uuid.UUID,
        link_name: str,
        slo_name: str,
        sli_name: str,
        data_source_name: str,
    ) -> AssetSLOLink:
        """Create an SLO link for an asset.

        Args:
            asset_id: UUID of the asset.
            link_name: Unique name for this link within the asset.
            slo_name: Name of the referenced SLO.
            sli_name: Name of the referenced SLI.
            data_source_name: Name of the referenced data source.

        Returns:
            The newly created AssetSLOLink record.
        """
        link = AssetSLOLink(
            id=uuid.uuid4(),
            link_name=link_name,
            asset_id=asset_id,
            slo_name=slo_name,
            sli_name=sli_name,
            data_source_name=data_source_name,
        )
        self._session.add(link)
        await self._session.flush()
        return link

    async def list_by_asset(self, asset_id: uuid.UUID) -> list[AssetSLOLink]:
        """Return all SLO links for an asset ordered by link name."""
        result = await self._session.execute(
            select(AssetSLOLink)
            .where(AssetSLOLink.asset_id == asset_id)
            .order_by(AssetSLOLink.link_name)
        )
        return list(result.scalars().all())

    async def delete(self, asset_id: uuid.UUID, link_name: str) -> None:
        """Hard-delete an SLO link by asset id and link name."""
        await self._session.execute(
            delete(AssetSLOLink).where(
                AssetSLOLink.asset_id == asset_id,
                AssetSLOLink.link_name == link_name,
            )
        )

    async def get_by_link_name(
        self,
        asset_id: uuid.UUID,
        link_name: str,
    ) -> AssetSLOLink | None:
        """Return the SLO link for a specific asset + link name, or None."""
        result = await self._session.execute(
            select(AssetSLOLink).where(
                AssetSLOLink.asset_id == asset_id,
                AssetSLOLink.link_name == link_name,
            )
        )
        return result.scalars().first()

    async def get_by_asset_and_slo(
        self,
        asset_id: uuid.UUID,
        slo_name: str,
    ) -> AssetSLOLink | None:
        """Return the SLO link for a specific asset + SLO name, or None.

        Used by the evaluation flow (P2b) to resolve comparison rules
        when the worker has asset_id + slo_name from the evaluation row.
        """
        result = await self._session.execute(
            select(AssetSLOLink).where(
                AssetSLOLink.asset_id == asset_id,
                AssetSLOLink.slo_name == slo_name,
            )
        )
        return result.scalars().first()

    async def update_comparison_rules(
        self,
        link_id: uuid.UUID,
        rules: list[dict[str, Any]],
    ) -> None:
        """Replace comparison_rules on an SLO link."""
        await self._session.execute(
            update(AssetSLOLink).where(AssetSLOLink.id == link_id).values(comparison_rules=rules)
        )


class AssetGroupSLOLinkRepository:
    """CRUD for asset_group_slo_links — mirrors AssetSLOLinkRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        group_id: uuid.UUID,
        slo_name: str,
        sli_name: str,
        data_source_name: str,
    ) -> AssetGroupSLOLink:
        """Create an SLO link for an asset group.

        The link_name is auto-generated as ``{slo_name}--{sli_name}``.

        Args:
            group_id: UUID of the asset group.
            slo_name: Name of the referenced SLO.
            sli_name: Name of the referenced SLI.
            data_source_name: Name of the referenced data source.

        Returns:
            The newly created AssetGroupSLOLink record.
        """
        link = AssetGroupSLOLink(
            id=uuid.uuid4(),
            link_name=f"{slo_name}--{sli_name}",
            group_id=group_id,
            slo_name=slo_name,
            sli_name=sli_name,
            data_source_name=data_source_name,
        )
        self._session.add(link)
        await self._session.flush()
        return link

    async def list_by_group(self, group_id: uuid.UUID) -> list[AssetGroupSLOLink]:
        """Return all SLO links for an asset group ordered by link name."""
        result = await self._session.execute(
            select(AssetGroupSLOLink)
            .where(AssetGroupSLOLink.group_id == group_id)
            .order_by(AssetGroupSLOLink.link_name)
        )
        return list(result.scalars().all())

    async def delete(self, group_id: uuid.UUID, link_name: str) -> None:
        """Hard-delete an SLO link by group id and link name."""
        await self._session.execute(
            delete(AssetGroupSLOLink).where(
                AssetGroupSLOLink.group_id == group_id,
                AssetGroupSLOLink.link_name == link_name,
            )
        )
