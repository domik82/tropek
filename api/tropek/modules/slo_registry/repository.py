"""SLO registry repository — versioned CRUD for slo_definitions table."""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tropek.cache.redis_cache import RedisCache
from tropek.db.models import SLODefinition
from tropek.db.models import SLOObjective as SLOObjectiveORM
from tropek.modules.common.tag_mixin import TagQueryMixin
from tropek.modules.slo_registry.params import SLOCreateParams


class SLORepository(TagQueryMixin):
    """Data access layer for versioned SLO definitions."""

    _tag_model = SLODefinition

    def __init__(self, session: AsyncSession, cache: RedisCache | None = None) -> None:
        self._session = session
        self._cache = cache

    async def create(self, params: SLOCreateParams) -> SLODefinition:
        """Insert a new version of a named SLO.

        Version is auto-incremented using SELECT ... FOR UPDATE to prevent races.

        Args:
            params: SLO creation parameters including name, objectives, scoring thresholds,
                comparison config, metadata, and optional SLI binding.

        Returns:
            The newly created SLODefinition with its assigned version.
        """
        result = await self._session.execute(
            select(SLODefinition.version)
            .where(SLODefinition.name == params.name)
            .order_by(SLODefinition.version.desc())
            .limit(1)
            .with_for_update()
        )
        max_version = result.scalar_one_or_none()
        next_version = (max_version or 0) + 1

        if params.comparable_from_version is not None:
            resolved_cfv = params.comparable_from_version
        elif max_version is not None:
            resolved_cfv = max_version
        else:
            resolved_cfv = 1

        slo = SLODefinition(
            id=uuid.uuid4(),
            name=params.name,
            version=next_version,
            comparable_from_version=resolved_cfv,
            total_score_pass_threshold=params.total_score_pass_threshold,
            total_score_warning_threshold=params.total_score_warning_threshold,
            comparison=params.comparison or {},
            display_name=params.display_name,
            notes=params.notes,
            author=params.author,
            tags=params.tags,
            variables=params.variables,
            kind=params.kind,
            sli_definition_id=params.sli_definition_id,
            method_criteria=params.method_criteria,
            generated_by_group_id=params.generated_by_group_id,
            active=True,
        )
        self._session.add(slo)
        await self._session.flush()

        for i, obj in enumerate(params.objectives):
            orm_obj = SLOObjectiveORM(
                id=uuid.uuid4(),
                slo_definition_id=slo.id,
                sli=obj.sli,
                display_name=obj.display_name or '',
                weight=obj.weight,
                key_sli=obj.key_sli,
                sort_order=i,
                pass_threshold=obj.pass_threshold,
                warning_threshold=obj.warning_threshold,
            )
            self._session.add(orm_obj)

        await self._session.flush()
        # Eagerly load objectives and sli_definition so callers can access them
        await self._session.refresh(slo, ['objectives', 'sli_definition'])
        if self._cache:
            await self._cache.invalidate(f'slo:{params.name}:latest')
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
            .options(selectinload(SLODefinition.sli_definition))
            .where(SLODefinition.name == name, SLODefinition.active == True)  # noqa: E712
            .order_by(SLODefinition.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, slo_id: uuid.UUID) -> SLODefinition | None:
        """Return a specific SLO definition by primary key, or None."""
        result = await self._session.execute(
            select(SLODefinition).options(selectinload(SLODefinition.sli_definition)).where(SLODefinition.id == slo_id)
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
            select(SLODefinition)
            .options(selectinload(SLODefinition.sli_definition))
            .where(
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
            .options(selectinload(SLODefinition.sli_definition))
            .where(SLODefinition.name == name)
            .order_by(SLODefinition.version.desc())
        )
        return list(result.scalars().all())

    async def list_by_group_id(self, group_id: uuid.UUID) -> list[SLODefinition]:
        """Return all active SLOs generated by a specific group."""
        result = await self._session.execute(
            select(SLODefinition)
            .options(selectinload(SLODefinition.sli_definition))
            .where(SLODefinition.generated_by_group_id == group_id, SLODefinition.active == True)  # noqa: E712
            .order_by(SLODefinition.name)
        )
        return list(result.scalars().all())

    async def list_all(
        self,
        *,
        tag_key: str | None = None,
        tag_val: str | None = None,
        kind: str | None = None,
    ) -> list[SLODefinition]:
        """Return the latest active version of every named SLO.

        Uses DISTINCT ON (name) ORDER BY name, version DESC — PostgreSQL-specific.

        Args:
            tag_key: Tag key to filter by (requires tag_val).
            tag_val: Tag value to filter by (requires tag_key).
            kind: Optional SLO kind filter (e.g. "standard" or "template").

        Returns:
            One SLODefinition per active SLO name, the highest version of each.
        """
        # DISTINCT ON (name) with ORDER BY name, version DESC — PostgreSQL-specific
        base_filter = SLODefinition.active == True  # noqa: E712
        if kind is not None:
            base_filter = base_filter & (SLODefinition.kind == kind)
        subq = (
            select(SLODefinition.name, SLODefinition.version)
            .where(base_filter)
            .distinct(SLODefinition.name)
            .order_by(SLODefinition.name, SLODefinition.version.desc())
        ).subquery()

        q = (
            select(SLODefinition)
            .options(selectinload(SLODefinition.sli_definition))
            .join(
                subq,
                (SLODefinition.name == subq.c.name) & (SLODefinition.version == subq.c.version),
            )
        )
        if tag_key and tag_val:
            q = q.where(SLODefinition.tags[tag_key].as_string() == tag_val)
        result = await self._session.execute(q)
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
            'CursorResult[Any]',
            await self._session.execute(update(SLODefinition).where(SLODefinition.name == name).values(active=False)),
        )
        return cursor.rowcount
