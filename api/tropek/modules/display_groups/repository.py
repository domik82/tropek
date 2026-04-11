"""Repository for slo_display_groups and slo_display_group_members."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import SLODisplayGroup, SLODisplayGroupMember


class DisplayGroupRepository:
    """CRUD for slo_display_groups and slo_display_group_members."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        name: str,
        display_name: str | None = None,
        parent_id: uuid.UUID | None = None,
        sort_order: int = 0,
    ) -> SLODisplayGroup:
        """Insert a new display group."""
        group = SLODisplayGroup(
            id=uuid.uuid4(),
            name=name,
            display_name=display_name,
            parent_id=parent_id,
            sort_order=sort_order,
        )
        self._session.add(group)
        await self._session.flush()
        return group

    async def get_by_name(self, name: str) -> SLODisplayGroup | None:
        """Return display group by unique name, or None."""
        result = await self._session.execute(select(SLODisplayGroup).where(SLODisplayGroup.name == name))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[SLODisplayGroup]:
        """Return all display groups ordered by sort_order, then name."""
        result = await self._session.execute(
            select(SLODisplayGroup).order_by(SLODisplayGroup.sort_order, SLODisplayGroup.name)
        )
        return list(result.scalars().all())

    async def delete(self, name: str) -> None:
        """Hard-delete a display group by name (cascades to members)."""
        await self._session.execute(delete(SLODisplayGroup).where(SLODisplayGroup.name == name))

    async def add_member(self, group_id: uuid.UUID, slo_name: str) -> None:
        """Add an SLO concept name to a display group. No-op if already a member."""
        existing = await self._session.execute(
            select(SLODisplayGroupMember).where(
                SLODisplayGroupMember.group_id == group_id,
                SLODisplayGroupMember.slo_name == slo_name,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return
        row = SLODisplayGroupMember(group_id=group_id, slo_name=slo_name)
        self._session.add(row)
        await self._session.flush()

    async def remove_member(self, group_id: uuid.UUID, slo_name: str) -> None:
        """Remove an SLO concept name from a display group."""
        await self._session.execute(
            delete(SLODisplayGroupMember).where(
                SLODisplayGroupMember.group_id == group_id,
                SLODisplayGroupMember.slo_name == slo_name,
            )
        )

    async def list_members(self, group_id: uuid.UUID) -> list[str]:
        """Return all slo_names in a display group, sorted."""
        result = await self._session.execute(
            select(SLODisplayGroupMember.slo_name)
            .where(SLODisplayGroupMember.group_id == group_id)
            .order_by(SLODisplayGroupMember.slo_name)
        )
        return list(result.scalars().all())
