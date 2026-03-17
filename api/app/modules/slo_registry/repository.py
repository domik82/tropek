"""SLO registry repository — versioned CRUD for slo_definitions table."""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SLODefinition
from app.db.models import SLOObjective as SLOObjectiveORM


class SLORepository:
    """Data access layer for versioned SLO definitions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        name: str,
        objectives: list[dict[str, Any]],
        total_score_pass_pct: float = 90.0,
        total_score_warning_pct: float = 75.0,
        comparison: dict[str, Any] | None = None,
        display_name: str | None = None,
        notes: str | None = None,
        author: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> SLODefinition:
        """Insert a new version of a named SLO.

        Version is auto-incremented using SELECT ... FOR UPDATE to prevent races.

        Args:
            name: Stable external identifier for the SLO.
            objectives: List of objective dicts; must be non-empty (caller must supply at least one).
            total_score_pass_pct: Minimum score percentage to pass. Default 90.0.
            total_score_warning_pct: Minimum score percentage to warn. Default 75.0.
            comparison: Optional comparison config dict. None uses defaults.
            display_name: Optional human-readable display name for the SLO.
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
            total_score_pass_pct=total_score_pass_pct,
            total_score_warning_pct=total_score_warning_pct,
            comparison=comparison or {},
            display_name=display_name,
            notes=notes,
            author=author,
            meta=meta or {},
            active=True,
        )
        self._session.add(slo)
        await self._session.flush()

        for i, obj_dict in enumerate(objectives):
            obj = SLOObjectiveORM(
                id=uuid.uuid4(),
                slo_definition_id=slo.id,
                sli=obj_dict["sli"],
                display_name=obj_dict.get("display_name", ""),
                weight=obj_dict.get("weight", 1),
                key_sli=obj_dict.get("key_sli", False),
                sort_order=i,
                pass_criteria=obj_dict.get("pass_criteria", []),
                warning_criteria=obj_dict.get("warning_criteria", []),
            )
            self._session.add(obj)

        await self._session.flush()
        # Eagerly load objectives so callers can access them outside async context
        await self._session.refresh(slo, ["objectives"])
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

    async def list_all(self) -> list[SLODefinition]:
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

    async def deactivate(self, name: str) -> int:
        """Mark all versions of a named SLO as inactive.

        Evaluations that used this SLO retain their `slo_name`/`slo_version` snapshots.

        Args:
            name: Stable external SLO identifier.

        Returns:
            Number of rows affected (versions deactivated).
        """
        cursor = cast(
            "CursorResult[Any]",
            await self._session.execute(
                update(SLODefinition).where(SLODefinition.name == name).values(active=False)
            ),
        )
        return cursor.rowcount
