"""SLI registry repository — versioned CRUD for sli_definitions table."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.cache.redis_cache import RedisCache
from tropek.db.models import SLIDefinition
from tropek.modules.common.tag_mixin import TagQueryMixin
from tropek.modules.sli_registry.params import SLICreateParams


class SLIRepository(TagQueryMixin):
    """Data access layer for versioned SLI definitions."""

    _tag_model = SLIDefinition

    def __init__(self, session: AsyncSession, cache: RedisCache | None = None) -> None:
        self._session = session
        self._cache = cache

    async def create(self, params: SLICreateParams) -> SLIDefinition:
        """Insert a new version of a named SLI.

        Version is auto-incremented using SELECT ... FOR UPDATE to prevent races.

        Args:
            params: SLICreateParams with all fields for the new SLI version.

        Returns:
            The newly created SLIDefinition with its assigned version.
        """
        result = await self._session.execute(
            select(SLIDefinition.version)
            .where(SLIDefinition.name == params.name)
            .order_by(SLIDefinition.version.desc())
            .limit(1)
            .with_for_update()
        )
        max_version = result.scalar_one_or_none()
        next_version = (max_version or 0) + 1

        if params.comparable_from_version is not None:
            resolved_cfv = params.comparable_from_version
        elif max_version is not None:
            resolved_cfv = max_version  # previous version (N-1)
        else:
            resolved_cfv = 1  # first version

        sli = SLIDefinition(
            id=uuid.uuid4(),
            name=params.name,
            adapter_type=params.adapter_type,
            display_name=params.display_name,
            version=next_version,
            indicators=params.indicators,
            notes=params.notes,
            author=params.author,
            tags=params.tags,
            active=True,
            comparable_from_version=resolved_cfv,
            mode=params.mode,
            query_template=params.query_template,
            interval=params.interval,
            methods=params.methods,
        )
        self._session.add(sli)
        await self._session.flush()
        if self._cache:
            await self._cache.invalidate(f'sli:{params.name}:latest')
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

    async def get_by_id(self, sli_id: uuid.UUID) -> SLIDefinition | None:
        """Return a specific SLI definition by primary key, or None."""
        result = await self._session.execute(select(SLIDefinition).where(SLIDefinition.id == sli_id))
        return result.scalar_one_or_none()

    async def list_versions(self, name: str) -> list[SLIDefinition]:
        """Return all versions newest-first.

        Args:
            name: Stable external SLI identifier.

        Returns:
            All SLIDefinition rows for this name, ordered by version descending.
        """
        result = await self._session.execute(
            select(SLIDefinition).where(SLIDefinition.name == name).order_by(SLIDefinition.version.desc())
        )
        return list(result.scalars().all())

    async def list_all(
        self,
        *,
        adapter_type: str | None = None,
        tag_key: str | None = None,
        tag_val: str | None = None,
    ) -> list[SLIDefinition]:
        """Return latest active version of every SLI name.

        Uses DISTINCT ON (name) ORDER BY name, version DESC — PostgreSQL-specific.

        Args:
            adapter_type: When given, only return SLIs targeting this adapter type.
            tag_key: Tag key to filter by.
            tag_val: Tag value to filter by (requires tag_key).

        Returns:
            One SLIDefinition per active SLI name, the highest version of each.
        """
        base = select(SLIDefinition.name, SLIDefinition.version).where(
            SLIDefinition.active == True  # noqa: E712
        )
        if adapter_type is not None:
            base = base.where(SLIDefinition.adapter_type == adapter_type)
        if tag_key and tag_val:
            base = base.where(SLIDefinition.tags[tag_key].as_string() == tag_val)
        elif tag_key:
            base = base.where(SLIDefinition.tags.has_key(tag_key))
        subq = (base.distinct(SLIDefinition.name).order_by(SLIDefinition.name, SLIDefinition.version.desc())).subquery()

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
        await self._session.execute(update(SLIDefinition).where(SLIDefinition.name == name).values(active=False))
