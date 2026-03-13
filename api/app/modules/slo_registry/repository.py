"""SLO registry repository — versioned CRUD for slo_definitions table."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SLODefinition


class SLORepository:
    """Data access layer for versioned SLO definitions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        name: str,
        slo_yaml: str,
        notes: str | None = None,
        author: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> SLODefinition:
        """Insert a new version of a named SLO.

        Version is auto-incremented using SELECT ... FOR UPDATE to prevent races.

        Args:
            name: Stable external identifier for the SLO.
            slo_yaml: Full SLO YAML content.
            notes: Optional description of changes in this version.
            author: Optional identifier of who created this version.
            meta: Optional arbitrary key-value metadata.

        Returns:
            The newly created SLODefinition with its assigned version.
        """
        result = await self._session.execute(
            select(SLODefinition.version)
            .where(SLODefinition.name == name)
            .order_by(SLODefinition.version.desc())
            .limit(1)
            .with_for_update()
        )
        max_version = result.scalar_one_or_none()
        next_version = (max_version or 0) + 1

        slo = SLODefinition(
            id=uuid.uuid4(),
            name=name,
            version=next_version,
            slo_yaml=slo_yaml,
            notes=notes,
            author=author,
            meta=meta or {},
            active=True,
        )
        self._session.add(slo)
        await self._session.flush()
        return slo

    async def get_latest(self, name: str) -> SLODefinition | None:
        """Return the highest version of a named SLO, or None if not found or deleted.

        Args:
            name: Stable external SLO identifier.

        Returns:
            Latest active SLODefinition, or None.
        """
        result = await self._session.execute(
            select(SLODefinition)
            .where(SLODefinition.name == name, SLODefinition.active == True)  # noqa: E712
            .order_by(SLODefinition.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_version(self, name: str, version: int) -> SLODefinition | None:
        """Return a specific version of a named SLO.

        Args:
            name: Stable external SLO identifier.
            version: Integer version number.

        Returns:
            Matching SLODefinition, or None.
        """
        result = await self._session.execute(
            select(SLODefinition).where(
                SLODefinition.name == name,
                SLODefinition.version == version,
            )
        )
        return result.scalar_one_or_none()

    async def list_versions(self, name: str) -> list[SLODefinition]:
        """Return all versions of a named SLO, newest first.

        Args:
            name: Stable external SLO identifier.

        Returns:
            All SLODefinition rows for this name, ordered by version descending.
        """
        result = await self._session.execute(
            select(SLODefinition)
            .where(SLODefinition.name == name)
            .order_by(SLODefinition.version.desc())
        )
        return list(result.scalars().all())

    async def list_all_latest(self) -> list[SLODefinition]:
        """Return the latest active version of every named SLO.

        Uses DISTINCT ON (name) ORDER BY name, version DESC — PostgreSQL-specific.

        Returns:
            One SLODefinition per active SLO name, the highest version of each.
        """
        # DISTINCT ON (name) with ORDER BY name, version DESC — PostgreSQL-specific
        subq = (
            select(SLODefinition.name, SLODefinition.version)
            .where(SLODefinition.active == True)  # noqa: E712
            .distinct(SLODefinition.name)
            .order_by(SLODefinition.name, SLODefinition.version.desc())
        ).subquery()

        result = await self._session.execute(
            select(SLODefinition).join(
                subq,
                (SLODefinition.name == subq.c.name) & (SLODefinition.version == subq.c.version),
            )
        )
        return list(result.scalars().all())

    async def soft_delete(self, name: str) -> int:
        """Mark all versions of a named SLO as inactive.

        Evaluations that used this SLO are unaffected — they store the resolved YAML.

        Args:
            name: Stable external SLO identifier.

        Returns:
            Number of rows affected (versions deactivated).
        """
        cursor: CursorResult[Any] = await self._session.execute(  # type: ignore[assignment]
            update(SLODefinition).where(SLODefinition.name == name).values(active=False)
        )
        return cursor.rowcount
