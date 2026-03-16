"""SLI registry repository — versioned CRUD for sli_definitions table."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SLIDefinition


class SLIRepository:
    """Data access layer for versioned SLI definitions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        name: str,
        indicators: dict[str, str],
        adapter_type: str,
        display_name: str | None = None,
        notes: str | None = None,
        author: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> SLIDefinition:
        """Insert a new version of a named SLI.

        Version is auto-incremented using SELECT ... FOR UPDATE to prevent races.

        Args:
            name: Stable external identifier for the SLI.
            indicators: Mapping of indicator name to adapter query string.
            adapter_type: Type of adapter this SLI targets (e.g. "prometheus").
            display_name: Optional human-readable display name.
            notes: Optional description of changes in this version.
            author: Optional identifier of who created this version.
            meta: Optional arbitrary key-value metadata.

        Returns:
            The newly created SLIDefinition with its assigned version.
        """
        result = await self._session.execute(
            select(SLIDefinition.version)
            .where(SLIDefinition.name == name)
            .order_by(SLIDefinition.version.desc())
            .limit(1)
            .with_for_update()
        )
        max_version = result.scalar_one_or_none()
        next_version = (max_version or 0) + 1

        sli = SLIDefinition(
            id=uuid.uuid4(),
            name=name,
            adapter_type=adapter_type,
            display_name=display_name,
            version=next_version,
            indicators=indicators,
            notes=notes,
            author=author,
            meta=meta or {},
            active=True,
        )
        self._session.add(sli)
        await self._session.flush()
        return sli

    async def get_latest(self, name: str) -> SLIDefinition | None:
        """Return the highest active version, or None.

        Args:
            name: Stable external SLI identifier.

        Returns:
            Latest active SLIDefinition, or None.
        """
        result = await self._session.execute(
            select(SLIDefinition)
            .where(SLIDefinition.name == name, SLIDefinition.active == True)  # noqa: E712
            .order_by(SLIDefinition.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_version(self, name: str, version: int) -> SLIDefinition | None:
        """Return a specific version, or None.

        Args:
            name: Stable external SLI identifier.
            version: Integer version number.

        Returns:
            Matching SLIDefinition, or None.
        """
        result = await self._session.execute(
            select(SLIDefinition).where(
                SLIDefinition.name == name,
                SLIDefinition.version == version,
            )
        )
        return result.scalar_one_or_none()

    async def list_versions(self, name: str) -> list[SLIDefinition]:
        """Return all versions newest-first.

        Args:
            name: Stable external SLI identifier.

        Returns:
            All SLIDefinition rows for this name, ordered by version descending.
        """
        result = await self._session.execute(
            select(SLIDefinition)
            .where(SLIDefinition.name == name)
            .order_by(SLIDefinition.version.desc())
        )
        return list(result.scalars().all())

    async def list_all(self, *, adapter_type: str | None = None) -> list[SLIDefinition]:
        """Return latest active version of every SLI name.

        Uses DISTINCT ON (name) ORDER BY name, version DESC — PostgreSQL-specific.

        Args:
            adapter_type: When given, only return SLIs targeting this adapter type.

        Returns:
            One SLIDefinition per active SLI name, the highest version of each.
        """
        base = select(SLIDefinition.name, SLIDefinition.version).where(
            SLIDefinition.active == True  # noqa: E712
        )
        if adapter_type is not None:
            base = base.where(SLIDefinition.adapter_type == adapter_type)
        subq = (
            base.distinct(SLIDefinition.name).order_by(
                SLIDefinition.name, SLIDefinition.version.desc()
            )
        ).subquery()

        result = await self._session.execute(
            select(SLIDefinition).join(
                subq,
                (SLIDefinition.name == subq.c.name) & (SLIDefinition.version == subq.c.version),
            )
        )
        return list(result.scalars().all())

    async def deactivate(self, name: str) -> None:
        """Soft-delete all versions of a named SLI.

        Args:
            name: Stable external SLI identifier.
        """
        await self._session.execute(
            update(SLIDefinition).where(SLIDefinition.name == name).values(active=False)
        )
